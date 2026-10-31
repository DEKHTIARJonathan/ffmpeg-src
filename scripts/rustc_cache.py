"""Windows sccache argument transport; no compiler flags or sources are dropped."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SUFFIX = '.exe' if os.name == 'nt' else ''
TOOLS = ROOT / '.tools'
CACHE = TOOLS / ('sccache' + SUFFIX)
WORK = TOOLS / 'windows-cache'
FRONT = WORK / ('sccache' + SUFFIX)
COMPILER = WORK / 'compiler' / ('rustc' + SUFFIX)
MARKER = 'ffmpeg_src_response_'


def expand(args):
    result = []
    for arg in args:
        if arg.startswith('@'):
            result.extend(expand(Path(arg[1:]).read_text(encoding='utf-8').splitlines()))
        else:
            result.append(arg)
    return result


def invoke_response(compiler, args):
    with tempfile.TemporaryDirectory(prefix='ffmpeg-rustc-') as directory:
        response = Path(directory) / 'args'
        response.write_text('\n'.join(args) + '\n', encoding='utf-8')
        return subprocess.call([str(compiler), '@' + str(response)], close_fds=False)


def main():
    if sys.argv[1] == 'setup':
        WORK.mkdir(parents=True, exist_ok=True)
        COMPILER.parent.mkdir(exist_ok=True)
        real = subprocess.check_output(['rustup', 'which', 'rustc'], text=True).strip()
        identity = {'compiler': real, 'sha256': hashlib.sha256(Path(real).read_bytes()).hexdigest()}
        (WORK / 'compiler.json').write_text(json.dumps(identity), encoding='utf-8')
        env = os.environ.copy()
        env.update(CACHE_EXECUTABLE=str(CACHE), CACHE_PYTHON=sys.executable,
                   CACHE_SCRIPT=str(Path(__file__).resolve()),
                   CACHE_SCRIPT_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        subprocess.run([str(CACHE), real, '--edition=2021', str(ROOT / 'scripts/rustc_cache.rs'),
                        '-o', str(FRONT)], env=env, check=True)
        shutil.copy2(FRONT, COMPILER)
        if os.environ.get('GITHUB_PATH'):
            with open(os.environ['GITHUB_PATH'], 'a') as output:
                output.write(str(WORK) + '\n')
        return

    if sys.argv[1] == 'test':
        identity = json.loads((WORK / 'compiler.json').read_text(encoding='utf-8'))
        directory = WORK / 'probe'
        directory.mkdir(exist_ok=True)
        source = directory / 'probe.rs'
        source.write_text('#[cfg(not(feature="flag_799_avcodec_version_greater_than_62_10"))]\n'
                          'compile_error!("compiler flags were lost");\n'
                          '#[cfg(choice_a)] pub fn value() -> u32 { 17 }\n'
                          '#[cfg(not(choice_a))] pub fn value() -> u32 { 23 }\n', encoding='utf-8')
        out = directory / 'out'
        args = ['--crate-name', 'cache_probe', '--crate-type', 'rlib', '--emit=link,dep-info',
                '--out-dir', str(out), str(source)]
        for number in range(800):
            args += ['--cfg', f'feature="flag_{number}_avcodec_version_greater_than_62_10"']
        response = directory / 'args'
        def stats():
            return json.loads(subprocess.check_output([str(CACHE), '--show-stats', '--stats-format=json'], text=True))['stats']
        before = stats()
        binaries = []
        for extra in [['--cfg', 'choice_a'], ['--cfg', 'choice_a'], []]:
            shutil.rmtree(out, ignore_errors=True)
            out.mkdir()
            response.write_text('\n'.join(args + extra) + '\n', encoding='utf-8')
            subprocess.run([str(FRONT), identity['compiler'], '@' + str(response)], check=True)
            binaries.append((out / 'libcache_probe.rlib').read_bytes())
        after = stats()
        assert binaries[0] == binaries[1], 'repeated output changed'
        assert binaries[0] != binaries[2], 'different cfg values reused the wrong output'
        assert after['cache_hits']['counts'].get('Rust', 0) > before['cache_hits']['counts'].get('Rust', 0), 'no Rust compiler-cache hit'
        print('Long Rust response-file compilation: cache hit and cfg isolation passed')
        return

    if sys.argv[2] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise SystemExit('Compiler adapter changed: rebuild it before compiling')
    args = expand(Path(sys.argv[3]).read_text(encoding='utf-8').splitlines())
    identity = json.loads((WORK / 'compiler.json').read_text(encoding='utf-8'))
    if sys.argv[1] == 'cache':
        compiler = args.pop(0)
        if Path(compiler).resolve() != Path(identity['compiler']).resolve():
            raise SystemExit('Compiler changed: rebuild the argument adapter')
        flags, short = [], []
        it = iter(args)
        for arg in it:
            if arg in ['--cfg', '--check-cfg']:
                flags.extend([arg, next(it)])
            elif arg.startswith(('--cfg=', '--check-cfg=')):
                flags.append(arg)
            else:
                short.append(arg)
        payload = json.dumps([identity, flags], ensure_ascii=False).encode('utf-8')
        digest = hashlib.sha256(payload).hexdigest()
        saved = WORK / (digest + '.json')
        # Publish an immutable payload atomically, including concurrent writers.
        with tempfile.NamedTemporaryFile(dir=WORK, delete=False) as stream:
            stream.write(payload)
            temporary = Path(stream.name)
        try:
            os.link(temporary, saved)
        except FileExistsError:
            pass
        finally:
            temporary.unlink()
        short += ['--cfg', MARKER + digest]
        raise SystemExit(subprocess.call([str(CACHE), str(COMPILER), *short], close_fds=False))

    flags, short = [], []
    it = iter(args)
    for arg in it:
        if arg == '--cfg':
            value = next(it)
            if value.startswith(MARKER):
                digest = value[len(MARKER):]
                if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                    raise SystemExit('Invalid compiler argument digest')
                payload = (WORK / (digest + '.json')).read_bytes()
                if hashlib.sha256(payload).hexdigest() != digest:
                    raise SystemExit('Compiler argument payload changed')
                saved_identity, saved_flags = json.loads(payload)
                if saved_identity != identity:
                    raise SystemExit('Compiler identity changed')
                flags.extend(saved_flags)
            else:
                short.extend([arg, value])
        else:
            short.append(arg)
    raise SystemExit(invoke_response(identity['compiler'], short + flags))


if __name__ == '__main__':
    main()
