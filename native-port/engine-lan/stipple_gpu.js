// Legacy Bayer levels 1–15; codes 16–31 carry the engine's exact 2x2 phase mask.
// The normal shader and its resource/IO layout stay unchanged at level zero.
function zemaWithStipple(text, level) {
 if (!Number.isInteger(level) || level < 1 || level > 31) throw Error('Stipple level');
 const head = /@fragment\s*fn\s+main\s*\(/.exec(text);
 if (!head) throw Error('Fragment main missing for stipple');
 const start = head.index + head[0].length;
 let end = start, depth = 1;
 for (; end < text.length && depth; end++) {
  if (text[end] === '(') depth++;
  else if (text[end] === ')') depth--;
 }
 if (depth) throw Error('Fragment parameter list for stipple');
 let params = text.slice(start, end - 1);
 const position = /@builtin\(position\)\s*(\w+)\s*:/.exec(params);
 const name = position ? position[1] : 'zema_fade_position';
 if (!position) params += (params.trim() ? ', ' : '') + '@builtin(position) ' + name + ' : vec4<f32>';
 text = text.slice(0, start) + params + text.slice(end - 1);
 const body = text.indexOf('{', start + params.length);
 if (body < 0) throw Error('Fragment body for stipple');
 const test = (level & 16) ? `
  let zema_fade_x = u32(max(${name}.x, 0.0)) & 1u;
  let zema_fade_y = u32(max(${name}.y, 0.0)) & 1u;
  let zema_fade_phase = zema_fade_x + 2u * zema_fade_y;
  if (((${level & 15}u >> zema_fade_phase) & 1u) == 0u) { discard; }
` : `
  let zema_fade_x = u32(${name}.x) & 3u;
  let zema_fade_y = u32(${name}.y) & 3u;
  let zema_fade_low = (((zema_fade_x ^ zema_fade_y) & 1u) << 1u) | (zema_fade_y & 1u);
  let zema_fade_high = ((((zema_fade_x ^ zema_fade_y) >> 1u) & 1u) << 1u) | (zema_fade_y >> 1u);
  if ((4u * zema_fade_low + zema_fade_high) >= ${level}u) { discard; }
`;
 text = text.slice(0, body + 1) + test + text.slice(body + 1);
 return text.includes('derivative_uniformity') ? text : 'diagnostic(off, derivative_uniformity);\n' + text;
}
