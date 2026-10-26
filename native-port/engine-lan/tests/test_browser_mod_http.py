"""Read-only real-stage integration with tiny synthetic DLC and disposable HTTP.

These tests never start the game, use a device, or mutate the mirror/stage. They
skip when the existing reviewed local mirror and v8 stage are unavailable.
"""
import gzip
import hashlib
import http.client
import json
import re
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import browser_mods
import serve_browser as server
from test_browser_mods import pack


class BrowserModHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mirror = Path.home() / 'Library/Application Support/ZRemote Controller/Games/playgta5-offline/mirror/playgta5.com'
        cls.stage = server.ROOT.parent / 'app/Build/EngineLAN-FeaturesBrowser-20261017-v10'
        if not (cls.mirror / 'index.html').is_file() or not (cls.stage / 'browser-stage.json').is_file():
            raise unittest.SkipTest('Existing reviewed mirror/v8 stage unavailable; no download or stage generation attempted.')
        cls.preserved = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in (
            cls.mirror / 'index.html', cls.mirror / 'data/manifest.json',
            cls.mirror / 'data/common/data/dlcList.xml', cls.stage / 'browser-stage.json')}
        cls.content = server.Content(cls.mirror, cls.stage)
        cls.listener = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.listener.content = cls.content
        cls.listener.daemon_threads = True
        cls.thread = threading.Thread(target=cls.listener.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.listener.shutdown(); cls.listener.server_close(); cls.thread.join()
        for path, digest in cls.preserved.items():
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise AssertionError('Read-only source changed: ' + str(path))

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='zema-mod-http-')
        self.content.mods = browser_mods.BrowserMods(Path(self.temporary.name).resolve() / 'imports')
        self.content.sessions.clear()
        self.content.session_leases.clear();self.content.session_releases.clear();self.content.session_clock=server.time.monotonic

    def tearDown(self):
        self.content.sessions.clear()
        self.temporary.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.listener.server_port, timeout=15)
        try:
            connection.request(method, path, body, headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def api(self, path, body, *, binary=False, expected=200):
        headers = {'X-Zema-Lab': '1', 'Content-Type': 'application/octet-stream' if binary else 'application/json',
                   'Origin': 'http://127.0.0.1:' + str(self.listener.server_port)}
        result = self.request('POST', '/zema-lab/' + path, body if binary else json.dumps(body), headers)
        self.assertEqual(result[0], expected, result[2][:500])
        self.assertEqual(result[1]['Cross-Origin-Embedder-Policy'], 'require-corp')
        return json.loads(result[2])

    def import_pack(self):
        result = self.api('mods/import?filename=fixture.rpf', pack(), binary=True)
        self.assertEqual(len(result['packs']), 1)
        return result['packs'][0]['id']

    def get(self, path):
        result = self.request('GET', path)
        self.assertEqual(result[0], 200, result[2][:500])
        return result[2]

    def test_vehicle_menu_uses_immutable_loaded_models_and_shared_assets(self):
        pack_id = self.import_pack()
        launch = self.api('launch', {'mode': 'story'})['prefix']
        page = self.get(launch + '/play/story').decode()
        match = re.search(r'window.ZemaLoadedVehiclePacks=(.*?);</script>', page)
        self.assertEqual(json.loads(match[1]), [{'vehicleModels': ['testvehicle']}])
        self.api('mods/toggle', {'id': pack_id, 'enabled': False})
        again = self.get(launch + '/play/story').decode()
        self.assertEqual(json.loads(re.search(r'window.ZemaLoadedVehiclePacks=(.*?);</script>', again)[1]), [{'vehicleModels': ['testvehicle']}])
        new_page = self.get(self.api('launch', {'mode': 'story'})['prefix'] + '/play/story').decode()
        self.assertIn('window.ZemaLoadedVehiclePacks=[];', new_page)
        lan_page = self.get('/play/lan').decode()
        self.assertIn('window.ZemaLoadedVehiclePacks=[];', lan_page)
        for name in ['vehicle-catalog.js', 'vehicle-ui.js']:
            self.assertEqual(self.get('/zema-lab/' + name), (server.ROOT/name).read_bytes())
            self.assertIn('/zema-lab/' + name, page)

    def test_exact_map_archive_full_ranges_and_snapshot_manifest_agree(self):
        import modern_map_assets
        patch=json.loads(modern_map_assets.PATCH.read_text())
        self.assertTrue(self.content.map_icons['active'])
        for prefix in ('','/offline/story','/offline/sandbox',self.api('launch',{'mode':'story'})['prefix']):
            manifest=json.loads(self.get(prefix+'/data/manifest.json'))
            row=next(r for r in manifest['files'] if r[0]==modern_map_assets.PATH)
            archive=self.get(prefix+'/data/'+modern_map_assets.PATH)
            self.assertEqual(row[1],len(archive));self.assertEqual(hashlib.sha256(archive).hexdigest(),patch['result_sha256'])
            status,headers,tail=self.request('GET',prefix+'/data/'+modern_map_assets.PATH,headers={'Range':f'bytes={len(archive)-18}-{len(archive)-1}'})
            self.assertEqual(status,206);self.assertEqual(tail,archive[-18:]);self.assertEqual(headers['Content-Range'],f'bytes {len(archive)-18}-{len(archive)-1}/{len(archive)}')
        original=server.Content(self.mirror,self.stage,modern_icons=False)
        self.assertFalse(original.map_icons['active']);self.assertNotIn('/data/manifest.json',original.ui_overlays)

    def test_renderer_english_and_ui_parity_across_modes(self):
        gpu=(self.stage/'wgpu_worker.js').read_bytes()
        self.assertIn(b'normalized16 skin targets',gpu)
        self.assertIn(b'ZEMA_MINIMAP_PARITY_V1',gpu)
        import launch_channels
        import graphics_status
        gpu=graphics_status.worker('wgpu_worker.js',launch_channels.worker('wgpu_worker.js',server.fps_transport('wgpu_worker.js',gpu)))
        self.assertEqual(self.get(server.BUILD+'wgpu_worker.js'),gpu)
        for mode in ('story','sandbox'):
            prefix=self.api('launch', {'mode':mode})['prefix']
            self.assertEqual(self.get(prefix+server.BUILD+'wgpu_worker.js'),gpu)
            page=self.get(prefix+'/play/'+mode).decode()
            self.assertIn('window.ZemaBenchmarkEngine="'+self.content.engine_hashes[mode]+'";',page)
            self.assertIn('fpsChannel:window.ZemaFPSChannel',page)
            loader=self.get(prefix+server.BUILD+'loader.js')
            self.assertIn(b"gq.set('fpsChannel', m.fpsChannel)",loader)
            game=self.get(prefix+server.BUILD+'game.js')
            self.assertNotIn(b'navigator.language',game)
            self.assertIn(b'stringToUTF8("en-US",$0,$1)',game)
            self.assertEqual(self.get(prefix+server.BUILD+'memory_filename.js'),(self.stage/'memory_filename.js').read_bytes())
            self.assertEqual(self.get(prefix+server.BUILD+'text_fallback.js'),(self.stage/'text_fallback.js').read_bytes())
        for prefix in ('','/offline/story','/offline/sandbox'):
            for rel in ('common/data/ui/frontend.xml','common/data/ui/pausemenu.XML'):
                raw=(self.mirror/'data'/rel).read_bytes()
                actual=self.get(prefix+'/data/'+rel)
                self.assertEqual(len(actual),len(raw))
                self.assertNotEqual(actual,raw)

    def test_character_save_diagnostics_survive_unrelated_log_noise(self):
        self.content.save_signals.clear()
        message='[online] LAN save: file write refused; bytes=128'
        self.content.record_runtime([message]+['unrelated '+str(i) for i in range(1100)])
        data=json.loads(self.get('/zema-lab/diagnostics'))
        self.assertNotIn(message,data['lines'])
        self.assertIn({'text':message,'count':1},data['save_signals'])
        self.content.record_runtime(['[online] LAN save: state '+str(i) for i in range(100)])
        self.assertEqual(len(self.content.save_signals),64)

    def test_asset_lookup_failures_survive_noise_without_retaining_arbitrary_text(self):
        messages=['[text-missing] hash 0x68431ca7','[blip-missing] sprite 673 table 426','[blip-fallback] sprite 445 -> 86 table 426']
        self.content.record_runtime(messages+['unrelated '+str(i) for i in range(1100)])
        data=json.loads(self.get('/zema-lab/diagnostics'))
        self.assertEqual([x['text'] for x in data['asset_signals']],messages)
        self.content.record_runtime(['[text-missing] private arbitrary text'])
        self.assertEqual(len(self.content.asset_signals),3)
        self.content.record_runtime(['[text-missing] hash 0x%08x'%i for i in range(300)])
        self.assertEqual(len(self.content.asset_signals),256)

    def test_bounded_runtime_diagnostics_are_local_text_only(self):
        self.content.runtime_lines.clear()
        self.content.runtime_signals.clear()
        self.assertEqual(self.api('runtime', {'lines':['[loading] native-active 1']}), {'accepted':1})
        self.assertEqual(json.loads(self.get('/zema-lab/diagnostics'))['lines'], ['[loading] native-active 1'])
        self.assertEqual(self.content.runtime_lines.maxlen,1024)
        for lines in (['x']*25,['x'*513],[123],'not a list'):
            self.api('runtime', {'lines':lines}, expected=400)
        self.assertEqual(self.request('POST','/zema-lab/runtime',json.dumps({'lines':['forged']}),{'Content-Type':'application/json'})[0],403)

    def test_repeated_audio_dump_does_not_erase_distinct_gpu_signal(self):
        self.content.runtime_lines.clear();self.content.runtime_signals.clear()
        gpu='[wgpu] validation error: rejected world draw'
        self.content.record_runtime([gpu]+['[Audio_NorthAudio] Network Script 0: none']*2000)
        result=json.loads(self.get('/zema-lab/diagnostics'))
        self.assertNotIn(gpu,result['lines'])
        self.assertEqual(result['signals'],[{'text':gpu,'count':1},{'text':'[Audio_NorthAudio] Network Script 0: none','count':2000}])
        self.content.record_runtime(['distinct '+str(i) for i in range(300)])
        self.assertEqual(len(json.loads(self.get('/zema-lab/diagnostics'))['signals']),256)

    def test_import_toggle_remove_and_persisted_catalog(self):
        self.assertEqual(json.loads(self.get('/zema-lab/mods'))['packs'], [])
        identifier = self.import_pack()
        self.assertFalse(self.api('mods/toggle', {'id': identifier, 'enabled': False})['packs'][0]['enabled'])
        self.assertTrue(self.api('mods/toggle', {'id': identifier, 'enabled': True})['packs'][0]['enabled'])
        root = self.content.mods.root
        self.assertEqual(browser_mods.BrowserMods(root).catalog(), json.loads(self.get('/zema-lab/mods')))
        self.assertEqual(self.api('mods/remove', {'id': identifier})['packs'], [])
        self.assertEqual(browser_mods.BrowserMods(root).catalog()['packs'], [])

    def test_snapshot_routes_ranges_batch_and_immutable_after_removal(self):
        identifier = self.import_pack()
        launch = self.api('launch', {'mode': 'story'})
        prefix = launch['prefix']
        self.assertRegex(prefix, r'^/session/[a-f0-9]{32}$')
        self.assertEqual(launch['mods'][0]['name'], 'testcar')
        manifest_bytes = self.get(prefix + '/data/manifest.json')
        manifest = json.loads(manifest_bytes)
        original = json.loads((self.mirror / 'data/manifest.json').read_bytes())
        self.assertEqual([r[0] for r in manifest['files'][:len(original['files'])]], [r[0] for r in original['files']])
        archive_path = '/data/x64/dlcPacks/testcar/dlc.rpf'
        self.assertEqual(self.get(prefix + archive_path), pack())
        ranged = self.request('GET', prefix + archive_path, headers={'Range': 'bytes=8-23'})
        self.assertEqual((ranged[0], ranged[2]), (206, pack()[8:24]))
        xml = self.get(prefix + '/data/common/data/dlcList.xml')
        self.assertIn(b'platform:\\dlcPacks\\testcar\\', xml)
        runs = [['x64/dlcPacks/testcar/dlc.rpf', 8, 23], ['common/data/dlcList.xml', 0, len(xml)-1]]
        status, headers, data = self.request('POST', prefix + '/data/batch?gz=1', json.dumps(runs), {'Content-Type': 'application/json'})
        self.assertEqual(status, 200)
        self.assertEqual(gzip.decompress(data), pack()[8:24] + xml)
        self.assertEqual(headers['X-Run-Lengths'], '16,' + str(len(xml)))
        io_worker = self.get(prefix + server.BUILD + 'io_worker.js').decode()
        fingerprint = manifest['version'][len('zema-mods-'):]
        self.assertIn("getDirectoryHandle('zema-browser-story-gamedata-" + fingerprint + "'", io_worker)
        loader = self.get(prefix + server.BUILD + 'loader.js').decode()
        self.assertIn("self.location.origin + '" + prefix + "/data/'", loader)
        self.assertIn("indexedDB.open('zema-browser-story-userdata-v1'", loader)
        page = self.get(prefix + '/play/story').decode()
        self.assertIn("const BASE = '" + prefix + "/b/8b0b5899ed'", page)
        self.api('mods/toggle', {'id': identifier, 'enabled': False})
        unmodified = self.api('launch', {'mode': 'story'})['prefix']
        # With no user mods, optional first-party UI compatibility still applies.
        self.assertEqual(self.get(unmodified + '/data/manifest.json'), self.get('/data/manifest.json'))
        plain_worker = self.get(unmodified + server.BUILD + 'io_worker.js').decode()
        self.assertIn("getDirectoryHandle('zema-browser-story-gamedata-v1'", plain_worker)
        self.assertNotIn(fingerprint, plain_worker)
        self.assertEqual(self.get(prefix + archive_path), pack())
        self.api('mods/remove', {'id': identifier})
        self.assertEqual(self.get(prefix + '/data/manifest.json'), manifest_bytes)
        self.assertEqual(self.get(prefix + archive_path), pack())
        self.assertEqual(self.api('launch', {'mode': 'sandbox'})['mods'], [])

    def test_lan_unchanged_offline_save_namespaces_and_snapshot_cap_release(self):
        before = self.get('/data/common/data/gameconfig.xml')
        self.import_pack()
        self.assertEqual(self.api('launch', {'mode': 'lan'}), {'prefix': '', 'mode': 'lan', 'mods': []})
        self.assertEqual(self.get('/data/common/data/gameconfig.xml'), before)
        self.assertEqual(self.get(server.BUILD + 'engine-lan-module.js'), (self.stage / 'engine-lan-module.js').read_bytes())
        self.assertEqual(len(self.content.sessions), 0)
        launches = [self.api('launch', {'mode': 'story' if n % 2 else 'sandbox'}) for n in range(4)]
        self.assertEqual(len({x['prefix'] for x in launches}), 4)
        self.assertIn('Four launch snapshots', self.api('launch', {'mode': 'story'}, expected=400)['error'])
        for launch in launches:
            worker = self.get(launch['prefix'] + server.BUILD + 'loader.js').decode()
            self.assertIn("indexedDB.open('zema-browser-" + launch['mode'] + "-userdata-v1'", worker)
        first = launches[0]
        page=self.get(first['prefix']+'/play/'+first['mode']).decode()
        lease=re.search(r'window.ZemaLaunchLease="([a-f0-9]{32})"',page)[1]
        self.assertTrue(self.api('session/release', {'id': first['prefix'].rsplit('/', 1)[1],'lease':lease})['released'])
        self.assertEqual(self.request('GET', first['prefix'] + '/data/manifest.json')[0], 200)
        self.assertEqual(self.api('launch', {'mode': 'story'})['mode'], 'story')
        self.assertEqual(self.request('GET', first['prefix'] + '/data/manifest.json')[0], 404)

    def test_refresh_survives_both_release_orderings_and_stale_page_cannot_release_new_page(self):
        now=[100.0];self.content.session_clock=lambda:now[0]
        for mode in ['story','sandbox']:
            launch=self.api('launch',{'mode':mode});prefix=launch['prefix'];identifier=prefix.rsplit('/',1)[1]
            def page_lease():return re.search(r'window.ZemaLaunchLease="([a-f0-9]{32})"',self.get(prefix+'/play/'+mode).decode())[1]
            first=page_lease()
            self.assertTrue(self.api('session/release',{'id':identifier,'lease':first})['released'])
            # Reload's index can arrive after the previous pagehide POST.
            now[0]+=1;second=page_lease();self.assertNotEqual(first,second)
            self.assertEqual(self.request('HEAD',prefix+'/play/'+mode)[0],200)
            self.assertEqual(self.content.session_leases[identifier],second,'HEAD must not replace the active page lease')
            # Or the old pagehide POST can arrive after the new index GET.
            self.assertFalse(self.api('session/release',{'id':identifier,'lease':first})['released'])
            now[0]+=60
            self.assertIn(b'gq.set(\'fpsChannel\'',self.get(prefix+server.BUILD+'loader.js'))
            self.assertEqual(self.request('GET',prefix+server.BUILD+'wgpu_worker.js')[0],200)
            self.assertTrue(self.api('session/release',{'id':identifier,'lease':second})['released'])
            now[0]+=46
            self.assertEqual(self.request('GET',prefix+'/data/manifest.json')[0],404)
            self.assertNotIn(identifier,self.content.session_leases)
            self.assertNotIn(identifier,self.content.session_releases)

    def test_reject_cross_origin_missing_header_and_unsafe_api_requests(self):
        url = '/zema-lab/mods/import?filename=fixture.rpf'
        for headers in ({'Content-Type': 'application/octet-stream'},
                        {'X-Zema-Lab': '1', 'Content-Type': 'application/octet-stream', 'Origin': 'https://evil.example'},
                        {'X-Zema-Lab': '1', 'Content-Type': 'application/octet-stream', 'Host': 'evil.example'}):
            self.assertEqual(self.request('POST', url, pack(), headers)[0], 403)
        self.api('mods/import?filename=fixture.rpf', {}, expected=400)
        self.api('mods/import?filename=bad.rpf', b'invalid archive', binary=True, expected=400)
        self.api('mods/import?filename=a.rpf&filename=b.rpf', pack(), binary=True, expected=400)
        self.api('mods/toggle', {'id': 'unknown', 'enabled': 'yes'}, expected=400)
        self.api('mods/remove', {'id': '../outside'}, expected=400)
        self.api('launch', {'mode': 'story', 'path': '/outside'}, expected=400)
        self.api('launch', {'mode': 'unknown'}, expected=400)
        self.api('session/release', {'id': '../outside'}, expected=400)
        self.assertEqual(json.loads(self.get('/zema-lab/mods'))['packs'], [])

    def test_snapshot_cannot_escape_paths_or_access_other_mode(self):
        self.import_pack()
        prefix = self.api('launch', {'mode': 'story'})['prefix']
        for tail in ('/data/%2e%2e/index.html', '/data/x64/%2e%2e/index.html', '/play/sandbox', '/data/x64%5csecret', '/data/%00secret'):
            self.assertIn(self.request('GET', prefix + tail)[0], (400, 404))
        bad = [['../index.html', 0, 9]]
        self.assertEqual(self.request('POST', prefix + '/data/batch', json.dumps(bad))[0], 400)
        self.assertEqual(self.request('GET', '/session/' + '0'*32 + '/data/manifest.json')[0], 404)


if __name__ == '__main__':
    unittest.main()
