"""Source adaptations of Glue5's immutable tables and CPU uniform mirrors.

Applied after the existing pinned worker transforms, in private build outputs.
GPU regions and frame fences remain separate: only synchronous JS upload
scratch is shared. queue.writeBuffer captures its source before returning.
"""
from stage_browser import once


def apply(text):
    text = text.replace('\r\n', '\n')
    text = once(text, 'let shaderIndex = null;', 'const zemaConstantTables = new Map();\nlet shaderIndex = null;')
    old = '''		const n = Math.max(1, arr.length);
		const data = new Uint32Array(n * 4);
		arr.forEach((v, i) => { data[i * 4] = v >>> 0; });
		consts = device.createBuffer({ size: Math.max(16, data.byteLength), usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST });
		device.queue.writeBuffer(consts, 0, data);'''
    new = '''		// Key the GPU-visible words, including length; different tables never
		// alias through a hash collision. The cache lives with this device.
		const key = JSON.stringify(arr.map(v => v >>> 0));
		consts = zemaConstantTables.get(key);
		if (!consts) {
			const data = new Uint32Array(Math.max(1, arr.length) * 4);
			arr.forEach((v, i) => { data[i * 4] = v >>> 0; });
			consts = device.createBuffer({ size: data.byteLength, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST });
			device.queue.writeBuffer(consts, 0, data);
			zemaConstantTables.set(key, consts);
		}'''
    text = once(text, old, new)
    text = once(text, 'shared: [], slot: 0,', 'shared: [], mirrors: [], slot: 0,')
    text = once(text, 'c = { buf: sh.buf, id: sh.id, base: ubo.slot * RING_CHUNK };',
                'const mirror = ubo.mirrors[ubo.chunk] || (ubo.mirrors[ubo.chunk] = {});\n\t\t\tc = { buf: sh.buf, id: sh.id, base: ubo.slot * RING_CHUNK, mirror };')
    start = text.index('function stageReserve(chunk, off, n) {')
    end = text.index('\nconst curObjs =', start)
    text = text[:start] + '''function stageReserve(chunk, off, n) {
	const end = off + n, m = chunk.mirror;
	if (!Number.isInteger(off) || !Number.isInteger(n) || off < 0 || n < 0 || end > RING_CHUNK) throw Error('Uniform staging range');
	if (!m.stage || m.stage.length < end) {
		const grown = new Uint8Array(Math.min(RING_CHUNK, Math.max(end, m.stage ? m.stage.length * 2 : 262144)));
		if (m.stage) grown.set(m.stage.subarray(0, m.top));
		m.stage = grown;
	}
	m.top = Math.max(m.top || 0, end);
	if (chunk.lo === undefined || off < chunk.lo) chunk.lo = off;
	chunk.hi = Math.max(chunk.hi || 0, end);
	dirtyChunks.add(chunk);
	return m.stage;
}
function flushUniforms() {
	for (const c of dirtyChunks) {
		const stage = c.mirror.stage, hi = Math.min(stage.length, (c.hi + 3) & ~3);
		device.queue.writeBuffer(c.buf, c.base + c.lo, stage, c.lo, hi - c.lo);
		c.lo = undefined; c.hi = 0;
	}
	dirtyChunks.clear();
}
''' + text[end:]
    text = once(text, "flush('present');\n\tframeSlotDone[ubo.slot]", "flush('present');\n\tif (dirtyChunks.size) throw Error('Uniforms not uploaded before frame advance');\n\tframeSlotDone[ubo.slot]")
    text = once(text, '// its own mirror and dirty range.', '// its own dirty range and one CPU mirror shared by chunk index across slots.')
    return text
