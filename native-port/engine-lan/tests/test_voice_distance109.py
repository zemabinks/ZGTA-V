"""Measure the actual native/browser PCM mixers, including movement continuity."""
import ctypes as C
import json
import math
import subprocess
import unittest
import test_voice108 as baseline

class DistanceTests(unittest.TestCase):
    setUpClass=classmethod(baseline.VoiceTests.setUpClass.__func__)
    tearDownClass=classmethod(baseline.VoiceTests.tearDownClass.__func__)
    setUp=baseline.VoiceTests.setUp
    frames=baseline.VoiceTests.frames
    deliver=baseline.VoiceTests.deliver
    mix=baseline.VoiceTests.mix

    def pcm(self):
        left=(C.c_float*960)();right=(C.c_float*960)()
        self.peers[1].ZemaVoiceMixAudio(left,right,960)
        self.assertEqual(list(left),list(right))
        return list(left)

    def test_native_browser_levels_and_smooth_movement_agree(self):
        browser=json.loads(subprocess.check_output(['node',str(baseline.ROOT/'tests/voice_distance109.js')],text=True))
        levels=[]
        for distance in browser['distances']:
            self.setUp();self.peers[1].ZemaVoiceSetPosition(100+distance,100,20,True)
            self.deliver(self.frames());levels.append(self.mix())
        full=levels[0]
        # Audible requirements: full close conversation, clearer 10/20 m
        # separation, very quiet near the edge, exact silence at the limit.
        db=[20*math.log10(x/full) if x else None for x in levels]
        self.assertAlmostEqual(db[1],0,delta=.01)
        self.assertTrue(-5.2<db[3]<-4.5,db)
        self.assertTrue(-14.1<db[4]<-13.3,db)
        self.assertLess(db[5],-32)
        self.assertEqual(levels[-1],0)
        self.assertTrue(all(a>b for a,b in zip(levels[1:],levels[2:])))
        for rate,actual in browser['levels'].items():
            for native,js in zip(levels,actual):self.assertAlmostEqual(native,js,delta=1e-6,msg=rate)

        self.setUp();self.deliver(self.frames());near=self.pcm()[-1]
        self.peers[1].ZemaVoiceSetPosition(120,100,20,True);trace=[]
        for _ in range(15):self.deliver(self.frames(1));trace.extend(self.pcm())
        self.assertLess(abs(trace[0]-near),.0002,'position update must not make a volume step')
        self.assertTrue(all(a>=b for a,b in zip(trace,trace[1:])))
        self.assertAlmostEqual(trace[-1],levels[4],delta=.001)
        self.assertLess(max(abs(a-b) for a,b in zip(trace,browser['trace'])),.00002)
        self.peers[1].ZemaVoiceSetPosition(135,100,20,True)
        self.assertEqual(self.mix(),0,'out-of-range speech must stop immediately')
        self.peers[1].ZemaVoiceSetPosition(120,100,20,True);self.deliver(self.frames())
        self.assertAlmostEqual(self.mix(),browser['returned'],delta=1e-6)
        self.assertEqual(browser['far'],0)

if __name__=='__main__':unittest.main()
