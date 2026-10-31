import importlib.util
import json
import gzip
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import render_performance
import stipple_gpu


class RenderingPerformance(unittest.TestCase):
    def test_real_worker_memory_and_fade_composition(self):
        worker = ROOT.parents[1]/'docs/verification/render-performance98/inputs/wgpu_worker97.js.gz'
        if not worker.is_file(): self.skipTest('Supply pinned Build97 worker fixture')
        output = stipple_gpu.apply(render_performance.apply(gzip.decompress(worker.read_bytes()).decode()))
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)/'worker.js';stage.write_text(output)
            subprocess.run(['node','--check',str(stage)],check=True)
            subprocess.run(['node',str(Path(__file__).with_name('render_performance.cjs')),str(stage),str(ROOT/'stipple_gpu.js')],check=True)
        self.assertIn('rc.stipple || 0',output)
        self.assertIn('psProg ? S.stipple : 0',output)
        with self.assertRaises(ValueError): render_performance.apply(output)

    def test_native_exact_tables_and_padding(self):
        header = ROOT.parent/'app/Source/MetalRenderer/MRConstantTables.h'
        code = '''#include "MRConstantTables.h"
#include <cassert>
int main(){PGConstantTables p; auto a=p.intern({1,2});
assert(p.intern({1,2})==a); auto b=p.intern({1,2,0});
assert(b!=a && b%256==0); assert(p.intern({1,3})!=a);
assert(p.count()==3 && p.bytes()==768);
std::vector<uint32_t> data(p.bytes()/4,0xdeadbeef);p.write((uint8_t*)data.data());
assert(data[0]==1 && data[4]==2 && data[64]==1 && data[68]==2);
for(size_t i=0;i<data.size();++i)if(i%4)assert(data[i]==0);
assert(data[63]==0 && data[127]==0);}
'''
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'tables.cpp';binary=source.with_suffix('');source.write_text(code)
            subprocess.run(['clang++','-std=c++17','-fsanitize=address,undefined','-I',str(header.parent),str(source),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)


if __name__=='__main__': unittest.main()
