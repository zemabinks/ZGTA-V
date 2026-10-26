from pathlib import Path
import sys,unittest,copy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import resource_reclaim as r
class ResourceReclaim(unittest.TestCase):
 def test_wrappers_restore_before_return_and_release_before_original_free(self):
  a=r.wrapper(3038);f=r.wrapper(3039)
  self.assertLess(a.index('pg_original_resource_allocate('),a.index('pg_resource_reclaim_reuse('))
  self.assertLess(a.index('pg_resource_reclaim_reuse('),a.index('return result'))
  self.assertLess(f.index('pg_resource_reclaim_free('),f.index('pg_original_resource_free('))
  self.assertIn('WASM_RT_TRAP_UNREACHABLE',a)
 def test_known_function_signatures_and_unrelated_browser_untouched(self):
  rows={x['index']:x for x in r.PINS['hooks']}
  self.assertEqual(rows[3038]['params'],['i64','i64','i64','i32'])
  self.assertEqual(rows[3039]['results'],[])
  self.assertEqual(rows[3046]['results'],['i64'])
  self.assertFalse(hasattr(r,'stage_browser'))
