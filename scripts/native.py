"""Build pristine native sources exclusively in Cargo OUT_DIR; never download."""
import io
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tarfile

ROOT, OUT = map(lambda p: Path(p).resolve(), sys.argv[1:])
FEATURES = {k.removeprefix('CARGO_FEATURE_').lower().replace('_', '-')
            for k in os.environ if k.startswith('CARGO_FEATURE_')}
LIBS = ['avutil', 'avcodec', 'avformat', 'avdevice', 'avfilter', 'swscale', 'swresample']
TARGET = os.environ['TARGET']
if TARGET != os.environ['HOST']:
    raise SystemExit('Cross compilation is not supported in this release')
if TARGET not in ['aarch64-apple-darwin', 'x86_64-unknown-linux-gnu', 'x86_64-pc-windows-msvc']:
    raise SystemExit('Unsupported target: ' + TARGET)
if len(FEATURES & {'static', 'shared'}) != 1 or 'avutil' not in FEATURES:
    raise SystemExit('Select exactly one of shared/static and at least one library')
WINDOWS = TARGET.endswith('windows-msvc')
APPLE = TARGET.endswith('apple-darwin')
for feature, supported in [('videotoolbox', APPLE), ('vaapi', 'linux' in TARGET),
                           ('d3d11va', WINDOWS), ('dxva2', WINDOWS), ('static-crt', WINDOWS)]:
    if feature in FEATURES and not supported:
        raise SystemExit(feature + ' is not supported on ' + TARGET)
ENV = os.environ.copy()
MSYS = os.environ.get('FFMPEG_SRC_MSYS_BIN')
if WINDOWS:
    if not MSYS:
        raise SystemExit('Set FFMPEG_SRC_MSYS_BIN to the MSYS2 usr/bin directory')
    # Keep MSVC first, then one consistent MSYS toolset before Git/Strawberry tools.
    paths = ENV['PATH'].split(os.pathsep)
    msvc = [p for p in paths if (Path(p) / 'cl.exe').is_file()]
    ENV['PATH'] = os.pathsep.join(msvc + [MSYS] + [p for p in paths if p not in msvc and p != MSYS])
SH = str(Path(MSYS) / 'sh.exe') if WINDOWS else 'sh'
MAKE = str(Path(MSYS) / 'make.exe') if WINDOWS else 'make'

def shell_path(path):
    if WINDOWS:
        return subprocess.check_output([str(Path(MSYS) / 'cygpath.exe'), '-u', str(path)], text=True).strip()
    return str(path)

# Do not discover the wrapper checkout's RC tag from staged source directories.
ENV['GIT_CEILING_DIRECTORIES'] = str(OUT)
PREFIX = OUT / 'sdk'
JOBS = os.environ.get('NUM_JOBS', str(os.cpu_count() or 2))
WRAPPER = os.environ.get('RUSTC_WRAPPER', '')
CACHE = WRAPPER if Path(WRAPPER).stem.lower() == 'sccache' else ''
if os.environ.get('FFMPEG_SRC_REQUIRE_SCCACHE') == '1' and not CACHE:
    raise SystemExit('Project builds require RUSTC_WRAPPER=sccache')
if CACHE:
    subprocess.run([CACHE, '--version'], check=True)


def run(args, cwd=OUT, env=None):
    print('+ ' + shlex.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, env=env or ENV, check=True)


def extract(name):
    dest = OUT / 'sources' / name
    archive = ROOT / 'native' / (name + '.tar.xz')
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists():
        with tarfile.open(archive) as source:
            source.extractall(dest.parent, filter='data')
    else:
        data = subprocess.check_output(['git', '-C', str(ROOT / name), 'archive', '--prefix=' + name + '/', 'HEAD'])
        with tarfile.open(fileobj=io.BytesIO(data)) as source:
            source.extractall(dest.parent, filter='data')
    return dest


def compiler(key, default):
    value = os.environ.get(key, default)
    if CACHE and not any(Path(p).stem == 'sccache' for p in shlex.split(value)):
        value = shlex.quote(CACHE) + ' ' + value
    return value


def cmake(name, source, options):
    build = OUT / (name + '-build')
    if build.exists():
        shutil.rmtree(build)
    args = ['cmake', '-S', source, '-B', build, '-G', os.environ.get('CMAKE_GENERATOR', 'Ninja'),
            '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_INSTALL_PREFIX=' + str(PREFIX),
            '-DCMAKE_INSTALL_LIBDIR=lib', '-DCMAKE_POSITION_INDEPENDENT_CODE=ON']
    if CACHE:
        args += ['-DCMAKE_C_COMPILER_LAUNCHER=' + CACHE, '-DCMAKE_CXX_COMPILER_LAUNCHER=' + CACHE]
    if WINDOWS:
        args += ['-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded' + ('' if 'static-crt' in FEATURES else 'DLL')]
    if APPLE:
        args += ['-DCMAKE_INSTALL_NAME_DIR=@rpath', '-DCMAKE_BUILD_WITH_INSTALL_NAME_DIR=ON']
        if os.environ.get('MACOSX_DEPLOYMENT_TARGET'):
            args += ['-DCMAKE_OSX_DEPLOYMENT_TARGET=' + os.environ['MACOSX_DEPLOYMENT_TARGET']]
    if 'linux' in TARGET:
        args += ['-DCMAKE_INSTALL_RPATH=$ORIGIN']
    run(args + options)
    run(['cmake', '--build', build, '--parallel', JOBS])
    for component in (['Runtime', 'Development'] if name == 'zlib' else [None]):
        run(['cmake', '--install', build] + (['--component', component] if component else []))


OUT.mkdir(parents=True, exist_ok=True)
if PREFIX.exists():
    shutil.rmtree(PREFIX)
PREFIX.mkdir()
if 'zlib' in FEATURES:
    z = extract('zlib')
    cmake('zlib', z, ['-DZLIB_BUILD_SHARED=OFF', '-DZLIB_BUILD_STATIC=ON', '-DZLIB_BUILD_TESTING=OFF'])
    if WINDOWS:
        for name in ['z.lib', 'zlib.lib']:
            shutil.copy2(PREFIX / 'lib/zs.lib', PREFIX / 'lib' / name)
if 'kvazaar' in FEATURES:
    k = extract('kvazaar')
    cmake('kvazaar', k, ['-DBUILD_SHARED_LIBS=' + ('ON' if 'shared' in FEATURES else 'OFF'),
                        '-DBUILD_TESTS=OFF', '-DBUILD_KVAZAAR_BINARY=OFF', '-DUSE_CRYPTO=OFF']
          # Upstream's pkg-config template consumes LIBS, but CMake leaves it unset.
          + ([] if WINDOWS else ['-DLIBS=-lm -pthread']))
source = extract('ffmpeg')
build = OUT / 'ffmpeg-build'
if build.exists():
    shutil.rmtree(build)
build.mkdir()
ENV['PKG_CONFIG_PATH'] = shell_path(PREFIX / 'lib/pkgconfig') + ':' + ENV.get('PKG_CONFIG_PATH', '')
cc = compiler('CC', 'cl.exe' if WINDOWS else 'cc')
args = [SH, shell_path(source / 'configure'), '--prefix=' + shell_path(PREFIX), '--disable-programs', '--disable-doc',
        '--disable-autodetect', '--disable-nonfree', '--enable-pic', '--disable-debug',
        '--cc=' + cc, '--cxx=' + compiler('CXX', 'cl.exe' if WINDOWS else 'c++'),
        '--host-cc=' + compiler('HOST_CC', 'cl.exe' if WINDOWS else 'cc'), '--objcc=' + cc]
for feature in LIBS + ['shared', 'static', 'zlib', 'asm', 'network']:
    args.append(('--enable-' if feature in FEATURES else '--disable-') + feature)
for feature, option in [('enable-gpl', 'gpl'), ('enable-version3', 'version3'), ('kvazaar', 'libkvazaar'),
                        ('videotoolbox', 'videotoolbox'), ('vaapi', 'vaapi'), ('vaapi', 'libdrm'),
                        ('d3d11va', 'd3d11va'), ('dxva2', 'dxva2')]:
    args.append(('--enable-' if feature in FEATURES else '--disable-') + option)
if APPLE:
    args += ['--install-name-dir=@rpath']
if 'static' in FEATURES:
    args += ['--pkg-config-flags=--static']
if WINDOWS:
    args += ['--toolchain=msvc', '--extra-cflags=-' + ('MT' if 'static-crt' in FEATURES else 'MD')]
if 'linux' in TARGET:
    args += [r'--extra-ldflags=-Wl,-rpath,\$$ORIGIN']
if 'zlib' in FEATURES:
    args += ['--extra-cflags=-I' + shell_path(PREFIX / 'include'),
             '--extra-ldflags=' + ('-libpath:' + (PREFIX / 'lib').as_posix() if WINDOWS
                                   else '-L' + str(PREFIX / 'lib'))]
run(args, build)
run([MAKE, '-j' + JOBS, 'V=1', 'REVISION=8.0'], build)
run([MAKE, 'install-libs', 'install-headers', 'REVISION=8.0'], build)
if WINDOWS:
    for lib in (PREFIX / 'bin').glob('*.lib'):
        shutil.copy2(lib, PREFIX / 'lib' / lib.name)
for name in ['ffmpeg', 'zlib', 'kvazaar']:
    directory = OUT / 'sources' / name
    if not directory.exists():
        continue
    for license_path in directory.iterdir():
        if license_path.name.startswith(('COPYING', 'LICENSE')) and license_path.is_file():
            dest = PREFIX / 'share/licenses' / name
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(license_path, dest / license_path.name)
