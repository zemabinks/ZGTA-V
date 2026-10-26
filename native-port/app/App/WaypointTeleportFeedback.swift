/// Matches PGTeleportToWaypointStatus. A queued request is never reported as a completed move.
enum WaypointTeleportFeedback {
    static func message(status: Int32) -> String? {
        switch status {
        case 1: return "Preparing waypoint destination…"
        case 2: return "Moved to waypoint."
        case -1: return "No waypoint selected. Set one on the map first."
        case -2: return "No safe ground found at that waypoint. Choose a nearby road or open area."
        case -3: return "Your character is not ready. Wait until you are in the world."
        case -4: return "Leave the vehicle first, or drive a vehicle you control."
        case -5: return "The waypoint area did not finish loading. Your position was preserved."
        case -6: return "Another world action is running. Wait for it to finish."
        case -7: return "Waypoint teleport is unavailable in this session."
        case -8: return "Your character or vehicle changed. Select the waypoint and try again."
        case -9: return "The game is loading another scene. Wait before teleporting."
        default: return nil
        }
    }
}
