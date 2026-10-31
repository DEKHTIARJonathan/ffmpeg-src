"""Build a fresh consumer against the exact candidate archive."""
import os
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
root = Path(__file__).resolve().parent.parent
version = tomllib.loads((root / 'Cargo.toml').read_text())['package']['version']
work = Path(tempfile.mkdtemp(prefix='ffmpeg-src-consumer-'))
with tarfile.open(root / 'dist' / f'ffmpeg-src-{version}.crate') as archive:
    archive.extractall(work, filter='data')
crate = work / f'ffmpeg-src-{version}'
preparer = work / 'prepare'
(preparer / 'src').mkdir(parents=True)
shutil.copy2(root / 'examples/prepare.rs', preparer / 'src/main.rs')
features = os.environ.get('FEATURES', '')
defaults = os.environ.get('NO_DEFAULT_FEATURES') != '1'
if 'static' in features.split(','):
    selected = tomllib.loads((crate / 'Cargo.toml').read_text())['features']['default']
    features = ','.join([f for f in selected if f != 'shared'] + features.split(','))
    defaults = False
dependency = 'ffmpeg-src = { path = ' + json.dumps(str(crate)) + ', default-features = ' + str(defaults).lower() + ', features = ' + json.dumps([f for f in features.split(',') if f]) + ' }'
(preparer / 'Cargo.toml').write_text('[package]\nname="prepare-sdk"\nversion="0.0.0"\nedition="2021"\n[dependencies]\n' + dependency + '\n[workspace]\n')
subprocess.run(['cargo', 'generate-lockfile', '--manifest-path', str(preparer / 'Cargo.toml')], check=True)
command = ['cargo', 'run', '--locked', '--manifest-path', str(preparer / 'Cargo.toml')]
try:
    prefix = Path(subprocess.check_output(command, text=True).strip().splitlines()[-1])
except subprocess.CalledProcessError:
    for log in (preparer / 'target').glob('**/ffbuild/config.log'):
        print(f'FFmpeg configure diagnostics: {log}', file=sys.stderr)
        print(log.read_text(errors='replace'), file=sys.stderr)
    raise
consumer = work / 'consumer'
shutil.copytree(root / 'testcrate', consumer, ignore=shutil.ignore_patterns('target'))
env = os.environ.copy()
env['FFMPEG_DIR'] = str(prefix)
env['PKG_CONFIG_PATH'] = str(prefix / 'lib/pkgconfig')
env['DYLD_LIBRARY_PATH'] = str(prefix / 'lib')
env['LD_LIBRARY_PATH'] = str(prefix / 'lib')
env['PATH'] = str(prefix / 'bin') + os.pathsep + env['PATH']
if os.name == 'nt':
    env['PKG_CONFIG'] = str(Path(env['FFMPEG_SRC_MSYS_BIN']) / 'pkgconf.exe')
env['EXPECT_KVAZAAR'] = str(int('kvazaar' in features.split(',')))
env['EXPECT_VERSION3'] = str(int('enable-version3' in features.split(',')))
env['EXPECT_GPL'] = str(int('enable-gpl' in features.split(',')))
command = ['cargo', 'run', '--locked', '--manifest-path', str(consumer / 'Cargo.toml')]
if not (prefix / 'include/libavfilter/avfilter.h').exists():
    command += ['--no-default-features']
if 'static' in features.split(','):
    env.pop('FFMPEG_DIR', None)
    command += ['--features', 'static']
subprocess.run(command, env=env, check=True)
# Run a copied executable with the original SDK physically unavailable.
staged = work / 'relocated'
staged.mkdir()
exe = 'ffmpeg-src-smoke' + ('.exe' if os.name == 'nt' else '')
shutil.copy2(consumer / 'target/debug' / exe, staged / exe)
if 'static' not in features.split(','):
    shutil.copytree(prefix / 'lib', staged / 'lib', symlinks=True)
    if (prefix / 'bin').exists():
        for dll in (prefix / 'bin').glob('*.dll'):
            shutil.copy2(dll, staged / dll.name)
relocated_env = env.copy()
for key in ['FFMPEG_DIR', 'PKG_CONFIG_PATH', 'DYLD_LIBRARY_PATH', 'LD_LIBRARY_PATH']:
    relocated_env.pop(key, None)
relocated_env['DYLD_LIBRARY_PATH'] = str(staged / 'lib')
relocated_env['LD_LIBRARY_PATH'] = str(staged / 'lib')
relocated_env['PATH'] = os.environ['PATH']
hidden = prefix.with_name('sdk-unavailable')
prefix.rename(hidden)
try:
    subprocess.run([str(staged / exe)], cwd=staged, env=relocated_env, check=True)
finally:
    hidden.rename(prefix)
print('Packaged consumer passed:', work)
