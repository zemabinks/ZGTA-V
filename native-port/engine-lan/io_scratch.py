"""Bound temporary OPFS reads when a browser rejects shared destinations.

The worker's readFromStore is synchronous: a single worker-owned scratch can
be reused without concurrent borrowers. The normal shared-heap path is intact.
Call only after the public entry point validates the original worker hash.
"""
MARK = 'ZGTA_IO_BOUNDED_SCRATCH_V1'

def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Reviewed IO scratch anchor changed')
    return text.replace(before, after)

def apply(text):
    if MARK in text:
        raise ValueError('IO scratch already installed')
    text = once(text, 'function readFromStore(id, off, len, dst) {', '''// ZGTA_IO_BOUNDED_SCRATCH_V1: lazy, bounded, synchronous worker-local storage.
let storeReadScratch = null;
function readFromStore(id, off, len, dst) {''')
    # Retain original line endings outside the reviewed replacement.
    before = '''\t\tif (sharedReadFails) {
\t\t\tconst tmp = new Uint8Array(n);
\t\t\tgot = sh.read(tmp, { at: storeOff });
\t\t\tHEAPU8.set(tmp, dst + done);
\t\t}'''
    if '\r\n' in text:
        before = before.replace('\n', '\r\n')
    return once(text, before, '''\t\tif (sharedReadFails) {
\t\t\tif (!storeReadScratch) storeReadScratch = new Uint8Array(256 * 1024);
\t\t\tfor (let copied = 0; copied < n;) {
\t\t\t\tconst count = Math.min(n - copied, storeReadScratch.length);
\t\t\t\tconst tmp = storeReadScratch.subarray(0, count);
\t\t\t\tconst read = sh.read(tmp, { at: storeOff + copied });
\t\t\t\tif (read !== count) throw new Error('store read returned ' + read + ' of ' + count);
\t\t\t\tHEAPU8.set(tmp, dst + done + copied);
\t\t\t\tcopied += count;
\t\t\t}
\t\t\tgot = n;
\t\t}''')
