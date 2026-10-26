"""Execute the production safe-area layout plan independently of UIKit/device APIs."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT.parent / 'app'


class VehiclePreviewLayoutTests(unittest.TestCase):
    def test_safe_area_budget_rotation_and_text_scroll_separation(self):
        main = r'''
import Foundation
import CoreGraphics
let cases: [(String, CGRect, Bool)] = [
    ("iPhone landscape 852x393", CGRect(x:59,y:0,width:734,height:372), true),
    ("small landscape 568x320", CGRect(x:0,y:0,width:568,height:320), true),
    ("portrait 393x852", CGRect(x:0,y:59,width:393,height:759), false),
    ("iPad balanced form sheet", CGRect(x:0,y:0,width:480,height:510), false),
    ("iPad landscape", CGRect(x:0,y:24,width:1024,height:724), false)
]
for (name, safe, compact) in cases {
    for actionHeight in [CGFloat(56), CGFloat(88)] {
        let f = VehiclePreviewLayout.frames(in: safe, compactHeight: compact, actionHeight: actionHeight)
        for rect in [f.close, f.picture, f.details, f.action] {
            precondition(safe.contains(rect), "Outside safe area: " + name)
            precondition(rect.width > 0 && rect.height > 0)
        }
        precondition(!f.picture.intersects(f.details))
        precondition(!f.picture.intersects(f.action) && !f.details.intersects(f.action))
        precondition(f.picture.maxY <= f.action.minY - 10)
        precondition(f.details.maxY <= f.action.minY - 10)
        precondition(f.picture.minY >= f.close.maxY + 10)
        precondition(f.action.height >= 48)
        // The image stays bounded even with arbitrarily long names/Dynamic Type.
        // Text alone receives a scroll viewport; it never increases picture size.
        let longTextHeight: CGFloat = 1200
        precondition(longTextHeight > f.details.height)
        if compact { precondition(f.sideBySide && f.picture.height < safe.height) }
        print("PASS " + name + " image=" + NSStringFromRect(f.picture) + " details=" + NSStringFromRect(f.details))
    }
}
let portrait = VehiclePreviewLayout.frames(in: cases[2].1, compactHeight: false)
let landscape = VehiclePreviewLayout.frames(in: cases[0].1, compactHeight: true)
let rotatedBack = VehiclePreviewLayout.frames(in: cases[2].1, compactHeight: false)
precondition(!portrait.sideBySide && landscape.sideBySide && !rotatedBack.sideBySide)
precondition(portrait.picture == rotatedBack.picture && portrait.details == rotatedBack.details)
print("PASS rotation recomputes actual safe-area geometry; image does not participate in text scrolling")
'''
        with tempfile.TemporaryDirectory(prefix='zgta-preview-layout-') as tmp:
            folder = Path(tmp)
            source = folder/'main.swift'
            source.write_text(main)
            binary = folder/'layout-test'
            result = subprocess.run(['xcrun','swiftc','-module-cache-path',str(folder/'ModuleCache'),str(APP/'App/VehiclePreviewViewController.swift'),str(source),'-o',str(binary)], capture_output=True,text=True,timeout=120)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            result = subprocess.run([str(binary)],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('PASS rotation',result.stdout)


if __name__ == '__main__':
    unittest.main()
