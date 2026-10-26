// ZEMA_MINIMAP_PARITY_V1
// Adapted from glue5 a62e56a5 shader.rs/draw.rs/pipeline.rs. Original shader
// bindings and the distinct HUD / world-space pause-map paths are preserved.
const zemaMinimapMaskWGSL = /*__MASK_WGSL__*/;
const zemaMinimapPauseWGSL = /*__PAUSE_WGSL__*/;

function zemaMinimapShaderSource(rec, source) {
    if (rec.effect !== 'radar' || rec.program !== 'PS_TexturedUnlitAA') return source;
    const edge = '@location(5u) v5 : vec4<f32>';
    const main = /(@fragment\s*fn\s+main\s*\()((?:[^()]|\([^)]*\))*)(\)\s*->)/;
    const m = main.exec(source);
    if (!m || m[2].split(',').filter(x => x.trim() === edge).length !== 1)
        throw new Error('Unexpected radar geometry-stage edge input');
    const args = m[2].split(',').filter(x => x.trim() !== edge).map(x => x.trim());
    const text = source.replace(main, (_, before, _args, after) => before + args.join(', ') + after);
    const call = /\n\s*main_inner\([^;]*\);/g;
    if ((text.match(call) || []).length !== 1) throw new Error('Unexpected radar entry call');
    // WebGPU has no geometry shader supplying edge distances. Full coverage
    // keeps texture/depth/clipping calculations and removes the invisible zero.
    return text.replace(call, '\n  let v5 = vec4<f32>(1.0f);$&');
}

function zemaPauseMapBlend(state) {
    const w = state && state.words;
    return !!w && w[2] === 1 && w[5] === 4 && w[8] === 4 && w[9] === 8;
}

function zemaMinimapVariant(base, source, suffix, alreadyPacked = false) {
    const cache = base.zemaMinimapVariants || (base.zemaMinimapVariants = new Map());
    if (cache.has(suffix)) return cache.get(suffix);
    // HUD coordinates modify base.text, which shaderProgram already packed.
    // Repacking that would mistake binding 0 for the original D3D slot and
    // wrap cbpack_t a second time. Raw mask/pause sources still pack once.
    const { text, pack } = alreadyPacked ? { text: source, pack: base.pack } : packUniforms(source);
    const label = base.label + ' [' + suffix + ']';
    const module = device.createShaderModule({ code: text, label });
    const info = parseWgsl(text), groupBindings = {};
    for (const b of info.bindings) (groupBindings[b.group] || (groupBindings[b.group] = [])).push(b);
    for (const g in groupBindings) groupBindings[g].sort((a, b) => a.binding - b.binding);
    const flat = [];
    for (const m of text.matchAll(/@location\((\d+)u?\)\s*@interpolate\(flat[^)]*\)/g)) flat.push(+m[1]);
    // Binding/constant caches belong to this program, never its source shader.
    const result = { module, info, consts: null, pack, text, flat, groupBindings,
        variants: new Map(), bgls: [], label, vid: /\bvertex_index\b/.test(text), iid: /\binstance_index\b/.test(text) };
    cache.set(suffix, result);
    return result;
}

function zemaMinimapPrograms(vs, ps, blend) {
    if (!vs || !ps || vs.label !== 'im::VS_Blit' || ps.label !== 'im::PS_BlitDepthToAlpha') return [vs, ps];
    if (zemaPauseMapBlend(blend))
        return [zemaMinimapVariant(vs, zemaMinimapPauseWGSL, 'pause-map world coordinates'), ps];
    // Same exact original vertex shader is used by ordinary blits; only the
    // radar-mask pair uses normalized [0,1] coordinates with y pointing down.
    const from = 'o0 = vec4<f32>(v0.xyz, o0.w);';
    if (vs.text.split(from).length !== 2) throw new Error('Unexpected HUD mask vertex source');
    const source = vs.text.replace(from,
        'o0 = vec4<f32>(v0.x * 2.0f - 1.0f, 1.0f - v0.y * 2.0f, v0.z, o0.w);');
    return [zemaMinimapVariant(vs, source, 'HUD mask coordinates', true),
        zemaMinimapVariant(ps, zemaMinimapMaskWGSL, 'filtered radar mask')];
}
