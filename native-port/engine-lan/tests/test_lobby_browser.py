"""Compile the actual Swift browser policy and explicit-favorites storage."""
import subprocess, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
class BrowserPolicy(unittest.TestCase):
 def test_live_policy_and_favorites(self):
  with tempfile.TemporaryDirectory(prefix='zgta-browser-') as tmp:
   folder=Path(tmp)
   script='import Foundation\n'
   for name in ['LobbyInvitation.swift','LobbyHealthProbe.swift','LobbyFavorites.swift','LobbyBrowserModel.swift']:
    script+='\n'+(ROOT/name).read_text()
   script+='''
let suite="zgta-browser-fixture-"+UUID().uuidString
let store=UserDefaults(suiteName:suite)!
defer {store.removePersistentDomain(forName:suite)}
let relay="ws://192.168.1.11:47540/engine-lan"
let stale=LobbyRecord(relay:relay,room:"STALE")
let live=LobbyRecord(relay:relay,room:"LIVE")
let remote=LobbyRecord(relay:"ws://100.70.1.9:47540/engine-lan",room:"REMOTE")
let offline=LobbyRecord(relay:"ws://192.168.1.12:47540/engine-lan",room:"OFFLINE")
let history=Data("preserve history".utf8)
store.set(history,forKey:"zgta.saved-lobbies.v1")
precondition(LobbyFavorites.load(store:store).isEmpty)
precondition(LobbyFavorites.set(offline,saved:true,store:store))
precondition(LobbyFavorites.set(offline,saved:true,store:store))
precondition(LobbyFavorites.load(store:store).count==1)
precondition(store.data(forKey:"zgta.saved-lobbies.v1")==history)
let now=Date(timeIntervalSince1970:1000)
func health(_ names:[String], catalog:Bool=true, restricted:Bool=true,incompatible:Bool=false)->LobbyHealth {
 var obj:[String:Any] = ["service":"zgta-engine-lan","protocol":"zema-engine-lan/1","build":incompatible ? "other":"8b0b5899ed","instance":String(repeating:"a",count:32),"peers":1,"rooms":names.count]
 if catalog {obj["catalog_version"]=1;obj["room_policy"]=restricted ? "hosted":"open";obj["lobbies"]=names.map{["room":$0,"players":1,"slots":1,"capacity":8] as [String:Any]}}
 return LobbyHealth.decode(try! JSONSerialization.data(withJSONObject:obj),latency:3)!
}
var model=LobbyBrowserModel()
precondition(model.begin(records:[stale,stale,offline,remote]).count==3)
func online(_ date:Date=now)->[String] {model.visible(favorites:[],onlyFavorites:false,mode:.lan,at:date).map{$0.record.room}}
precondition(online().isEmpty) // Unchecked seeds never leak into live results.
model.receive(relay:relay,health:health(["LIVE"]),at:now)
model.receive(relay:offline.relay,health:nil,at:now)
model.receive(relay:remote.relay,health:health(["REMOTE"]),at:now)
precondition(online()==["LIVE"])
let favoriteRows=model.visible(favorites:LobbyFavorites.load(store:store),onlyFavorites:true,mode:.lan,at:now)
precondition(favoriteRows.count==1 && favoriteRows[0].state(at:now)=="Offline" && !favoriteRows[0].canJoin(at:now))
precondition(model.visible(favorites:[stale],onlyFavorites:true,mode:.lan,at:now)[0].state(at:now)=="Room unavailable")
precondition(!model.visible(favorites:[stale],onlyFavorites:true,mode:.lan,at:now)[0].canJoin(at:now))
precondition(model.visible(favorites:[],onlyFavorites:false,mode:.remote,at:now).map{$0.record.room}==["REMOTE"])
precondition(online(now.addingTimeInterval(31)).isEmpty)
_ = model.begin(records:[stale,offline,remote])
precondition(online()==["LIVE"]) // Fresh advertisements survive an in-flight refresh.
model.receive(relay:relay,health:nil,at:now.addingTimeInterval(1));precondition(online().isEmpty)
model.receive(relay:relay,health:health(["LIVE"],incompatible:true),at:now);precondition(online().isEmpty)
model.receive(relay:relay,health:health([],catalog:false),at:now);precondition(online().isEmpty)
model.receive(relay:relay,health:health([],restricted:false),at:now)
let manual=model.visible(favorites:[stale],onlyFavorites:true,mode:.lan,at:now)[0]
precondition(manual.canJoin(at:now) && manual.state(at:now)=="Host online · room not advertised")
precondition(online().isEmpty)
precondition(LobbyFavorites.set(live,saved:true,store:store))
precondition(LobbyFavorites.set(live,saved:false,store:store))
precondition(!LobbyFavorites.contains(live,store:store) && LobbyFavorites.contains(offline,store:store))
for i in 0..<31 {precondition(LobbyFavorites.set(LobbyRecord(relay:relay,room:"F-\\(i)"),saved:true,store:store))}
precondition(!LobbyFavorites.set(live,saved:true,store:store))
precondition(LobbyFavorites.load(store:store).count==32)
precondition(store.data(forKey:"zgta.saved-lobbies.v1")==history)
store.set(Data(repeating:0,count:32769),forKey:"zgta.favorite-lobbies.v1");precondition(LobbyFavorites.load(store:store).isEmpty)
store.set(Data("broken".utf8),forKey:"zgta.favorite-lobbies.v1");precondition(LobbyFavorites.load(store:store).isEmpty)
print("PASS live advertisement, stale/offline/incompatible filtering, mode, refresh, explicit favorites and preservation")
'''
   main=folder/'main.swift';main.write_text(script)
   binary=folder/'browser'
   run=subprocess.run(['/usr/bin/swiftc','-warnings-as-errors','-module-cache-path',str(folder/'cache'),str(ROOT/'EngineLanSession.swift'),str(ROOT/'EngineLanPreferences.swift'),str(main),'-o',str(binary)],capture_output=True,text=True,timeout=90)
   self.assertEqual(run.returncode,0,run.stderr)
   result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=10)
   self.assertEqual(result.returncode,0,result.stderr)
   self.assertIn('PASS',result.stdout)
if __name__=='__main__':unittest.main()
