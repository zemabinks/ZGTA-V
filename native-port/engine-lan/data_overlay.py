"""Length-preserving UI data overlays from pinned glue5 overlay.rs.

Pure byte transformations: callers supply the bytes and decide how to serve
them. No file, process, network, save, or original-mirror access is performed.
None means the exact expected source shape was unavailable; serve the original.
"""
from __future__ import annotations


def feed_width(data: bytes) -> bytes | None:
    """Only the GameStream block's stretched notification widths are changed."""
    start = data.find(b'<GameStream>')
    if start < 0:
        return None
    end = data.find(b'</GameStream>', start)
    if end < 0:
        return None
    block = data[start:end]
    old, new = b'sizeX="0.19890859375"', b'sizeX="0.15000000000"'
    if old not in block:
        return None
    return data[:start] + block.replace(old, new) + data[end:]


def autosave_first(data: bytes) -> bytes | None:
    """Swap the two complete adjacent lines, preserving their exact bytes."""
    def line(pref: bytes):
        at = data.find(b'<MenuPref>' + pref + b'</MenuPref>')
        if at < 0:
            return None
        start = data.rfind(b'\n', 0, at)
        end = data.find(b'\n', at)
        if start < 0 or end < 0:
            return None
        return start + 1, end + 1

    flow, autosave = line(b'PREF_STARTUP_FLOW'), line(b'PREF_AUTOSAVE')
    if flow is None or autosave is None or flow[1] != autosave[0]:
        return None
    return data[:flow[0]] + data[autosave[0]:autosave[1]] + data[flow[0]:flow[1]] + data[autosave[1]:]


PATCHES = {
    'common/data/ui/frontend.xml': feed_width,
    'common/data/ui/pausemenu.xml': autosave_first,
}


def patch(rel: str, data: bytes) -> bytes | None:
    """`rel` is under game data/, matching glue5 case-insensitively.

    Caller must enforce its existing safe-path handling before opening data.
    This dispatch intentionally does not normalize paths or accept suffixes.
    """
    fn = PATCHES.get(rel.lower())
    if fn is None or not isinstance(data, bytes):
        return None
    try:
        data.decode('utf-8')
    except UnicodeDecodeError:
        return None
    result = fn(data)
    if result is None or len(result) != len(data):
        return None
    return result
