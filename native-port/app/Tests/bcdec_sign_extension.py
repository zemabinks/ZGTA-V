#!/usr/bin/env python3
"""Check the exact staged vendor patch and before/after BC6 pixel output.

Uses an explicitly selected existing pinned header; never changes that input.
Only temporary independent copies are compiled, with no application execution.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SCRIPT = Path(__file__).resolve().parents[1] / 'Scripts/prepare_bcdec.py'
SPEC = importlib.util.spec_from_file_location('prepare_bcdec', SCRIPT)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)

FIXTURE = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define BCDEC_STATIC
#define BCDEC_IMPLEMENTATION
#include "bcdec.h"
static uint32_t state=0x548fa927;
static uint32_t random32(void){state^=state<<13;state^=state>>17;state^=state<<5;return state;}
int main(void){
 uint64_t hash=1469598103934665603ULL;size_t signs=0,blocks=0;
 for(unsigned bits=1;bits<=32;bits++){
  const uint64_t mask=(1ULL<<bits)-1,sign=1ULL<<(bits-1);
  const uint32_t count=bits<=16?(1u<<bits):4096;
  for(uint32_t i=0;i<count;i++){
   const uint32_t input=bits<=16?i:random32();
   const uint64_t low=input&mask;
   const int expected=(int)((int64_t)low-(low&sign?(int64_t)(1ULL<<bits):0));
   assert(bcdec__extend_sign((int)input,(int)bits)==expected);signs++;
  }
 }
 for(unsigned sample=0;sample<16384;sample++){
  _Alignas(16) uint8_t input[16];
  for(unsigned i=0;i<16;i++)input[i]=(uint8_t)random32();
  if(sample<256)memset(input,sample,16);
  // Exercise every 5-bit BC6 mode, its signed decode and varied endpoints.
  input[0]=(input[0]&0xe0)|(sample&31);
  for(int signedMode=0;signedMode<=1;signedMode++){
   uint16_t pixels[48];memset(pixels,0xa5,sizeof pixels);
   bcdec_bc6h_half(input,pixels,12,signedMode);
   const uint8_t *bytes=(const uint8_t *)pixels;
   for(size_t i=0;i<sizeof pixels;i++){hash^=bytes[i];hash*=1099511628211ULL;}
   blocks++;
  }
 }
 printf("sign_cases=%zu bc6_blocks=%zu output_fnv64=%016llx\n",signs,blocks,(unsigned long long)hash);
 return 0;
}
'''


def check(source):
    original = source.read_bytes()
    if hashlib.sha256(original).hexdigest() != PATCH.SOURCE_SHA256:
        raise ValueError('The fixture requires the unmodified pinned BC decoder input.')
    updated = PATCH.transform(original)
    assert PATCH.transform(updated) == updated
    for data in (b'unknown', original + b'\n', updated + b'\n'):
        try:
            PATCH.transform(data)
        except ValueError:
            pass
        else:
            raise AssertionError('Unexpected vendor bytes accepted')
    with tempfile.TemporaryDirectory(prefix='zgta-bcdec101-', dir='/private/tmp') as temporary:
        root = Path(temporary)
        app = root / 'Build/Fixture/AppRoot'
        header = app / 'Tools/bcdec/bcdec.h'
        header.parent.mkdir(parents=True)
        header.write_bytes(original)
        assert PATCH.stage(app)['status'] == 'PATCHED'
        assert PATCH.stage(app)['status'] == 'REUSED'
        assert header.read_bytes() == updated
        header.unlink();header.symlink_to(source)
        try:
            PATCH.stage(app)
        except ValueError:
            pass
        else:
            raise AssertionError('Symlink input accepted')
        header.unlink()
        header.write_bytes(original)
        alias = header.with_name('alias.h');os.link(header, alias)
        try:
            PATCH.stage(app)
        except ValueError:
            pass
        else:
            raise AssertionError('Hard-linked input accepted')
        alias.unlink()
        # The new compilation-input key is required only by the new stage
        # marker. Old receipts must remain byte/schema comparable for reuse.
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'engine-lan'))
        import build_experimental
        for name in ['Build/Online/libmugoat_online.a', 'project.experimental.json', 'PlayGTA5Native.xcodeproj/project.pbxproj']:
            file = app / name;file.parent.mkdir(parents=True, exist_ok=True);file.write_bytes(b'fixture')
        legacy = build_experimental.staged_sources(app.parent)
        assert 'Tools/bcdec/bcdec.h' not in legacy
        patch_receipt = PATCH.stage(app)
        stage_file = app.parent / 'stage.json'
        stage_file.write_text(json.dumps({'bcdec_sign_extension': patch_receipt}))
        current = build_experimental.staged_sources(app.parent)
        assert current.pop('Tools/bcdec/bcdec.h') == PATCH.PATCHED_SHA256
        assert current == legacy
        for tamper_header in (True, False):
            header.write_bytes(updated + b'\n' if tamper_header else updated)
            receipt = dict(patch_receipt)
            if not tamper_header:receipt['patched_sha256'] = '0' * 64
            stage_file.write_text(json.dumps({'bcdec_sign_extension': receipt}))
            try:
                build_experimental.staged_sources(app.parent)
            except ValueError:
                pass
            else:
                raise AssertionError('Tampered vendor build proof accepted')
        results = {}
        for name, data, sanitizers in [('before', original, []), ('after', updated, ['-fsanitize=address,undefined', '-fno-omit-frame-pointer'])]:
            folder = root / name;folder.mkdir()
            (folder / 'bcdec.h').write_bytes(data)
            fixture = folder / 'fixture.c';fixture.write_text(FIXTURE)
            executable = folder / 'fixture'
            command = ['clang', '-std=c11', '-O2', *sanitizers, str(fixture), '-o', str(executable)]
            subprocess.run(command, check=True, capture_output=True, text=True)
            run = subprocess.run([str(executable)], check=True, capture_output=True, text=True,
                                 env={**os.environ, 'UBSAN_OPTIONS': 'halt_on_error=1'})
            if run.stderr:
                raise AssertionError('Unexpected diagnostic: ' + run.stderr)
            results[name] = run.stdout.strip()
        assert results['before'] == results['after'], results
    assert source.read_bytes() == original
    return {'format': 'zgta-bcdec-sign-extension-check-v1', 'input_sha256': PATCH.SOURCE_SHA256,
            'patched_sha256': PATCH.PATCHED_SHA256, 'input_unchanged': True,
            'unknown_input_rejection': 'PASS', 'idempotence': 'PASS', 'symlink_rejection': 'PASS', 'hardlink_rejection': 'PASS',
            'new_build_header_hash_and_tamper_rejection': 'PASS', 'legacy_receipt_schema_preserved': 'PASS',
            'all_sign_widths_and_bc6_pixels': results, 'patched_asan_ubsan': 'PASS'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-header', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.source_header), indent=2))
