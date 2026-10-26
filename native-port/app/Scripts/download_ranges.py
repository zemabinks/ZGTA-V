"""Download exact byte ranges, then atomically publish a complete verified file."""
import concurrent.futures
import hashlib
from pathlib import Path
import re
import time
import urllib.request

CHUNK = 65536


def download(url, target: Path, expected_sha256=None):
    def get(start, end, total=None):
        error = None
        for attempt in range(3):
            try:
                request = urllib.request.Request(url, headers={'Range': f'bytes={start}-{end}'})
                with urllib.request.urlopen(request, timeout=30) as response:
                    if response.status == 200 and start == 0 and total is None:
                        body = response.read()  # raises on truncated Content-Length
                        return body, len(body), True
                    match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('Content-Range', ''))
                    if response.status != 206 or not match:
                        raise ValueError('Server did not return an exact byte range')
                    first, last, length = map(int, match.groups())
                    if first != start or last != min(end, length-1) or (total is not None and total != length):
                        raise ValueError('Byte range or total size changed')
                    body = response.read()
                    if len(body) != last-first+1:
                        raise ValueError('Truncated byte range')
                    return body, length, False
            except Exception as exc:
                error = exc
                if attempt < 2: time.sleep(0.2 * (attempt+1))
        raise OSError(f'Download failed at byte {start}: {error}') from error

    first, total, complete = get(0, CHUNK-1)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name+'.part')
    try:
        with partial.open('wb') as stream:
            stream.truncate(total)
            stream.write(first)
            if not complete:
                starts = range(CHUNK, total, CHUNK)
                def part(start): return start, get(start, min(start+CHUNK-1,total-1), total)[0]
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                    for start, body in pool.map(part, starts):
                        stream.seek(start); stream.write(body)
        if partial.stat().st_size != total:
            raise ValueError('Downloaded file has wrong size')
        digest = hashlib.sha256()
        with partial.open('rb') as stream:
            while block := stream.read(1048576): digest.update(block)
        if expected_sha256 and digest.hexdigest() != expected_sha256:
            raise ValueError('Downloaded file does not match the pinned SHA-256')
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    return target
