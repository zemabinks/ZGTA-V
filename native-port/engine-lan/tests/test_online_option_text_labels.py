"""Observed Online Options label and both script-selected values resolve safely."""
from pathlib import Path
import subprocess
import unittest


class OnlineOptionLabels(unittest.TestCase):
    def test_post_session_return_prompts_preserve_script_token_arguments(self):
        helper = Path(__file__).resolve().parents[1] / 'text_fallback.js'
        script = r"""
const a=require('node:assert/strict'),api=require(process.argv[1]);
const memory=new WebAssembly.Memory({initial:1}),decoder=new TextDecoder();let next=256;
const callback=api.callback(memory,()=>0n,n=>{const p=next;next+=Number(n);return BigInt(p);});
// Ordered contracts from a41fa82b10d1c49cee82b2a07671e8deeec8b4ce,
// identities observed in the retained QA-RECOVERY63 post-session-return log.
const tokens=new Map([
 [0x5c5e8467,[]],[0xf806013a,[]],
 [0x4fd87431,['~INPUT_CONTEXT~']],[0x3e15d0ac,['~INPUT_CONTEXT~']],
 [0xa4719d6a,['~INPUT_CONTEXT~']],[0x7af404b0,[]],
 [0x2d1d5ee6,['~INPUT_CONTEXT~']],[0xfe94e015,['~INPUT_CONTEXT~']],
 [0x20d075b0,['~INPUT_CONTEXT~']],[0x795864cd,[]],[0xb6a4d2d7,[]],
 [0x50026bed,[]],[0xfb4d7fb9,['~INPUT_CONTEXT~']],
 [0xab594369,['~s~','~INPUT_CONTEXT~','~s~','~s~']],[0xd0484a7b,[]]
]);
for(const [hash,expected] of tokens){
 const p=callback(hash);a.ok(p>0n,'Observed key must resolve');
 const bytes=new Uint8Array(memory.buffer,Number(p),512),end=bytes.indexOf(0);
 a.ok(end>0);const text=decoder.decode(bytes.subarray(0,end));
 a.deepEqual(text.match(/~[^~]+~/g)||[],expected,'Script arguments keep their order');
 a.ok(!text.includes('missing'));a.equal(callback(hash),p);
}
// An absent portrait dictionary is not supplied by inventing a label value.
for(const hash of [0,0x7c0323a1,0x39c55dfe,0x7427c7d0,0x8721505e,0x89b2a065])a.equal(callback(hash),0n);
"""
        result = subprocess.run(['node', '-e', script, str(helper)], capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_spectator_join_setting_and_values_keep_original_priority(self):
        helper = Path(__file__).resolve().parents[1] / 'text_fallback.js'
        # Exact reference blob a41fa82b10d1c49cee82b2a07671e8deeec8b4ce;
        # pausemenu_multiplayer case 4 selects Join / Don't Join for this row.
        script = r"""
const a=require('node:assert/strict'),api=require(process.argv[1]);
const memory=new WebAssembly.Memory({initial:1}),decoder=new TextDecoder();let next=256,allocations=0;
const expected=new Map([[0x21ae8f46,'Join Next Mode from Spectator Box'],[0xcadfe9a0,'Join'],[0x58e547fa,"Don't Join"]]);
let existing=0n;
const callback=api.callback(memory,()=>existing,n=>{allocations++;const p=next;next+=Number(n);return BigInt(p);});
for(const [hash,text] of expected){
 const p=callback(hash),bytes=new Uint8Array(memory.buffer,Number(p),text.length+1);
 a.ok(p>0n);a.equal(decoder.decode(bytes.subarray(0,bytes.indexOf(0))),text);
 a.equal(callback(hash),p,'Each resolved label is cached');
}
a.equal(allocations,3);
existing=128n;
for(const hash of expected.keys())a.equal(callback(hash),128n,'Original engine translations retain priority');
a.equal(allocations,3);existing=0n;
for(const hash of [0,0x7427c7d0,0x89b2a065])a.equal(callback(hash),0n,'Unknown metadata is not fabricated');
a.equal(allocations,3);
"""
        result = subprocess.run(['node', '-e', script, str(helper)], capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
