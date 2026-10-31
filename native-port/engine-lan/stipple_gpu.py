"""Carry the explicit host fade level through live and recorded GPU pipelines."""
from pathlib import Path
from stage_browser import once


def apply(text):
    text = text.replace('\r\n', '\n')
    text = once(text, 'const S = {', 'const S = {\n\tstipple: 0,')
    text = once(text, '\tS.shader = [0, 0, 0];', '\tS.stipple = 0;\n\tS.shader = [0, 0, 0];')
    text = once(text, '\t\tcase 0 /* NOP */:', '''		case 65 /* host STIPPLE */: {
			if (n !== 1) throw Error('Malformed stipple packet');
			const level = u32[p] < 32 ? u32[p] : 0;
			if (S.stipple !== level) { S.stipple = level; pdirty = true; }
			break;
		}
		case 0 /* NOP */:''')
    text = once(text, 'T[n++] = S.topo;', 'T[n++] = psProg ? S.stipple : 0;\n\tT[n++] = S.topo;')
    for function in ('pipelineRecipe', 'pipelineDescFor'):
        # Three occurrences: live call, declaration and recorded pipeline call
        # (the latter is spelled separately below).
        tail = 'passInfoNow.roDepth, passInfoNow.roStencil);'
        anchor = next(line for line in text.splitlines() if function + '(' in line and tail in line)
        text = once(text, anchor, anchor.replace(tail, 'passInfoNow.roDepth, passInfoNow.roStencil, psProg ? S.stipple : 0);'))
        signature = next(line for line in text.splitlines() if line.startswith('function ' + function + '('))
        text = once(text, signature, signature.replace('roStencil) {', 'roStencil, stipple = 0) {'))
    text = once(text, "vs: vsObj.hash, ps: psObj ? psObj.hash : '',", "vs: vsObj.hash, ps: psObj ? psObj.hash : '', stipple,")
    text = once(text, 'rc.rt, rc.n, rc.ds, rc.ro]', 'rc.rt, rc.n, rc.ds, rc.ro, rc.stipple || 0]')
    text = once(text, 'rtInfo, rc.ds || null, (rc.ro & 1) !== 0, (rc.ro & 2) !== 0);', 'rtInfo, rc.ds || null, (rc.ro & 1) !== 0, (rc.ro & 2) !== 0, rc.stipple || 0);')
    text = once(text, 'module: pixelModule(psProg, a2c, remap),', 'module: pixelModule(psProg, a2c, remap, stipple),')
    start = text.index('function pixelModule(')
    end = text.index('\nfunction getPipeline(', start)
    text = text[:start] + Path(__file__).with_suffix('.js').read_text() + '''
function pixelModule(psProg, a2c, remap, stipple = 0) {
	if (!stipple && (!remap || !remap.ps)) return a2c ? (a2cModule(psProg) || psProg.module) : psProg.module;
	const key = 'remap|' + (remap && remap.ps ? remap.key : '') + (a2c ? '|a2c' : '') + '|stipple=' + stipple;
	let m = psProg.variants.get(key);
	if (!m) {
		let text = psProg.text;
		if (a2c) text = text.replace(/(\\n\\s*main_inner\\([^;]*\\);)/, '$1\\n  if (o0.w < 0.5f) { discard; }');
		if (remap && remap.ps) { text = remapLocations(text, 'ps', remap.map); remapVariants[1]++; }
		if (stipple) text = zemaWithStipple(text, stipple);
		m = device.createShaderModule({ code: text, label: psProg.label + ' [' + key + ']' });
		psProg.variants.set(key, m);
	}
	return m;
}
''' + text[end:]
    return text
