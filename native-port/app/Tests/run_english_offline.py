"""Run source/resource tests, never an iOS application or a network service.

Requires existing macOS Swift command-line tools. Installs/downloads nothing.
All compiled Foundation test harnesses and module caches are temporary.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / 'Tests'
APP = ROOT / 'App'
CATALOG = ROOT / 'Resources/Localizations.json'

def run(args):
    subprocess.run([str(arg) for arg in args], check=True, timeout=120, cwd=ROOT)

def main():
    for test in ['english_catalog.py', 'online_codegen.py', 'lan_manifest.py',
                 'intel_shader_cache.py', 'shader_build.py', 'intel_dependency_stage.py',
                 'intel_build_route.py', 'intel_ui_assets.py', 'native_feature_parity.py',
                 'engine_lan_compat.py']:
        run([sys.executable, '-B', TESTS / test])
    with tempfile.TemporaryDirectory(prefix='mugoat-english-offline-') as scratch:
        temp = Path(scratch)
        cache = temp / 'module-cache'
        files = ['CheatMenu', 'HomeView', 'Localization', 'LocalizationUI', 'OnlinePreferences',
                 'OnlineSettingsViewController', 'NativePortViewController', 'SettingsViewController',
                 'TouchControlsView', 'ModManagerViewController', 'ModRuntime', 'RPFArchive']
        run(['/usr/bin/swiftc', '-frontend', '-parse', *[APP / (name + '.swift') for name in files]])
        harnesses = [
            ('english_preferences', ['Localization', 'OnlinePreferences']),
            ('control_appearance', ['ControlAppearance']),
            ('english_mod_errors', ['Localization', 'RPFArchive']),
            ('save_store', ['Localization', 'SaveStore']),
        ]
        for name, sources in harnesses:
            executable = temp / name
            run(['/usr/bin/swiftc', '-module-cache-path', cache,
                 *[APP / (source + '.swift') for source in sources],
                 TESTS / (name + '.swift'), '-o', executable])
            run([executable, CATALOG])
    print('PASS: English offline suite; no app build, install, preferences write or network request.')

if __name__ == '__main__':
    main()
