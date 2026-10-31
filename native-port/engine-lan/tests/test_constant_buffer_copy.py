"""Execute the production CPU-shadow copy helper, without Metal or a GPU wait."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[2] / 'app' / 'Source'


class ConstantBufferCopyTests(unittest.TestCase):
    def test_compiled_shadow_copy_and_snapshot_contract(self):
        compiler = shutil.which('clang++') or shutil.which('c++')
        self.assertIsNotNone(compiler, 'C++ compiler required for constant-buffer regression')
        fixture = r'''
#include "NativeConstantBufferCopy.h"
#include <cassert>
#include <iostream>

struct ConstantBuffer {
    std::vector<uint8_t> shadow;
    uint64_t cbFrame = 17;
    uint32_t version = 9;
};
static uint64_t copy(ConstantBuffer& d, const ConstantBuffer& s,
                     uint64_t dx, uint64_t sx, uint64_t n) {
    return PGCopyConstantBufferShadow(d.shadow, s.shadow, dx, sx, n, d.cbFrame, d.version);
}
int main() {
    ConstantBuffer source{{0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15}};
    ConstantBuffer d{std::vector<uint8_t>(16, 99)};
    const auto oldSnapshot = d.shadow;
    assert(copy(d, source, 0, 0, 16) == 16);
    assert(d.shadow == source.shadow && oldSnapshot == std::vector<uint8_t>(16, 99));
    assert(d.cbFrame == UINT64_MAX && d.version == 10);

    d = ConstantBuffer{std::vector<uint8_t>(16, 99)};
    assert(copy(d, source, 4, 8, 4) == 4);
    assert(d.shadow == std::vector<uint8_t>({99,99,99,99,8,9,10,11,99,99,99,99,99,99,99,99}));
    assert(d.version == 10 && d.cbFrame == UINT64_MAX);

    // Bounds are clamped by subtraction, never by an overflowing offset+size.
    d = ConstantBuffer{std::vector<uint8_t>(12, 99)};
    assert(copy(d, source, 8, 12, UINT64_MAX) == 4);
    assert(d.shadow == std::vector<uint8_t>({99,99,99,99,99,99,99,99,12,13,14,15}));
    const auto saved = d.shadow;
    d.cbFrame = 18;
    const auto version = d.version;
    for (const auto dx : {uint64_t(13), UINT64_MAX})
        assert(copy(d, source, dx, 0, UINT64_MAX) == 0);
    for (const auto sx : {uint64_t(17), UINT64_MAX})
        assert(copy(d, source, 0, sx, UINT64_MAX) == 0);
    assert(copy(d, source, 12, 0, 16) == 0);
    assert(copy(d, source, 0, 16, 16) == 0);
    assert(copy(d, source, 0, 0, 0) == 0);
    assert(d.shadow == saved && d.cbFrame == 18 && d.version == version);

    ConstantBuffer empty;
    assert(copy(empty, source, 0, 0, 16) == 0);
    assert(copy(d, empty, 0, 0, 16) == 0);
    assert(empty.cbFrame == 17 && empty.version == 9);

    ConstantBuffer overlap = source;
    assert(copy(overlap, overlap, 4, 0, 12) == 12);
    assert(overlap.shadow == std::vector<uint8_t>({0,1,2,3,0,1,2,3,4,5,6,7,8,9,10,11}));
    overlap = source;
    assert(copy(overlap, overlap, 0, 4, 12) == 12);
    assert(overlap.shadow == std::vector<uint8_t>({4,5,6,7,8,9,10,11,12,13,14,15,12,13,14,15}));

    // Exercise every valid source/destination offset, including an empty end,
    // and requests longer than either buffer, against an independent snapshot.
    unsigned cases = 0;
    for (uint64_t dx = 0; dx <= 16; ++dx)
      for (uint64_t sx = 0; sx <= 16; ++sx)
        for (uint64_t n = 0; n <= 20; ++n) {
            ConstantBuffer actual = source;
            auto expected = source.shadow;
            const uint64_t bytes = std::min(n, std::min(uint64_t(16)-dx, uint64_t(16)-sx));
            for (uint64_t j = 0; j < bytes; ++j) expected[dx+j] = source.shadow[sx+j];
            assert(copy(actual, actual, dx, sx, n) == bytes);
            assert(actual.shadow == expected);
            assert(actual.version == 9 + bool(bytes));
            assert(actual.cbFrame == (bytes ? UINT64_MAX : 17));
            ++cases;
        }
    std::cout << "PASS whole/partial/bounds/overlap/invalidation; " << cases << " differential cases\n";
}
'''
        with tempfile.TemporaryDirectory(prefix='zgta-cb-copy-') as temporary:
            root = Path(temporary)
            test = root / 'constant_buffer_copy.cpp'
            binary = root / 'constant_buffer_copy'
            test.write_text(fixture)
            subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I', str(SOURCE), str(test), '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], check=True, text=True, capture_output=True)
            self.assertIn('6069 differential cases', result.stdout)


if __name__ == '__main__':
    unittest.main()
