"""Exercise the actual renderer catch and page UI with a failed GPU device."""
import json
from pathlib import Path
from public_test_inputs import game_file
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import graphics_status as g
import launch_channels
import serve_browser

MIRROR = game_file('')


class GraphicsStatus(unittest.TestCase):
    def test_renderer_failure_reports_once_preserves_drain_and_never_reports_ready(self):
        original = (MIRROR / 'b/8b0b5899ed/wgpu_worker.js').read_bytes()
        scoped = launch_channels.worker('wgpu_worker.js', original)
        fixed = g.worker('wgpu_worker.js', scoped).decode()
        body = fixed[fixed.index('async function start(msg) {'):fixed.index('\nif (!isNode)', fixed.index('async function start(msg) {'))]
        fixture = r'''
const a=require('node:assert/strict'),vm=require('node:vm');
const body=JSON.parse(process.argv[1]);
async function test(isNode,throwSend=false){
 let reports=[],closed=0,stores=[],ready=[],drained=false;
 const sentinel=new Error('stop fixture after entering the unchanged drain');
 const ctx={isNode,logLine:()=>{},w32:n=>n,refreshViews:()=>{},initDevice:async()=>{throw Error('fixture GPU unavailable');},
  ZemaLaunchChannels:{name:n=>n+'-launch-identity'},BroadcastChannel:class {constructor(n){a.equal(n,'game-progress-launch-identity');}postMessage(m){reports.push(m);if(throwSend)throw Error('channel closed');}close(){closed++;}},
  Atomics:{store:(...v)=>stores.push(v),load:()=>{drained=true;throw sentinel;},notify:()=>{}},i32:[],post:m=>ready.push(m)};
 vm.createContext(ctx);vm.runInContext(body,ctx);
 await a.rejects(ctx.start({ring:40,size:100,canvas:{},memory:{}}),e=>e===sentinel);
 a.equal(drained,true);a.equal(stores[0][1],42);a.equal(stores[0][2],2);a.equal(ready.length,0);
 a.equal(reports.length,isNode?0:1);a.equal(closed,isNode?0:1);
 if(!isNode)a.deepEqual(JSON.parse(JSON.stringify(reports[0])),{gpuInitFailed:true});
}
(async()=>{await test(false);await test(true);await test(false,true);console.log('PASS failed device, node path, broken channel and unchanged drain');})().catch(e=>{console.error(e);process.exitCode=1;});
'''
        self.node(fixture, body)
        with self.assertRaises(ValueError):
            g.worker('wgpu_worker.js', fixed.encode())
        with self.assertRaises(ValueError):
            g.worker('wgpu_worker.js', original)
        self.assertEqual(original, (MIRROR / 'b/8b0b5899ed/wgpu_worker.js').read_bytes())

    def test_actual_device_loss_callback_reports_empty_details_and_preserves_expected_destroy(self):
        original = (MIRROR / 'b/8b0b5899ed/wgpu_worker.js').read_bytes()
        fixed = g.worker('wgpu_worker.js', launch_channels.worker('wgpu_worker.js', original)).decode()
        start = fixed.index('device.lost.then((info) => {')
        callback = fixed[start:fixed.index('\n\t});', start) + len('\n\t});')]
        fixture = r'''
const a=require('node:assert/strict'),vm=require('node:vm'),code=JSON.parse(process.argv[1]);
function test({isNode=false,reason='unknown',message='',broken=null}={}){
 let handler,reports=[],logs=[],closed=0,opened=0;
 const ctx={device:{lost:{then:fn=>handler=fn}},isNode,logLine:text=>logs.push(text),
  ZemaLaunchChannels:{name:n=>n+'-own-launch'},
  BroadcastChannel:class {constructor(name){a.equal(name,'game-progress-own-launch');if(broken==='constructor')throw Error('channel unavailable');opened++;}postMessage(value){reports.push(value);if(broken==='send')throw Error('channel send failed');}close(){closed++;}}};
 vm.runInNewContext(code,ctx);a.doesNotThrow(()=>handler({reason,message}));
 a.deepEqual(logs,['device lost: '+reason+' '+message],'Keep exact diagnostics in the existing local worker log');
 const expected=!isNode&&reason!=='destroyed';
 a.equal(opened,expected&&broken!=='constructor'?1:0);a.equal(closed,opened,'Every opened loss channel closes, including failed send');
 a.equal(reports.length,expected&&broken!=='constructor'?1:0);
 if(reports.length)a.deepEqual(JSON.parse(JSON.stringify(reports[0])),{gpuLost:true},'Status is independent of empty/private diagnostic text');
}
for(const message of ['', 'private driver detail', '\nsecond line detail'])test({message});
test({reason:'destroyed'});test({reason:'destroyed',message:'expected shutdown'});test({isNode:true,message:''});
test({broken:'constructor'});test({broken:'send'});
console.log('PASS actual loss callback: empty/nonempty/newline diagnostics, expected destruction, Node, broken channel and scoped cleanup');
'''
        self.node(fixture, callback)
        with self.assertRaises(ValueError):
            g.worker('wgpu_worker.js', launch_channels.worker('wgpu_worker.js', original).replace(g.LOSS_ANCHOR.encode(), b'changed-loss-handler'))

    def test_failure_ui_is_accessible_bounded_and_not_cleared_by_later_progress(self):
        fixture = r'''
const a=require('node:assert/strict'),vm=require('node:vm');
const code=JSON.parse(process.argv[1]),nodes=new Map();
function element(tag){return {tag,style:{},children:[],attrs:{},setAttribute(k,v){this.attrs[k]=v;},append(...items){this.children.push(...items);for(const item of items)if(item.id)nodes.set(item.id,item);}};}
const ctx={window:{ZemaGameReady:true},document:{getElementById:id=>nodes.get(id),createElement:element,body:element('body')}};
vm.createContext(ctx);vm.runInContext('function handle(m){'+code+';window.continued=true;}',ctx);
ctx.handle({gpuInitFailed:true});const card=nodes.get('zema-graphics-failure');
a.equal(card.attrs.role,'alert');a.equal(card.children[0].textContent,'Graphics could not start');a.equal(ctx.window.ZemaGameReady,false);
a.equal(card.children[2].href,'/');a.match(card.children[1].textContent,/saved games are kept/);
ctx.handle({world:true});a.equal(ctx.window.continued,undefined);a.equal(ctx.document.body.children.length,1);
ctx.handle({gpuLost:'<script>driver-private-details</script>'});a.equal(ctx.document.body.children.length,1);a.ok(!JSON.stringify(card).includes('driver-private-details'));
for(const value of ['',true,'device lost','\nsecond line']){
 nodes.clear();ctx.document.body.children=[];ctx.window.ZemaGameReady=true;delete ctx.window.continued;
 ctx.handle({gpuLost:value});a.equal(nodes.get('zema-graphics-failure').children[0].textContent,'Graphics device disconnected');a.equal(ctx.window.ZemaGameReady,false);
 ctx.handle({world:true});a.equal(ctx.window.continued,undefined);a.equal(ctx.document.body.children.length,1);
}
nodes.clear();ctx.window.ZemaGameReady=true;delete ctx.window.continued;ctx.handle({gpuLost:false});a.equal(nodes.size,0);a.equal(ctx.window.ZemaGameReady,true);a.equal(ctx.window.continued,true);
console.log('PASS accessible manual return, no reload, no raw driver details, later progress suppressed');
'''
        self.node(fixture, g.PAGE_HANDLER)
        for mode in ('story', 'sandbox', 'lan'):
            page = serve_browser.index((MIRROR / 'index.html').read_bytes(), mode).decode()
            self.assertIn(g.MARK, page)
        with self.assertRaises(ValueError):
            g.page(g.PAGE_HANDLER)
        self.assertEqual(g.worker('game.wasm', b'unchanged'), b'unchanged')

    def node(self, code, data):
        result = subprocess.run(['node', '-e', code, json.dumps(data)], text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
