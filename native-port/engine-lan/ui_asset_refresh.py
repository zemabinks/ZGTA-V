"""Refresh two small UI XML files and the bounded minimap compatibility archive.

Server-side overlays alone are skipped when OPFS or a precomputed boot batch
already contains older bytes. Game archives and user saves keep their caches.
"""
MARK='ZEMA_UI_ASSET_REFRESH_V1'
HELPER=r'''
// ZEMA_UI_ASSET_REFRESH_V1: only explicit UI assets, once per worker.
const zemaUICopies = new Map();
function zemaUIAsset(file, baseURL, query, fetcher = fetch) {
  if (!file.zemaUIRefresh || !Number.isSafeInteger(file.size) || file.size <= 0 || file.size > 1048576) return Promise.resolve(null);
  if (!zemaUICopies.has(file.path)) zemaUICopies.set(file.path, (async () => {
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 5000);
    let reader;
    try {
      const response = await fetcher(baseURL + file.path + query, {cache:'no-store', signal:controller.signal});
      if (!response.ok || !response.body) throw Error('UI layout unavailable');
      reader = response.body.getReader();
      const bytes = new Uint8Array(file.size); let used = 0;
      for (;;) {
        const item = await reader.read(); if (item.done) break;
        if (item.value.length > bytes.length - used) throw Error('UI layout exceeds manifest size');
        bytes.set(item.value, used); used += item.value.length;
      }
      if (used !== file.size) throw Error('UI layout size differs from manifest');
      return bytes;
    } catch (_) {
      // Keep the existing cache available during an offline/failed refresh.
      if (reader) try { await reader.cancel(); } catch (_) {}
      return null;
    } finally { clearTimeout(timer); if (reader) reader.releaseLock(); }
  })());
  return zemaUICopies.get(file.path);
}
'''


def apply(text):
    if MARK in text:
        raise ValueError('UI refresh already installed; preserve the staged worker')
    manifest="files = j.files.map((f) => ({ path: f[0], size: f[1] }));"
    request='\t\tif (off >= f.size) result = 0;'
    before='async function serve(slot) {'
    if any(text.count(anchor)!=1 for anchor in (manifest,request,before)):
        raise ValueError('Reviewed UI read/manifest anchors changed')
    text=text.replace(manifest,"files = j.files.map((f) => ({ path: f[0], size: f[1], zemaUIRefresh: /^(?:common\\/data\\/ui\\/(frontend|pausemenu)\\.xml|x64\\/data\\/cdimages\\/scaleform_minimap\\.rpf)$/i.test(f[0]) }));")
    text=text.replace(before,HELPER+'\n'+before)
    return text.replace(request,'''\t\tconst ui = f.zemaUIRefresh ? await zemaUIAsset(f, base, dataQuery) : null;
\t\tif (ui) {
\t\t\tviews(); result = off >= ui.length ? 0 : Math.min(len, ui.length - off);
\t\t\tif (result > 0) HEAPU8.set(ui.subarray(off, off + result), dst);
\t\t} else if (off >= f.size) result = 0;''')
