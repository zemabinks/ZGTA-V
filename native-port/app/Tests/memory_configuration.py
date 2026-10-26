"""Check the actual engine ABI and removal of cached generated RAM clamps."""
import argparse
import importlib.util
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wasm = load('memory_wasm', ROOT / 'Scripts/prepare_online_exports.py')
restore = load('restore_memory', ROOT / 'Scripts/restore_engine_memory.py').restore


def check_engine(path):
    imports = next(payload for kind, payload, _ in wasm.sections(path.read_bytes()) if kind == 2)
    r = wasm.Reader(imports)
    memory = None
    for _ in range(r.uint()):
        module, name = r.string(), r.string()
        kind = r.data[r.pos]; r.pos += 1
        if kind == 0:
            r.uint()
        elif kind in (1, 2):
            if kind == 1: r.pos += 1
            flags, minimum = r.uint(), r.uint()
            maximum = r.uint() if flags & 1 else None
            if kind == 2 and (module, name) == ('env', 'memory'):
                memory = flags, minimum, maximum
        elif kind == 3:
            r.pos += 2
        elif kind == 4:
            r.pos += 1; r.uint()
        else:
            raise AssertionError(f'Unsupported import kind {kind}')
    assert memory == (7, 49152, 262144), f'Pinned engine memory ABI changed: {memory}'
    header = (ROOT / 'Source/NativeEngineMemory.h').read_text()
    for label, pages in [('MIN', memory[1]), ('MAX', memory[2])]:
        value = int(re.search(r'PG_ENGINE_MEMORY_'+label+r'_BYTES \((\d+)ull \* 1048576\)', header)[1])
        assert value * 1048576 == pages * 65536
    print('PASS: actual memory64 engine import supports 3..16 GiB; native reservation matches its ABI.')


def check_reused_generated_code():
    with tempfile.TemporaryDirectory(prefix='mugoat-memory-') as temp:
        generated = Path(temp)
        originals = {
            'game_15.c': '#include "game-impl.h"\nu64 query(void) {\n  FUNC_EPILOGUE;\n  return var_j0;\n}\n',
            'game_63.c': '#include "game-heap-impl.h"\nu64 query(void) {\n  FUNC_EPILOGUE;\n  return var_j0;\n}\n',
        }
        old15 = originals['game_15.c'].replace('game-impl.h', 'game-memory-budget-impl.h').replace('  FUNC_EPILOGUE;', '  var_j0 = pg_streaming_available_memory(var_j0);\n  FUNC_EPILOGUE;')
        old63 = originals['game_63.c'].replace('#include "game-heap-impl.h"', '#include "game-heap-impl.h"\n#include "game-memory-budget-decl.h"').replace('  FUNC_EPILOGUE;', '  var_j0 = pg_streaming_resource_memory(var_j0);\n  FUNC_EPILOGUE;')
        (generated/'game_15.c').write_text(old15)
        (generated/'game_63.c').write_text(old63)
        for name in ('game-memory-budget-impl.h', 'game-memory-budget-decl.h'):
            (generated/name).write_text('obsolete')
        restore(generated)
        restore(generated)
        assert all((generated/name).read_text() == text for name,text in originals.items())
        assert not list(generated.glob('game-memory-budget-*.h'))
    print('PASS: reused generated sources restored byte-for-byte; repeated restoration is safe.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', type=Path, required=True)
    args = parser.parse_args()
    check_engine(args.engine)
    check_reused_generated_code()
