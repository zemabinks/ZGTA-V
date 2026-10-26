"""Real preference validation and failure text using only an in-memory store."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT.parent/'app'

class ConnectionPreferences(unittest.TestCase):
    def test_only_valid_relay_and_room_are_remembered_without_tokens_or_connections(self):
        source='''import Foundation
final class Store: EngineLanPreferenceStore {
 var values: [String: Any]=[:]
 func string(forKey key: String) -> String? { values[key] as? String }
 func set(_ value: Any?, forKey key: String) { values[key]=value }
}
let store=Store()
precondition(EngineLanPreferences.load(from:store).room=="LOS-SANTOS")
let relay="ws://100.70.8.9:47540/engine-lan"
precondition(EngineLanPreferences.save(relay:relay,room:"PRIVATE-TEST",to:store))
let restored=EngineLanPreferences.load(from:store)
precondition(restored.relay==relay && restored.room=="PRIVATE-TEST")
precondition(Set(store.values.keys)==Set([EngineLanPreferences.relayKey,EngineLanPreferences.roomKey]))
for room in ["", "   ", "bad\\nroom", String(repeating:"a",count:65)] {
 precondition(!EngineLanPreferences.save(relay:relay,room:room,to:store))
}
precondition(!EngineLanPreferences.save(relay:"ws://8.8.8.8:47540/engine-lan",room:"PUBLIC",to:store))
precondition(EngineLanPreferences.load(from:store).room=="PRIVATE-TEST")
store.values[EngineLanPreferences.relayKey]="https://example.com/"
store.values[EngineLanPreferences.roomKey]="bad\\nroom"
let fallback=EngineLanPreferences.load(from:store)
precondition(fallback.relay==EngineLanPreferences.defaultRelay && fallback.room=="LOS-SANTOS")
precondition(EngineLanPreferences.summary(relay:relay,room:"PRIVATE-TEST").contains("PRIVATE-TEST"))
let isolated=Store()
let lan="ws://192.168.1.7:47540/engine-lan"
let remote="ws://100.70.8.9:47540/engine-lan"
precondition(EngineLanPreferences.selected(from:isolated) == .lan)
precondition(EngineLanPreferences.save(mode:.lan,relay:lan,room:"LOCAL",to:isolated))
precondition(EngineLanPreferences.save(mode:.remote,relay:remote,room:"REMOTE",to:isolated))
precondition(EngineLanPreferences.selected(from:isolated) == .remote)
precondition(EngineLanPreferences.load(mode:.lan,from:isolated).relay==lan)
precondition(EngineLanPreferences.load(mode:.lan,from:isolated).room=="LOCAL")
precondition(EngineLanPreferences.load(mode:.remote,from:isolated).room=="REMOTE")
precondition(!EngineLanPreferences.save(mode:.remote,relay:lan,room:"BAD",to:isolated))
precondition(!EngineLanPreferences.save(mode:.lan,relay:remote,room:"BAD",to:isolated))
precondition(EngineLanPreferences.load(mode:.lan,from:isolated).room=="LOCAL")
let migrated=Store()
migrated.values[EngineLanPreferences.relayKey]=remote
migrated.values[EngineLanPreferences.roomKey]="OLD-REMOTE"
precondition(EngineLanPreferences.selected(from:migrated) == .remote)
precondition(EngineLanPreferences.load(mode:.remote,from:migrated).relay==remote)
precondition(EngineLanPreferences.load(mode:.remote,from:migrated).room=="OLD-REMOTE")
precondition(EngineLanPreferences.load(mode:.lan,from:migrated).relay==EngineLanPreferences.defaultRelay)
precondition(MultiplayerConnection.remote.endpoint(from:" 100.70.8.9 ")==remote)
precondition(MultiplayerConnection.lan.endpoint(from:"192.168.1.7")==lan)
for bad in ["8.8.8.8", "100.63.0.1", "100.128.0.1", "100.070.8.9", "foo.ts.net", "ws://100.70.8.9:0/engine-lan"] {
 precondition(MultiplayerConnection.remote.endpoint(from:bad)==nil)
}
precondition(EngineLanPreferences.load(mode:.remote,from:Store()).relay.isEmpty)
precondition(VehicleSpawnFeedback.failure(status:-4,model:"sultan").contains("control"))
precondition(!VehicleSpawnFeedback.failure(status:-4,model:"sultan").contains("name"))
precondition(VehicleSpawnFeedback.failure(status:-2,model:"sultan").contains("time"))
precondition(VehicleSpawnFeedback.failure(status:-5,model:"bad").contains("creation"))
precondition(VehicleSpawnFeedback.failure(status:-8,model:"bad").contains("model name"))
precondition(!VehicleSpawnFeedback.failure(status:-8,model:"bad").contains("Another"))
precondition(VehicleSpawnFeedback.failure(status:-9,model:"sultan").contains("cleanup"))
print("CONNECTION_PREFERENCES_VALIDATED_MEMORY_ONLY_AND_SPAWN_ERRORS_DISTINCT_PASS")
'''
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'main.swift').write_text(source)
            result=subprocess.run(['/usr/bin/swiftc','-warnings-as-errors','-module-cache-path',str(p/'cache'),str(ROOT/'EngineLanPreferences.swift'),str(ROOT/'EngineLanSession.swift'),str(APP/'App/VehicleSpawnFeedback.swift'),str(p/'main.swift'),'-o',str(p/'test')],capture_output=True,text=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(p/'test')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('MEMORY_ONLY',result.stdout)

if __name__=='__main__':unittest.main()
