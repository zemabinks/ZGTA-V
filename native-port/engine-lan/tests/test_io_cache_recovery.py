from pathlib import Path
import json,subprocess,tempfile,unittest
from public_test_inputs import game_file
import io_cache_recovery,stage_browser,launch_channels


class IOCacheRecovery(unittest.TestCase):
    def test_actual_worker_exact_bytes_and_real_failures(self):
        raw=game_file('b/8b0b5899ed/io_worker.js').read_bytes()
        proposed=stage_browser.patch('io_worker.js',raw)
        self.assertIn(io_cache_recovery.MARK.encode(),proposed)
        with self.assertRaises(ValueError):io_cache_recovery.apply(proposed.decode())
        self.assertNotIn(b'removeEntry(',proposed)
        scoped=launch_channels.worker('io_worker.js',proposed)
        self.assertNotRegex(scoped.decode(),launch_channels.LITERAL)
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'fixture.json'
            target.write_text(json.dumps({'original':raw.decode(),'proposed':scoped.decode()}))
            run=subprocess.run(['node',str(Path(__file__).with_name('io_cache_recovery.cjs')),str(target)],capture_output=True,text=True,timeout=20)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            print(run.stdout.strip())


if __name__=='__main__':unittest.main()
