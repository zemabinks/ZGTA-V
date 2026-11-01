"""Run the real C codec/mixer and JavaScript wire implementation together."""
import asyncio
import ctypes as C
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
VIP=0x0a4d0000

class VoiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='zgta-voice108-')
        cls.path=Path(cls.temp.name)
        cls.peers=[]
        for n in range(2):
            lib=cls.path/f'voice{n}.dylib'
            subprocess.run(['/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror','-O2','-dynamiclib',str(ROOT/'ZemaVoice.c'),'-o',str(lib)],check=True,capture_output=True)
            p=C.CDLL(str(lib));p.ZemaVoiceSetPosition.argtypes=[C.c_float]*3+[C.c_bool]
            p.ZemaVoiceConfigure.argtypes=[C.c_uint32]
            for name in ['ZemaVoiceSetMicEnabled','ZemaVoiceSetSpeakerEnabled','ZemaVoiceConnected']:
                getattr(p,name).argtypes=[C.c_bool]
            p.ZemaVoiceIsMicEnabled.restype=C.c_bool
            p.ZemaVoiceSubmitMicAudio.argtypes=[C.POINTER(C.c_float),C.c_uint32]
            p.ZemaVoiceDeliver.argtypes=[C.c_void_p,C.c_size_t];p.ZemaVoiceDeliver.restype=C.c_bool
            p.ZemaVoiceTakeOutgoing.argtypes=[C.c_void_p,C.c_size_t]
            p.ZemaVoiceMixAudio.argtypes=[C.POINTER(C.c_float),C.POINTER(C.c_float),C.c_uint32]
            cls.peers.append(p)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):
        for i,p in enumerate(self.peers):
            p.ZemaVoiceConnected(False);p.ZemaVoiceConfigure(VIP+i+1);p.ZemaVoiceConnected(True);p.ZemaVoiceSetSpeakerEnabled(True);p.ZemaVoiceSetPosition(100,100,20,True)
    def frames(self,count=2,value=.3,pos=(100,100,20)):
        p=self.peers[0];p.ZemaVoiceSetPosition(*pos,True);p.ZemaVoiceSetMicEnabled(True)
        samples=(C.c_float*(960*count))(*([value]*(960*count)));p.ZemaVoiceSubmitMicAudio(samples,len(samples))
        out=[];b=C.create_string_buffer(356)
        while p.ZemaVoiceTakeOutgoing(b,356):out.append(b.raw)
        return out
    def deliver(self,frames):
        for f in frames:self.assertTrue(self.peers[1].ZemaVoiceDeliver(f,len(f)))
    def mix(self,base=0):
        a=(C.c_float*960)(*([base]*960));b=(C.c_float*960)(*([base]*960));self.peers[1].ZemaVoiceMixAudio(a,b,960);self.assertEqual(list(a),list(b));return sum(a)/960
    def test_microphone_opt_in_and_no_position_means_no_transmission(self):
        p=self.peers[0];b=C.create_string_buffer(356);samples=(C.c_float*960)(*([.4]*960))
        p.ZemaVoiceSubmitMicAudio(samples,960);self.assertEqual(p.ZemaVoiceTakeOutgoing(b,356),0)
        p.ZemaVoiceSetMicEnabled(True);p.ZemaVoiceSetPosition(0,0,0,False);p.ZemaVoiceSubmitMicAudio(samples,960);self.assertEqual(p.ZemaVoiceTakeOutgoing(b,356),0)
    def test_native_speech_full_volume_nearby_without_receiver_microphone(self):
        self.deliver(self.frames());self.assertFalse(self.peers[1].ZemaVoiceIsMicEnabled());self.assertAlmostEqual(self.mix(),.3,delta=.015)
    def test_attenuation_and_cutoff_recomputed_when_listener_moves(self):
        self.deliver(self.frames());self.peers[1].ZemaVoiceSetPosition(120.5,100,20,True);self.assertAlmostEqual(self.mix(),.058,delta=.005)
        self.peers[1].ZemaVoiceSetPosition(135,100,20,True);self.assertEqual(self.mix(.2),C.c_float(.2).value)
    def test_large_world_coordinates_do_not_saturate(self):
        self.peers[1].ZemaVoiceSetPosition(4501,7000,30,True);self.deliver(self.frames(pos=(4500,7000,30)));self.assertGreater(self.mix(),.28)
    def test_speaker_mute_flushes_speech_and_preserves_game_audio(self):
        self.deliver(self.frames());p=self.peers[1];p.ZemaVoiceSetSpeakerEnabled(False);self.assertAlmostEqual(self.mix(.2),.2,delta=1e-6);p.ZemaVoiceSetSpeakerEnabled(True);self.assertEqual(self.mix(),0)
    def test_disconnect_forgets_audio_and_requires_new_mic_opt_in(self):
        frames=self.frames();self.deliver(frames)
        for p in self.peers:p.ZemaVoiceConnected(False);p.ZemaVoiceConnected(True);p.ZemaVoiceSetPosition(100,100,20,True)
        self.assertFalse(self.peers[0].ZemaVoiceIsMicEnabled());self.assertEqual(self.mix(),0)
    def test_capped_transmit_queue_and_muting_discards_pending_audio(self):
        self.assertEqual(len(self.frames(100)),5)
        self.frames();self.peers[0].ZemaVoiceSetMicEnabled(False);b=C.create_string_buffer(356);self.assertEqual(self.peers[0].ZemaVoiceTakeOutgoing(b,356),0)
    def test_short_jitter_preroll_duplicate_and_out_of_order_packets(self):
        a,b=self.frames();self.deliver([a,a]);self.assertEqual(self.mix(),0);self.deliver([b,a]);self.assertGreater(self.mix(),.28)
    def test_malformed_nonfinite_and_spoofed_receiver_do_not_play(self):
        a,b=self.frames();p=self.peers[1]
        for change in ['nan','destination','source','marker','short']:
            data=bytearray(a)
            if change=='nan':struct.pack_into('>f',data,24,float('nan'))
            elif change=='destination':struct.pack_into('>I',data,10,VIP+7)
            elif change=='source':struct.pack_into('>I',data,4,VIP+33)
            elif change=='marker':data[16]=0
            else:data.pop()
            self.assertTrue(p.ZemaVoiceDeliver(bytes(data),len(data)))
        self.assertEqual(self.mix(),0);self.assertFalse(p.ZemaVoiceDeliver(b'not a datagram',14))
    def test_stale_outbound_packets_are_dropped(self):
        p=self.peers[0];p.ZemaVoiceSetMicEnabled(True);samples=(C.c_float*960)(*([.3]*960));p.ZemaVoiceSubmitMicAudio(samples,960);time.sleep(.13);b=C.create_string_buffer(356);self.assertEqual(p.ZemaVoiceTakeOutgoing(b,356),0)
    def test_javascript_and_native_wire_audio_interoperate(self):
        frames=self.frames();input_file=self.path/'native.json';input_file.write_text(json.dumps([list(f) for f in frames]))
        script='''const V=require(process.argv[1]),fs=require('fs'),frames=JSON.parse(fs.readFileSync(process.argv[2]));const m=new V.Mixer();for(const b of frames)m.receive(Uint8Array.from(b),[100,100,20],0x0a4d0002,1000);let l=new Float32Array(960),r=new Float32Array(960);m.render(l,r,[100,100,20],48000,1000);if(l.reduce((a,b)=>a+b)/960<.28)throw Error('Native to browser');const bytes=new Uint8Array(356),audio=new Uint8Array(320).fill(V.encode(.3));console.log(JSON.stringify([Array.from(V.frame(bytes,0x0a4d0001,100,[100,100,20],audio)),Array.from(V.frame(bytes.slice(),0x0a4d0001,101,[100,100,20],audio))]));'''
        generated=json.loads(subprocess.check_output(['node','-e',script,str(ROOT/'voice-core.js'),str(input_file)],text=True))
        self.peers[1].ZemaVoiceSetSpeakerEnabled(False);self.peers[1].ZemaVoiceSetSpeakerEnabled(True);self.deliver([bytes(b) for b in generated]);self.assertAlmostEqual(self.mix(),.3,delta=.015)
        self.assertEqual(frames[0][36:],bytes(generated[0][36:]))

class BrowserVoiceTests(unittest.TestCase):
    def test_real_audio_worklet_and_bounded_shared_queues(self):
        r=subprocess.run(['node',str(ROOT/'tests/voice108.js')],capture_output=True,text=True,timeout=20);self.assertEqual(r.returncode,0,r.stderr);self.assertIn('VOICE108_WORKLET_PASS',r.stdout)

if __name__=='__main__':unittest.main()
