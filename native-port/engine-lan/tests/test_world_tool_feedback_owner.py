"""Execute production completion watchers; only scheduling and C status reads are doubled."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT.parent / 'app'


def method(source, prefix):
    start = source.index(prefix)
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        if source[end] == '{': depth += 1
        if source[end] == '}': depth -= 1
        end += 1
    return source[start:end].replace('private func', 'func', 1)


class WorldToolFeedbackOwner(unittest.TestCase):
    def test_newest_accepted_action_owns_feedback_and_failed_engine_stops_watchers(self):
        production = (APP / 'App/NativePortViewController.swift').read_text()
        watchers = '\n'.join(method(production, 'private func ' + name) for name in
            ['spawnVehicle(', 'teleportToWaypoint(', 'watchVehicleSpawn(', 'watchWaypointTeleport('])
        source = '''import Foundation
struct Deadline {
 static func now() -> Deadline { Deadline() }
 static func + (left: Deadline, right: Double) -> Deadline { left }
}
final class DispatchQueue {
 static let main=DispatchQueue()
 var pending: [() -> Void]=[]
 func asyncAfter(deadline: Deadline, execute: @escaping () -> Void) { pending.append(execute) }
 func flush() { let batch=pending;pending=[];batch.forEach { $0() } }
}
enum L10n { static func text(_ value: String) -> String { value } }
var spawnStatus: Int32=1, waypointStatus: Int32=1
var spawnAdmission: Int32=1, waypointAdmission=true, spawnCalls=0
func PGWorldToolsMode() -> Int32 { 2 }
func PGQueueSpawnVehicle(_ model: UnsafePointer<CChar>) -> Int32 {
 spawnCalls += 1
 if spawnAdmission == 1 { spawnStatus=1 }
 return spawnAdmission
}
func PGTeleportToWaypoint() -> Bool {
 if waypointAdmission { waypointStatus=1 }
 return waypointAdmission
}
func PGSpawnVehicleStatus() -> Int32 { spawnStatus }
func PGTeleportToWaypointStatus() -> Int32 { waypointStatus }
final class Controller {
 var engineStarted=true,engineFailed=false
 var worldToolFeedbackGeneration: UInt64=1
 var messages: [String]=[],logs: [String]=[]
 func showCheatToast(_ value: String) { messages.append(value) }
 func appendLog(_ value: String) { logs.append(value) }
''' + watchers + '''
}
let controller=Controller()
controller.watchVehicleSpawn("adder",generation:1)
controller.worldToolFeedbackGeneration=2
controller.watchVehicleSpawn("sultan",generation:2)
spawnStatus=2;DispatchQueue.main.flush()
precondition(controller.messages.count==1 && controller.messages[0].contains("sultan"))
precondition(!controller.messages.contains { $0.contains("adder") })
controller.messages=[];spawnStatus=1
controller.watchVehicleSpawn("buzzard",generation:2);DispatchQueue.main.flush()
precondition(DispatchQueue.main.pending.count==1)
controller.worldToolFeedbackGeneration=3
controller.watchWaypointTeleport(generation:3);spawnStatus=2;waypointStatus=2
DispatchQueue.main.flush()
precondition(controller.messages==["Moved to waypoint."])
controller.messages=[];controller.watchVehicleSpawn("sultan",generation:3)
controller.engineFailed=true;DispatchQueue.main.flush();precondition(controller.messages.isEmpty)
controller.engineFailed=false;spawnStatus=1
controller.watchVehicleSpawn("adder",generation:3);DispatchQueue.main.flush();precondition(controller.messages.isEmpty)
spawnStatus = -4;DispatchQueue.main.flush()
precondition(controller.messages.count==1 && controller.messages[0].contains("local control"))
controller.messages=[];controller.spawnVehicle("sultan")
waypointAdmission=false;waypointStatus = -6;controller.teleportToWaypoint()
let rejection=controller.messages.last!
precondition(rejection.hasPrefix("Waypoint teleport not queued:"))
spawnStatus = -5;DispatchQueue.main.flush()
precondition(controller.messages.last==rejection)
precondition(!controller.messages.contains { $0.contains("engine rejected creation") })
let before=spawnCalls
waypointAdmission=true;controller.teleportToWaypoint();waypointStatus=2
DispatchQueue.main.flush()
precondition(spawnCalls==before && controller.messages.last=="Moved to waypoint.")
print("WORLD_TOOL_FEEDBACK_NEWEST_OWNER_PENDING_RETRY_AND_FAILED_ENGINE_PASS")
'''
        with tempfile.TemporaryDirectory(prefix='zema-tool-feedback-owner-') as temporary:
            directory = Path(temporary)
            (directory / 'main.swift').write_text(source)
            result = subprocess.run(['/usr/bin/swiftc', '-warnings-as-errors', '-module-cache-path',
                str(directory / 'cache'), str(APP / 'App/VehicleSpawnFeedback.swift'),
                str(APP / 'App/WaypointTeleportFeedback.swift'), str(directory / 'main.swift'),
                '-o', str(directory / 'fixture')], capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(directory / 'fixture')], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('WORLD_TOOL_FEEDBACK_NEWEST_OWNER', result.stdout)
