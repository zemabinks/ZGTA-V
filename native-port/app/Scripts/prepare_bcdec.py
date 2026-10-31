#!/usr/bin/env python3
"""Patch one pinned BC6 sign-extension UB in an isolated native build copy.

The reviewed Intel source/input manifest remains unchanged. The build receipt
hashes the resulting Tools/bcdec/bcdec.h as an actual compilation input.
"""
import argparse
import hashlib
import json
from pathlib import Path
import stat

SOURCE_SHA256 = '134520764d96f70a27db814173616c89ad85db95fbd3328417c7a8c77e7ca189'
PATCHED_SHA256 = '3b381b0d31a59cda110bf47e218d70bff43726f1d3707c88657719eb1d63a837'
OLD = b'''static int bcdec__extend_sign(int val, int bits) {
    return (val << (32 - bits)) >> (32 - bits);
}'''
NEW = b'''static int bcdec__extend_sign(int val, int bits) {
    /* Define sign extension without overflowing a signed left shift. */
    if (bits == 32) return val;
    unsigned int sign = 1u << (bits - 1);
    unsigned int word = (unsigned int)val & ((1u << bits) - 1u);
    return (int)(word ^ sign) - (int)sign;
}'''


def transform(data):
    before = hashlib.sha256(data).hexdigest()
    if before == PATCHED_SHA256:
        return data
    if before != SOURCE_SHA256 or data.count(OLD) != 1:
        raise ValueError('BC decoder differs from the pinned reviewed input; preserved.')
    result = data.replace(OLD, NEW)
    if hashlib.sha256(result).hexdigest() != PATCHED_SHA256:
        raise ValueError('BC decoder patched output differs; preserved.')
    return result


def stage(app):
    app = Path(app).absolute()
    if app.name != 'AppRoot' or app.parent.parent.name != 'Build':
        raise ValueError('An isolated Build/<candidate>/AppRoot copy is required.')
    header = app / 'Tools/bcdec/bcdec.h'
    if any(p.is_symlink() for p in (header, *header.parents)):
        raise ValueError('BC decoder paths must not contain symlinks.')
    info = header.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('BC decoder must be an independent regular staged file.')
    original = header.read_bytes()
    updated = transform(original)  # Validate full input/output before writing.
    if updated != original:
        header.write_bytes(updated)
    if hashlib.sha256(header.read_bytes()).hexdigest() != PATCHED_SHA256:
        raise ValueError('BC decoder readback differs from checked output.')
    return {
        'format': 'zgta-bcdec-sign-extension-v1',
        'source_sha256': SOURCE_SHA256,
        'patched_sha256': PATCHED_SHA256,
        'input_sha256': hashlib.sha256(original).hexdigest(),
        'status': 'PATCHED' if updated != original else 'REUSED',
        'change': 'Defined integer sign extension; pixel output equivalence tested separately.',
        'cached_inputs_modified': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-root', required=True, type=Path)
    arguments = parser.parse_args()
    print(json.dumps(stage(arguments.app_root), indent=2))
