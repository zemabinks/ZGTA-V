#!/usr/bin/env python3
"""Download the prebuilt shader translator (ShaderTool/pgmsl.cc built against Google's Tint).

It turns the game's WGSL shaders into Metal Shading Language at build time. The
prebuilt binary is attached to this project's releases (macOS 13+, Apple Silicon);
set PGMSL_PREBUILT_URL to use another copy, or build it yourself with
ShaderTool/build_pgmsl.sh from a Dawn checkout. The archive is checked against a
pinned SHA-256 before use. Tint/Dawn: BSD-3-Clause and Apache-2.0 (licenses inside).
"""
import hashlib
import os
import sys
import tarfile
import urllib.request
from pathlib import Path

URL = os.environ.get('PGMSL_PREBUILT_URL') or 'https://github.com/kevinerikjs/gta5-ios-port/releases/download/shadertool-1/pgmsl-macos-arm64.tar.gz'
SHA256 = 'c80005c5fe22653cc7b2dd10a8276202df8e8fbfcb6d6d1a3e6599c2240105a1'
root = Path(__file__).resolve().parents[1]
target = root / 'Tools/pgmsl'
if (target / 'pgmsl').exists():
    print('Shader translator already present.')
    sys.exit(0)
archive = root / 'Tools/pgmsl.tar.gz'
archive.parent.mkdir(parents=True, exist_ok=True)
print('Downloading the shader translator...', flush=True)
with urllib.request.urlopen(URL, timeout=300) as response:
    archive.write_bytes(response.read())
if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
    sys.exit('Shader translator checksum mismatch: refusing to use it.')
sys.path.insert(0, str(Path(__file__).parent))
from safe_extract import extract
with tarfile.open(archive) as package:
    extract(package, root / 'Tools')
os.chmod(target / 'pgmsl', 0o755)
print('Shader translator ready.')
