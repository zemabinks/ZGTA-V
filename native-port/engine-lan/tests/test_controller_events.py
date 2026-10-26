"""Actual event handlers, shared input memory and pad publisher; only DOM/RAF are doubled."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ControllerEvents(unittest.TestCase):
    def check(self, scenario):
        result = subprocess.run(['node', str(ROOT / 'tests/controller_events.cjs'), str(ROOT), scenario],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('BROWSER_CONTROLLER_EVENTS_PASS ' + scenario, result.stdout)

    def test_release_discards_accumulated_mouse_and_wheel_input(self): self.check('release')
    def test_hidden_page_without_blur_neutralizes_and_refocuses(self): self.check('hidden')
    def test_tools_suspension_releases_held_keys_and_controller(self): self.check('suspended')
    def test_pointer_lock_loss_releases_held_input(self): self.check('pointer-loss')
    def test_unload_cancels_polling_and_refuses_more_input(self): self.check('unload')
    def test_pointer_lock_rejection_and_old_api_do_not_escape_handler(self): self.check('pointer-rejection')
    def test_ordinary_keyboard_aliases_analog_axes_and_shared_memory_growth(self): self.check('ordinary-input')
