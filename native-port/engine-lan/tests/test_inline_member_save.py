from pathlib import Path
import subprocess
import unittest

class InlineMemberSave(unittest.TestCase):
    def test_original_serializer_runs_before_durable_commit_and_failures_stay_failed(self):
        p=subprocess.run(['node',str(Path(__file__).with_name('inline_member_save.cjs'))],capture_output=True,text=True,timeout=20)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertIn('INLINE_MEMBER_SAVE_ORIGINAL_SERIALIZER',p.stdout)

    def test_prior_stage_still_stalls_without_the_inline_candidate(self):
        root=Path(__file__).resolve().parents[1]
        old=root.parent/'app/Build/EngineLAN-FeaturesBrowser-20261018-v22/online.js'
        p=subprocess.run(['node',str(Path(__file__).with_name('inline_member_save.cjs')),str(old)],capture_output=True,text=True,timeout=20)
        self.assertNotEqual(p.returncode,0)

if __name__=='__main__':unittest.main()
