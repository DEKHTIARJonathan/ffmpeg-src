"""Validate the Cargo release against the pristine upstream submodule tag."""
from pathlib import Path
import re
import subprocess
import tomllib

root = Path(__file__).resolve().parent.parent
version = tomllib.loads((root / 'Cargo.toml').read_text())['package']['version']
assert re.fullmatch(r'\d+\.\d+\.\d+(?:-rc[1-9]\d*)?', version), version
release = (root / 'ffmpeg/RELEASE').read_text().strip()
assert version.split('-')[0] == release + ('.0' if release.count('.') == 1 else '')
for name, revision in [('ffmpeg', 'n' + release),
                       ('kvazaar', '6040962bed5cc68c5ad01234c38c08b8b2822068'),
                       ('nv-codec-headers', '1889e62e2d35ff7aa9baca2bceb14f053785e6f1')]:
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root / name), *args], text=True).strip()
    assert git('rev-parse', 'HEAD') == git('rev-parse', revision + '^{}'), name
    assert not git('status', '--porcelain'), name + ' must remain pristine'
print(f'{version}: pristine FFmpeg n{release}; reviewed dependency pins')
