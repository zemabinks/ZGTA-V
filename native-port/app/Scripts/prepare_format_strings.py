"""Make the engine's Windows-only printf sizes print.

About 450 engine messages use MSVC's %Iu, %Id, %Ix, %Ii and %IX for size_t values. musl rejects
the whole format when one conversion is invalid, so those messages came out as bare "Error: " and
"Warning: " lines (most of a long log). Each I in such a conversion becomes z, the standard size
modifier: same length, and size_t is 64-bit in this wasm64 build, as it is on Windows x64.
"""
from pathlib import Path
import re
root = Path(__file__).resolve().parents[1]
path = root / 'Generated/game_0.c'
s = path.read_text()
CONVERSION = re.compile(rb'%[-+ #0]*\d*(?:\.\d+)?I[udixX]')
ARRAY = re.compile(r'^const u8 (data_segment_data_w2c_game_d\d+)\[\] = \{\n(.*?)\n\};$', re.M | re.S)
TOKEN = re.compile(r'0x[0-9a-f]{2}')
pieces, last, patched, segments = [], 0, 0, 0
for match in ARRAY.finditer(s):
    body = match.group(2)
    if b'%' not in bytes(int(t, 16) for t in TOKEN.findall(body)) or 'I' not in body and '0x49' not in body:
        continue
    tokens = list(TOKEN.finditer(body))
    data = bytes(int(t.group(0), 16) for t in tokens)
    offsets = []
    i = 0
    while i < len(data):
        if data[i] != 0x25: i += 1; continue
        if i + 1 < len(data) and data[i + 1] == 0x25: i += 2; continue  # %%
        m = CONVERSION.match(data, i)
        if m: offsets.append(m.end() - 2)
        i += 1
    if not offsets: continue
    body = list(body)
    for o in offsets:
        t = tokens[o]
        assert ''.join(body[t.start():t.end()]) == '0x49'
        body[t.start():t.end()] = list('0x7a')
    pieces.append(s[last:match.start(2)]); pieces.append(''.join(body)); last = match.end(2)
    patched += len(offsets); segments += 1
pieces.append(s[last:])
if patched:
    path.write_text(''.join(pieces))
print(f'format strings: {patched} size conversions in {segments} segments use %z')
