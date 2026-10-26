"""Extract a tar archive without letting entries escape the destination
(tarfile's filter='data' where available, an explicit check otherwise)."""
import tarfile
from pathlib import Path

def extract(archive: tarfile.TarFile, destination: Path):
    try:
        archive.extractall(destination, filter='data')
        return
    except TypeError:
        pass  # Python without extraction filters (e.g. macOS's /usr/bin/python3 3.9)
    root = destination.resolve()
    for member in archive.getmembers():
        target = (root / member.name).resolve()
        if root not in target.parents and target != root:
            raise SystemExit(f'Unsafe path in archive: {member.name}')
        if member.issym() or member.islnk():
            raise SystemExit(f'Links are not expected in this archive: {member.name}')
    archive.extractall(root)
