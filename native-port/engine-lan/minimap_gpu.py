"""Port the pinned glue5 radar/HUD/pause-map distinctions to isolated web stages.

This edits a caller-owned worker string, never the original mirror. Shader
variants are selected before pipeline reflection AND draw resource bindings.
No minimap is enabled during character creation, where the game hides it.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PINS = {
    'minimap_mask.wgsl': 'e3fe4180b3c57a0b1c04bd8b985ba16606396df7bb87502088b41408b6106e98',
    'minimap_pause_vertex.wgsl': '00f3c7e796717b43410a978b49d9db7d3a3998811060ddbfc8e1e60a7b033fe7',
}


def pinned(name):
    data = (ROOT / name).read_bytes()
    if hashlib.sha256(data).hexdigest() != PINS[name]:
        raise ValueError('Minimap shader source pin changed: ' + name)
    return data.decode()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Minimap worker boundary changed: ' + old[:100])
    return text.replace(old, new)


def apply(text):
    """Apply once after validating the original worker at the stage boundary.

    Compatible with other narrow worker patches. Does not itself bless an
    arbitrary input worker; the caller must check its original source pin.
    """
    if 'ZEMA_MINIMAP_PARITY_V1' in text:
        raise ValueError('Minimap worker patch is already installed')
    helper = (ROOT / 'minimap_gpu.js').read_text()
    helper = helper.replace('/*__MASK_WGSL__*/', json.dumps(pinned('minimap_mask.wgsl')))
    helper = helper.replace('/*__PAUSE_WGSL__*/', json.dumps(pinned('minimap_pause_vertex.wgsl')))
    text = once(text, 'const { text, pack } = packUniforms(source);',
                'const { text, pack } = packUniforms(zemaMinimapShaderSource(rec, source));')
    # Both normal draws and compile-ahead recipes need the same programs. The
    # recipe's original shader hashes + blend words uniquely select the mode;
    # persisted recipes therefore retain real hashes and are replayable.
    draw = 'const vsProg = shaderProgram(vsObj);\n\tconst psProg = psObj ? shaderProgram(psObj) : null;'
    draw_crlf = draw.replace('\n', '\r\n')
    if draw_crlf in text:
        draw = draw_crlf
    text = once(text, draw,
        "let vsProg = shaderProgram(vsObj), psProg = psObj ? shaderProgram(psObj) : null;\n"
        "\t[vsProg, psProg] = zemaMinimapPrograms(vsProg, psProg, S.blend.id ? objs.get(S.blend.id) : null);")
    ahead = 'const vsProg = shaderProgram(vsObj), psProg = psObj ? shaderProgram(psObj) : null;'
    # The new draw declaration uses let; this remains unique to compileAhead.
    text = once(text, ahead,
        "let vsProg = shaderProgram(vsObj), psProg = psObj ? shaderProgram(psObj) : null;\n"
        "\t[vsProg, psProg] = zemaMinimapPrograms(vsProg, psProg, rc.b ? { words: rc.b } : null);")
    return once(text, 'function shaderProgram(sh) {', helper + '\nfunction shaderProgram(sh) {')
