/// Matches PGVehicleSpawnResult. Failed ownership must not be described as a bad model.
enum VehicleSpawnFeedback {
    static func failure(status: Int32, model: String) -> String {
        switch status {
        case -10: return "Required vehicle files are missing or not loaded in this game."
        case -2: return "Model '\(model)' did not load in time. Check its name and installed DLC."
        case -3: return "Your character is not ready. Wait until you are in the world."
        case -4: return "The character or new vehicle is not under local control. Try again after the session settles."
        case -5: return "Vehicle spawn '\(model)': the engine rejected creation after the model loaded. This is not a model-download error."
        case -6: return "The game could not run the required vehicle command."
        case -8: return "Use a vehicle model name of 1–63 English letters, digits or underscores, starting with a letter, or a nonzero hexadecimal hash such as 0x1234."
        case -9: return "A waypoint action is running or finishing cleanup. Wait before spawning a vehicle."
        case -7: return "Your character's position is not ready for a vehicle spawn."
        default: return "Could not spawn '\(model)'. Check that its model or DLC is available."
        }
    }
}
