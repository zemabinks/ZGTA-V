"""Bundled Mac app entry; reuse the exact checked portable host and data folder."""
import argparse
import json
from pathlib import Path
import sys

RESOURCES = Path(__file__).resolve().parent
PAYLOAD = RESOURCES / 'Payload'
sys.path.insert(0, str(PAYLOAD / 'native-port/engine-lan'))
from portable_launcher import main, package_identity, verify_package

def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--mirror', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.verify:
        manifest = verify_package(PAYLOAD)
        import bz2, ctypes, hashlib, lzma, socket, sqlite3, ssl, zlib
        print(json.dumps({'identity': package_identity(manifest), 'python': sys.version.split()[0], 'payload': 'HASHES_PASS'}))
        return
    flags = ['--data', str(args.data), '--no-open', '--no-desktop']
    if args.mirror:
        flags += ['--mirror', str(args.mirror)]
    if args.check:
        flags += ['--check']
    main(flags)

if __name__ == '__main__':
    run()
