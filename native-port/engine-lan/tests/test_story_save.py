"""Bounded SGTA5 parsing parity and real native writes in isolated temp folders."""
import base64
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

def vectors():
    def data(title='The Big Score (100.0%)', size=65536, terminated=True):
        head=b'\0\0\0\1'+title.encode('utf-16le')+(b'\0\0' if terminated else b'')
        return head+b'\0'*(size-len(head))
    valid=data()
    cases=[('valid',valid,'The Big Score (100.0%)'),('unicode',data('  Los Santos — 城市 🚗  '),'Los Santos — 城市 🚗'),
           ('bom',data('\ufeffStory save'),'Story save'),('tiny',data(size=1024),None),
           ('version',b'\0\0\0\2'+valid[4:],None),('empty',data(''),None),('short-title',data('Hi'),None),
           ('control',data('Bad\u0085title'),None),('unterminated',data('x'*256,terminated=False),None),
           ('surrogate',valid[:4]+b'\0\xd8'+valid[6:],None),('too-big',data(size=8*1024*1024+1),None)]
    return [{'name':n,'data':base64.b64encode(d).decode(),'title':t} for n,d,t in cases]

class StorySave(unittest.TestCase):
    def test_parser_parity_and_exclusive_slot_writes(self):
        def run(args):
            p=subprocess.run([str(x) for x in args],text=True,capture_output=True,timeout=120)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            return p.stdout
        with tempfile.TemporaryDirectory(prefix='zgta-story-save-') as temp:
            d=Path(temp);cases=vectors();(d/'cases.json').write_text(json.dumps(cases))
            run(['/usr/bin/swiftc','-module-cache-path',d/'ModuleCache',ROOT.parent/'app/App/StorySave.swift',ROOT/'tests/story_save.swift','-o',d/'story-save'])
            native=json.loads(run([d/'story-save',d]))
            browser=json.loads(run(['node','-e',r'''
const fs=require('fs'),assert=require('assert/strict'),S=require(process.argv[1]);
const rows=JSON.parse(fs.readFileSync(process.argv[2])).map(c=>{let title=null;try{title=S.storyTitle(new Uint8Array(Buffer.from(c.data,'base64')));}catch(_){}return {name:c.name,title};});
assert.equal(S.storyCandidates('sgta50004.bak',new Set(['sgta50004.BAK','SGTA50000']))[0],1);
assert.equal(S.storyCandidates('../../SGTA50009',[])[0],0);
assert.equal(S.storyCandidates('SGTA50015',[])[0],0);
assert.equal(S.storyCandidates('SGTA50009',[])[0],9);
assert.deepEqual(S.storyCandidates('SGTA50000',Array.from({length:15},(_,n)=>'SGTA500'+String(n).padStart(2,'0'))),[]);
console.log(JSON.stringify(rows));
''',ROOT/'browser-saves.js',d/'cases.json']))
            expected=[{'name':c['name'],'title':c['title']} for c in cases]
            self.assertEqual(native,expected);self.assertEqual(browser,expected)

if __name__=='__main__':unittest.main()
