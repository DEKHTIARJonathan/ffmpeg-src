"""Package pristine pinned sources; this is the only source-download step."""
import hashlib
import io
import lzma
from pathlib import Path
import shutil
import subprocess
import tarfile
import tomllib
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
VERSION = tomllib.loads((ROOT / 'Cargo.toml').read_text())['package']['version']
PINS = {'ffmpeg': '140fd653aed8cad774f991ba083e2d01e86420c7',
        'kvazaar': '6040962bed5cc68c5ad01234c38c08b8b2822068'}
for name, pin in PINS.items():
    assert subprocess.check_output(['git', '-C', name, 'rev-parse', 'HEAD'], text=True).strip() == pin
    assert not subprocess.check_output(['git', '-C', name, 'status', '--porcelain'])
assert VERSION.split('-')[0] == '8.0.0'
paths = ['configure', 'Makefile', 'RELEASE', 'LICENSE.md', 'COPYING.GPLv2', 'COPYING.GPLv3',
         'COPYING.LGPLv2.1', 'COPYING.LGPLv3', 'CREDITS', 'compat', 'ffbuild', 'libavcodec',
         'libavdevice', 'libavfilter', 'libavformat', 'libavutil', 'libswresample', 'libswscale',
         'fftools/Makefile', 'fftools/resources/Makefile', 'doc/Makefile', 'doc/examples/Makefile',
         'tests/Makefile', 'tests/api/Makefile', 'tests/checkasm/Makefile', 'tests/fate', 'tools/Makefile']
native = ROOT / 'native'
native.mkdir(exist_ok=True)
for name in PINS:
    data = subprocess.check_output(['git', '-C', name, 'archive', '--prefix=' + name + '/', 'HEAD',
                                    *(paths if name == 'ffmpeg' else [])])
    (native / (name + '.tar.xz')).write_bytes(lzma.compress(data, preset=9))
data = urllib.request.urlopen('https://github.com/madler/zlib/releases/download/v1.3.2/zlib-1.3.2.tar.gz').read()
assert hashlib.sha256(data).hexdigest() == 'bb329a0a2cd0274d05519d61c667c062e06990d72e125ee2dfa8de64f0119d16'
output = io.BytesIO()
with tarfile.open(fileobj=io.BytesIO(data)) as source, tarfile.open(fileobj=output, mode='w') as dest:
    for member in source.getmembers():
        parts = member.name.split('/')[1:]
        path = '/'.join(parts)
        if not path or (len(parts) > 1 and path != 'contrib/CMakeLists.txt') or path.endswith('.pdf'):
            continue
        member.name = 'zlib/' + path
        dest.addfile(member, source.extractfile(member) if member.isfile() else None)
(native / 'zlib.tar.xz').write_bytes(lzma.compress(output.getvalue(), preset=9))
stage = ROOT / 'target/package-src'
shutil.rmtree(stage, ignore_errors=True)
stage.mkdir(parents=True)
for name in ['Cargo.toml', 'Cargo.lock', 'build.rs', 'README.md', 'LICENSE.md']:
    shutil.copy2(ROOT / name, stage / name)
for name in ['src', 'native']:
    shutil.copytree(ROOT / name, stage / name)
(stage / 'scripts').mkdir()
for name in ['native.py', 'pkg_config.py', 'pkg_config.cmd']:
    shutil.copy2(ROOT / 'scripts' / name, stage / 'scripts' / name)
subprocess.run(['cargo', 'package', '--manifest-path', str(stage / 'Cargo.toml'), '--locked', '--no-verify'], check=True)
archive = stage / 'target/package' / f'ffmpeg-src-{VERSION}.crate'
size = archive.stat().st_size
print(f'{archive.name}: {size:,} bytes', flush=True)
assert size < 10_000_000, 'Archive must be strictly smaller than 10,000,000 bytes'
(ROOT / 'dist').mkdir(exist_ok=True)
shutil.copy2(archive, ROOT / 'dist' / archive.name)
