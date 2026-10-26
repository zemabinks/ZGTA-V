"""Pinned IO startup failures and close-during-cache-open ownership.

Apply once to the original IO worker, before UI refresh and storage namespaces.
Engine and save storage are unchanged. Cache recovery retries actual source reads;
it never supplies synthetic data or deletes an existing cache.
"""
import hashlib
PIN='d91c89e64f7f280666b5c9d1669ed6d65d66605077264569a49146ed79fe0bae'
MARK='ZGTA_IO_LIFECYCLE_V1'

def once(text,before,after):
    if text.count(before)!=1:raise ValueError('Reviewed IO lifecycle anchor changed')
    return text.replace(before,after)

def apply(text):
    if MARK in text:raise ValueError('IO lifecycle already installed')
    if hashlib.sha256(text.encode()).hexdigest()!=PIN:raise ValueError('Reviewed original IO worker changed')
    text=once(text,'async function openStore(version) {', '''// ZGTA_IO_LIFECYCLE_V1: close intent owns pending asynchronous opens too.
let storeClosing = false;
function closeStoreHandle(handle) { try { if (handle) handle.close(); } catch (_) {} }
async function openStore(version) {
\tif (storeClosing) return;''')
    text=once(text,"const dir = await root.getDirectoryHandle('gamedata', { create: true });", "const dir = await root.getDirectoryHandle('gamedata', { create: true });\n\t\tif (storeClosing) return;")
    text=once(text,"try { return await (await dir.getFileHandle(name, { create: true })).createSyncAccessHandle(); }\r\n\t\t\t\tcatch (e) { if (attempt >= 40 || e.name !== 'NoModificationAllowedError') throw e; await new Promise((r) => setTimeout(r, 250)); }", '''try {
\t\t\t\t\tif (storeClosing) return null;
\t\t\t\t\tconst file = await dir.getFileHandle(name, { create: true });
\t\t\t\t\tif (storeClosing) return null;
\t\t\t\t\tconst handle = await file.createSyncAccessHandle();
\t\t\t\t\tif (storeClosing) { closeStoreHandle(handle); return null; }
\t\t\t\t\treturn handle;
\t\t\t\t} catch (e) { if (storeClosing) return null; if (attempt >= 40 || e.name !== 'NoModificationAllowedError') throw e; await new Promise((r) => setTimeout(r, 250)); }''')
    text=once(text,"const s = await openHandle('store.bin');", "const s = await openHandle('store.bin');\n\t\tif (!s || storeClosing) { closeStoreHandle(s); return; }")
    text=once(text,"try { j = await openHandle('journal.bin'); } catch (e) { s.close(); throw e; }", "try { j = await openHandle('journal.bin'); } catch (e) { closeStoreHandle(s); throw e; }\n\t\tif (!j || storeClosing) { closeStoreHandle(s); closeStoreHandle(j); return; }")
    text=once(text,"if (ev.data !== 'close') return;", "if (ev.data !== 'close') return;\n\tstoreClosing = true;")
    text=once(text,'try { if (sh) sh.close(); if (jh) jh.close(); } catch (e) {}', 'closeStoreHandle(sh); closeStoreHandle(jh);')
    text=once(text,'let ready = null;', '''let ready = null, ioStartupFailureReported = false;
function reportIoStartupFailure(error) {
\tif (ioStartupFailureReported || storeClosing) return;
\tioStartupFailureReported = true;
\tlet detail = 'unknown data initialization error';
\ttry { detail = String(error && error.message || error).split('\\n')[0].slice(0, 220); } catch (_) {}
\ttry { bc.postMessage({ error: 'Game data could not initialize: ' + detail + '. Return to the launcher before retrying.' }); } catch (_) {}
}''')
    text=once(text,'if (m.init) { ready = init(m); return; }', 'if (m.init) { ready = init(m); ready.catch(reportIoStartupFailure); return; }')
    text=once(text,'await ready;\t\t// the store is open and the manifest is loaded', 'try { await ready; } catch (error) { reportIoStartupFailure(error); return; }\t\t// Never start IO against failed initialization.\n\tif (storeClosing) return;')
    import io_cache_recovery
    return io_cache_recovery.apply(text)
