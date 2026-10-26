"""Actual pinned launcher transforms and controller adapter; no GTA launch."""
import hashlib
from pathlib import Path
from public_test_inputs import game_file
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import serve_browser as server
from stage_browser import PINS
MIRROR=game_file('')

class Launcher(unittest.TestCase):
    def test_performance_script_is_loaded_before_launcher(self):
        html=(server.ROOT/'launcher.html').read_text()
        self.assertLess(html.index('/zema-lab/browser-performance.js'),html.index('/zema-lab/launcher.js'))

    def test_settings_and_controller(self):
        result=subprocess.run(['node',str(server.ROOT/'tests/launcher_fixture.cjs')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    def test_runtime_gate(self):
        result=subprocess.run(['node',str(server.ROOT/'tests/runtime_gate.cjs'),str(server.ROOT/'runtime.js')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    def test_real_pinned_source_transform(self):
        data=(MIRROR/'index.html').read_bytes()
        for mode in ('story','sandbox','lan'):
            page=server.index(data,mode).decode()
            self.assertIn('href="/zema-lab/zplay-gta-green.svg"',page)
            self.assertIn('href="/zema-lab/zplay-gta-green-32.png"',page)
            self.assertIn('href="/zema-lab/zplay-gta-green-180.png"',page)
            self.assertLess(page.index('await window.ZemaRuntimeReady'),page.index('canvas.transferControlToOffscreen()'))
            self.assertNotIn('await dropOldCache();',page)
            self.assertNotIn('Low-memory device (',page)
            self.assertIn('Lower-detail graphics mode.',page)
            self.assertIn('setInterval(() => {}, 1);',page)
            self.assertIn('browser-performance.js',page)
            self.assertNotIn("'worker error: ' + e.message",page)
            self.assertIn("back.textContent='Back to launcher'",page)
            self.assertIn('const q = window.ZemaRuntime.query;',page)
            self.assertIn('ZemaController.install(',page)
            self.assertEqual('window.ZemaLabLaunch(worker,{' in page,mode=='lan')
            if mode=='lan':self.assertIn("1: 'Loading multiplayer'",page)
            if mode!='lan':self.assertIn("const BASE = '/offline/"+mode+"/b/8b0b5899ed';",page)
    def test_exact_brand_icon_routes_and_launcher(self):
        from pathlib import Path
        html=(server.ROOT/'launcher.html').read_text()
        self.assertIn('href="/zema-lab/zplay-gta-green.svg"',html)
        content=server.Content.__new__(server.Content)
        names=('favicon.ico','zplay-gta-green.svg','zplay-gta-green-32.png','zplay-gta-green-180.png')
        content.assets={name:(server.ROOT/name).read_bytes() for name in names}
        for path,mime in (('/favicon.ico','image/x-icon'),('/zema-lab/zplay-gta-green.svg','image/svg+xml'),('/zema-lab/zplay-gta-green-32.png','image/png'),('/zema-lab/zplay-gta-green-180.png','image/png')):
            stream,actual=content._select(path)
            self.assertEqual(actual,mime)
            self.assertEqual(stream.read(),content.assets[Path(path).name])
    def test_original_workers_separate_modes_and_cache(self):
        for mode in ('story','sandbox'):
            for name,sha in PINS.items():
                data=(MIRROR/server.BUILD.lstrip('/')/name).read_bytes();self.assertEqual(hashlib.sha256(data).hexdigest(),sha)
                patched=server.offline_worker(name,data,mode).decode()
                self.assertNotIn('zema-engine-lan-userdata-v1',patched)
                if name!='game.js':self.assertIn("indexedDB.open('zema-browser-"+mode+"-userdata-v1', 1)",patched)
                if name=='io_worker.js':self.assertIn("getDirectoryHandle('zema-browser-"+mode+"-gamedata-v1'",patched)
                if name=='loader.js':self.assertIn("self.location.origin + '/offline/"+mode+"/data/'",patched)
        with self.assertRaises(ValueError):server.offline_worker('loader.js',b'changed','story')

if __name__=='__main__':unittest.main()
