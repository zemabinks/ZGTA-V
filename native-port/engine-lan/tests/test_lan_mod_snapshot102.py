"""Actual LAN snapshot routes with read-only owner inputs and an inert HTTP transport.

No game, relay, HTTP listener, browser or production save is opened. Physical
cross-client mod visibility remains an owner test, not a result of these fixtures.
"""
import gzip,hashlib,io,json,os,re,sys,tempfile,threading,time,unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import browser_mods,modern_map_assets,serve_browser as server
from test_browser_mods import pack

def read(c,path):
 stream,_=c.select(path)
 with stream:return stream.read()
def request(c,method,path,body=b'',headers=None):
 response=SimpleNamespace(status=None,headers={},body=io.BytesIO())
 h=SimpleNamespace(path=path,headers=headers or {},rfile=io.BytesIO(body),wfile=response.body,server=SimpleNamespace(content=c),allowed=lambda:True)
 h.send_response=lambda status:setattr(response,'status',status)
 h.send_header=lambda key,value:response.headers.__setitem__(key,value)
 h.end_headers=lambda:None
 h.send_error=lambda status:(_ for _ in ()).throw(AssertionError('HTTP '+str(status)))
 if method=='GET':server.Handler.serve(h,False)
 elif method=='HEAD':server.Handler.serve(h,True)
 else:server.Handler.do_POST(h)
 return response


class LanModSnapshot102(unittest.TestCase):
    def test_real_stage_immutable_lan_snapshot_and_worker_graph(self):
        mirror_value=os.environ.get('ZGTA_GAME_MIRROR');stage_value=os.environ.get('ZGTA_TEST_BROWSER_STAGE')
        if not mirror_value or not stage_value:
            self.skipTest('Set ZGTA_GAME_MIRROR and ZGTA_TEST_BROWSER_STAGE to existing reviewed inputs; nothing downloaded.')
        mirror=Path(mirror_value).resolve();stage=Path(stage_value).resolve()
        metadata=json.loads((stage/'engine-lan-module.json').read_text());record=json.loads((stage/'browser-stage.json').read_text())
        expected=dict(record['staged_hashes']);expected['game.engine-lan.wasm']=metadata['patched_sha256']
        for name,want in expected.items():self.assertEqual(hashlib.sha256((stage/name).read_bytes()).hexdigest(),want,name)
        preserved={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [mirror/'index.html',mirror/'data/manifest.json',mirror/'data/common/data/dlcList.xml',stage/'browser-stage.json',stage/'game.engine-lan.wasm']}
        checks=[]
        def ok(name,condition):self.assertTrue(condition,name);checks.append(name)
        with tempfile.TemporaryDirectory(prefix='zgta-lan-mod-proof102-',dir='/private/tmp') as temp, ExitStack() as cleanup:
         folder=Path(temp);c=server.Content(mirror,stage,browser_mods.BrowserMods(folder/'imports'));cleanup.callback(c.lobby_host.close);cleanup.callback(c.lobby_directory.close);identifier=c.mods.import_bytes('testcar.rpf',pack())['packs'][0]['id']
         launch=c.launch('lan');prefix=launch['prefix'];ok('LAN launch gets immutable session route',bool(re.fullmatch('/session/[a-f0-9]{32}',prefix)))
         page=read(c,prefix+'/play/lan').decode();lease=c.session_leases[prefix.split('/')[-1]]
         ok('LAN page BASE uses session prefix',"const BASE = '"+prefix+"/b/8b0b5899ed';" in page)
         ok('Loaded vehicle catalog comes from this snapshot','"vehicleModels": ["testvehicle"]' in page)
         ok('LAN page keeps admitted typed startup','window.ZemaLabLaunch(worker,{' in page and 'await window.ZemaRuntimeReady' in page)
         manifest=read(c,prefix+'/data/manifest.json');m=json.loads(manifest);base=json.loads(c.ui_overlays['/data/manifest.json'])
         ok('Base manifest indices including modern symbols retained',[r[0] for r in m['files'][:len(base['files'])]]==[r[0] for r in base['files']])
         ok('Modern map archive byte overlay composes',read(c,prefix+'/data/'+modern_map_assets.PATH)==c.ui_overlays['/data/'+modern_map_assets.PATH])
         ok('Host-capacity gameconfig overlay composes',read(c,prefix+'/data/common/data/gameconfig.xml')==c.config)
         rpf=read(c,prefix+'/data/x64/dlcPacks/testcar/dlc.rpf');ok('Snapshot serves original imported RPF bytes',rpf==pack())
         ok('DLC path registered',b'platform:\\dlcPacks\\testcar\\' in read(c,prefix+'/data/common/data/dlcList.xml'))
         response=request(c,'GET',prefix+'/data/x64/dlcPacks/testcar/dlc.rpf',headers={'Range':'bytes=8-23'})
         ok('Actual Handler range logic stays inside snapshot',response.status==206 and response.body.getvalue()==rpf[8:24])
         xml=read(c,prefix+'/data/common/data/dlcList.xml');runs=[['x64/dlcPacks/testcar/dlc.rpf',8,23],['common/data/dlcList.xml',0,len(xml)-1]];raw=json.dumps(runs).encode()
         response=request(c,'POST',prefix+'/data/batch?gz=1',raw,{'Content-Length':str(len(raw))})
         ok('Actual Handler gzip batch composes snapshot assets',response.status==200 and gzip.decompress(response.body.getvalue())==rpf[8:24]+xml)
         response=request(c,'HEAD',prefix+'/play/lan');ok('HEAD does not replace current page lease',c.session_leases[prefix.split('/')[-1]]==lease and response.body.getvalue()==b'')

         loader=read(c,prefix+server.BUILD+'loader.js').decode();io=read(c,prefix+server.BUILD+'io_worker.js').decode()
         ok('Loader IO base is snapshot-local',"self.location.origin + '"+prefix+"/data/'" in loader)
         ok('LAN IO cache is immutable fingerprint namespace',"getDirectoryHandle('zema-engine-lan-gamedata-"+m['version'].removeprefix('zema-mods-')+"'" in io)
         ok('LAN save DB remains unchanged',"indexedDB.open('zema-engine-lan-userdata-v1', 1)" in io)
         ok('LAN typed admission/imports remain intact','ZemaEngineLan.requireGameReady();' in loader and 'Explicit admitted engine-LAN context required' in loader and 'ZemaEngineLan.instantiate(' in loader)
         ok('Launch channels remain per-document','ZemaLaunchChannels.url(B + \'/io_worker.js\')' in loader and 'ZemaLaunchChannels.name(' in io)
         for helper in re.findall(r"new URL\('([^']+\.js)',self.location.href\)",loader):
          ok('Staged relative import routable: '+helper,bool(read(c,prefix+server.BUILD+helper)))
         for name in ['network-worker.js','profile-worker.js','profile-rpc.js','online.js','engine-lan-module.js']:
          ok('Session helper bytes unchanged: '+name,read(c,prefix+server.BUILD+name)==(stage/name).read_bytes())
         ok('LAN engine bytes unchanged',hashlib.sha256(read(c,prefix+server.BUILD+'game.engine-lan.wasm')).hexdigest()==metadata['patched_sha256'])
         # No activation change or removal can alter existing launch bytes/catalog.
         c.mods.set_enabled(identifier,False);next_launch=c.launch('lan');ok('Later disabled pack absent from new snapshot',next_launch['mods']==[])
         ok('Running snapshot remains after disable',read(c,prefix+'/data/manifest.json')==manifest and read(c,prefix+'/data/x64/dlcPacks/testcar/dlc.rpf')==rpf)
         c.mods.remove(identifier);ok('Running snapshot remains after source removal',read(c,prefix+'/data/manifest.json')==manifest and read(c,prefix+'/data/x64/dlcPacks/testcar/dlc.rpf')==rpf)
         ok('Current page release lease retained',c.release(prefix.split('/')[-1],lease)['released'])
         # Real supplied Supra uses the same registration and read graph.
         supra_path=os.environ.get('ZGTA_TEST_SUPRA_RPF')
         supra=Path(supra_path) if supra_path else None
         if supra is not None and supra.is_file():
          original_hash=hashlib.sha256(supra.read_bytes()).hexdigest();c.mods.import_bytes('dlc.rpf',supra.read_bytes());s=c.launch('lan');p=s['prefix']
          ok('Supplied Supra snapshot catalog registers casup',s['mods'][0]['vehicleModels']==['casup'])
          ok('Supplied Supra snapshot serves matching archive',hashlib.sha256(read(c,p+'/data/x64/dlcPacks/casup/dlc.rpf')).hexdigest()==original_hash)
          ok('Supplied Supra original preserved',hashlib.sha256(supra.read_bytes()).hexdigest()==original_hash)
         read(c,prefix+'/play/lan')  # Reclaim this page so no recently released slot can be recycled.
         c.launch('lan')
         try:c.launch('lan');raise AssertionError('Fifth simultaneous snapshot unexpectedly accepted')
         except ValueError as error:ok('LAN retains four-snapshot bound','Four launch snapshots' in str(error))
         c.release(prefix.split('/')[-1],c.session_leases[prefix.split('/')[-1]])
         now=c.session_clock();c.session_clock=lambda:now+46;c.launch('lan');ok('Released LAN snapshot expires and frees capacity',len(c.sessions)==4)
        for p,want in preserved.items():ok('Read-only input preserved: '+Path(p).name,hashlib.sha256(Path(p).read_bytes()).hexdigest()==want)
        print(json.dumps({'LAN_snapshot_checks':len(checks),'temporary_services_started':False,'gameplay':'NOT_TESTED','paired_mod_visibility':'NOT_TESTED'},sort_keys=True))

if __name__=='__main__':unittest.main()
