"""Narrow renderer parity fixes; applied only to a separately pinned worker stage.

Glue5 format.rs preserves normalized 16-bit render targets when supported.
Its stencil proxy replicates the stencil plane into both D3D sample channels.
Neither change is a claim of paired gameplay or full native/browser parity.
"""
from stage_browser import once
from pathlib import Path


def apply(text):
    text=once(text,"adapter = await gpu.requestAdapter({ powerPreference: 'high-performance' });", "logLine('initialization: requesting WebGPU adapter');\n\tadapter = await gpu.requestAdapter({ powerPreference: 'high-performance' });\n\tlogLine('initialization: WebGPU adapter request resolved');")
    text=once(text,"device = await adapter.requestDevice({ requiredFeatures, requiredLimits: limits });", "logLine('initialization: requesting WebGPU device');\n\tdevice = await adapter.requestDevice({ requiredFeatures, requiredLimits: limits });\n\tlogLine('initialization: WebGPU device request resolved');")
    # Opt-in local trace: observe queue progress without touching its state.
    text=once(text,'post({ ready: true });',"""post({ ready: true });
\tif (!isNode && new URLSearchParams(self.location.search).get('log') === '1') setInterval(() => {
\t\trefreshViews();
\t\tlogLine('queue observation: head/tail/state/executed ' + [0, 1, 2, 3].map(n => Atomics.load(i32, ringW + n)).join('/'));
\t}, 5000);""")
    text=once(text,"case DXGI.R16G16B16A16_UNORM: return { format: 'rgba16float' };\t// no core rgba16unorm: TODO texture-formats-tier1",
        "case DXGI.R16G16B16A16_UNORM: return { format: device.features.has('texture-formats-tier1') ? 'rgba16unorm' : 'rgba16float' }; // preserve BC compressor's normalized u16 words")
    text=once(text,"case DXGI.R16G16_TYPELESS: case DXGI.R16G16_FLOAT: case DXGI.R16G16_UNORM: return { format: 'rg16float' };",
        "case DXGI.R16G16_TYPELESS: case DXGI.R16G16_FLOAT: return { format: 'rg16float' };\n\tcase DXGI.R16G16_UNORM: return { format: device.features.has('texture-formats-tier1') ? 'rg16unorm' : 'rg16float' };")
    text=once(text,"logLine('device ready: '","logLine('normalized16 skin targets: ' + (device.features.has('texture-formats-tier1') ? 'exact UNORM16' : 'legacy float fallback; compressed skin fidelity unverified'));\n\tlogLine('device ready: '")
    if text.count("kind === 'depth' ? 'r32float' : 'r8uint'")!=2:
        raise ValueError('Stencil proxy format anchors changed')
    text=text.replace("kind === 'depth' ? 'r32float' : 'r8uint'","kind === 'depth' ? 'r32float' : 'rg8uint'")
    text=once(text,"-> @location(0) vec4<u32> { return textureLoad(src, vec2i(pos.xy), 0); }`",
        "-> @location(0) vec4<u32> { let s = textureLoad(src, vec2i(pos.xy), 0).x; return vec4<u32>(s, s, 0u, 1u); }`")
    text=once(text,'// r8uint (stencil) texture is refreshed','// rg8uint (replicated D3D stencil .x/.y) texture is refreshed')
    # Muguet c16d5df / Glue5 mark_aspects_written: one plane can be read-only
    # while the other is written. The old conjunction left that plane stale.
    text=once(text,'function markDepthDirty(t) { t.proxy_depth && (t.proxy_depth.dirty = true); t.proxy_stencil && (t.proxy_stencil.dirty = true); }',
        'function markDepthDirty(t, depth = true, stencil = true) { if(depth && t.proxy_depth)t.proxy_depth.dirty=true; if(stencil && t.proxy_stencil)t.proxy_stencil.dirty=true; }')
    text=once(text,'if (!roDepth && !roStencil) markDepthDirty(dt);',
        'markDepthDirty(dt, !roDepth, hasStencil(dt.format) && !roStencil);')
    text=once(text,'const NAN_TEXEL = { r8uint: 1,','const NAN_TEXEL = { rg8uint: 2, rgba16unorm: 8, rg16unorm: 4, r8uint: 1,')
    helper=(Path(__file__).with_name('normalized_gpu.js')).read_text()
    text=once(text,'function mapFormat(f, bind) {',helper+'\nfunction mapFormat(f, bind) {')
    text=once(text,"let proxied = false;", "let proxied = false;\n\tif(zemaNorm16(t.format) && b.sample==='float'){t=zemaNormalizedProxy(t);proxied=true;sawProxy=true;}")
    text=once(text,"function markColorDirty(t) { if (t && t.proxy_fdepth) t.proxy_fdepth.dirty = true; }",
        "function markColorDirty(t) { if(t && t.proxy_norm16)t.proxy_norm16.dirty=true; if (t && t.proxy_fdepth) t.proxy_fdepth.dirty = true; }")
    anchor="else if (t && t.kind === 'texture' && !isDepth(t.format) && b.sample === 'depth') { any = true; floatToDepthProxy(t); }"
    text=once(text,anchor,anchor+"\n\t\telse if(t && t.kind==='texture' && zemaNorm16(t.format) && b.sample==='float'){any=true;zemaNormalizedProxy(t);}")
    text=once(text,'if (o.tex) { o.tex.destroy();','if (o.tex) { if(o.proxy_norm16)o.proxy_norm16.tex.destroy(); o.tex.destroy();')
    # Native glue5's clamped box filter uses only textureLoad. Browser auto
    # layout still requires filterable Float, so use an explicit load layout.
    start=text.index("\t\tconst module = device.createShaderModule({ code: `@group(0) @binding(0) var src: texture_2d<f32>;", text.index('function generateMips('))
    end=text.index('\n\t\tmipPipelines.set(fmt, pl);',start)
    text=text[:start]+"\t\tpl = zemaMipPipeline(fmt);"+text[end:]
    text=once(text,"isDepth(fmt) || fmt.startsWith('bc') || t.desc.dimension === '3d'", "isDepth(fmt) || fmt.startsWith('bc') || t.desc.dimension === '3d' || t.desc.sampleCount > 1")
    text=once(text,"let mipSampler = null;", "// Mip generation uses textureLoad without a sampler.")
    text=once(text,"if (!mipSampler) mipSampler = device.createSampler({ magFilter: 'linear', minFilter: 'linear', addressModeU: 'clamp-to-edge', addressModeV: 'clamp-to-edge' });", "logOnce('mips-load-' + fmt, 'GenerateMips textureLoad box filter: ' + fmt);")
    text=once(text,", { binding: 1, resource: mipSampler }", "")
    text=once(text,"f2dPipeline = device.createRenderPipeline({ layout: 'auto',", "const sourceLayout=zemaLoadLayout();\n\t\t\tf2dPipeline = device.createRenderPipeline({ layout: device.createPipelineLayout({bindGroupLayouts:[sourceLayout]}),")
    text=once(text,"let px = t.proxy_fdepth;", "logOnce('float-depth-load-' + t.format, 'Float-to-depth textureLoad conversion: ' + t.format);\n\tlet px = t.proxy_fdepth;")
    text=once(text,"const TEXEL_BYTES = {", "const TEXEL_BYTES = { 'rg16unorm': 4, 'rgba16unorm': 8,")
    text=once(text,"const mip = uav.a, w =", "if(zemaNorm16(t.format))logOnce('clear-norm16-' + t.format + '-' + !!isFloat, 'Normalized16 UAV clear: ' + t.format + (isFloat ? ' numeric float' : ' exact channel bits'));\n\tconst mip = uav.a, w =")
    text=once(text,"const dv = new DataView(data.buffer);\r\n\t\tfor (let i = 0; i < w * h; i++) for (let c = 0; c < bpt / 4; c++) dv.setUint32(i * bpt + c * 4, values[c & 3], true);", "if(zemaNorm16(t.format))zemaPackNormClear(data,bpt,isFloat,values);\n\t\telse { const dv = new DataView(data.buffer);\n\t\tfor (let i = 0; i < w * h; i++) for (let c = 0; c < bpt / 4; c++) dv.setUint32(i * bpt + c * 4, values[c & 3], true); }")
    text=once(text,"for (let l = 0; l < layers; l++) device.queue.writeTexture({ texture: t.tex, mipLevel: mip, origin: { x: 0, y: 0, z: l } }, data, { bytesPerRow: w * bpt, rowsPerImage: h }, { width: w, height: h, depthOrArrayLayers: 1 });", "for (let l = 0; l < layers; l++) device.queue.writeTexture({ texture: t.tex, mipLevel: mip, origin: { x: 0, y: 0, z: l } }, data, { bytesPerRow: w * bpt, rowsPerImage: h }, { width: w, height: h, depthOrArrayLayers: 1 });\n\tmarkColorDirty(t);")
    return text
