"""Remove obsolete streaming RAM clamps, including from reused generated code."""
from pathlib import Path


def restore(generated: Path):
    for name in ('game_15.c', 'game_63.c'):
        path = generated / name
        text = path.read_text()
        text = text.replace('  var_j0 = pg_streaming_available_memory(var_j0);\n', '')
        text = text.replace('  var_j0 = pg_streaming_resource_memory(var_j0);\n', '')
        text = text.replace('#include "game-memory-budget-impl.h"', '#include "game-impl.h"')
        text = text.replace('#include "game-memory-budget-decl.h"\n', '')
        if 'pg_streaming_' in text or 'game-memory-budget-' in text:
            raise RuntimeError(f'Unrecognised obsolete memory hook in {name}')
        if text != path.read_text():
            path.write_text(text)
    for name in ('game-memory-budget-impl.h', 'game-memory-budget-decl.h'):
        (generated / name).unlink(missing_ok=True)


if __name__ == '__main__':
    restore(Path(__file__).resolve().parents[1] / 'Generated')
