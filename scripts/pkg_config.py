"""Adapt pristine FFmpeg MSVC pkg-config output for portable consumers."""
import os
from pathlib import Path
import shlex
import subprocess
import sys

backend = os.environ.get('FFMPEG_SRC_PKG_CONFIG')
if not backend:
    backend = str(Path(os.environ['FFMPEG_SRC_MSYS_BIN']) / 'pkgconf.exe')
result = subprocess.run([backend, *sys.argv[1:]], stdout=subprocess.PIPE)
if result.returncode:
    sys.exit(result.returncode)
output = result.stdout.decode()
if any(arg.startswith('--libs') for arg in sys.argv[1:]):
    flags = []
    for flag in shlex.split(output):
        if flag.lower().startswith(('-libpath:', '/libpath:')):
            flag = '-L' + flag.split(':', 1)[1]
        elif flag.lower().endswith('.lib') and not flag.startswith('-'):
            # MSVC system libraries may be bare names, not existing file paths.
            path = Path(flag)
            if path.parent != Path('.'):
                flags.append('-L' + path.parent.as_posix())
            flag = '-l' + path.stem
        flags.append(flag)
    # pkg-config escapes whitespace with backslashes, rather than shell quotes.
    output = ' '.join(''.join('\\' + c if c.isspace() or c == '\\' else c
                              for c in flag) for flag in flags) + '\n'
sys.stdout.write(output)
