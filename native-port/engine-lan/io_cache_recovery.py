"""Recover a failed disposable data cache by reading the original source.

Composes with the pinned IO worker. Userdata and character storage are untouched.
Cache bytes and journal are retained; a failing cache is bypassed for this launch.
"""
from stage_browser import once

MARK = 'ZGTA_IO_CACHE_RECOVERY_V1'


def apply(text):
    if MARK in text:
        raise ValueError('IO cache recovery already applied')
    text = once(text, "function log(text) { if (remoteLog) fetch('/log', { method: 'POST', body: text }).catch(() => {}); }", """// ZGTA_IO_CACHE_RECOVERY_V1: bounded local diagnostics, including otherwise hidden IO errors.
const ioNotes = new Set();
function log(text) {
 if (remoteLog) fetch('/log', {method:'POST',body:text}).catch(()=>{});
 if (!/\\[io\\].*(failed|persistent store|cache bypass)/i.test(text)) return;
 const note=String(text).split('\\n')[0].slice(0,512);
 if (ioNotes.has(note) || ioNotes.size>=32) return;
 ioNotes.add(note);
 try {const channel=new BroadcastChannel('game-log');channel.postMessage(note);channel.close();} catch (_) {}
}""")
    text = once(text, 'let sh = null, jh = null, storeEnd = 0, journalEnd = 16;', """let sh = null, jh = null, storeEnd = 0, journalEnd = 16;
let cacheFailed = false;
function bypassCache(error) {
 if (cacheFailed) return;
 cacheFailed = true;
 log('[io] cache bypass: '+String(error && error.name || 'Error')+': '+String(error && error.message || error)+'. Streaming original game data; saves are kept.');
}
function writeCache(chunk, at) {
 if (cacheFailed) throw Error('Data cache is bypassed for this launch');
 try {
  const written=sh.write(chunk,{at});
  if (written!==chunk.byteLength) throw Error('Data cache short write: '+written+' of '+chunk.byteLength);
 } catch(error) {bypassCache(error);throw error;}
}""")
    text = once(text, 'const memCache = new Map();', 'const memInflight = new Map();\nconst memCache = new Map();')
    text = once(text, 'sh.write(value.subarray(pos, pos + n), { at: r.offset + inRun });', 'writeCache(value.subarray(pos, pos + n), r.offset + inRun);')
    text = once(text, 'sh.write(chunk, { at: offset + pos + at })', 'writeCache(chunk, offset + pos + at)')
    # A failed cache write must also release the response being streamed into it.
    text = once(text, '\tlet pos = 0;\r\n\tfor (;;) {', '\tlet pos = 0;\n\ttry {\n\tfor (;;) {')
    text = once(text, '\t}\r\n\treturn pos;\r\n}', '\t}\n\t} finally {try {await reader.cancel();} catch (_) {} try {reader.releaseLock();} catch (_) {}}\n\treturn pos;\n}')
    text = once(text, '\t\tconst consume = async (reader) => {', '\t\tconst consume = async (reader) => {\n\t\t try {')
    text = once(text, "if (ri !== runs.length) throw new Error('short batch answer: ' + ri + ' of ' + runs.length + ' runs');\r\n\t\t};", "if (ri !== runs.length) throw new Error('short batch answer: ' + ri + ' of ' + runs.length + ' runs');\n\t\t } finally {try {await reader.cancel();} catch (_) {} try {reader.releaseLock();} catch (_) {}}\n\t\t};")
    text = once(text, 'while (nextRun < runs.length) {', 'while (nextRun < runs.length && !cacheFailed) {')
    text = once(text, 'while (nextBatch < batches.length) {', 'while (nextBatch < batches.length && !cacheFailed) {')
    text = once(text, 'if (!pendingJournal.length || !jh || !sh) return;', 'if (cacheFailed || !pendingJournal.length || !jh || !sh) return;')
    text = once(text, 'async function ensureBlocks(id, first, last, low) {', "async function ensureBlocks(id, first, last, low) {\n\tif(cacheFailed) throw Error('Data cache is bypassed for this launch');")
    # These keys use 256 KiB blocks, while persistent runs use 4 KiB blocks.
    # Recovery must never join an old persistent promise under a colliding key.
    start = text.index('async function getMemBlock(id, block) {')
    end = text.index('async function readWithoutStore(', start)
    part = text[start:end]
    if part.count('inflight') != 4:
        raise ValueError('Reviewed memory fetch bookkeeping changed')
    text = text[:start] + part.replace('inflight', 'memInflight') + text[end:]
    text = once(text, '\t\t\tif (sh) {', '\t\t\tif (sh && !cacheFailed) {\n\t\t\t try {')
    text = once(text, '\t\t\t\tresult = len;\r\n\t\t\t} else result = await readWithoutStore(id, off, len, dst);', """\t\t\t\tresult = len;
\t\t\t } catch(error) {
\t\t\t\tbypassCache(error);
\t\t\t\tviews();result=await readWithoutStore(id,off,len,dst);
\t\t\t }
\t\t\t} else result = await readWithoutStore(id, off, len, dst);""")
    text = once(text, "log('[io] read failed: ' + e.message);", """const detail=String(e && e.name || 'Error')+': '+String(e && e.message || e);
\t\tlog('[io] read failed: '+(files[id]?.path || 'unknown file')+' at '+off+' for '+len+' bytes: '+detail);
\t\ttry {bc.postMessage({error:'Game data could not be read: '+detail.split('\\n')[0].slice(0,180)+'. Your saves are kept. Return to the launcher before retrying.'});} catch (_) {}""")
    text = once(text, 'function pumpHints() {', 'function pumpHints() {\n\tif(cacheFailed){hintQueue.length=0;lowQueue.length=0;return;}')
    return text
