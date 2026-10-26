"""Native-source parity, strict guards and immutable real game data checks."""
import hashlib
import ctypes
import subprocess
import tempfile
from pathlib import Path
from public_test_inputs import game_file
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import data_overlay as overlay

MIRROR = game_file('data')


class DataOverlay(unittest.TestCase):
    def test_native_feed_fixture_and_scope(self):
        source = b'<other sizeX="0.19890859375"/>\r\n<GameStream>\r\n\t<position posX="0.0" sizeX="0.19890859375" />\r\n\t<posloading sizeX="0.19890859375" />\r\n</GameStream>\r\n'
        want = b'<other sizeX="0.19890859375"/>\r\n<GameStream>\r\n\t<position posX="0.0" sizeX="0.15000000000" />\r\n\t<posloading sizeX="0.15000000000" />\r\n</GameStream>\r\n'
        result = overlay.patch('common/data/ui/frontend.xml', source)
        self.assertEqual(result, want)
        self.assertEqual(len(result), len(source))
        self.assertIsNone(overlay.patch('common/data/ui/frontend.xml', result))

    def test_native_browser_feed_bytes_match(self):
        with tempfile.TemporaryDirectory(prefix='zgta-feed-parity-') as folder:
            p=Path(folder);(p/'feed.c').write_text('#include "NativeFeedWidth.h"\nint patch(unsigned char *p,size_t n){return pg_feed_width(p,n); }\nvoid read_patch(unsigned char *d,int64_t c,uint64_t o,const unsigned char *p,size_t n){pg_feed_width_read(d,c,o,p,n); }\n')
            subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-dynamiclib','-I',str(ROOT.parent/'app/Source'),str(p/'feed.c'),'-o',str(p/'feed.dylib')],check=True,capture_output=True)
            native=ctypes.CDLL(str(p/'feed.dylib')).patch
            native.argtypes=[ctypes.c_void_p,ctypes.c_size_t];native.restype=ctypes.c_int
            source=(MIRROR/'common/data/ui/frontend.xml').read_bytes()
            malformed=[b'',b'<GameStream>sizeX="0.19890859375"',b'prefix\0<GameStream>sizeX="0.19890859375"</GameStream>']
            for data in [source,overlay.feed_width(source),*malformed]:
                buf=ctypes.create_string_buffer(data);changed=native(buf,len(data))
                want=overlay.feed_width(data) if b'\0' not in data else None
                self.assertEqual(bool(changed),want is not None)
                self.assertEqual(buf.raw[:len(data)],want if want is not None else data)
            patched=overlay.feed_width(source);read=ctypes.CDLL(str(p/'feed.dylib')).read_patch
            read.argtypes=[ctypes.c_void_p,ctypes.c_int64,ctypes.c_uint64,ctypes.c_void_p,ctypes.c_size_t]
            full=ctypes.create_string_buffer(patched)
            for start in [*range(0,len(source),137),len(source),2**64-1]:
                output=ctypes.create_string_buffer(b'!'*137)
                read(output,137,start,full,len(patched))
                actual=patched[start:start+137]
                self.assertEqual(output.raw[:137],actual+b'!'*(137-len(actual)))
            output=ctypes.create_string_buffer(b'!'*137);read(output,-1,0,full,len(patched));self.assertEqual(output.raw[:137],b'!'*137)

    def test_native_autosave_fixture_keeps_exact_lines(self):
        source = b'<a>\r\n\t<Item> <MenuPref>PREF_STARTUP_FLOW</MenuPref> </Item>\r\n\t<Item> <MenuPref>PREF_AUTOSAVE</MenuPref> </Item>\r\n</a>\r\n'
        want = b'<a>\r\n\t<Item> <MenuPref>PREF_AUTOSAVE</MenuPref> </Item>\r\n\t<Item> <MenuPref>PREF_STARTUP_FLOW</MenuPref> </Item>\r\n</a>\r\n'
        self.assertEqual(overlay.patch('COMMON/DATA/UI/PAUSEMENU.XML', source), want)
        self.assertEqual(len(want), len(source))
        self.assertIsNone(overlay.patch('common/data/ui/pausemenu.xml', want))
        self.assertIsNone(overlay.patch('common/data/ui/pausemenu.xml', source.replace(b'</Item>\r\n\t<Item>', b'</Item>\r\n<!-- gap -->\r\n\t<Item>')))

    def test_unexpected_paths_shape_and_encoding_are_unchanged(self):
        for rel in ('frontend.xml', '../common/data/ui/frontend.xml', 'common/data/ui/notfrontend.xml', '/data/common/data/ui/frontend.xml'):
            self.assertIsNone(overlay.patch(rel, b'<GameStream>sizeX="0.19890859375"</GameStream>'))
        for source in (b'', b'<GameStream>sizeX="0.19890859375"', b'\xff<GameStream>sizeX="0.19890859375"</GameStream>'):
            self.assertIsNone(overlay.patch('common/data/ui/frontend.xml', source))
        for source in (b'', b'<MenuPref>PREF_STARTUP_FLOW</MenuPref>\n<MenuPref>PREF_AUTOSAVE</MenuPref>\n', b'\n<MenuPref>PREF_STARTUP_FLOW</MenuPref>\n<MenuPref>PREF_AUTOSAVE</MenuPref>'):
            self.assertIsNone(overlay.patch('common/data/ui/pausemenu.xml', source))

    def test_pinned_mirror_inputs_and_lengths_preserved(self):
        rows = [
            ('frontend.xml', 'a44b162013209d6b149f66039f47fedfcd32d1831b6b1dbfe34e57b5247755eb'),
            ('pausemenu.XML', '7910ad2b1e3310ee29da770ce2e99a0d325b4dd9b9be54b9750e3b6035472320'),
        ]
        for name, pin in rows:
            path = MIRROR / 'common/data/ui' / name
            before = path.read_bytes()
            self.assertEqual(hashlib.sha256(before).hexdigest(), pin)
            result = overlay.patch('common/data/ui/' + name, before)
            self.assertIsNotNone(result)
            self.assertEqual(len(result), len(before))
            self.assertNotEqual(result, before)
            self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
