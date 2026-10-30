"""Install a checksum-pinned prebuilt compiler cache into this checkout only."""
import hashlib
import io
import os
from pathlib import Path
import platform
import tarfile
import urllib.request

assets = {
    ('Darwin', 'arm64'): ('aarch64-apple-darwin', 'a35a0b7d622618774bc1bb8102d72562dfb21e619f88b153b370d7f89bc286af'),
    ('Linux', 'x86_64'): ('x86_64-unknown-linux-musl', 'aa73c7270c997894038c0d8f0d297865f57569e1687883322bc431713d4bb9dd'),
    ('Windows', 'AMD64'): ('x86_64-pc-windows-msvc', '130e4f8eb672e76590e9993c2ab890c4763b88238577bb11d8062158c7698353'),
}
triple, digest = assets[(platform.system(), platform.machine())]
name = 'sccache-v0.19.0-' + triple
payload = urllib.request.urlopen('https://github.com/mozilla/sccache/releases/download/v0.19.0/' + name + '.tar.gz').read()
assert hashlib.sha256(payload).hexdigest() == digest
root = Path(__file__).resolve().parent.parent / '.tools'
root.mkdir(exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
    binary = 'sccache.exe' if os.name == 'nt' else 'sccache'
    stream = archive.extractfile(name + '/' + binary)
    (root / binary).write_bytes(stream.read())
    (root / binary).chmod(0o755)
if os.environ.get('GITHUB_PATH'):
    with open(os.environ['GITHUB_PATH'], 'a') as output:
        output.write(str(root) + '\n')
