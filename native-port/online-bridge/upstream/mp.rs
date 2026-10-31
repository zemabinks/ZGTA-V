// muguet - mp.rs
// Constantin Clerc (c22dev) - 0.1

use crate::proto::{self, Look, PopEntry, Shot, State, VehLook};
use crate::{read_cstr, read_u32, read_u64, write_u64, HostState};
use std::collections::{HashMap, VecDeque};
use std::net::UdpSocket;
use std::sync::atomic::{AtomicBool, AtomicI32, AtomicU16, AtomicU64, AtomicUsize, Ordering};
use std::sync::{Mutex, OnceLock};
use std::time::{Duration, Instant};
#[cfg(not(feature = "native-port"))]
use wasmtime::{Caller, Val};
#[cfg(feature = "native-port")]
use crate::engine_bridge::{Caller, Val};

#[cfg_attr(not(feature = "jit"), allow(dead_code))]
pub const COMMANDS: &[(&str, &str)] = &[
    ("PlayerPedId", "player_commands::CommandPlayerPedId()"),
    ("GetEntityCoords", "entity_commands::CommandGetEntityCoords(int, bool)"),
    ("GetEntityHeading", "entity_commands::CommandGetEntityHeading(int)"),
    ("GetEntityVelocity", "entity_commands::CommandGetEntityVelocity(int)"),
    ("GetEntityRotation", "entity_commands::CommandGetEntityRotation(int, int)"),
    ("GetEntityModel", "entity_commands::CommandGetEntityModel(int)"),
    ("GetEntityHealth", "entity_commands::CommandGetEntityHealth(int)"),
    ("SetEntityHealth", "entity_commands::CommandSetEntityHealth(int, int, int)"),
    ("FreezeEntityPosition", "entity_commands::CommandFreezeEntityPosition(int, bool)"),
    ("DoesEntityExist", "entity_commands::CommandDoesEntityExist(int)"),
    ("IsEntityAMissionEntity", "entity_commands::CommandIsEntityAMissionEntity(int)"),
    ("SetEntityCoordsNoOffset", "entity_commands::CommandSetEntityCoordsNoOffset(int, rage::scrVector const&, bool, bool, bool)"),
    ("SetEntityHeading", "entity_commands::CommandSetEntityHeading(int, float)"),
    ("SetEntityRotation", "entity_commands::CommandSetEntityRotation(int, rage::scrVector const&, int, bool)"),
    ("SetEntityVelocity", "entity_commands::CommandSetEntityVelocity(int, rage::scrVector const&)"),
    ("SetEntityInvincible", "entity_commands::CommandSetEntityInvincible(int, bool)"),
    ("SetEntityAsMissionEntity", "entity_commands::CommandSetEntityAsMissionEntity(int, bool, bool)"),
    ("DeleteEntity", "entity_commands::CommandDeleteEntity(int&)"),
    ("CreatePed", "ped_commands::CommandCreatePed(int, int, rage::scrVector const&, float, bool, bool)"),
    ("DeletePed", "ped_commands::CommandDeletePed(int&)"),
    ("GetVehiclePedIsIn", "ped_commands::CommandGetVehiclePedIsIn(int, bool)"),
    ("IsPedInAnyVehicle", "ped_commands::CommandIsPedInAnyVehicle(int, bool)"),
    ("IsPedDeadOrDying", "ped_commands::CommandIsPedDeadOrDying(int, bool)"),
    ("IsPedShooting", "ped_commands::CommandIsPedShooting(int)"),
    ("GetPedArmour", "ped_commands::CommandGetPedArmour(int)"),
    ("GetPedBoneCoords", "ped_commands::CommandGetPedBoneCoords(int, int, rage::scrVector const&)"),
    ("SetPedIntoVehicle", "ped_commands::CommandSetPedIntoVehicle(int, int, int)"),
    ("ResurrectPed", "ped_commands::CommandResurrectPed(int)"),
    ("ReviveInjuredPed", "ped_commands::CommandReviveInjuredPed(int)"),
    ("SetBlockingOfNonTemporaryEvents", "ped_commands::CommandSetBlockingOfNonTemporaryEvents(int, bool)"),
    ("SetPedCanRagdoll", "ped_commands::CommandSetPedCanRagdoll(int, bool)"),
    ("SetPedKeepTask", "ped_commands::CommandSetPedKeepTask(int, bool)"),
    ("SetPedCanBeDraggedOut", "ped_commands::CommandSetPedCanBeDraggedOut(int, bool)"),
    ("SetPedDefaultComponentVariation", "ped_commands::CommandSetPedDefaultComponentVariation(int)"),
    ("GetPedDrawableVariation", "ped_commands::CommandGetPedDrawableVariation(int, int)"),
    ("GetPedTextureVariation", "ped_commands::CommandGetPedTextureVariation(int, int)"),
    ("GetPedPaletteVariation", "ped_commands::CommandGetPedPaletteVariation(int, int)"),
    ("SetPedComponentVariation", "ped_commands::CommandSetPedComponentVariation(int, int, int, int, int)"),
    ("GetPedPropIndex", "ped_commands::CommandGetPedPropIndex(int, int)"),
    ("GetPropTextureIndex", "ped_commands::CommandGetPropTextureIndex(int, int)"),
    ("SetPedPropIndex", "ped_commands::CommandSetPedPropIndex(int, int, int, int, bool)"),
    ("ClearPedProp", "ped_commands::CommandClearPedProp(int, int)"),
    ("GetNearbyVehicles", "ped_commands::CommandGetNearbyVehicles(int, int&)"),
    ("GetNearbyPeds", "ped_commands::CommandGetNearbyPeds(int, int&, int)"),
    ("SetPedDensityMultiplierThisFrame", "ped_commands::CommandSetPedDensityMultiplierThisFrame(float)"),
    ("SetScenarioPedDensityMultiplierThisFrame", "ped_commands::CommandSetScenarioPedDensityMultiplierThisFrame(float, float)"),
    ("CreateVehicle", "vehicle_commands::CommandCreateVehicle(int, rage::scrVector const&, float, bool, bool, bool)"),
    ("DeleteVehicle", "vehicle_commands::CommandDeleteVehicle(int&)"),
    ("SetVehicleEngineOn", "vehicle_commands::CommandSetVehicleEngineOn(int, bool, bool, bool)"),
    ("GetPedInVehicleSeat", "vehicle_commands::CommandGetPedInVehicleSeat(int, int, bool)"),
    ("IsVehicleSeatFree", "vehicle_commands::CommandIsVehicleSeatFree(int, int, bool)"),
    ("GetVehicleColours", "vehicle_commands::CommandGetVehicleColours(int, int&, int&)"),
    ("SetVehicleColour", "vehicle_commands::CommandSetVehicleColour(int, int, int)"),
    ("SetVehicleDensityMultiplierThisFrame", "vehicle_commands::CommandSetVehicleDensityMultiplierThisFrame(float)"),
    ("SetRandomVehicleDensityMultiplierThisFrame", "vehicle_commands::CommandSetRandomVehicleDensityMultiplierThisFrame(float)"),
    ("SetParkedVehicleDensityMultiplierThisFrame", "vehicle_commands::CommandSetParkedVehicleDensityMultiplierThisFrame(float)"),
    ("ClearAreaOfVehicles", "misc_commands::CommandClearAreaOfVehicles(rage::scrVector const&, float, bool, bool, bool, bool, bool, bool, bool)"),
    ("ClearAreaOfPeds", "misc_commands::CommandClearAreaOfPeds(rage::scrVector const&, float, bool)"),
    ("FireSingleBulletIgnoreEntity", "misc_commands::CommandFireSingleBulletIgnoreEntity(rage::scrVector const&, rage::scrVector const&, int, bool, int, int, bool, bool, float, int, int)"),
    ("RequestWeaponAsset", "weapon_commands::RequestWeaponAsset(int, int, int)"),
    ("HasWeaponAssetLoaded", "weapon_commands::HasWeaponAssetLoaded(int)"),
    ("GetPlayerInvincible", "player_commands::CommandGetPlayerInvincible(int)"),
    ("SetPlayerInvincible", "player_commands::CommandSetPlayerInvincible(int, bool)"),
    ("SetPlayerInvincible2", "player_commands::SetPlayerInvincible(int, bool)"),
    ("GetEntityCanBeDamaged", "entity_commands::CommandGetEntityCanBeDamaged(int)"),
    ("GetVehicleEngineHealth", "vehicle_commands::CommandGetVehicleEngineHealth(int)"),
    ("SetVehicleEngineHealth", "vehicle_commands::CommandSetVehicleEngineHealth(int, float)"),
    ("GetVehicleBodyHealth", "vehicle_commands::CommandGetVehicleBodyHealth(int)"),
    ("SetVehicleBodyHealth", "vehicle_commands::CommandSetVehicleBodyHealth(int, float)"),
    ("GetVehiclePetrolTankHealth", "vehicle_commands::CommandGetVehiclePetrolTankHealth(int)"),
    ("SetVehiclePetrolTankHealth", "vehicle_commands::CommandSetVehiclePetrolTankHealth(int, float)"),
    ("IsVehicleTyreBurst", "vehicle_commands::CommandIsVehicleTyreBurst(int, int, bool)"),
    ("SetVehicleTyreBurst", "vehicle_commands::CommandSetVehicleTyreBurst(int, int, bool, float)"),
    ("IsVehicleWindowIntact", "vehicle_commands::CommandIsVehicleWindowIntact(int, int)"),
    ("SmashVehicleWindow", "vehicle_commands::CommandSmashVehicleWindow(int, int)"),
    ("ExplodeVehicle", "vehicle_commands::CommandExplodeVehicle(int, bool, bool)"),
    ("SetVehicleFixed", "vehicle_commands::CommandSetVehicleFixed(int)"),
    ("SetVehicleDeformationFixed", "vehicle_commands::CommandSetVehicleDeformationFixed(int)"),
    ("IsEntityDead", "entity_commands::CommandIsEntityDead(int, bool)"),
    ("IsEntityAPed", "entity_commands::CommandIsEntityAPed(int)"),
    ("IsEntityOnScreen", "entity_commands::CommandIsEntityOnScreen(int)"),
    ("SetEntityAsNoLongerNeeded", "entity_commands::CommandSetEntityAsNoLongerNeeded(int&)"),
    ("SetDrawOrigin", "graphics_commands::CommandSetDrawOrigin(rage::scrVector const&, bool)"),
    ("ClearDrawOrigin", "graphics_commands::CommandClearDrawOrigin()"),
    ("BeginTextCommandDisplayText", "hud_commands::CommandBeginTextCommandDisplayText(char const*)"),
    ("AddTextComponentSubStringPlayerName", "hud_commands::CommandAddTextComponentSubStringPlayerName(char const*)"),
    ("EndTextCommandDisplayText", "hud_commands::CommandEndTextCommandDisplayText(float, float, int)"),
    ("SetTextScale", "hud_commands::CommandSetTextScale(float, float)"),
    ("SetTextColour", "hud_commands::CommandSetTextColour(int, int, int, int)"),
    ("SetTextCentre", "hud_commands::CommandSetTextCentre(bool)"),
    ("SetTextFont", "hud_commands::CommandSetTextFont(int)"),
    ("SetTextOutline", "hud_commands::CommandSetTextOutline()"),
    ("DoesScriptExist", "script_commands::DoesScriptExist(char const*)"),
    ("AddRelationshipGroup", "ped_commands::CommandAddRelationshipGroup(char const*, int&)"),
    ("DoesRelationshipGroupExist", "ped_commands::CommandDoesRelationshipGroupExist(int)"),
    ("SetRelationshipBetweenGroups", "ped_commands::CommandSetRelationshipBetweenGroups(int, int, int)"),
    ("SetRelationshipGroupAffectsWantedLevel", "ped_commands::CommandSetRelationshipGroupAffectsWantedLevel(int, bool)"),
    ("GetPedRelationshipGroupHash", "ped_commands::CommandGetPedRelationshipGroupHash(int)"),
    ("SetPedRelationshipGroupHash", "ped_commands::CommandSetPedRelationshipGroupHash(int, int)"),
    ("SetPedCanBeTargetted", "ped_commands::CommandSetPedCanBeTargetted(int, bool)"),
    ("SetCanAttackFriendly", "ped_commands::CommandSetCanAttackFriendly(int, bool, bool)"),
    ("PlayerId", "player_commands::CommandPlayerId()"),
    ("IsPlayerFreeAiming", "player_commands::CommandIsPlayerFreeAiming(int)"),
    ("GetGameplayCamCoord", "camera_commands::CommandGetGameplayCamCoord()"),
    ("GetGameplayCamRot", "camera_commands::CommandGetGameplayCamRot(int)"),
    ("TaskGoToCoordWhileAimingAtCoord", "task_commands::CommandTaskGoToCoordWhileAimingAtCoord(int, rage::scrVector const&, rage::scrVector const&, float, bool, float, float, bool, int, bool, int)"),
    ("GetVehicleExtraColours", "vehicle_commands::CommandGetVehicleExtraColours(int, int&, int&)"),
    ("SetVehicleExtraColours", "vehicle_commands::CommandSetVehicleExtraColours(int, int, int)"),
    ("GetVehicleLivery", "vehicle_commands::CommandGetVehicleLivery(int)"),
    ("SetVehicleLivery", "vehicle_commands::CommandSetVehicleLivery(int, int)"),
    ("GetVehicleWindowTint", "vehicle_commands::CommandGetVehicleWindowTint(int)"),
    ("SetVehicleWindowTint", "vehicle_commands::CommandSetVehicleWindowTint(int, int)"),
    ("GetVehicleWheelType", "vehicle_commands::CommandGetVehicleWheelType(int)"),
    ("SetVehicleWheelType", "vehicle_commands::CommandSetVehicleWheelType(int, int)"),
    ("SetVehicleModKit", "vehicle_commands::CommandSetVehicleModKit(int, int)"),
    ("GetVehicleMod", "vehicle_commands::CommandGetVehicleMod(int, int)"),
    ("SetVehicleMod", "vehicle_commands::CommandSetVehicleMod(int, int, int, bool)"),
    ("IsToggleModOn", "vehicle_commands::CommandIsToggleModOn(int, int)"),
    ("ToggleVehicleMod", "vehicle_commands::CommandToggleVehicleMod(int, int, bool)"),
    ("GetVehicleNumberPlateText", "vehicle_commands::CommandGetVehicleNumberPlateText(int)"),
    ("SetVehicleNumberPlateText", "vehicle_commands::CommandSetVehicleNumberPlateText(int, char const*)"),
    ("GetPlayerRadioStationIndex", "audio_commands::CommandGetPlayerRadioStationIndex()"),
    ("RetuneRadioToStationIndex", "audio_commands::CommandRetuneRadioToStationIndex(int)"),
    ("GetBaseFromGuid", "rage::fwScriptGuid::GetBaseFromGuid(int)"),
    ("AddOwnedExplosion", "fire_commands::CommandAddOwnedExplosion(int, rage::scrVector const&, int, float, bool, bool, float)"),
    ("AddExplosion", "fire_commands::CommandAddExplosion(rage::scrVector const&, int, float, bool, bool, float, bool)"),
    ("SetEntityProofs", "entity_commands::CommandSetEntityProofs(int, bool, bool, bool, bool, bool, bool, bool, bool)"),
    ("SetPedArmour", "ped_commands::CommandSetPedArmour(int, int)"),
    ("SetEnableHandCuffs", "ped_commands::CommandSetEnableHandCuffs(int, bool)"),
    ("TaskHandsUp", "task_commands::CommandTaskHandsUp(int, int, int, int, int)"),
    ("DisablePlayerFiring", "player_commands::CommandDisablePlayerFiring(int, bool)"),
    ("SetNewWaypoint", "hud_commands::CommandSetNewWaypoint(float, float)"),
    ("SetTimeScale", "misc_commands::CommandSetTimeScale(float)"),
    ("IsControlPressed", "pad_commands::CommandIsControlPressed(int, int)"),
    ("DisableControlAction", "pad_commands::CommandDisableControlAction(int, int, bool)"),
    ("DisableControlAction2", "pad_commands::DisableControlAction(int, int, bool)"),
    ("SetClockTime", "clock_commands::CommandSetClockTime(int, int, int)"),
    ("GetClockHours", "clock_commands::CommandGetClockHours()"),
    ("GetClockMinutes", "clock_commands::CommandGetClockMinutes()"),
    ("GetClockSeconds", "clock_commands::CommandGetClockSeconds()"),
    ("GetNextWeatherTypeHashName", "misc_commands::CommandGetNextWeatherTypeHashName()"),
    ("SetWeatherTypeNowPersist", "misc_commands::CommandSetWeatherTypeNowPersist(char const*)"),
    ("HasEntityBeenDamagedByEntity", "entity_commands::CommandHasEntityBeenDamagedByEntity(int, int, bool)"),
    ("ClearEntityLastDamageEntity", "entity_commands::CommandClearEntityLastDamageEntity(int)"),
    ("GetEntitySpeed", "entity_commands::CommandGetEntitySpeed(int)"),
    ("GetMeleeTargetForPed", "ped_commands::CommandGetMeleeTargetForPed(int)"),
    ("DoesAnimDictExist", "streaming_commands::DoesAnimDictExist(char const*)"),
    ("HasAnimDictLoaded", "streaming_commands::HasAnimDictLoaded(char const*)"),
    ("RequestAnimDict", "streaming_commands::RequestAnimDict(char const*)"),
    ("GetAnimDuration", "entity_commands::CommandGetAnimDuration(char const*, char const*)"),
    ("TaskPlayAnim", "task_commands::CommandTaskPlayAnim(int, char const*, char const*, float, float, int, int, float, bool, int, bool)"),
    ("GetWeatherState", "misc_commands::CommandGetWeatherState(int&, int&, float&)"),
    ("SetWeatherState", "misc_commands::CommandSetWeatherState(int, int, float)"),
    ("ClearWeatherTypePersist", "misc_commands::CommandClearWeatherTypePersist()"),
    ("ClearPedTasks", "task_commands::CommandClearPedTasks(int)"),
    ("SetEntityAngularVelocity", "entity_commands::CommandSetEntityAngularVelocity(int, rage::scrVector const&)"),
    ("GetPedCauseOfDeath", "ped_commands::CommandGetPedCauseOfDeath(int)"),
    ("BeginTheFeedPost", "hud_commands::CommandBeginTheFeedPost(char const*)"),
    ("EndTheFeedPostTicker", "hud_commands::CommandEndTheFeedPostTicker(bool, bool)"),
    ("IsPlayerPressingHorn", "player_commands::CommandIsPlayerPressingHorn(int)"),
    ("IsPedRagdoll", "ped_commands::CommandIsPedRagdoll(int)"),
    ("TaskLeaveVehicle", "task_commands::CommandTaskLeaveVehicle(int, int, int)"),
    ("GetVehiclePedIsTryingToEnter", "ped_commands::CommandGetVehiclePedIsTryingToEnter(int)"),
    ("GetSeatPedIsTryingToEnter", "ped_commands::CommandGetSeatPedIsTryingToEnter(int)"),
    ("GetVehicleLightsState", "vehicle_commands::CommandGetVehicleLightsState(int, int&, int&)"),
    ("SetVehicleLights", "vehicle_commands::CommandSetVehicleLights(int, int)"),
    ("SetVehicleFullBeam", "vehicle_commands::CommandSetVehicleFullBeam(int, bool)"),
    ("IsHornActive", "audio_commands::CommandIsHornActive(int)"),
    ("SoundCarHorn", "vehicle_commands::CommandSoundCarHorn(int, int, int, bool)"),
    ("IsVehicleSirenOn", "vehicle_commands::CommandIsVehicleSirenOn(int)"),
    ("SetVehicleSiren", "vehicle_commands::CommandSetVehicleSiren(int, bool)"),
    ("GetVehicleDoorAngleRatio", "vehicle_commands::CommandGetVehicleDoorAngleRatio(int, int)"),
    ("SetVehicleDoorOpen", "vehicle_commands::CommandSetVehicleDoorOpen(int, int, bool, bool)"),
    ("SetVehicleDoorShut", "vehicle_commands::CommandSetVehicleDoorShut(int, int, bool)"),
    ("DrawRect", "graphics_commands::CommandDrawRect(float, float, float, float, int, int, int, int, bool)"),
    ("PlaySoundFrontend", "audio_commands::CommandPlaySoundFrontend(int, char const*, char const*, bool)"),
    ("GetInteriorFromEntity", "interior_commands::CommandGetInteriorFromEntity(int)"),
    ("GetPedSourceOfDeath", "ped_commands::CommandGetPedSourceOfDeath(int)"),
    ("IsPedArmed", "weapon_commands::CommandIsPedArmed(int, int)"),
    ("GetWeaponDamage", "weapon_commands::CommandGetWeaponDamage(int, int)"),
    ("GetWeaponDamageType", "weapon_commands::CommandGetWeaponDamageType(int)"),
    ("SetPedToRagdoll", "ped_commands::CommandSetPedToRagdoll(int, int, int, int, bool, bool, bool)"),
    ("ShakeGameplayCam", "camera_commands::CommandShakeGameplayCam(char const*, float)"),
    ("SetPedShootsAtCoord", "ped_commands::CommandSetPedShootsAtCoord(int, rage::scrVector const&, bool)"),
    ("SetPedMaxHealth", "ped_commands::CommandSetPedMaxHealth(int, int)"),
    ("GetSelectedPedWeapon", "weapon_commands::CommandGetSelectedPedWeapon(int)"),
    ("GiveWeaponToPed", "weapon_commands::CommandGiveWeaponToPed(int, int, int, bool, bool)"),
    ("SetCurrentPedWeapon", "weapon_commands::CommandSetCurrentPedWeapon(int, int, bool)"),
    ("SetPedInfiniteAmmoClip", "weapon_commands::CommandSetPedInfiniteAmmoClip(int, bool)"),
    ("GetPedLastWeaponImpactCoord", "weapon_commands::CommandGetPedLastWeaponImpactCoord(int, rage::Vector3&)"),
    ("RemoveAllPedWeapons", "weapon_commands::CommandRemoveAllPedWeapons(int, bool)"),
    ("RemoveAllPedWeapons2", "weapon_commands::RemoveAllPedWeapons(int, bool)"),
    ("RemoveWeaponFromPed", "weapon_commands::CommandRemoveWeaponFromPed(int, int)"),
    ("RemoveWeaponFromPed2", "weapon_commands::RemoveWeaponFromPed(int, int)"),
    ("HasPedGotWeapon", "weapon_commands::CommandHasPedGotWeapon(int, int, bool)"),
    ("HasPedGotWeapon2", "weapon_commands::HasPedGotWeapon(int, int, bool)"),
    ("GetAmmoInPedWeapon", "weapon_commands::CommandGetAmmoInPedWeapon(int, int)"),
    ("GetAmmoInPedWeapon2", "weapon_commands::GetAmmoInPedWeapon(int, int)"),
    ("SetPedAmmo", "weapon_commands::CommandSetPedAmmo(int, int, int)"),
    ("SetPedAmmo2", "weapon_commands::SetPedAmmo(int, int, int)"),
    ("RequestModel", "streaming_commands::CommandRequestModel(int)"),
    ("HasModelLoaded", "streaming_commands::HasModelLoaded(int)"),
    ("TaskGoStraightToCoord", "task_commands::CommandTaskGoStraightToCoord(int, rage::scrVector const&, float, int, float, float)"),
    ("TaskAimGunAtCoord", "task_commands::CommandTaskAimGunAtCoord(int, rage::scrVector const&, int, bool, bool)"),
    ("TaskEnterVehicle", "task_commands::CommandTaskEnterVehicle(int, int, int, int, float, int, char const*)"),
    ("ClearPedTasksImmediately", "task_commands::CommandClearPedTasksImmediately(int)"),
    ("AddBlipForEntity", "hud_commands::AddBlipForEntity(int)"),
    ("RemoveBlip", "hud_commands::CommandRemoveBlip(int&)"),
    ("ShowHeadingIndicatorOnBlip", "hud_commands::CommandShowHeadingIndicatorOnBlip(int, bool)"),
    ("AddBlipForCoord", "hud_commands::AddBlipForCoord(rage::scrVector const&)"),
    ("AddBlipForCoord2", "hud_commands::CommandAddBlipForCoord(rage::scrVector const&)"),
    ("SetBlipSprite", "hud_commands::CommandSetBlipSprite(int, int)"),
    ("SetBlipSprite2", "hud_commands::SetBlipSprite(int, int)"),
    ("SetBlipColour", "hud_commands::ChangeBlipColour(int, int)"),
    ("SetBlipColour2", "hud_commands::CommandSetBlipColour(int, int)"),
    ("SetBlipScale", "hud_commands::CommandChangeBlipScale(int, float)"),
    ("SetBlipScale2", "hud_commands::SetBlipScale(int, float)"),
    ("SetBlipAsShortRange", "hud_commands::CommandSetBlipAsShortRange(int, bool)"),
    ("SetBlipAsShortRange2", "hud_commands::SetBlipAsShortRange(int, bool)"),
    ("SetBlipCoords", "hud_commands::CommandSetBlipCoords(int, rage::scrVector const&)"),
    ("SetBlipCoords2", "hud_commands::SetBlipCoords(int, rage::scrVector const&)"),
    ("DoesBlipExist", "hud_commands::CommandDoesBlipExist(int)"),
    ("SetFollowPedCamViewMode", "camera_commands::CommandSetFollowPedCamViewMode(int)"),
    ("SetFollowPedCamViewMode2", "camera_commands::SetFollowPedCamViewMode(int)"),
    ("GetFollowPedCamViewMode", "camera_commands::CommandGetFollowPedCamViewMode()"),
    ("GetFollowPedCamViewMode2", "camera_commands::GetFollowPedCamViewMode()"),
    ("SetFollowVehicleCamViewMode", "camera_commands::CommandSetFollowVehicleCamViewMode(int)"),
    ("SetFollowVehicleCamViewMode2", "camera_commands::SetFollowVehicleCamViewMode(int)"),
    ("GetFollowVehicleCamViewMode", "camera_commands::CommandGetFollowVehicleCamViewMode()"),
    ("GetFollowVehicleCamViewMode2", "camera_commands::GetFollowVehicleCamViewMode()"),
    ("RequestScript", "script_commands::CommandRequestScript(char const*)"),
    ("RequestScript2", "script_commands::RequestScript(char const*)"),
    ("HasScriptLoaded", "script_commands::HasScriptLoaded(char const*)"),
    ("StartNewScript", "script_commands::CommandStartNewScript(char const*, int)"),
    ("StartNewScript2", "script_commands::StartNewScript(char const*, int)"),
    ("GetMissionFlag", "misc_commands::CommandGetMissionFlag()"),
    ("StopCutsceneImmediately", "cutscene_commands::CommandStopCutsceneImmediately()"),
    ("DoScreenFadeIn", "cam_commands::CommandDoScreenFadeIn(int)"),
];

const ACTIVE_THREAD_TLS: u64 = 3088;

const THREAD_NAME: u64 = 428;
const SEND_EVERY: Duration = Duration::from_millis(33);
const LOOK_EVERY: Duration = Duration::from_secs(1);
const POP_EVERY: Duration = Duration::from_millis(100);

const INTERP_DELAY: Duration = Duration::from_millis(80);

const SHARE_NEAR: f32 = 150.0;
const SHARE_FAR: f32 = 220.0;

const BONE_RIGHT_HAND: i32 = 57005;

const TAG_RANGE: f32 = 80.0;

const AVATAR_HEALTH: i32 = 5000;

const SCRATCH: i64 = 2048;
const S_INT: u64 = 160;
const S_INT2: u64 = 168;
const S_V3: u64 = 192;
const S_VEHS: u64 = 256;
const S_PEDS: u64 = 1024;
const S_DICT: u64 = 1360;
const S_CLIP: u64 = 1430;
const S_TEXT: u64 = 1500;
const S_NAME: u64 = 1520;
const NEARBY_MAX: u64 = 40;

struct Peer {
    name: String,
    snaps: VecDeque<(Instant, State)>,
    last: Instant,
    look: Option<Look>,
    vlook: Option<VehLook>,

    pop: Option<(Instant, Vec<PopEntry>)>,

    extras: Option<(Instant, Vec<PopEntry>)>,

    vctl: Option<[u8; 4]>,

    pop_parts: [Option<(Instant, Vec<PopEntry>)>; POP_PARTS],
    clock: Clock,
}

impl Peer {
    fn new(name: String) -> Peer {
        Peer { name, snaps: VecDeque::new(), last: Instant::now(), look: None, vlook: None, pop: None, extras: None, vctl: None, pop_parts: Default::default(), clock: Clock::default() }
    }
}

fn pvp_enabled() -> bool {
    let raw = std::env::var("MUGUET_ROOM").unwrap_or_default().to_lowercase();
    if raw.contains("-pvp-") || raw.contains("-pvp") { return true; }
    if raw.contains("-peace-") || raw.contains("-peace") { return false; }
    std::env::var("MUGUET_PVP").map(|v| v != "0").unwrap_or(false)
}

struct Net {
    sock: UdpSocket,
    name: String,
    room: String,
    last_server: Mutex<Instant>,
    full: AtomicBool,
    my_id: Mutex<Option<u8>>,
    peers: Mutex<HashMap<u8, Peer>>,
    shots: Mutex<Vec<(u8, Shot)>>,

    kills: Mutex<Vec<(u8, u32)>>,

    taken: Mutex<Vec<(u8, u32)>>,
    explosions: Mutex<Vec<(u8, i32, [f32; 3])>>,

    hits: Mutex<Vec<(u8, u8, u16, u32)>>,

    car_hits: Mutex<Vec<(u8, i16, i16, u8, i16, Option<(u32, u32)>)>>,

    time: Mutex<Option<(u8, [u8; 4], Option<(u8, u8, f32)>)>>,

    pending: Mutex<Vec<Pending>>,
    rel_seq: Mutex<u16>,

    rel_seen: Mutex<HashMap<u8, VecDeque<u16>>>,

    deaths: Mutex<Vec<(u8, u8, u32)>>,
}

struct Pending {
    seq: u16,
    packet: Vec<u8>,
    waiting: Vec<u8>,
    first: Instant,
    last: Instant,
}

const RESEND_EVERY: Duration = Duration::from_millis(150);
const RESEND_FOR: Duration = Duration::from_secs(4);

fn send_reliable(net: &Net, kind: u8, payload: &[u8], to: Option<u8>) {
    let seq = {
        let mut s = net.rel_seq.lock().unwrap();
        *s = s.wrapping_add(1);
        *s
    };
    let mut body = seq.to_le_bytes().to_vec();
    body.push(kind);
    body.extend_from_slice(payload);
    let packet = proto::packet(proto::REL, &body);
    let _ = net.sock.send(&packet);
    let waiting: Vec<u8> = match to {
        Some(id) => vec![id],
        None => net.peers.lock().unwrap().keys().copied().collect(),
    };
    if !waiting.is_empty() {
        let now = Instant::now();
        net.pending.lock().unwrap().push(Pending { seq, packet, waiting, first: now, last: now });
    }
}

fn resend(net: &Net) {
    let peers: Vec<u8> = net.peers.lock().unwrap().keys().copied().collect();
    let mut pending = net.pending.lock().unwrap();
    pending.retain_mut(|p| {
        p.waiting.retain(|id| peers.contains(id));
        if p.waiting.is_empty() || p.first.elapsed() > RESEND_FOR {
            return false;
        }
        if p.last.elapsed() >= RESEND_EVERY {
            p.last = Instant::now();
            let _ = net.sock.send(&p.packet);
        }
        true
    });
}

static NET: OnceLock<Option<Net>> = OnceLock::new();
static START: OnceLock<Instant> = OnceLock::new();

pub fn shutdown() {
    if let Some(Some(net)) = NET.get() {
        let _ = net.sock.send(&proto::packet(proto::BYE, &[]));
    }
}

static LOCAL_PED: AtomicU64 = AtomicU64::new(0);
static LOCAL_CAR: AtomicU64 = AtomicU64::new(0);
static LAST_EXPLOSION: Mutex<Option<Instant>> = Mutex::new(None);

pub fn explosion(args: u64) {
    let Some(Some(net)) = NET.get() else { return };
    let mem = &crate::RT.get().unwrap().mem;
    let owner = read_u64(mem, args + 40).unwrap_or(0);
    let mine = owner != 0 && (owner == LOCAL_PED.load(Ordering::Relaxed) || owner == LOCAL_CAR.load(Ordering::Relaxed));
    if !mine {
        return;
    }

    let mut last = LAST_EXPLOSION.lock().unwrap();
    if last.map(|t| t.elapsed() < Duration::from_millis(50)).unwrap_or(false) {
        return;
    }
    *last = Some(Instant::now());
    let kind = read_u32(mem, args).unwrap_or(0);
    let mut payload = kind.to_le_bytes().to_vec();
    for o in [16, 20, 24] {
        payload.extend(read_u32(mem, args + o).unwrap_or(0).to_le_bytes());
    }
    send_reliable(net, proto::EXPLODE, &payload, None);
}

static OTHERS_HERE: AtomicBool = AtomicBool::new(false);

pub fn time_warp(dir: i64) -> i64 {
    if OTHERS_HERE.load(Ordering::Relaxed) { 0 } else { dir }
}

static WANT_ENTER: AtomicBool = AtomicBool::new(false);
static WANT_BULLETS: AtomicBool = AtomicBool::new(false);
static TYPED: Mutex<String> = Mutex::new(String::new());

// Economy & Gun Shop State
pub static WALLET_CASH: AtomicI32 = AtomicI32::new(1000);
pub static AMMU_BUY_REQUESTED: AtomicBool = AtomicBool::new(false);
static SELECTED_AMMU_ITEM: AtomicUsize = AtomicUsize::new(0);
static LAST_PAYCHECK: Mutex<Option<Instant>> = Mutex::new(None);
static LAST_AMMU_BUY: Mutex<Option<Instant>> = Mutex::new(None);
static WEAPONS_INITIALIZED: AtomicBool = AtomicBool::new(false);
static PURCHASED_WEAPONS: Mutex<Vec<u32>> = Mutex::new(Vec::new());

// Voice Chat State (Loa & Mic)
pub static VOICE_MIC_ENABLED: AtomicBool = AtomicBool::new(false);
pub static VOICE_SPEAKER_ENABLED: AtomicBool = AtomicBool::new(true);

struct SpeakerQueue {
    samples: VecDeque<f32>,
    last_heard: Instant,
}

static SPEAKER_QUEUES: Mutex<Vec<(u8, SpeakerQueue)>> = Mutex::new(Vec::new());
static ACTIVE_SPEAKERS: Mutex<Vec<(u8, String, Instant)>> = Mutex::new(Vec::new());
static VOICE_SEQ: AtomicU16 = AtomicU16::new(0);
static LOCAL_POS: Mutex<Option<[f32; 3]>> = Mutex::new(None);

pub struct ShopItem {
    pub name: &'static str,
    pub weapon_hash: &'static str,
    pub price: i32,
    pub ammo: i32,
    pub is_armor: bool,
}

pub const AMMU_ITEMS: &[ShopItem] = &[
    ShopItem { name: "Combat Pistol", weapon_hash: "weapon_combatpistol", price: 500, ammo: 60, is_armor: false },
    ShopItem { name: "Micro SMG", weapon_hash: "weapon_microsmg", price: 1200, ammo: 120, is_armor: false },
    ShopItem { name: "Shotgun (Pump Shotgun)", weapon_hash: "weapon_pumpshotgun", price: 2000, ammo: 40, is_armor: false },
    ShopItem { name: "Carbine Rifle", weapon_hash: "weapon_carbinerifle", price: 3500, ammo: 150, is_armor: false },
    ShopItem { name: "Sniper Rifle", weapon_hash: "weapon_sniperrifle", price: 5000, ammo: 30, is_armor: false },
    ShopItem { name: "Body Armor (100% Armor)", weapon_hash: "", price: 800, ammo: 0, is_armor: true },
    ShopItem { name: "Refill All Ammo", weapon_hash: "AMMO_REFILL", price: 400, ammo: 999, is_armor: false },
];

pub const ALL_CHEAT_WEAPONS: &[&str] = &[
    "weapon_knife", "weapon_nightstick", "weapon_hammer", "weapon_bat", "weapon_golfclub", "weapon_crowbar",
    "weapon_bottle", "weapon_dagger", "weapon_hatchet", "weapon_knuckle", "weapon_machete", "weapon_flashlight",
    "weapon_switchblade", "weapon_battleaxe", "weapon_poolcue", "weapon_wrench",
    "weapon_pistol", "weapon_combatpistol", "weapon_appistol", "weapon_pistol50", "weapon_snspistol",
    "weapon_heavypistol", "weapon_vintagepistol", "weapon_marksmanpistol", "weapon_revolver", "weapon_doubleaction",
    "weapon_microsmg", "weapon_smg", "weapon_assaultsmg", "weapon_combatpdw", "weapon_machinepistol",
    "weapon_minismg", "weapon_gusenberg",
    "weapon_assaultrifle", "weapon_carbinerifle", "weapon_advancedrifle", "weapon_specialcarbine",
    "weapon_bullpuprifle", "weapon_compactrifle",
    "weapon_mg", "weapon_combatmg",
    "weapon_pumpshotgun", "weapon_sawnoffshotgun", "weapon_assaultshotgun", "weapon_bullpupshotgun",
    "weapon_musket", "weapon_heavyshotgun", "weapon_dbshotgun", "weapon_autoshotgun",
    "weapon_sniperrifle", "weapon_heavysniper", "weapon_marksmanrifle",
    "weapon_grenadelauncher", "weapon_rpg", "weapon_minigun", "weapon_railgun", "weapon_hominglauncher",
    "weapon_compactlauncher", "weapon_firework",
    "weapon_grenade", "weapon_stickybomb", "weapon_molotov", "weapon_smokegrenade", "weapon_flaregun",
    "weapon_ball", "weapon_snowball", "weapon_petrolcan", "weapon_parachute",
];

/// Weapon hashes never change: hash the list once instead of 77 joaat() calls per check.
fn cheat_weapon_hashes() -> &'static [(&'static str, u32)] {
    static HASHES: OnceLock<Vec<(&'static str, u32)>> = OnceLock::new();
    HASHES.get_or_init(|| ALL_CHEAT_WEAPONS.iter().map(|name| (*name, proto::joaat(name))).collect())
}
/// A full inventory scan costs ~150 engine calls on the game thread, so it runs at most this often.
/// The weapon in the player's hand is still checked every frame.
const WEAPON_SCAN_EVERY: Duration = Duration::from_millis(500);
static LAST_WEAPON_SCAN: Mutex<Option<Instant>> = Mutex::new(None);

pub const BANNED_CHEAT_WEAPONS: &[&str] = &[
    "weapon_rpg", "weapon_minigun", "weapon_grenadelauncher", "weapon_stickybomb", "weapon_molotov",
    "weapon_railgun", "weapon_hominglauncher", "weapon_firework", "weapon_grenade",
];

pub fn submit_mic_audio(samples: &[f32]) {
    if !VOICE_MIC_ENABLED.load(Ordering::Relaxed) { return; }
    let Some(Some(net)) = NET.get() else { return; };
    if net.my_id.lock().unwrap().is_none() { return; }

    // Noise gate: skip transmitting background hiss / ambient room silence
    let rms = (samples.iter().map(|s| s * s).sum::<f32>() / samples.len().max(1) as f32).sqrt();
    if rms < 0.005 { return; }

    let my_pos = LOCAL_POS.lock().unwrap().unwrap_or([0.0, 0.0, 0.0]);
    let pos_dm = [
        (my_pos[0] * 10.0).clamp(i16::MIN as f32, i16::MAX as f32) as i16,
        (my_pos[1] * 10.0).clamp(i16::MIN as f32, i16::MAX as f32) as i16,
        (my_pos[2] * 10.0).clamp(i16::MIN as f32, i16::MAX as f32) as i16,
    ];

    // Transmit in 20ms chunks (960 samples @ 48kHz) to stay well within network MTU
    for chunk_samples in samples.chunks(960) {
        let seq = VOICE_SEQ.fetch_add(1, Ordering::Relaxed);
        let data: Vec<u8> = chunk_samples.iter().map(|&s| {
            let s_clamped = s.clamp(-1.0, 1.0);
            ((s_clamped * 127.0) + 128.0) as u8
        }).collect();
        let chunk = proto::VoiceChunk { seq, pos: pos_dm, data };
        let mut payload = Vec::new();
        chunk.encode(&mut payload);
        let _ = net.sock.send(&proto::packet(proto::VOICE, &payload));
    }
}

pub fn voice_mix_audio(left: &mut [f32], right: &mut [f32]) {
    if !VOICE_SPEAKER_ENABLED.load(Ordering::Relaxed) { return; }
    let count = left.len().min(right.len());
    if count == 0 { return; }

    let mut queues = SPEAKER_QUEUES.lock().unwrap();
    if queues.is_empty() { return; }

    // Drop stale queues (silent for > 3s)
    let now = Instant::now();
    queues.retain(|(_, q)| now.duration_since(q.last_heard) < Duration::from_secs(3) || !q.samples.is_empty());

    // Mix active speakers into left and right audio channels sequentially with soft limiting
    for (_, q) in queues.iter_mut() {
        let take = count.min(q.samples.len());
        for i in 0..take {
            let s = q.samples[i];
            left[i] = (left[i] + s).clamp(-1.0, 1.0);
            right[i] = (right[i] + s).clamp(-1.0, 1.0);
        }
        q.samples.drain(..take);
    }
}

pub fn voice_active_speakers() -> Vec<String> {
    let now = Instant::now();
    let mut speakers = ACTIVE_SPEAKERS.lock().unwrap();
    speakers.retain(|(_, _, t)| now.duration_since(*t) < Duration::from_millis(1500));
    speakers.iter().map(|(_, name, _)| name.clone()).collect()
}

pub fn key_pressed(code: &str) {
    if code == "KeyH" {
        WANT_ENTER.store(true, Ordering::Relaxed);
    }
    if code == "KeyE" {
        AMMU_BUY_REQUESTED.store(true, Ordering::Relaxed);
    }
    if let Some(c) = code.strip_prefix("Key").filter(|c| c.len() == 1) {
        let mut t = TYPED.lock().unwrap();
        t.push_str(&c.to_ascii_lowercase());
        if t.len() > 32 {
            let cut = t.len() - 32;
            t.drain(..cut);
        }

        if t.ends_with("ineedmorebullets") {
            t.clear();
            if crate::input::muguet_is_multiplayer() {
                eprintln!("[anti-cheat] 'ineedmorebullets' cheat blocked in multiplayer");
            } else {
                WANT_BULLETS.store(true, Ordering::Relaxed);
            }
        }
    }
}

pub fn network_status() -> Option<String> {
    if std::env::var("MUGUET_HOST").is_err() && std::env::var("MUGUET_SERVER").is_err() { return None; }
    let net = match NET.get() {
        Some(Some(net)) => net,
        Some(None) => return Some("Online: invalid or unreachable server address".into()),
        None => return Some("Online: waiting for game startup".into()),
    };
    if net.full.load(Ordering::Relaxed) { return Some("Online: room full — retrying".into()); }
    if net.last_server.lock().unwrap().elapsed() > Duration::from_secs(proto::TIMEOUT_SECS) {
        return Some("Online: no server response — check IP / UDP 47520".into());
    }
    if net.my_id.lock().unwrap().is_some() {
        Some(format!("Online: connected · {} player(s)", net.peers.lock().unwrap().len() + 1))
    } else { Some("Online: connecting…".into()) }
}

fn net() -> Option<&'static Net> {
    NET.get_or_init(|| {
        let host = std::env::var("MUGUET_HOST").map(|v| v == "1").unwrap_or(false);
        if host {
            std::thread::Builder::new()
                .name("mp-server".into())
                .spawn(|| {
                    if let Err(e) = crate::server::run(proto::DEFAULT_PORT, proto::MAX_ROOM_PLAYERS) {
                        eprintln!("[mp] cannot host on port {}: {e}", proto::DEFAULT_PORT);
                    }
                })
                .ok();
        }
        let server = std::env::var("MUGUET_SERVER").ok().filter(|s| !s.trim().is_empty()).or(host.then(|| "127.0.0.1".to_string()))?;
        let server = if server.contains(':') { server } else { format!("{server}:{}", proto::DEFAULT_PORT) };
        let name = std::env::var("MUGUET_NAME").ok().filter(|s| !s.is_empty()).unwrap_or_else(|| std::env::var("USER").unwrap_or_else(|_| "Player".into()));
        let raw_room = std::env::var("MUGUET_ROOM").ok().filter(|s| !s.trim().is_empty()).unwrap_or_else(|| "default".into());
        let room = raw_room.trim().to_lowercase();
        let sock = match UdpSocket::bind("0.0.0.0:0").and_then(|s| s.connect(&server).map(|_| s)) {
            Ok(s) => s,
            Err(e) => {
                eprintln!("[mp] cannot reach {server}: {e}");
                return None;
            }
        };
        eprintln!("[mp] server {server}, room [{room}], playing as {name}");
        let net = Net { sock, name, room, last_server: Mutex::new(Instant::now()), full: AtomicBool::new(false), my_id: Mutex::new(None), peers: Mutex::new(HashMap::new()), shots: Mutex::new(Vec::new()), kills: Mutex::new(Vec::new()), taken: Mutex::new(Vec::new()), explosions: Mutex::new(Vec::new()), hits: Mutex::new(Vec::new()), car_hits: Mutex::new(Vec::new()), time: Mutex::new(None), pending: Mutex::new(Vec::new()), rel_seq: Mutex::new(0), rel_seen: Mutex::new(HashMap::new()), deaths: Mutex::new(Vec::new()) };
        let rx = net.sock.try_clone().expect("socket clone");
        std::thread::Builder::new().name("mp-net".into()).spawn(move || receive_loop(rx)).ok();
        Some(net)
    })
    .as_ref()
}

fn receive_loop(sock: UdpSocket) {
    let mut buf = [0u8; 1500];

    let _ = sock.set_read_timeout(Some(Duration::from_millis(50)));
    let mut last_hello = Instant::now() - Duration::from_secs(10);
    loop {
        let Some(net) = net() else { return };
        if net.last_server.lock().unwrap().elapsed() > Duration::from_secs(proto::TIMEOUT_SECS) {
            *net.my_id.lock().unwrap() = None;
        }
        let every = if net.my_id.lock().unwrap().is_none() { 1 } else { 2 };
        if last_hello.elapsed() > Duration::from_secs(every) {
            last_hello = Instant::now();
            let hello_payload = if net.room.is_empty() {
                net.name.as_bytes().to_vec()
            } else {
                format!("{}\0{}", net.room, net.name).into_bytes()
            };
            let _ = net.sock.send(&proto::packet(proto::HELLO, &hello_payload));
        }
        resend(net);
        let n = match sock.recv(&mut buf) {
            Ok(n) => n,
            Err(_) => continue,
        };
        let Some((kind, p)) = proto::parse(&buf[..n]) else { continue };
        let now = Instant::now();
        *net.last_server.lock().unwrap() = now;
        match kind {
            proto::REL if p.len() >= 4 => {
                let (from, seq) = (p[0], u16::from_le_bytes([p[1], p[2]]));
                let _ = net.sock.send(&proto::packet(proto::ACK, &[from, p[1], p[2]]));
                let new = {
                    let mut seen = net.rel_seen.lock().unwrap();
                    let list = seen.entry(from).or_default();
                    let new = !list.contains(&seq);
                    if new {
                        list.push_back(seq);
                        while list.len() > 256 {
                            list.pop_front();
                        }
                    }
                    new
                };
                if new {
                    let mut inner = vec![from];
                    inner.extend_from_slice(&p[4..]);
                    dispatch(net, p[3], &inner, now);
                }
            }

            proto::ACK if p.len() >= 4 => {
                if Some(p[1]) == *net.my_id.lock().unwrap() {
                    let seq = u16::from_le_bytes([p[2], p[3]]);
                    for m in net.pending.lock().unwrap().iter_mut().filter(|m| m.seq == seq) {
                        m.waiting.retain(|id| *id != p[0]);
                    }
                }
            }
            _ => dispatch(net, kind, p, now),
        }
    }
}

fn dispatch(net: &Net, kind: u8, p: &[u8], now: Instant) {
    {
        match kind {
            proto::WELCOME if !p.is_empty() => {
                net.full.store(false, Ordering::Relaxed);
                let mut id = net.my_id.lock().unwrap();
                if *id != Some(p[0]) {
                    eprintln!("[mp] joined as player {}", p[0]);
                }
                *id = Some(p[0]);
            }
            proto::FULL => {
                net.full.store(true, Ordering::Relaxed);
                eprintln!("[mp] server is full");
                std::thread::sleep(Duration::from_secs(5));
            }
            proto::NAME if !p.is_empty() => {
                let mut peers = net.peers.lock().unwrap();
                let name = proto::clean_name(&p[1..]);
                let peer = peers.entry(p[0]).or_insert_with(|| Peer::new(String::new()));
                if peer.name != name {
                    eprintln!("[mp] player {} is {name}", p[0]);
                    peer.name = name;
                }
            }
            proto::STATE if p.len() >= 5 => {
                let Some(state) = State::decode(&p[5..]) else { return };

                let sent = p.get(5 + proto::STATE_SIZE..9 + proto::STATE_SIZE).map(|b| u32::from_le_bytes(b.try_into().unwrap()));
                let mut peers = net.peers.lock().unwrap();
                let peer = peers.entry(p[0]).or_insert_with(|| Peer::new(format!("Player {}", p[0])));
                peer.last = now;
                let at = match sent {
                    Some(ms) => peer.clock.place(ms, now),
                    None => now,
                };

                let at = peer.snaps.back().map(|(t, _)| (*t + Duration::from_millis(1)).max(at)).unwrap_or(at);
                peer.snaps.push_back((at, state));
                while peer.snaps.len() > 20 {
                    peer.snaps.pop_front();
                }
            }
            proto::LOOK if !p.is_empty() => {
                if let Some(look) = Look::decode(&p[1..]) {
                    if let Some(peer) = net.peers.lock().unwrap().get_mut(&p[0]) {
                        peer.look = Some(look);
                    }
                }
            }
            proto::SHOT if !p.is_empty() => {
                if let Some(shot) = Shot::decode(&p[1..]) {
                    let mut shots = net.shots.lock().unwrap();
                    if shots.len() < 64 {
                        shots.push((p[0], shot));
                    }
                }
            }
            proto::HIT if p.len() >= 4 => {
                let mut h = net.hits.lock().unwrap();
                let weapon = if p.len() >= 8 { u32::from_le_bytes(p[4..8].try_into().unwrap()) } else { 0 };
                if h.len() < 64 {
                    h.push((p[0], p[1], u16::from_le_bytes([p[2], p[3]]), weapon));
                }
            }
            proto::VHIT if p.len() >= 7 => {
                let mut h = net.car_hits.lock().unwrap();
                let (tank, destroyed) = if p.len() >= 10 { (i16::from_le_bytes([p[7], p[8]]), p[9] & 1 != 0) } else { (0, false) };
                let engine = i16::from_le_bytes([p[2], p[3]]);
                let body = i16::from_le_bytes([p[4], p[5]]);
                let model = (p.len() >= 18).then(|| (u32::from_le_bytes(p[10..14].try_into().unwrap()), u32::from_le_bytes(p[14..18].try_into().unwrap())));
                // Legacy replica-death claims are not permission to explode
                // the owner's current (possibly different) vehicle.
                if !destroyed && p[0] != p[1] && [engine,body,tank].iter().all(|v| (0..=5000).contains(v)) && h.len() < 64 {
                    h.push((p[1], engine, body, p[6] & 0x3f, tank, model));
                }
            }
            proto::TIME if p.len() >= 5 => {
                let state = (p.len() >= 11).then(|| (p[5], p[6], f32::from_le_bytes(p[7..11].try_into().unwrap()))).filter(|s| s.2.is_finite());
                *net.time.lock().unwrap() = Some((p[0], [p[1], p[2], p[3], p[4]], state));
            }
            proto::VCTL if p.len() >= 5 => {
                if let Some(peer) = net.peers.lock().unwrap().get_mut(&p[0]) {
                    peer.vctl = Some([p[1], p[2], p[3], p[4]]);
                }
            }
            proto::VOICE if p.len() >= 9 => {
                let sender_id = p[0];
                if VOICE_SPEAKER_ENABLED.load(Ordering::Relaxed) {
                    if let Some(chunk) = proto::VoiceChunk::decode(&p[1..]) {
                        receive_voice_chunk(net, sender_id, chunk, now);
                    }
                }
            }
            proto::ROLE if p.len() >= 3 => {
                let status = PeerRole { wanted: p[1].min(5), jailed: p[2] & 1 != 0, cuffed: p[2] & 2 != 0 };
                let mut roles = ROLE_PEERS.lock().unwrap();
                roles.retain(|(_, _, at)| at.elapsed() < Duration::from_secs(30));
                match roles.iter_mut().find(|(id, ..)| *id == p[0]) {
                    Some(entry) => { entry.1 = status; entry.2 = now; }
                    None => roles.push((p[0], status, now)),
                }
            }
            proto::ARREST if p.len() >= 2 => {
                if Some(p[1]) == *net.my_id.lock().unwrap() {
                    ROLE_EVENTS.lock().unwrap().push(RoleEvent::Arrested { by: p[0] });
                }
            }
            proto::HEAL if p.len() >= 2 => {
                if Some(p[1]) == *net.my_id.lock().unwrap() {
                    ROLE_EVENTS.lock().unwrap().push(RoleEvent::Healed { by: p[0] });
                }
            }
            proto::CALL911 if p.len() >= 13 => {
                let f = |o: usize| f32::from_le_bytes(p[o..o + 4].try_into().unwrap());
                let pos = [f(1), f(5), f(9)];
                if pos.iter().all(|v| v.is_finite()) {
                    ROLE_EVENTS.lock().unwrap().push(RoleEvent::Call { by: p[0], pos });
                }
            }
            proto::ROB if p.len() >= 4 => {
                if Some(p[1]) == *net.my_id.lock().unwrap() {
                    let amount = u16::from_le_bytes([p[2], p[3]]).min(1000) as i32;
                    ROLE_EVENTS.lock().unwrap().push(RoleEvent::Robbed { by: p[0], amount });
                }
            }
            proto::PAID if p.len() >= 4 => {
                if Some(p[1]) == *net.my_id.lock().unwrap() {
                    let amount = u16::from_le_bytes([p[2], p[3]]).min(1000) as i32;
                    ROLE_EVENTS.lock().unwrap().push(RoleEvent::Paid { by: p[0], amount });
                }
            }
            proto::KILLFEED if p.len() >= 6 => {
                let mut d = net.deaths.lock().unwrap();
                if d.len() < 16 {
                    d.push((p[0], p[1], u32::from_le_bytes(p[2..6].try_into().unwrap())));
                }
            }
            proto::EXPLODE if p.len() >= 17 => {
                let f = |o: usize| f32::from_le_bytes(p[o..o + 4].try_into().unwrap());
                let (kind, pos) = (i32::from_le_bytes(p[1..5].try_into().unwrap()), [f(5), f(9), f(13)]);
                let mut ex = net.explosions.lock().unwrap();
                if ex.len() < 64 && pos.iter().all(|v| v.is_finite()) {
                    ex.push((p[0], kind, pos));
                }
            }
            proto::VLOOK if !p.is_empty() => {
                if let Some(l) = VehLook::decode(&p[1..]) {
                    if let Some(peer) = net.peers.lock().unwrap().get_mut(&p[0]) {
                        peer.vlook = Some(l);
                    }
                }
            }
            proto::TAKEN if p.len() >= 6 => {
                let mut taken = net.taken.lock().unwrap();
                if taken.len() < 64 {
                    taken.push((p[1], u32::from_le_bytes(p[2..6].try_into().unwrap())));
                }
            }
            proto::KILL if p.len() >= 6 => {
                let mut kills = net.kills.lock().unwrap();
                if kills.len() < 64 {
                    kills.push((p[1], u32::from_le_bytes(p[2..6].try_into().unwrap())));
                }
            }
            proto::POP if p.len() >= 2 => {
                let entries = proto::decode_pop(&p[1..]);

                let end = 2 + p[1] as usize * proto::POP_ENTRY_SIZE;
                let (part, parts) = match p.get(end..end + 2) {
                    Some(t) if t[1] >= 1 && t[0] < t[1] && (t[1] as usize) <= POP_PARTS => (t[0] as usize, t[1] as usize),
                    _ => (0, 1),
                };
                if let Some(peer) = net.peers.lock().unwrap().get_mut(&p[0]) {
                    peer.pop_parts[part] = Some((now, entries));
                    for k in parts..POP_PARTS {
                        peer.pop_parts[k] = None;
                    }
                    let mut all = Vec::new();
                    for (t, e) in peer.pop_parts.iter().flatten() {
                        if now.duration_since(*t) < Duration::from_millis(500) {
                            all.extend(e.iter().copied());
                        }
                    }
                    peer.pop = Some((now, all));
                }
            }
            proto::POPX if !p.is_empty() => {
                let entries = proto::decode_pop(&p[1..]);
                if let Some(peer) = net.peers.lock().unwrap().get_mut(&p[0]) {
                    peer.extras = Some((now, entries));
                }
            }
            proto::LEAVE if !p.is_empty() => {
                if p[0] == 0 {
                    *net.my_id.lock().unwrap() = None;
                } else if let Some(peer) = net.peers.lock().unwrap().remove(&p[0]) {
                    eprintln!("[mp] {} left", peer.name);
                }
            }
            _ => {}
        }
    }
}

#[derive(Default)]
struct Clock {
    gaps: VecDeque<f64>,

    offset: f64,

    delay: f64,
}

impl Clock {
    fn place(&mut self, sent_ms: u32, now: Instant) -> Instant {
        let start = *START.get_or_init(Instant::now);
        let local = now.duration_since(start).as_secs_f64() * 1000.0;
        let gap = local - sent_ms as f64;
        self.gaps.push_back(gap);
        while self.gaps.len() > 90 {
            self.gaps.pop_front();
        }
        self.offset = self.gaps.iter().copied().fold(f64::MAX, f64::min);

        let mut late: Vec<f64> = self.gaps.iter().map(|g| g - self.offset).collect();
        late.sort_by(|a, b| a.total_cmp(b));
        let p90 = late[(late.len() * 9 / 10).min(late.len() - 1)];
        let want = (p90 + SEND_EVERY.as_secs_f64() * 1000.0 + 12.0).clamp(45.0, 300.0);

        self.delay = if want > self.delay { want } else { self.delay + (want - self.delay) * 0.02 };
        let at_ms = (sent_ms as f64 + self.offset).max(0.0);
        start + Duration::from_secs_f64(at_ms / 1000.0)
    }
    fn delay(&self) -> Duration {
        Duration::from_secs_f64(if self.delay > 0.0 { self.delay } else { INTERP_DELAY.as_secs_f64() * 1000.0 } / 1000.0)
    }
}

fn lerp_angle(x: f32, y: f32, k: f32) -> f32 {
    let d = (y - x + 540.0).rem_euclid(360.0) - 180.0;
    x + d * k
}

fn sample(peer: &Peer, at: Instant) -> Option<State> {
    let snaps = &peer.snaps;
    let (t_last, last) = *snaps.back()?;
    if at >= t_last {
        let dt = (at - t_last).as_secs_f32().min(0.25);
        let mut s = last;
        for i in 0..3 {
            s.pos[i] += s.vel[i] * dt;
            s.veh_pos[i] += s.veh_vel[i] * dt;
        }
        return Some(s);
    }
    let i = snaps.iter().position(|(t, _)| *t > at)?;
    if i == 0 {
        return Some(snaps[0].1);
    }
    let ((t0, a), (t1, b)) = (snaps[i - 1], snaps[i]);
    if a.in_vehicle() != b.in_vehicle() || a.veh_model != b.veh_model || a.veh_key != b.veh_key {
        return Some(b);
    }
    let k = ((at - t0).as_secs_f32() / (t1 - t0).as_secs_f32().max(1e-3)).clamp(0.0, 1.0);
    let lerp = |x: [f32; 3], y: [f32; 3]| [x[0] + (y[0] - x[0]) * k, x[1] + (y[1] - x[1]) * k, x[2] + (y[2] - x[2]) * k];
    let mut s = b;
    s.pos = lerp(a.pos, b.pos);
    s.vel = lerp(a.vel, b.vel);
    s.heading = lerp_angle(a.heading, b.heading, k);
    s.veh_pos = lerp(a.veh_pos, b.veh_pos);
    s.veh_vel = lerp(a.veh_vel, b.veh_vel);
    s.veh_rot = [lerp_angle(a.veh_rot[0], b.veh_rot[0], k), lerp_angle(a.veh_rot[1], b.veh_rot[1], k), lerp_angle(a.veh_rot[2], b.veh_rot[2], k)];
    Some(s)
}

#[cfg(test)]
mod interpolation_tests {
    use super::*;

    #[test]
    fn switching_identical_vehicle_models_does_not_interpolate_between_cars() {
        let start = Instant::now();
        let mut peer = Peer::new("test".into());
        let a = State { flags: proto::FLAG_IN_VEHICLE, veh_model: 123, veh_key: 77, veh_pos: [0.; 3], ..State::default() };
        let b = State { veh_key: 78, veh_pos: [100.; 3], ..a };
        peer.snaps.push_back((start, a));
        peer.snaps.push_back((start + Duration::from_millis(100), b));
        let sampled = sample(&peer, start + Duration::from_millis(50)).unwrap();
        assert_eq!(sampled.veh_key, 78);
        assert_eq!(sampled.veh_pos, [100.; 3]);
    }
}

#[derive(Default, Clone, Copy)]
struct Walker {
    target: [f32; 3],

    blend: f32,
    since: Option<Instant>,

    aim: Option<([f32; 3], Instant)>,
}

#[derive(Default)]
struct Avatar {
    ped: i32,
    ped_model: u32,
    veh: i32,
    veh_model: u32,
    veh_key: u32,
    veh_colours: [u8; 2],

    veh_damage: (i16, i16, i16, u8, u8, bool),
    veh_look: Option<VehLook>,

    veh_wait: Option<Instant>,

    hit: u16,

    bullet: u16,

    car_hit: (i16, i16, u8, i16),
    blip: i32,
    blip_is_entity: bool,
    walk: Walker,
    weapon: u32,
    dead: bool,
    look: Option<Look>,
    aim_until: Option<Instant>,

    veh_spin: f32,

    ragdoll: Option<Instant>,
    /// When the remote player died here; the body is removed a few seconds later.
    dead_since: Option<Instant>,

    entering: Option<(i32, Instant)>,

    leaving_until: Option<Instant>,

    vctl: Option<[u8; 4]>,
    horn_at: Option<Instant>,
}

struct Mirror {
    is_vehicle: bool,

    dead: bool,
    ent: i32,
    driver: i32,
    walk: Walker,
    seen: Instant,

    still: bool,
}

struct Game {
    host: u64,
    host_name: String,
    host_seen: Instant,
    frame_start: Option<Instant>,
    last_send: Instant,
    last_look: Instant,
    sent_look: Option<(Instant, Look)>,
    last_shot: Instant,

    last_impact: [f32; 3],

    last_swing: Instant,

    my_car: i32,

    was_dead: bool,
    was_enter_pressed: bool,
    last_enter_task: Option<Instant>,
    last_tidy: Instant,
    last_pop: Instant,
    sent_vlook: Option<(Instant, VehLook)>,
    sent_vctl: Option<(Instant, [u8; 4])>,

    marker: Option<(Instant, bool)>,

    hurt: Vec<(u8, Instant)>,
    last_vlook: Instant,
    last_time: Instant,

    weather: Option<u8>,

    clock_seen: Option<i32>,

    taken: std::collections::HashSet<(u8, u32)>,
    seq: u32,
    avatars: HashMap<u8, Avatar>,

    mirrors: HashMap<(u8, u32), Mirror>,

    pop_owner: Option<u8>,

    met: bool,
    unfreeze_at: Option<Instant>,
    spawn_shield: Option<Instant>,
    last_player_loc_feed: Instant,
}

struct ShopBlip {
    pos: [f32; 3],
    sprite: i32,
    colour: i32,
}

const WORLD_SHOPS: &[ShopBlip] = &[
    // Ammu-Nation (Vũ khí / Súng đạn)
    ShopBlip { pos: [16.9, -1107.8, 29.8], sprite: 110, colour: 2 },
    ShopBlip { pos: [253.9, -50.0, 69.9], sprite: 110, colour: 2 },
    ShopBlip { pos: [-1305.4, -393.4, 36.7], sprite: 110, colour: 2 },
    ShopBlip { pos: [-662.3, -935.3, 21.8], sprite: 110, colour: 2 },
    ShopBlip { pos: [842.4, -1033.4, 28.2], sprite: 110, colour: 2 },
    ShopBlip { pos: [810.2, -2157.6, 29.6], sprite: 110, colour: 2 },
    ShopBlip { pos: [1693.4, 3759.5, 34.7], sprite: 110, colour: 2 },
    ShopBlip { pos: [-330.2, 6083.9, 31.5], sprite: 110, colour: 2 },
    ShopBlip { pos: [-3171.5, 1087.9, 20.8], sprite: 110, colour: 2 },
    ShopBlip { pos: [252.3, 259.7, 105.7], sprite: 110, colour: 2 },

    // Los Santos Customs (Sửa xe / Độ xe)
    ShopBlip { pos: [-1155.5, -2005.4, 13.2], sprite: 72, colour: 0 },
    ShopBlip { pos: [-365.1, -131.8, 38.7], sprite: 72, colour: 0 },
    ShopBlip { pos: [731.8, -1088.8, 22.2], sprite: 72, colour: 0 },
    ShopBlip { pos: [1175.0, 2640.0, 37.8], sprite: 72, colour: 0 },
    ShopBlip { pos: [108.8, 6626.3, 31.8], sprite: 72, colour: 0 },

    // Bệnh viện (Hospitals)
    ShopBlip { pos: [340.5, -1396.8, 32.5], sprite: 61, colour: 1 },
    ShopBlip { pos: [-449.6, -340.8, 34.5], sprite: 61, colour: 1 },
    ShopBlip { pos: [1839.2, 3672.9, 34.3], sprite: 61, colour: 1 },

    // Đồn Cảnh Sát (Police)
    ShopBlip { pos: [426.0, -981.8, 30.7], sprite: 60, colour: 38 },
    ShopBlip { pos: [638.5, 1.5, 44.7], sprite: 60, colour: 38 },
    ShopBlip { pos: [1848.7, 3689.9, 34.3], sprite: 60, colour: 38 },
    ShopBlip { pos: [-442.2, 6012.3, 31.7], sprite: 60, colour: 38 },

    // Cửa hàng Quần Áo (Clothes)
    ShopBlip { pos: [125.8, -223.8, 54.6], sprite: 73, colour: 0 },
    ShopBlip { pos: [-709.8, -153.1, 37.4], sprite: 73, colour: 0 },
    ShopBlip { pos: [-1192.8, -768.4, 17.3], sprite: 73, colour: 0 },
    ShopBlip { pos: [75.3, -1392.7, 29.4], sprite: 73, colour: 0 },
    ShopBlip { pos: [1693.8, 3760.1, 34.7], sprite: 73, colour: 0 },

    // Tiệm Cắt Tóc (Barber)
    ShopBlip { pos: [-32.9, -152.3, 57.1], sprite: 71, colour: 0 },
    ShopBlip { pos: [-814.3, -183.8, 37.6], sprite: 71, colour: 0 },
    ShopBlip { pos: [136.8, -1708.4, 29.3], sprite: 71, colour: 0 },
    ShopBlip { pos: [1931.5, 3729.7, 32.8], sprite: 71, colour: 0 },

    // Cửa Hàng Tiện Lợi 24/7 (Stores)
    ShopBlip { pos: [373.9, 325.8, 103.6], sprite: 52, colour: 2 },
    ShopBlip { pos: [-48.5, -1757.5, 29.4], sprite: 52, colour: 2 },
    ShopBlip { pos: [-707.5, -914.3, 19.2], sprite: 52, colour: 2 },
    ShopBlip { pos: [1961.5, 3740.7, 32.3], sprite: 52, colour: 2 },
];

static WORLD_BLIPS_DONE: AtomicBool = AtomicBool::new(false);
pub static TOGGLE_FP_REQUESTED: AtomicBool = AtomicBool::new(false);

pub fn request_toggle_first_person() {
    TOGGLE_FP_REQUESTED.store(true, Ordering::Relaxed);
}

#[no_mangle]
pub extern "C" fn muguet_toggle_first_person() {
    request_toggle_first_person();
}

fn init_world_blips_once(c: &mut Cmd<'_, '_>) {
    let ped = c.i("PlayerPedId", &[]);
    if ped == 0 || !c.exists(ped) { return; }
    if WORLD_BLIPS_DONE.swap(true, Ordering::Relaxed) { return; }

    for shop in WORLD_SHOPS {
        let coord_arg = c.vec_arg(0, shop.pos);
        let mut blip = c.i("AddBlipForCoord", &[coord_arg]);
        if blip == 0 { blip = c.i("AddBlipForCoord2", &[coord_arg]); }
        if blip != 0 {
            let _ = c.i("SetBlipSprite", &[i(blip), i(shop.sprite)]);
            let _ = c.i("SetBlipSprite2", &[i(blip), i(shop.sprite)]);
            let _ = c.i("SetBlipColour", &[i(blip), i(shop.colour)]);
            let _ = c.i("SetBlipColour2", &[i(blip), i(shop.colour)]);
            let _ = c.i("SetBlipScale", &[i(blip), f(0.75)]);
            let _ = c.i("SetBlipScale2", &[i(blip), f(0.75)]);
            let _ = c.i("SetBlipAsShortRange", &[i(blip), b(true)]);
            let _ = c.i("SetBlipAsShortRange2", &[i(blip), b(true)]);
        }
    }
    eprintln!("[blips] initialized {} world shop blips on minimap", WORLD_SHOPS.len());
}

fn update_camera_mode(c: &mut Cmd<'_, '_>) {
    if TOGGLE_FP_REQUESTED.swap(false, Ordering::Relaxed) {
        let mut cur = c.i("GetFollowPedCamViewMode", &[]);
        if cur == 0 { cur = c.i("GetFollowPedCamViewMode2", &[]); }
        let target = if cur == 4 { 1 } else { 4 };
        let _ = c.i("SetFollowPedCamViewMode", &[i(target)]);
        let _ = c.i("SetFollowPedCamViewMode2", &[i(target)]);
        let _ = c.i("SetFollowVehicleCamViewMode", &[i(target)]);
        let _ = c.i("SetFollowVehicleCamViewMode2", &[i(target)]);
        eprintln!("[camera] view mode toggled: {cur} -> {target}");
    }
}

static STORY_START_WARPED: AtomicBool = AtomicBool::new(false);

fn process_story_mode_startup(c: &mut Cmd<'_, '_>) {
    let mode = std::env::var("MUGUET_MODE").unwrap_or_default();
    let is_mp = crate::input::muguet_is_multiplayer();
    if is_mp || mode != "story" { return; }

    let ped = c.i("PlayerPedId", &[]);
    if ped == 0 || !c.exists(ped) { return; }

    // Central Los Santos (Legion Square): open, safe, no locked iron gates, no mission script cutscene crashes
    let spawn_pos = [215.0f32, -915.0f32, 30.6f32];

    if !STORY_START_WARPED.swap(true, Ordering::Relaxed) {
        let cur = c.v("GetEntityCoords", &[i(ped), b(false)]);
        // North Yankton heist coordinates are around x: 5300, y: -5200 (or initial 0,0,0) or mansion trap
        let in_yankton = cur[0] > 2000.0 || cur[1] < -3500.0 || (cur[0].abs() < 1.0 && cur[1].abs() < 1.0);
        let in_mansion_trap = (cur[0] - (-14.0)).abs() < 30.0 && (cur[1] - 525.0).abs() < 30.0;
        if in_yankton || in_mansion_trap {
            let pos_arg = c.vec_arg(0, spawn_pos);
            c.i("SetEntityCoordsNoOffset", &[i(ped), pos_arg, b(false), b(false), b(false)]);
            c.i("SetEntityHeading", &[i(ped), f(0.0)]);

            // Show HUD notification to player
            let text = "zema Server · Story Mode: Los Santos (Legion Square)";
            c.c_str(S_TEXT, "STRING");
            c.c_str(S_NAME, text);
            let _ = c.i("BeginTheFeedPost", &[c.ptr(S_TEXT)]);
            let _ = c.i("AddTextComponentSubStringPlayerName", &[c.ptr(S_NAME)]);
            let _ = c.i("EndTheFeedPostTicker", &[b(false), b(true)]);

            eprintln!("[story] skipped prologue heist -> spawned at Legion Square: {spawn_pos:?}");
        }
    }
}

static GAME: Mutex<Option<Game>> = Mutex::new(None);

const PREFERRED_SCRIPTS: &[&str] = &["main_persistent", "standard_global_reg", "main", "sandbox", "freemode"];

pub fn script_tick(caller: &mut Caller<'_, HostState>, thread: u64, tls: u64) -> anyhow::Result<()> {
    let net = net();
    let mem = &crate::RT.get().unwrap().mem;
    let name = read_cstr(mem, thread + THREAD_NAME);
    let mut guard = GAME.lock().unwrap();
    let game = guard.get_or_insert_with(|| Game {
        host: 0,
        host_name: String::new(),
        host_seen: Instant::now(),
        frame_start: None,
        last_send: Instant::now(),
        last_look: Instant::now(),
        sent_look: None,
        last_shot: Instant::now(),
        last_impact: [0.0; 3],
        last_swing: Instant::now(),
        my_car: 0,
        was_dead: false,
        was_enter_pressed: false,
        last_enter_task: None,
        last_tidy: Instant::now(),
        last_pop: Instant::now(),
        sent_vlook: None,
        sent_vctl: None,
        marker: None,
        hurt: Vec::new(),
        last_vlook: Instant::now(),
        last_time: Instant::now(),
        weather: None,
        clock_seen: None,
        taken: std::collections::HashSet::new(),
        seq: 0,
        avatars: HashMap::new(),
        mirrors: HashMap::new(),
        pop_owner: None,
        met: false,
        unfreeze_at: None,
        spawn_shield: Some(Instant::now() + Duration::from_secs(8)),
        last_player_loc_feed: Instant::now() - Duration::from_secs(30),
    });

    let is_host = thread == game.host && name == game.host_name;
    if !is_host {
        let current_rank = PREFERRED_SCRIPTS.iter().position(|s| *s == game.host_name).unwrap_or(usize::MAX);
        let rank = PREFERRED_SCRIPTS.iter().position(|s| *s == name).unwrap_or(usize::MAX);
        let host_gone = game.host_seen.elapsed() > Duration::from_secs(2);
        let started = game.frame_start.get_or_insert_with(Instant::now).elapsed() > Duration::from_secs(5);
        if (rank < current_rank && rank != usize::MAX) || (host_gone && (rank != usize::MAX || started)) {
            game.host = thread;
            game.host_name = name.clone();

            game.avatars.clear();
            game.mirrors.clear();
        } else {
            return Ok(());
        }
    }
    game.host_seen = Instant::now();

    let active = tls + ACTIVE_THREAD_TLS;
    let saved = read_u64(mem, active).unwrap_or(0);
    write_u64(mem, active, thread);
    let sp = call(caller, "emscripten_stack_get_current", &[]).map(|v| v.unwrap_i64()).unwrap_or(0);
    let scratch = call(caller, "_emscripten_stack_alloc", &[Val::I64(SCRATCH)]).map(|v| v.unwrap_i64() as u64).unwrap_or(0);
    if scratch != 0 {
        let mut c = Cmd { caller, scratch };
        init_world_blips_once(&mut c);
        // Before any weapon strip/re-grant runs, so bought weapons come back after a relaunch.
        load_wallet_once();
        update_camera_mode(&mut c);
        #[cfg(not(feature = "native-port"))]
        process_story_mode_startup(&mut c);

        if WANT_BULLETS.swap(false, Ordering::Relaxed) {
            more_bullets(&mut c);
        }

        if crate::pad::ACTIVE.load(Ordering::Relaxed) || cfg!(target_os = "ios") {
            let ped = c.i("PlayerPedId", &[]);
            let in_car = ped != 0 && c.exists(ped) && c.i("IsPedInAnyVehicle", &[i(ped), b(false)]) != 0;
            crate::pad::IN_VEHICLE.store(in_car, Ordering::Relaxed);

            static HORN_AT: Mutex<Option<Instant>> = Mutex::new(None);
            let mut horn_at = HORN_AT.lock().unwrap();
            if in_car && crate::pad::horn_held() && horn_at.map(|t| t.elapsed() > Duration::from_millis(250)).unwrap_or(true) {
                let veh = c.i("GetVehiclePedIsIn", &[i(ped), b(false)]);
                c.i("SoundCarHorn", &[i(veh), i(350), i(proto::joaat("HELDDOWN") as i32), b(false)]);
                *horn_at = Some(Instant::now());
            }
        }

        let ped = c.i("PlayerPedId", &[]);
        if ped != 0 && c.exists(ped) {
            let my_pos = c.v("GetEntityCoords", &[i(ped), b(false)]);
            process_sandbox_and_mp_checks(&mut c, ped, my_pos);
        }

        if let Some(net) = net {
            frame(&mut c, game, net);
        }
    }
    if sp != 0 {
        let _ = call(caller, "_emscripten_stack_restore", &[Val::I64(sp)]);
    }
    write_u64(mem, active, saved);
    Ok(())
}

fn call(caller: &mut Caller<'_, HostState>, name: &str, args: &[Val]) -> Option<Val> {
    let f = caller.get_export(name)?.into_func()?;
    let ty = f.ty(&mut *caller);
    let args = crate::coerce_args(args, &ty);
    let mut out: Vec<Val> = ty.results().map(|t| crate::default_val(&t)).collect();
    if let Err(e) = f.call(&mut *caller, &args, &mut out) {
        eprintln!("[mp] {name} trapped: {e}");
        return None;
    }
    Some(out.into_iter().next().unwrap_or(Val::I32(0)))
}

struct Cmd<'a, 'b> {
    caller: &'a mut Caller<'b, HostState>,
    scratch: u64,
}

/// Calls "mp:<cmd>" without allocating a new String for every engine call (hundreds per frame online).
fn call_mp(caller: &mut Caller<'_, HostState>, cmd: &str, args: &[Val]) -> Option<Val> {
    thread_local! { static NAME: std::cell::RefCell<String> = std::cell::RefCell::new(String::with_capacity(64)); }
    NAME.with(|name| match name.try_borrow_mut() {
        Ok(mut name) => {
            name.clear();
            name.push_str("mp:");
            name.push_str(cmd);
            call(caller, &name, args)
        }
        Err(_) => call(caller, &format!("mp:{cmd}"), args),
    })
}

impl Cmd<'_, '_> {
    fn i(&mut self, cmd: &str, args: &[Val]) -> i32 {
        match call_mp(self.caller, cmd, args) {
            Some(Val::I32(v)) => v,
            Some(Val::I64(v)) => v as i32,
            _ => 0,
        }
    }
    fn f(&mut self, cmd: &str, args: &[Val]) -> f32 {
        match call_mp(self.caller, cmd, args) {
            Some(Val::F32(v)) => f32::from_bits(v),
            _ => 0.0,
        }
    }
    fn mem(&self) -> &'static crate::SharedMemory {
        &crate::RT.get().unwrap().mem
    }
    fn read_i32(&self, off: u64) -> i32 {
        read_u32(self.mem(), self.scratch + off).unwrap_or(0) as i32
    }
    fn read_f32(&self, off: u64) -> f32 {
        f32::from_bits(read_u32(self.mem(), self.scratch + off).unwrap_or(0))
    }

    fn v(&mut self, cmd: &str, args: &[Val]) -> [f32; 3] {
        let mut full = vec![Val::I64(self.scratch as i64)];
        full.extend_from_slice(args);
        call_mp(self.caller, cmd, &full);
        [self.read_f32(0), self.read_f32(8), self.read_f32(16)]
    }

    fn v_packed(&mut self, cmd: &str, args: &[Val]) -> [f32; 3] {
        let mut full = vec![Val::I64(self.scratch as i64)];
        full.extend_from_slice(args);
        call_mp(self.caller, cmd, &full);
        [self.read_f32(0), self.read_f32(4), self.read_f32(8)]
    }

    fn vec_arg(&self, slot: u64, v: [f32; 3]) -> Val {
        let p = self.scratch + 32 * slot;
        let m = self.mem();
        for (i, c) in v.iter().enumerate() {
            crate::write_u32(m, p + 8 * i as u64, c.to_bits());
            crate::write_u32(m, p + 8 * i as u64 + 4, 0);
        }
        Val::I64(p as i64)
    }

    fn ref_arg(&self, v: i32) -> Val {
        crate::write_u32(self.mem(), self.scratch + S_INT, v as u32);
        Val::I64((self.scratch + S_INT) as i64)
    }

    fn c_str(&self, off: u64, s: &str) {
        // S_TEXT has 20 bytes before S_NAME; S_NAME is the last slot of the scratch block.
        let limit = match off { S_TEXT => 19, S_NAME => 200, _ => 60 };
        let mut end = s.len().min(limit);
        while !s.is_char_boundary(end) { end -= 1; }
        let mut b = s.as_bytes()[..end].to_vec();
        b.push(0);
        crate::write_bytes(self.mem(), self.scratch + off, &b);
    }
    fn ptr(&self, off: u64) -> Val {
        Val::I64((self.scratch + off) as i64)
    }
    fn exists(&mut self, ent: i32) -> bool {
        ent != 0 && self.i("DoesEntityExist", &[i(ent)]) != 0
    }

    fn nearby(&mut self, cmd: &str, ped: i32, off: u64, extra: &[Val]) -> Vec<i32> {
        let m = self.mem();
        write_u64(m, self.scratch + off, NEARBY_MAX);
        let mut args = vec![i(ped), self.ptr(off)];
        args.extend_from_slice(extra);
        let n = (self.i(cmd, &args).max(0) as u64).min(NEARBY_MAX);
        (0..n).map(|k| read_u32(m, self.scratch + off + 8 + 8 * k).unwrap_or(0) as i32).filter(|e| *e != 0).collect()
    }

    fn feed(&mut self, text: &str) {
        self.c_str(S_TEXT, "STRING");
        let _ = self.i("BeginTheFeedPost", &[self.ptr(S_TEXT)]);
        // Vietnamese lines are long in bytes: send them as several components (each ≤ 96 bytes,
        // whole characters) instead of cutting the text at 60 bytes, mid-character.
        let mut rest = text;
        while !rest.is_empty() {
            let mut end = rest.len().min(96);
            while !rest.is_char_boundary(end) { end -= 1; }
            self.c_str(S_NAME, &rest[..end]);
            let _ = self.i("AddTextComponentSubStringPlayerName", &[self.ptr(S_NAME)]);
            rest = &rest[end..];
        }
        let _ = self.i("EndTheFeedPostTicker", &[b(false), b(true)]);
    }

    fn play_frontend(&mut self, sound: &str, sound_set: &str) {
        // Separate 70-byte slots: a sound set name written to S_TEXT ran into S_NAME and broke the sound.
        self.c_str(S_DICT, sound);
        self.c_str(S_CLIP, sound_set);
        let _ = self.i("PlaySoundFrontend", &[i(-1), self.ptr(S_DICT), self.ptr(S_CLIP), b(true)]);
    }
}

fn b(v: bool) -> Val {
    Val::I32(v as i32)
}
fn f(v: f32) -> Val {
    Val::F32(v.to_bits())
}
fn i(v: i32) -> Val {
    Val::I32(v)
}

fn dist(a: [f32; 3], b: [f32; 3]) -> f32 {
    ((a[0] - b[0]).powi(2) + (a[1] - b[1]).powi(2) + (a[2] - b[2]).powi(2)).sqrt()
}

fn weapon(name: &str) -> u32 {
    proto::joaat(name)
}

fn weapon_name(hash: u32) -> Option<&'static str> {
    const NAMES: &[(&str, &str)] = &[
        ("weapon_unarmed", "fists"), ("weapon_knife", "knife"), ("weapon_bat", "bat"), ("weapon_crowbar", "crowbar"),
        ("weapon_golfclub", "golf club"), ("weapon_hammer", "hammer"), ("weapon_nightstick", "nightstick"),
        ("weapon_pistol", "pistol"), ("weapon_combatpistol", "combat pistol"), ("weapon_appistol", "AP pistol"),
        ("weapon_pistol50", "pistol .50"), ("weapon_stungun", "taser"), ("weapon_microsmg", "micro SMG"), ("weapon_smg", "SMG"),
        ("weapon_assaultsmg", "assault SMG"), ("weapon_assaultrifle", "assault rifle"), ("weapon_carbinerifle", "carbine rifle"),
        ("weapon_advancedrifle", "advanced rifle"), ("weapon_mg", "MG"), ("weapon_combatmg", "combat MG"),
        ("weapon_pumpshotgun", "pump shotgun"), ("weapon_sawnoffshotgun", "sawed-off"), ("weapon_assaultshotgun", "assault shotgun"),
        ("weapon_bullpupshotgun", "bullpup shotgun"), ("weapon_sniperrifle", "sniper rifle"), ("weapon_heavysniper", "heavy sniper"),
        ("weapon_grenadelauncher", "grenade launcher"), ("weapon_rpg", "RPG"), ("weapon_minigun", "minigun"),
        ("weapon_grenade", "grenade"), ("weapon_stickybomb", "sticky bomb"), ("weapon_molotov", "molotov"),
        ("weapon_run_over_by_car", "run over"), ("weapon_rammed_by_car", "rammed"), ("weapon_explosion", "explosion"),
        ("vehicle_weapon_tank", "tank"), ("weapon_fall", "fall"), ("weapon_fire", "fire"),
    ];
    NAMES.iter().find(|(n, _)| proto::joaat(n) == hash).map(|(_, s)| *s)
}

fn more_bullets(c: &mut Cmd) {
    const ALL: &[&str] = &[
        "weapon_knife", "weapon_bat", "weapon_pistol", "weapon_combatpistol", "weapon_appistol", "weapon_pistol50",
        "weapon_microsmg", "weapon_smg", "weapon_assaultsmg", "weapon_assaultrifle", "weapon_carbinerifle",
        "weapon_advancedrifle", "weapon_mg", "weapon_combatmg", "weapon_pumpshotgun", "weapon_sawnoffshotgun",
        "weapon_assaultshotgun", "weapon_sniperrifle", "weapon_heavysniper", "weapon_grenadelauncher",
        "weapon_rpg", "weapon_minigun", "weapon_grenade", "weapon_stickybomb", "weapon_molotov",
    ];
    let ped = c.i("PlayerPedId", &[]);
    if ped == 0 {
        return;
    }
    for w in ALL {
        c.i("GiveWeaponToPed", &[i(ped), i(weapon(w) as i32), i(9999), b(false), b(false)]);
    }
    c.i("SetPedInfiniteAmmoClip", &[i(ped), b(true)]);
    c.i("SetCurrentPedWeapon", &[i(ped), i(weapon("weapon_carbinerifle") as i32), b(true)]);
    eprintln!("[mp] more bullets");
    play_sound("morebullets.mp3");
}

fn play_sound(name: &str) {
    if std::env::var("MUGUET_MUTE").map(|v| v == "1").unwrap_or(false) {
        return;
    }
    let mut places: Vec<std::path::PathBuf> = crate::config::bundled_resources().into_iter().map(|r| r.join(name)).collect();
    if let Ok(exe) = std::env::current_exe() {
        places.extend(exe.ancestors().map(|d| d.join("assets").join(name)));
    }
    if let Some(path) = places.into_iter().find(|p| p.exists()) {
        let _ = std::process::Command::new("/usr/bin/afplay").arg(path).spawn();
    }
}

fn receive_voice_chunk(net: &Net, sender_id: u8, chunk: proto::VoiceChunk, now: Instant) {
    // The chunk's position is in decimetres as i16, so it saturates beyond ±3.2 km (Sandy Shores,
    // Paleto Bay): two players up north would "hear" each other across the map. Prefer the sender's
    // latest synced position and keep the chunk's only as a fallback.
    let (sender_name, synced_pos) = net.peers.lock().unwrap().get(&sender_id)
        .map(|p| (p.name.clone(), p.snaps.back().map(|(_, s)| if s.in_vehicle() { s.veh_pos } else { s.pos })))
        .unwrap_or_else(|| (format!("Player {sender_id}"), None));

    let [sender_x, sender_y, sender_z] = synced_pos.unwrap_or([
        chunk.pos[0] as f32 / 10.0,
        chunk.pos[1] as f32 / 10.0,
        chunk.pos[2] as f32 / 10.0,
    ]);

    let my_pos = LOCAL_POS.lock().unwrap().unwrap_or([0.0, 0.0, 0.0]);
    let dx = my_pos[0] - sender_x;
    let dy = my_pos[1] - sender_y;
    let dz = my_pos[2] - sender_z;
    let dist = (dx * dx + dy * dy + dz * dz).sqrt();

    // Strict Proximity Voice Chat: silent beyond 35 meters
    if dist > 35.0 {
        return;
    }

    // 0m - 6m: 100% full volume; 6m - 35m: smooth attenuation down to 0%
    let volume = if dist <= 6.0 {
        1.0
    } else {
        (1.0 - (dist - 6.0) / (35.0 - 6.0)).clamp(0.0, 1.0)
    };

    let incoming_samples: Vec<f32> = chunk.data.iter().map(|&b| {
        let normalized = (b as f32 - 128.0) / 128.0;
        normalized * volume
    }).collect();

    let mut queues = SPEAKER_QUEUES.lock().unwrap();
    let q = if let Some(idx) = queues.iter().position(|(id, _)| *id == sender_id) {
        &mut queues[idx].1
    } else {
        queues.push((sender_id, SpeakerQueue {
            samples: VecDeque::with_capacity(9600),
            last_heard: now,
        }));
        &mut queues.last_mut().unwrap().1
    };
    q.last_heard = now;
    q.samples.extend(incoming_samples);
    // Keep max 150ms buffer (7200 samples @ 48kHz) to prevent latency buildup
    if q.samples.len() > 7200 {
        let drop_count = q.samples.len() - 7200;
        q.samples.drain(..drop_count);
    }

    let mut speakers = ACTIVE_SPEAKERS.lock().unwrap();
    if let Some(entry) = speakers.iter_mut().find(|(id, _, _)| *id == sender_id) {
        entry.1 = sender_name;
        entry.2 = now;
    } else {
        speakers.push((sender_id, sender_name, now));
    }
}


// ---- Roleplay: police arrest wanted players, medics heal, kills make you wanted ------------------
// The role is the "[Cảnh sát] " / "[Bác sĩ] " ... prefix the Online settings add to the player name,
// so every client knows everyone's role without a protocol change. Wanted stars, arrests and heals
// travel as ROLE / ARREST / HEAL packets that the existing server already relays.

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Role { Civilian, Police, Medic, Gang, Driver }

fn role_of(name: &str) -> Role {
    let name = name.trim_start();
    if name.starts_with("[Cảnh sát]") { Role::Police }
    else if name.starts_with("[Bác sĩ]") { Role::Medic }
    else if name.starts_with("[Băng đảng]") { Role::Gang }
    else if name.starts_with("[Tài xế]") { Role::Driver }
    else { Role::Civilian }
}

fn my_role() -> Role {
    match NET.get() { Some(Some(net)) => role_of(&net.name), _ => Role::Civilian }
}

/// Police equipment, kept by the anti-cheat and given back after death.
const POLICE_WEAPONS: &[(&str, i32)] = &[("weapon_stungun", 100), ("weapon_nightstick", 1), ("weapon_combatpistol", 120), ("weapon_flashlight", 1)];

fn role_weapon_allowed(hash: u32) -> bool {
    my_role() == Role::Police && POLICE_WEAPONS.iter().any(|(name, _)| weapon(name) == hash)
}

fn grant_role_loadout(c: &mut Cmd, ped: i32) {
    if my_role() != Role::Police { return; }
    for &(name, ammo) in POLICE_WEAPONS {
        let _ = c.i("GiveWeaponToPed", &[i(ped), i(weapon(name) as i32), i(ammo), b(false), b(false)]);
    }
    let _ = c.i("SetPedArmour", &[i(ped), i(100)]);
}

#[derive(Clone, Copy, Default)]
struct PeerRole { wanted: u8, jailed: bool, cuffed: bool }

static ROLE_PEERS: Mutex<Vec<(u8, PeerRole, Instant)>> = Mutex::new(Vec::new());

fn peer_role(id: u8) -> PeerRole {
    ROLE_PEERS.lock().unwrap().iter()
        .find(|(peer, _, at)| *peer == id && at.elapsed() < Duration::from_secs(5))
        .map(|(_, role, _)| *role).unwrap_or_default()
}

enum RoleEvent {
    Arrested { by: u8 },
    Healed { by: u8 },
    Call { by: u8, pos: [f32; 3] },
    Robbed { by: u8, amount: i32 },
    Paid { by: u8, amount: i32 },
}
static ROLE_EVENTS: Mutex<Vec<RoleEvent>> = Mutex::new(Vec::new());

#[derive(Default)]
struct MyRole {
    wanted: u8,
    last_crime: Option<Instant>,
    cuffed_until: Option<Instant>,
    jail_until: Option<Instant>,
    jail_secs: u64,
    last_broadcast: Option<Instant>,
    last_jail_note: Option<Instant>,
    last_blips: Option<Instant>,
    loadout_given: bool,
    intro_shown: bool,
    /// Police: temporary map blips for 911 calls, removed after a minute.
    calls: Vec<(i32, Instant)>,
    last_call: Option<Instant>,
    last_fare: Option<Instant>,
    /// After being robbed, a civilian can call 911 with the cart button for a while.
    victim_until: Option<Instant>,
}
static MY_ROLE: Mutex<Option<MyRole>> = Mutex::new(None);
static ROLE_COOLDOWN: Mutex<Vec<(u8, Instant)>> = Mutex::new(Vec::new());

/// Bolingbroke Penitentiary: inside the yard, the area a prisoner must stay in, and the front gate.
const JAIL_CELL: [f32; 3] = [1641.6, 2570.5, 45.6];
const JAIL_CENTER: [f32; 3] = [1690.0, 2590.0, 45.6];
const JAIL_RADIUS: f32 = 150.0;
const JAIL_EXIT: [f32; 3] = [1847.9, 2586.1, 45.7];
const WANTED_DECAY: Duration = Duration::from_secs(120);

fn stars(n: u8) -> String { "*".repeat(n.min(5) as usize) }

/// Other players riding as passengers in the car this player drives (their synced seat says so).
fn taxi_passengers(net: &Net) -> usize {
    let Some(me) = *net.my_id.lock().unwrap() else { return 0; };
    net.peers.lock().unwrap().values().filter(|p| {
        p.snaps.back().is_some_and(|(at, s)| at.elapsed() < Duration::from_secs(3) && s.in_vehicle() && s.veh_owner == me && s.seat != -1 && !s.dead())
    }).count()
}

fn role_teleport(c: &mut Cmd, ped: i32, to: [f32; 3], heading: f32) {
    let pos = c.vec_arg(1, to);
    let zero = c.vec_arg(2, [0.0; 3]);
    c.i("ClearPedTasksImmediately", &[i(ped)]);
    c.i("SetEntityCoordsNoOffset", &[i(ped), pos, b(false), b(false), b(false)]);
    c.i("SetEntityVelocity", &[i(ped), zero]);
    c.i("SetEntityHeading", &[i(ped), f(heading)]);
}

/// Called for every kill this client is credited with (from the victim's KILLFEED).
fn role_on_kill(c: &mut Cmd, victim: u8) {
    let victim_role = NET.get().and_then(|n| n.as_ref()).and_then(|n| n.peers.lock().unwrap().get(&victim).map(|p| role_of(&p.name))).unwrap_or(Role::Civilian);
    let victim_wanted = peer_role(victim).wanted;
    let mut guard = MY_ROLE.lock().unwrap();
    let me = guard.get_or_insert_with(MyRole::default);
    // An officer stopping a wanted suspect commits no crime.
    if my_role() == Role::Police && victim_wanted > 0 {
        let bonus = 250 * victim_wanted as i32;
        let balance = WALLET_CASH.fetch_add(bonus, Ordering::Relaxed) + bonus;
        c.feed(&format!("~b~[Police]~s~ Wanted suspect taken down: ~g~+${bonus}~s~ | Wallet: ~g~${balance}~s~"));
        return;
    }
    let add = if victim_role == Role::Police { 3 } else { 2 };
    me.wanted = (me.wanted + add).min(5);
    me.last_crime = Some(Instant::now());
    c.feed(&format!("~r~You are WANTED {}~s~ ({} stars). Police can arrest you!", stars(me.wanted), me.wanted));
}

/// The interact button (the Ammu-Nation one) away from a shop: police arrest, medics heal.
/// Returns false when this role has no action, so the caller shows its usual hint.
fn role_interact(c: &mut Cmd, ped: i32, my_pos: [f32; 3]) -> bool {
    let Some(Some(net)) = NET.get() else { return false; };
    let role = role_of(&net.name);
    match role {
        Role::Civilian => {
            // Call 911 (after being robbed): every officer online gets the caller's position on the map.
            let mut guard = MY_ROLE.lock().unwrap();
            let me = guard.get_or_insert_with(MyRole::default);
            if !me.victim_until.is_some_and(|t| Instant::now() < t) { return false; }
            if me.last_call.map(|t| t.elapsed() < Duration::from_secs(30)).unwrap_or(false) {
                c.feed("~y~You just called the police. Wait 30 seconds.~s~");
                return true;
            }
            me.last_call = Some(Instant::now());
            drop(guard);
            let mut payload = Vec::with_capacity(12);
            for v in my_pos { payload.extend(v.to_le_bytes()); }
            send_reliable(net, proto::CALL911, &payload, None);
            c.feed("~b~[911]~s~ Police have been called to your location.");
            return true;
        }
        Role::Driver => {
            if c.i("IsPedInAnyVehicle", &[i(ped), b(false)]) == 0 { return false; }
            let passengers = taxi_passengers(net);
            c.feed(&format!("~y~[Driver]~s~ Carry other players: ~g~$40~s~ per passenger every 30 seconds while driving. Passengers: {passengers}."));
            return true;
        }
        _ => {}
    }
    if c.i("IsPedInAnyVehicle", &[i(ped), b(false)]) != 0 { return false; }
    let candidates: Vec<(u8, String, f32, u16, bool)> = net.peers.lock().unwrap().iter().filter_map(|(id, p)| {
        let (at, s) = p.snaps.back()?;
        if at.elapsed() > Duration::from_secs(2) { return None; }
        let pos = if s.in_vehicle() { s.veh_pos } else { s.pos };
        Some((*id, p.name.clone(), dist(pos, my_pos), s.health, s.dead()))
    }).collect();
    let mut nearby: Vec<_> = candidates.into_iter().filter(|(_, _, d, _, _)| *d < 3.5).collect();
    nearby.sort_by(|a, b| a.2.total_cmp(&b.2));
    let ready = |id: u8, secs: u64| {
        let mut list = ROLE_COOLDOWN.lock().unwrap();
        list.retain(|(_, t)| t.elapsed() < Duration::from_secs(30));
        if list.iter().any(|(peer, t)| *peer == id && t.elapsed() < Duration::from_secs(secs)) { return false; }
        list.push((id, Instant::now()));
        true
    };
    match role {
        Role::Police => {
            let target = nearby.iter().find(|(id, _, _, _, dead)| { let r = peer_role(*id); !dead && r.wanted > 0 && !r.jailed && !r.cuffed });
            let Some((id, name, ..)) = target else { return false; };
            if !ready(*id, 5) { return true; }
            let wanted = peer_role(*id).wanted;
            send_reliable(net, proto::ARREST, &[*id, wanted], Some(*id));
            let bounty = 400 * wanted as i32;
            let balance = WALLET_CASH.fetch_add(bounty, Ordering::Relaxed) + bounty;
            c.play_frontend("CHECKPOINT_NORMAL", "HUD_MINI_GAME_SOUNDSET");
            c.feed(&format!("~b~[Police]~s~ Arrested {name} {}. Reward: ~g~${bounty}~s~ | Wallet: ~g~${balance}~s~", stars(wanted)));
        }
        Role::Medic => {
            let target = nearby.iter().find(|(_, _, _, health, dead)| !dead && *health > 100 && *health < 195);
            let Some((id, name, ..)) = target else { return false; };
            if !ready(*id, 15) { c.feed("~g~[Medic]~s~ You just treated this player. Wait a moment."); return true; }
            send_reliable(net, proto::HEAL, &[*id], Some(*id));
            let balance = WALLET_CASH.fetch_add(150, Ordering::Relaxed) + 150;
            c.feed(&format!("~g~[Medic]~s~ Treated {name}. ~g~+$150~s~ | Wallet: ~g~${balance}~s~"));
        }
        Role::Gang => {
            // Rob a nearby civilian/medic/driver (not police, not other gang members). The victim's
            // client pays what its wallet really holds (PAID); the robbery itself adds a wanted star.
            let names: HashMap<u8, Role> = net.peers.lock().unwrap().iter().map(|(id, p)| (*id, role_of(&p.name))).collect();
            let target = nearby.iter().find(|(id, _, _, _, dead)| {
                !dead && !matches!(names.get(id), Some(Role::Police) | Some(Role::Gang)) && !peer_role(*id).jailed
            });
            let Some((id, name, ..)) = target else { return false; };
            if !ready(*id, 60) { c.feed("~r~[Gang]~s~ This player was just robbed. Wait 1 minute."); return true; }
            let amount: u16 = 300;
            let mut payload = vec![*id];
            payload.extend(amount.to_le_bytes());
            send_reliable(net, proto::ROB, &payload, Some(*id));
            let mut guard = MY_ROLE.lock().unwrap();
            let me = guard.get_or_insert_with(MyRole::default);
            me.wanted = (me.wanted + 1).min(5);
            me.last_crime = Some(Instant::now());
            c.feed(&format!("~r~[Gang]~s~ Robbing {name}... You are wanted {} ({} stars).", stars(me.wanted), me.wanted));
        }
        _ => {}
    }
    true
}

/// Once per frame online: arrests and heals received, cuffs, jail time, wanted decay, status broadcast,
/// police equipment and blip colours (wanted players red, police dark blue, medics green).
fn role_tick(c: &mut Cmd, game: &mut Game, net: &Net, ped: i32, my_pos: [f32; 3]) {
    let role = role_of(&net.name);
    let now = Instant::now();
    let dead = c.i("IsPedDeadOrDying", &[i(ped), b(true)]) != 0;
    let events = std::mem::take(&mut *ROLE_EVENTS.lock().unwrap());
    let mut guard = MY_ROLE.lock().unwrap();
    let me = guard.get_or_insert_with(MyRole::default);

    if !me.intro_shown {
        me.intro_shown = true;
        let text = match role {
            Role::Police => "~b~[Police]~s~ Approach a wanted player (*) and press Interact to handcuff and arrest them.",
            Role::Medic => "~g~[Medic]~s~ Approach an injured player and press Interact to treat them.",
            Role::Gang => "~r~[Gang]~s~ Approach another player and press Interact to rob them (1 wanted star). Avoid the police!",
            Role::Driver => "~y~[Driver]~s~ Carry other players in your vehicle: earn $40 per passenger every 30 seconds while driving.",
            Role::Civilian => "~s~[Civilian] Higher salary ($400/3 minutes). If robbed, press the shopping cart to call police (911).",
        };
        c.feed(text);
    }

    for event in events {
        let by_name = |id: u8| net.peers.lock().unwrap().get(&id).map(|p| p.name.clone()).unwrap_or_else(|| format!("Player {id}"));
        match event {
            RoleEvent::Arrested { by } if me.wanted > 0 && me.cuffed_until.is_none() && me.jail_until.is_none() && !dead => {
                me.jail_secs = (30 * me.wanted as u64).min(150);
                me.cuffed_until = Some(now + Duration::from_secs(3));
                let fine = (150 * me.wanted as i32).min(WALLET_CASH.load(Ordering::Relaxed).max(0));
                WALLET_CASH.fetch_sub(fine, Ordering::Relaxed);
                c.i("SetEnableHandCuffs", &[i(ped), b(true)]);
                c.i("TaskHandsUp", &[i(ped), i(3000), i(0), i(-1), i(0)]);
                c.i("FreezeEntityPosition", &[i(ped), b(true)]);
                c.feed(&format!("~r~You were arrested by {}!~s~ Fine: ~r~${fine}~s~, jail time: {} seconds.", by_name(by), me.jail_secs));
            }
            RoleEvent::Healed { by } if !dead => {
                c.i("SetEntityHealth", &[i(ped), i(200), i(0)]);
                c.feed(&format!("~g~[Medic] {} treated you.~s~", by_name(by)));
            }
            RoleEvent::Call { by, pos } if role == Role::Police => {
                let at = c.vec_arg(1, pos);
                let blip = c.i("AddBlipForCoord", &[at]);
                if blip != 0 {
                    c.i("SetBlipSprite", &[i(blip), i(280)]);
                    c.i("SetBlipSprite2", &[i(blip), i(280)]);
                    c.i("SetBlipColour", &[i(blip), i(1)]);
                    c.i("SetBlipColour2", &[i(blip), i(1)]);
                    c.i("SetBlipAsShortRange", &[i(blip), b(false)]);
                    c.i("SetBlipAsShortRange2", &[i(blip), b(false)]);
                    me.calls.push((blip, now));
                }
                c.play_frontend("CHECKPOINT_NORMAL", "HUD_MINI_GAME_SOUNDSET");
                c.feed(&format!("~b~[911]~s~ {} called police, {:.0}m away (red marker on the map).", by_name(by), dist(pos, my_pos)));
            }
            RoleEvent::Robbed { by, amount } => {
                let paid = amount.clamp(0, WALLET_CASH.load(Ordering::Relaxed).max(0));
                WALLET_CASH.fetch_sub(paid, Ordering::Relaxed);
                let mut payload = vec![by];
                payload.extend((paid as u16).to_le_bytes());
                send_reliable(net, proto::PAID, &payload, Some(by));
                me.victim_until = Some(now + Duration::from_secs(120));
                c.feed(&format!("~r~{} robbed you of ${paid}!~s~ Press the shopping cart within 2 minutes to call police (911).", by_name(by)));
            }
            RoleEvent::Paid { by, amount } => {
                let balance = WALLET_CASH.fetch_add(amount, Ordering::Relaxed) + amount;
                c.feed(&format!("~r~[Gang]~s~ Stole ~g~${amount}~s~ from {} | Wallet: ~g~${balance}~s~", by_name(by)));
            }
            _ => {}
        }
    }

    if let Some(until) = me.cuffed_until {
        if now >= until {
            me.cuffed_until = None;
            c.i("FreezeEntityPosition", &[i(ped), b(false)]);
            c.i("SetEnableHandCuffs", &[i(ped), b(false)]);
            role_teleport(c, ped, JAIL_CELL, 90.0);
            game.spawn_shield = Some(now + Duration::from_secs(8));
            me.wanted = 0;
            me.last_crime = None;
            me.jail_until = Some(now + Duration::from_secs(me.jail_secs));
            me.last_jail_note = Some(now);
            c.feed(&format!("~r~[Bolingbroke Prison]~s~ You are jailed for {} seconds.", me.jail_secs));
        }
    }
    if let Some(until) = me.jail_until {
        if now >= until {
            me.jail_until = None;
            role_teleport(c, ped, JAIL_EXIT, 270.0);
            c.feed("~g~Your sentence is over. Stay out of trouble!~s~");
        } else if !dead {
            let player = c.i("PlayerId", &[]);
            c.i("DisablePlayerFiring", &[i(player), b(true)]);
            if dist(my_pos, JAIL_CENTER) > JAIL_RADIUS {
                role_teleport(c, ped, JAIL_CELL, 90.0);
                c.feed("~r~You cannot escape prison!~s~");
            }
            if me.last_jail_note.map(|t| t.elapsed() >= Duration::from_secs(15)).unwrap_or(true) {
                me.last_jail_note = Some(now);
                c.feed(&format!("~r~[Prison]~s~ {} seconds remaining.", until.duration_since(now).as_secs()));
            }
        }
    }

    let expired: Vec<i32> = me.calls.iter().filter(|(_, t)| t.elapsed() >= Duration::from_secs(60)).map(|(blip, _)| *blip).collect();
    if !expired.is_empty() {
        me.calls.retain(|(_, t)| t.elapsed() < Duration::from_secs(60));
        for blip in expired {
            let r = c.ref_arg(blip);
            c.i("RemoveBlip", &[r]);
        }
    }

    if role == Role::Driver && !dead {
        let car = c.i("GetVehiclePedIsIn", &[i(ped), b(false)]);
        let driving = car != 0 && c.i("GetPedInVehicleSeat", &[i(car), i(-1), b(false)]) == ped && c.f("GetEntitySpeed", &[i(car)]) > 3.0;
        match (driving, me.last_fare) {
            (false, _) => me.last_fare = None,
            (true, None) => me.last_fare = Some(now),
            (true, Some(t)) if t.elapsed() >= Duration::from_secs(30) => {
                me.last_fare = Some(now);
                let passengers = taxi_passengers(net) as i32;
                if passengers > 0 {
                    let fare = 40 * passengers;
                    let balance = WALLET_CASH.fetch_add(fare, Ordering::Relaxed) + fare;
                    c.feed(&format!("~y~[Driver]~s~ Fare for {passengers} passengers: ~g~+${fare}~s~ | Wallet: ~g~${balance}~s~"));
                }
            }
            _ => {}
        }
    }

    if me.wanted > 0 && me.jail_until.is_none() && me.last_crime.map(|t| t.elapsed() >= WANTED_DECAY).unwrap_or(true) {
        me.wanted -= 1;
        me.last_crime = Some(now);
        c.feed(&if me.wanted == 0 { "~g~You are no longer wanted.~s~".to_string() } else { format!("~y~Your wanted level dropped to {} ({} stars).~s~", stars(me.wanted), me.wanted) });
    }

    if me.last_broadcast.map(|t| t.elapsed() >= Duration::from_secs(1)).unwrap_or(true) {
        me.last_broadcast = Some(now);
        let flags = u8::from(me.jail_until.is_some()) | (u8::from(me.cuffed_until.is_some()) << 1);
        let _ = net.sock.send(&proto::packet(proto::ROLE, &[me.wanted, flags]));
    }

    if dead {
        me.loadout_given = false;
    } else if !me.loadout_given && role == Role::Police {
        me.loadout_given = true;
        grant_role_loadout(c, ped);
    }

    if me.last_blips.map(|t| t.elapsed() >= Duration::from_secs(1)).unwrap_or(true) {
        me.last_blips = Some(now);
        let roles: HashMap<u8, Role> = net.peers.lock().unwrap().iter().map(|(id, p)| (*id, role_of(&p.name))).collect();
        for (id, a) in &game.avatars {
            if a.blip == 0 { continue; }
            let colour = if peer_role(*id).wanted > 0 { 1 } else {
                match roles.get(id) { Some(Role::Police) => 38, Some(Role::Medic) => 2, _ => 3 }
            };
            c.i("SetBlipColour", &[i(a.blip), i(colour)]);
            c.i("SetBlipColour2", &[i(a.blip), i(colour)]);
        }
    }
}

fn strip_all_unauthorized_weapons(c: &mut Cmd<'_, '_>, ped: i32) {
    if ped == 0 || !c.exists(ped) { return; }
    let _ = c.i("RemoveAllPedWeapons", &[i(ped), b(true)]);
    let _ = c.i("RemoveAllPedWeapons2", &[i(ped), b(true)]);
    for w in ALL_CHEAT_WEAPONS {
        let h = weapon(w) as i32;
        let _ = c.i("RemoveWeaponFromPed", &[i(ped), i(h)]);
        let _ = c.i("RemoveWeaponFromPed2", &[i(ped), i(h)]);
    }
    // Give basic melee knife:
    let knife = weapon("weapon_knife") as i32;
    let _ = c.i("GiveWeaponToPed", &[i(ped), i(knife), i(1), b(false), b(false)]);

    // Always give starting pistol so players can switch to guns immediately:
    let pistol = weapon("weapon_pistol") as i32;
    let _ = c.i("GiveWeaponToPed", &[i(ped), i(pistol), i(60), b(false), b(false)]);
    let _ = c.i("SetCurrentPedWeapon", &[i(ped), i(pistol), b(true)]);
    let _ = c.i("SetPedInfiniteAmmoClip", &[i(ped), b(false)]);

    // Re-grant purchased weapons
    let mut purchased = PURCHASED_WEAPONS.lock().unwrap();
    if !purchased.contains(&(pistol as u32)) {
        purchased.push(pistol as u32);
    }
    for &wh in purchased.iter() {
        let _ = c.i("GiveWeaponToPed", &[i(ped), i(wh as i32), i(120), b(false), b(false)]);
    }
    drop(purchased);
    grant_role_loadout(c, ped);
    eprintln!("[economy] stripped cheat weapons; granted starting pistol + knife, wallet: ${}", WALLET_CASH.load(Ordering::Relaxed));
}

fn strip_unauthorized_weapons_check(c: &mut Cmd<'_, '_>, ped: i32) {
    if ped == 0 || !c.exists(ped) { return; }
    let purchased = PURCHASED_WEAPONS.lock().unwrap().clone();
    let knife_h = weapon("weapon_knife");
    let pistol_h = weapon("weapon_pistol");
    let cur_w = c.i("GetSelectedPedWeapon", &[i(ped)]) as u32;
    let allowed = |wh: u32| wh == knife_h || wh == pistol_h || purchased.contains(&wh) || role_weapon_allowed(wh);

    let full_scan = {
        let mut last = LAST_WEAPON_SCAN.lock().unwrap();
        let due = last.map(|t| t.elapsed() >= WEAPON_SCAN_EVERY).unwrap_or(true);
        if due { *last = Some(Instant::now()); }
        due
    };
    let banned_in_hand = !allowed(cur_w) && cheat_weapon_hashes().iter().any(|(_, wh)| *wh == cur_w);
    if !full_scan && !banned_in_hand {
        return;
    }

    for &(w_name, wh) in cheat_weapon_hashes() {
        if allowed(wh) || (!full_scan && wh != cur_w) {
            continue;
        }
        let has_w = c.i("HasPedGotWeapon", &[i(ped), i(wh as i32), b(false)]) != 0
            || c.i("HasPedGotWeapon2", &[i(ped), i(wh as i32), b(false)]) != 0
            || cur_w == wh;
        if has_w {
            let _ = c.i("RemoveWeaponFromPed", &[i(ped), i(wh as i32)]);
            let _ = c.i("RemoveWeaponFromPed2", &[i(ped), i(wh as i32)]);
            let _ = c.i("SetPedInfiniteAmmoClip", &[i(ped), b(false)]);
            if cur_w == wh {
                let _ = c.i("SetCurrentPedWeapon", &[i(ped), i(pistol_h as i32), b(true)]);
            }
            eprintln!("[anti-cheat] stripped unpurchased weapon: {w_name}");
        }
    }
}

/// Why a player must be moved back to Legion Square, if at all. North Yankton lies around
/// x 3000..5600, y -4300..-5600: the real map east of x = 2000 (Grapeseed, Palmer-Taylor, the east
/// highway) and south of the port stays playable. The Vinewood Hills spawn trap is Franklin's street,
/// and divers go below sea level, so those two only count while the session is starting.
fn rescue_reason(my_pos: [f32; 3], in_car: bool) -> Option<&'static str> {
    static FIRST_SEEN: OnceLock<Instant> = OnceLock::new();
    let starting = FIRST_SEEN.get_or_init(Instant::now).elapsed() < Duration::from_secs(60);
    let [x, y, z] = my_pos;
    if x > 3000.0 && y < -4300.0 { return Some("north_yankton"); }
    // The engine's default (0, 0, 0) spawn; the land there is about 60 m above sea level.
    if !in_car && x.abs() < 50.0 && y.abs() < 50.0 && z < 10.0 { return Some("origin_void"); }
    if z < if starting { -5.0 } else { -190.0 } { return Some("under_map"); }
    if starting && (x + 14.0).abs() < 40.0 && (y - 525.0).abs() < 40.0 { return Some("mansion_spawn"); }
    None
}
static SANDBOX_RESCUE_CD: Mutex<Option<Instant>> = Mutex::new(None);
static SANDBOX_STARTUP_TICKS: AtomicUsize = AtomicUsize::new(0);

fn process_sandbox_and_mp_checks(c: &mut Cmd<'_, '_>, ped: i32, my_pos: [f32; 3]) {
    if ped == 0 || !c.exists(ped) { return; }
    let mode = std::env::var("MUGUET_MODE").unwrap_or_default();
    let is_mp = crate::input::muguet_is_multiplayer();
    let is_sandbox = mode == "sandbox";
    if !is_mp && !is_sandbox { return; }

    // 1. Legion Square spawn & out-of-bounds rescue (see rescue_reason).
    let in_car = c.i("IsPedInAnyVehicle", &[i(ped), b(false)]) != 0;
    let reason = rescue_reason(my_pos, in_car);

    let mut rescue_cd = SANDBOX_RESCUE_CD.lock().unwrap();
    let can_rescue = rescue_cd.map(|t| t.elapsed() > Duration::from_secs(4)).unwrap_or(true);

    if let (Some(reason), true) = (reason, can_rescue) {
        *rescue_cd = Some(Instant::now());
        let spawn_pos = [215.0f32, -915.0f32, 30.6f32]; // Legion Square, Los Santos
        let pos_arg = c.vec_arg(1, spawn_pos);
        let zero_vel = c.vec_arg(2, [0.0f32, 0.0f32, 0.0f32]);
        c.i("ClearPedTasksImmediately", &[i(ped)]);
        c.i("SetEntityCoordsNoOffset", &[i(ped), pos_arg, b(false), b(false), b(false)]);
        c.i("SetEntityVelocity", &[i(ped), zero_vel]);
        c.i("SetEntityHeading", &[i(ped), f(0.0)]);
        c.feed("~g~[zema] Moved to central Los Santos (Legion Square)~s~");
        eprintln!("[mp/sandbox] rescued player from {my_pos:?} ({reason}) to Legion Square {spawn_pos:?}");
    }

    // Only apply multiplayer economy/anti-cheat restrictions in MULTIPLAYER (Sandbox Online or Story Online)
    // In Sandbox OFFLINE (!is_mp), players can freely test all weapons and sandbox features.
    if !is_mp {
        return;
    }

    // 2. Cell phone controls are NOT disabled: player can freely bring out and use their in-game cell phone!

    // 3. Neutralize in-game cell phone godmode (1-999-PAINKILLER) in multiplayer
    c.i("SetEntityInvincible", &[i(ped), b(false)]);
    let player_id = c.i("PlayerId", &[]);
    if player_id != 0 {
        c.i("SetPlayerInvincible", &[i(player_id), b(false)]);
        c.i("SetPlayerInvincible2", &[i(player_id), b(false)]);
    }

    // 4. Neutralize cell phone infinite ammo and slowmo in multiplayer
    c.i("SetPedInfiniteAmmoClip", &[i(ped), b(false)]);
    c.i("SetTimeScale", &[f(1.0)]);

    // 5. Strip unpurchased cheat weapons every tick in multiplayer
    let count = SANDBOX_STARTUP_TICKS.fetch_add(1, Ordering::Relaxed);
    if count < 30 && count % 5 == 0 {
        strip_all_unauthorized_weapons(c, ped);
    } else {
        strip_unauthorized_weapons_check(c, ped);
    }
}

/// The wallet and bought weapons used to reset to $1000 / pistol on every launch.
/// Kept in the app's Documents folder (native app only), in the format "cash\nhash,hash,...".
#[cfg(feature = "native-port")]
fn wallet_path() -> Option<std::path::PathBuf> {
    std::env::var_os("HOME").map(|home| std::path::PathBuf::from(home).join("Documents").join("mugoat-wallet.txt"))
}
#[cfg(not(feature = "native-port"))]
fn wallet_path() -> Option<std::path::PathBuf> { None }

static WALLET_LOADED: AtomicBool = AtomicBool::new(false);
static WALLET_SAVED: Mutex<Option<(i32, Vec<u32>, Instant)>> = Mutex::new(None);

/// Weapons that can be restored from the save: only what Ammu-Nation sells, plus the starting pistol.
fn buyable_weapon(hash: u32) -> bool {
    hash == weapon("weapon_pistol")
        || AMMU_ITEMS.iter().any(|item| !item.is_armor && item.weapon_hash.starts_with("weapon_") && weapon(item.weapon_hash) == hash)
}

fn load_wallet_once() {
    if WALLET_LOADED.swap(true, Ordering::Relaxed) { return; }
    let Some(text) = wallet_path().and_then(|path| std::fs::read_to_string(path).ok()) else { return; };
    let mut lines = text.lines();
    if let Some(cash) = lines.next().and_then(|line| line.trim().parse::<i32>().ok()) {
        WALLET_CASH.store(cash.clamp(0, 10_000_000), Ordering::Relaxed);
    }
    let mut purchased = PURCHASED_WEAPONS.lock().unwrap();
    for hash in lines.next().unwrap_or("").split(',').filter_map(|h| h.trim().parse::<u32>().ok()) {
        if buyable_weapon(hash) && !purchased.contains(&hash) { purchased.push(hash); }
    }
    let saved = (WALLET_CASH.load(Ordering::Relaxed), purchased.clone(), Instant::now());
    drop(purchased);
    *WALLET_SAVED.lock().unwrap() = Some(saved);
    eprintln!("[economy] wallet restored: ${}", WALLET_CASH.load(Ordering::Relaxed));
}

/// Writes the wallet when it changed, at most every 2 s (a small file, off the hot path).
fn save_wallet_if_changed() {
    let cash = WALLET_CASH.load(Ordering::Relaxed);
    let purchased = PURCHASED_WEAPONS.lock().unwrap().clone();
    let mut saved = WALLET_SAVED.lock().unwrap();
    if let Some((c, p, at)) = saved.as_ref() {
        if (*c == cash && *p == purchased) || at.elapsed() < Duration::from_secs(2) { return; }
    }
    let Some(path) = wallet_path() else { return; };
    let text = format!("{cash}\n{}\n", purchased.iter().map(u32::to_string).collect::<Vec<_>>().join(","));
    let temporary = path.with_extension("tmp");
    if std::fs::write(&temporary, text).and_then(|_| std::fs::rename(&temporary, &path)).is_ok() {
        *saved = Some((cash, purchased, Instant::now()));
    }
}

fn update_economy_and_shops(c: &mut Cmd<'_, '_>, ped: i32, my_pos: [f32; 3]) {
    if ped == 0 || !c.exists(ped) { return; }
    load_wallet_once();
    save_wallet_if_changed();
    let purchased = PURCHASED_WEAPONS.lock().unwrap().clone();
    // process_sandbox_and_mp_checks already ran this frame's cheat neutralization and weapon check
    // when online; repeating them doubled ~150 engine calls per frame on the game thread.
    let already_checked = crate::input::muguet_is_multiplayer();

    if !already_checked {
        // Neutralize in-game cell phone godmode / invincibility (1-999-PAINKILLER)
        c.i("SetEntityInvincible", &[i(ped), b(false)]);
        let player_id = c.i("PlayerId", &[]);
        if player_id != 0 {
            c.i("SetPlayerInvincible", &[i(player_id), b(false)]);
            c.i("SetPlayerInvincible2", &[i(player_id), b(false)]);
        }

        // Neutralize in-game cell phone infinite ammo cheats
        c.i("SetPedInfiniteAmmoClip", &[i(ped), b(false)]);

        // Neutralize in-game cell phone slow-motion cheat (1-999-SLOWMO)
        c.i("SetTimeScale", &[f(1.0)]);
    }

    // 1. Paycheck every 180 seconds (+250$)
    let mut last_pay = LAST_PAYCHECK.lock().unwrap();
    if last_pay.map(|t| t.elapsed() > Duration::from_secs(180)).unwrap_or(true) {
        if last_pay.is_some() {
            // Civilians live on their wages: they get more than the other roles.
            let pay = if my_role() == Role::Civilian { 400 } else { 250 };
            let balance = WALLET_CASH.fetch_add(pay, Ordering::Relaxed) + pay;
            eprintln!("[economy] paycheck received: +${pay} (balance: ${balance})");
            c.feed(&format!("~g~+${pay}~s~ [Citizen salary] | Wallet: ~g~${balance}~s~"));
        }
        *last_pay = Some(Instant::now());
    }

    // 2. Anti-cheat check: Strip any unpurchased cheat weapons (from phone cheat 1-999-TOOLUP or singleplayer)
    if !already_checked {
        strip_unauthorized_weapons_check(c, ped);
    }

    // 3. Ammu-Nation interaction near blips (sprite 110)
    let near_shop = WORLD_SHOPS.iter().find(|s| {
        if s.sprite != 110 { return false; }
        let dx = my_pos[0] - s.pos[0];
        let dy = my_pos[1] - s.pos[1];
        let dz = my_pos[2] - s.pos[2];
        (dx * dx + dy * dy) < 36.0 && dz.abs() < 4.0 // within 6 m of the counter, same floor
    });

    if let Some(_shop) = near_shop {
        let idx = SELECTED_AMMU_ITEM.load(Ordering::Relaxed) % AMMU_ITEMS.len();
        let item = &AMMU_ITEMS[idx];
        let cash = WALLET_CASH.load(Ordering::Relaxed);

        // Draw screen banner notification
        static LAST_BANNER: Mutex<Option<Instant>> = Mutex::new(None);
        let mut banner_t = LAST_BANNER.lock().unwrap();
        if banner_t.map(|t| t.elapsed() > Duration::from_millis(1500)).unwrap_or(true) {
            c.feed(&format!("~g~[AMMU-NATION]~s~ Wallet: ~g~${cash}~s~ | Selected: ~y~{}~s~ (~g~${}~s~) [E/Horn]", item.name, item.price));
            *banner_t = Some(Instant::now());
        }

        let buy_trigger = AMMU_BUY_REQUESTED.swap(false, Ordering::Relaxed);
        let horn_trigger = crate::pad::horn_held();
        let mut last_buy = LAST_AMMU_BUY.lock().unwrap();
        let can_interact = last_buy.map(|t| t.elapsed() > Duration::from_millis(600)).unwrap_or(true);

        if (buy_trigger || horn_trigger) && can_interact {
            *last_buy = Some(Instant::now());
            if cash >= item.price {
                let remaining = WALLET_CASH.fetch_sub(item.price, Ordering::Relaxed) - item.price;
                if item.is_armor {
                    let _ = c.i("SetPedArmour", &[i(ped), i(100)]);
                    c.feed(&format!("~g~Purchased: {}!~s~ Remaining: ~g~${remaining}~s~", item.name));
                } else if item.weapon_hash == "AMMO_REFILL" {
                    for &wh in &purchased {
                        let _ = c.i("SetPedAmmo", &[i(ped), i(wh as i32), i(300)]);
                        let _ = c.i("SetPedAmmo2", &[i(ped), i(wh as i32), i(300)]);
                    }
                    c.feed(&format!("~g~All weapon ammo refilled!~s~ Remaining: ~g~${remaining}~s~"));
                } else {
                    let wh = weapon(item.weapon_hash) as i32;
                    let _ = c.i("GiveWeaponToPed", &[i(ped), i(wh), i(item.ammo), b(false), b(true)]);
                    let _ = c.i("SetCurrentPedWeapon", &[i(ped), i(wh), b(true)]);
                    let _ = c.i("SetPedInfiniteAmmoClip", &[i(ped), b(false)]);
                    PURCHASED_WEAPONS.lock().unwrap().push(wh as u32);
                    c.feed(&format!("~g~Purchased: {}!~s~ Remaining: ~g~${remaining}~s~", item.name));
                }
                c.play_frontend("PURCHASE", "HUD_LIQUOR_STORE_SOUNDSET");
                SELECTED_AMMU_ITEM.fetch_add(1, Ordering::Relaxed);
            } else {
                c.feed(&format!("~r~Not enough money! Need ${} (Wallet: ${cash})~s~", item.price));
                c.play_frontend("ERROR", "HUD_AMMO_SHOP_SOUNDSET");
            }
        }
    } else if AMMU_BUY_REQUESTED.swap(false, Ordering::Relaxed) && !role_interact(c, ped, my_pos) {
        let cash = WALLET_CASH.load(Ordering::Relaxed);
        let nearest = WORLD_SHOPS.iter().filter(|s| s.sprite == 110).min_by(|a, b| dist(a.pos, my_pos).total_cmp(&dist(b.pos, my_pos)));
        if let Some(shop) = nearest {
            c.i("SetNewWaypoint", &[f(shop.pos[0]), f(shop.pos[1])]);
            c.play_frontend("WAYPOINT_SET", "HUD_FRONTEND_DEFAULT_SOUNDSET");
            c.feed(&format!("~y~Wallet: ~g~${cash}~y~. GPS set to the nearest Ammu-Nation (~w~{:.0}m~y~). Approach the counter and press the shopping cart to buy.~s~", dist(shop.pos, my_pos)));
        } else {
            c.feed(&format!("~y~Wallet: ~g~${cash}~y~. Visit Ammu-Nation (~r~gun icon on the map~y~) to buy weapons!~s~"));
        }
    }
}

fn update_voice_speakers_hud(c: &mut Cmd<'_, '_>) {
    let speakers = voice_active_speakers();
    if !speakers.is_empty() {
        static LAST_VOICE_HUD: Mutex<Option<Instant>> = Mutex::new(None);
        let mut vhud = LAST_VOICE_HUD.lock().unwrap();
        if vhud.map(|t| t.elapsed() > Duration::from_millis(1500)).unwrap_or(true) {
            let names = speakers.join(", ");
            c.feed(&format!("~b~🔊 [{names}] speaking...~s~"));
            *vhud = Some(Instant::now());
        }
    }
}

fn frame(c: &mut Cmd, game: &mut Game, net: &Net) {
    let my_id = *net.my_id.lock().unwrap();
    let ped = c.i("PlayerPedId", &[]);
    let me_ok = ped != 0 && c.exists(ped);
    let my_pos = if me_ok { c.v("GetEntityCoords", &[i(ped), b(false)]) } else { [0.0; 3] };
    *LOCAL_POS.lock().unwrap() = Some(my_pos);
    let ptr_of = |c: &mut Cmd, e: i32| match call(c.caller, "mp:GetBaseFromGuid", &[i(e)]) { Some(Val::I64(p)) => p as u64, _ => 0 };
    LOCAL_PED.store(if me_ok { ptr_of(c, ped) } else { 0 }, Ordering::Relaxed);
    let my_car = if me_ok && c.i("IsPedInAnyVehicle", &[i(ped), b(false)]) != 0 { c.i("GetVehiclePedIsIn", &[i(ped), b(false)]) } else { 0 };
    LOCAL_CAR.store(if my_car != 0 { ptr_of(c, my_car) } else { 0 }, Ordering::Relaxed);

    if me_ok && game.my_car != my_car {
        let left = game.my_car;
        if left != 0 && c.exists(left) && c.i("IsEntityDead", &[i(left), b(false)]) == 0 && !game.avatars.values().any(|a| a.veh == left) && !game.mirrors.values().any(|m| m.ent == left) {
            park(left, c.i("GetEntityModel", &[i(left)]) as u32, 0);
        }
        game.my_car = my_car;
    }

    let is_mp = crate::input::muguet_is_multiplayer() || my_id.is_some();
    if me_ok && is_mp {
        if !WEAPONS_INITIALIZED.swap(true, Ordering::Relaxed) {
            strip_all_unauthorized_weapons(c, ped);
        }
        update_economy_and_shops(c, ped, my_pos);
        if my_id.is_some() {
            update_voice_speakers_hud(c);
            role_tick(c, game, net, ped, my_pos);
        }
        if game.last_send.elapsed() >= SEND_EVERY {
            let valid_pos = my_pos[0].abs() > 1.0 || my_pos[1].abs() > 1.0 || my_pos[2].abs() > 1.0;
            if valid_pos {
                game.last_send = Instant::now();
                let s = local_state(c, game, ped, my_pos);
                game.seq = game.seq.wrapping_add(1);
                let mut payload = game.seq.to_le_bytes().to_vec();
                s.encode(&mut payload);
                payload.extend((START.get_or_init(Instant::now).elapsed().as_millis() as u32).to_le_bytes());
                payload.extend(s.veh_key.to_le_bytes());
                let _ = net.sock.send(&proto::packet(proto::STATE, &payload));
            }
        }
        let veh = if c.i("IsPedInAnyVehicle", &[i(ped), b(false)]) != 0 { c.i("GetVehiclePedIsIn", &[i(ped), b(false)]) } else { 0 };
        let own_car = veh != 0 && !game.avatars.values().any(|a| a.veh == veh);
        if own_car && game.last_vlook.elapsed() >= LOOK_EVERY {
            game.last_vlook = Instant::now();
            let look = read_vlook(c, veh);
            let resend = game.sent_vlook.map(|(t, l)| l != look || t.elapsed() > Duration::from_secs(4)).unwrap_or(true);
            if resend {
                let mut payload = Vec::new();
                look.encode(&mut payload);
                let _ = net.sock.send(&proto::packet(proto::VLOOK, &payload));
                game.sent_vlook = Some((Instant::now(), look));
            }
        }

        let driver = veh != 0 && c.i("GetPedInVehicleSeat", &[i(veh), i(-1), b(false)]) == ped;
        if own_car && driver {
            let ctl = read_vctl(c, veh);
            let resend = game.sent_vctl.map(|(t, v)| v != ctl || t.elapsed() > Duration::from_secs(1)).unwrap_or(true);
            if resend {
                let _ = net.sock.send(&proto::packet(proto::VCTL, &ctl));
                game.sent_vctl = Some((Instant::now(), ctl));
            }
        }

        if veh != 0 {
            if let Some(key) = game.mirrors.iter().find(|(_, m)| m.is_vehicle && m.ent == veh).map(|(k, _)| *k) {
                game.mirrors.remove(&key);
                game.taken.insert(key);
                let mut payload = vec![key.0 & !EXTRAS];
                payload.extend(key.1.to_le_bytes());
                send_reliable(net, proto::TAKEN, &payload, Some(key.0 & !EXTRAS));
                eprintln!("[mp] took player {}'s traffic car", key.0 & !EXTRAS);
            }
        }
        if game.last_look.elapsed() >= LOOK_EVERY {
            game.last_look = Instant::now();
            let look = read_look(c, ped);
            let resend = game.sent_look.map(|(t, l)| l != look || t.elapsed() > Duration::from_secs(4)).unwrap_or(true);
            if resend {
                let mut payload = Vec::new();
                look.encode(&mut payload);
                let _ = net.sock.send(&proto::packet(proto::LOOK, &payload));
                game.sent_look = Some((Instant::now(), look));
            }
        }

        const ARMED_GUN: i32 = 4;
        const ARMED_THROWN: i32 = 2;
        let gun = c.i("IsPedArmed", &[i(ped), i(ARMED_GUN)]) != 0;

        const INPUT_ATTACK: i32 = 24;
        const INPUT_MELEE_LIGHT: i32 = 140;
        const INPUT_MELEE_HEAVY: i32 = 141;
        let melee = !gun && c.i("IsPedArmed", &[i(ped), i(ARMED_THROWN)]) == 0
            && c.i("IsPedInAnyVehicle", &[i(ped), b(false)]) == 0
            && c.i("IsPedRagdoll", &[i(ped)]) == 0;
        if melee && game.last_swing.elapsed() >= Duration::from_millis(450)
            && (c.i("IsPedShooting", &[i(ped)]) != 0 || [INPUT_ATTACK, INPUT_MELEE_LIGHT, INPUT_MELEE_HEAVY].iter().any(|k| c.i("IsControlPressed", &[i(0), i(*k)]) != 0))
        {
            game.last_swing = Instant::now();
            let target = c.i("GetMeleeTargetForPed", &[i(ped)]);
            if let Some((id, _)) = game.avatars.iter().find(|(_, a)| a.ped != 0 && a.ped == target) {
                eprintln!("[mp] swinging at player {id}");
            }
            let to = if target != 0 && c.exists(target) {
                c.v("GetEntityCoords", &[i(target), b(false)])
            } else {
                let h = c.f("GetEntityHeading", &[i(ped)]).to_radians();
                [my_pos[0] - 1.2 * h.sin(), my_pos[1] + 1.2 * h.cos(), my_pos[2]]
            };
            let shot = Shot { weapon: c.i("GetSelectedPedWeapon", &[i(ped)]) as u32, from: my_pos, to };
            let mut payload = Vec::new();
            shot.encode(&mut payload);
            let _ = net.sock.send(&proto::packet(proto::SHOT, &payload));
        }
        if game.last_shot.elapsed() >= Duration::from_millis(45) && c.i("IsPedShooting", &[i(ped)]) != 0 && gun {
            game.last_shot = Instant::now();
            let shot = local_shot(c, ped, my_pos);
            if shot.to != game.last_impact {
                game.last_impact = shot.to;
                bullet_on_driver(c, game, shot.weapon, shot.to);
            }
            let mut payload = Vec::new();
            shot.encode(&mut payload);
            let _ = net.sock.send(&proto::packet(proto::SHOT, &payload));
        }
    }

    if me_ok {
        if let Some(t) = game.spawn_shield {
            if Instant::now() < t {
                c.i("SetEntityInvincible", &[i(ped), b(true)]);
            } else {
                c.i("SetEntityInvincible", &[i(ped), b(false)]);
                game.spawn_shield = None;
            }
        }
    }

    if let Some(t) = game.unfreeze_at {
        if Instant::now() >= t {
            c.i("FreezeEntityPosition", &[i(ped), b(false)]);
            game.unfreeze_at = None;
        }
    }
    game.met = true;

    // Safety check: Prevent falling through map / spawning in ocean void / stuck in North Yankton
    if me_ok {
        let in_car = c.i("IsPedInAnyVehicle", &[i(ped), b(false)]) != 0;
        let reason = rescue_reason(my_pos, in_car);

        static RESCUE_COOLDOWN: Mutex<Option<Instant>> = Mutex::new(None);
        let mut rescue_cd = RESCUE_COOLDOWN.lock().unwrap();
        let can_rescue = rescue_cd.map(|t| t.elapsed() > Duration::from_secs(4)).unwrap_or(true);

        if let (Some(reason), true) = (reason, can_rescue) {
            *rescue_cd = Some(Instant::now());
            let spawn_pos = [215.0f32, -915.0f32, 30.6f32]; // Legion Square, Los Santos
            let pos_arg = c.vec_arg(1, spawn_pos);
            let zero_vel = c.vec_arg(2, [0.0f32, 0.0f32, 0.0f32]);
            c.i("ClearPedTasksImmediately", &[i(ped)]);
            c.i("SetEntityCoordsNoOffset", &[i(ped), pos_arg, b(false), b(false), b(false)]);
            c.i("SetEntityVelocity", &[i(ped), zero_vel]);
            c.i("SetEntityHeading", &[i(ped), f(0.0)]);
            game.spawn_shield = Some(Instant::now() + Duration::from_secs(8));
            c.feed("~g~[zema] Moved to central Los Santos (Legion Square)~s~");
            eprintln!("[mp] rescued player from out-of-bounds {my_pos:?} ({reason}) to Legion Square {spawn_pos:?}");
        }
    }

    let now = Instant::now();

    let mut spins: HashMap<u8, f32> = HashMap::new();
    let vctls: HashMap<u8, [u8; 4]> = net.peers.lock().unwrap().iter().filter_map(|(id, p)| p.vctl.map(|v| (*id, v))).collect();
    let states: Vec<(u8, Option<State>, Option<Look>, Option<VehLook>)> = {
        let mut peers = net.peers.lock().unwrap();
        peers.retain(|_, p| p.last.elapsed() < Duration::from_secs(proto::TIMEOUT_SECS + 2));
        peers.iter().map(|(id, p)| {
            let at = now - p.clock.delay();
            let s = sample(p, at);
            if let (Some(a), Some(b)) = (sample(p, at - Duration::from_millis(60)), s) {
                if a.in_vehicle() && b.in_vehicle() {
                    spins.insert(*id, ((b.veh_rot[2] - a.veh_rot[2] + 540.0).rem_euclid(360.0) - 180.0) / 0.06);
                }
            }
            (*id, s, p.look, p.vlook)
        }).collect()
    };
    let gone: Vec<u8> = game.avatars.keys().filter(|id| !states.iter().any(|(s, _, _, _)| s == *id)).copied().collect();
    for id in gone {
        if let Some(a) = game.avatars.remove(&id) {
            despawn(c, a);
        }
    }

    let mut cars: HashMap<u8, i32> = game.avatars.iter().filter(|(_, a)| a.veh != 0).map(|(id, a)| (*id, a.veh)).collect();
    if let (Some(me), true) = (my_id, me_ok) {
        let v = c.i("GetVehiclePedIsIn", &[i(ped), b(false)]);
        if v != 0 {
            cars.insert(me, v);
        }
    }

    let mut order: Vec<&(u8, Option<State>, Option<Look>, Option<VehLook>)> = states.iter().collect();
    order.sort_by_key(|(_, s, _, _)| s.map(|s| s.veh_owner != 0).unwrap_or(false));
    for (id, s, look, vlook) in order.iter().copied() {
        let Some(s) = s else { continue };
        let a = game.avatars.entry(*id).or_default();
        a.veh_spin = spins.get(id).copied().unwrap_or(0.0);
        update_avatar(c, *id, a, s, *look, &cars);

        if let (Some(l), true) = (vlook, a.veh != 0 && me_ok) {
            if l.radio != 255 && c.i("GetVehiclePedIsIn", &[i(ped), b(false)]) == a.veh && c.i("GetPlayerRadioStationIndex", &[]) != l.radio as i32 {
                c.i("RetuneRadioToStationIndex", &[i(l.radio as i32)]);
            }
        }
        if let (Some(l), true) = (vlook, a.veh != 0) {
            if l.model == a.veh_model && a.veh_look != Some(*l) {
                apply_vlook(c, a.veh, l);
                a.veh_look = Some(*l);
            }
        }
        if let (Some(v), true) = (vctls.get(id), a.veh != 0 && s.in_vehicle() && s.veh_owner == 0) {
            if a.vctl != Some(*v) || v[1] != 0 {
                apply_vctl(c, a, *v);
            }
        }
        if a.veh != 0 {
            cars.insert(*id, a.veh);
        }
    }

    *AVATAR_ENTS.lock().unwrap() = game.avatars.values().flat_map(|a| [a.ped, a.veh, a.entering.map(|e| e.0).unwrap_or(0)]).filter(|e| *e != 0).collect();

    if game.last_tidy.elapsed() >= Duration::from_secs(1) {
        game.last_tidy = Instant::now();
        let where_: HashMap<u8, [f32; 3]> = states.iter().filter_map(|(id, s, ..)| s.map(|s| (*id, if s.in_vehicle() { s.veh_pos } else { s.pos }))).collect();
        tidy_parked(c, &where_);
    }

    if me_ok {
        let dead = c.i("IsPedDeadOrDying", &[i(ped), b(true)]) != 0;
        if dead && !game.was_dead {
            let by = c.i("GetPedSourceOfDeath", &[i(ped)]);
            let killer = game.avatars.iter().find(|(_, a)| by != 0 && (a.ped == by || a.veh == by)).map(|(id, _)| *id).unwrap_or(0);
            let cause = c.i("GetPedCauseOfDeath", &[i(ped)]) as u32;
            let mut payload = vec![killer];
            payload.extend(cause.to_le_bytes());
            send_reliable(net, proto::KILLFEED, &payload, None);
            if let Some(me) = my_id {
                net.deaths.lock().unwrap().push((me, killer, cause));
            }
        }
        if dead && !game.was_dead {
            let cur = WALLET_CASH.load(Ordering::Relaxed);
            if cur > 100 {
                WALLET_CASH.fetch_sub(100, Ordering::Relaxed);
                eprintln!("[economy] hospital fee: -$100 (balance: ${})", cur - 100);
            }
        }
        if !dead && game.was_dead {
            game.spawn_shield = Some(Instant::now() + Duration::from_secs(8));
        }
        game.was_dead = dead;
    }
    let deaths = std::mem::take(&mut *net.deaths.lock().unwrap());
    for (victim, killer, cause) in deaths {
        let name = |id: u8| if Some(id) == my_id { net.name.clone() } else { net.peers.lock().unwrap().get(&id).map(|p| p.name.clone()).unwrap_or_else(|| format!("Player {id}")) };
        let text = match (killer, weapon_name(cause)) {
            (0, _) => format!("{} died", name(victim)),
            (k, Some(w)) => format!("{} killed {} ({w})", name(k), name(victim)),
            (k, None) => format!("{} killed {}", name(k), name(victim)),
        };
        eprintln!("[mp] {text}");
        if killer != 0 && Some(killer) == my_id && Some(victim) != my_id {
            game.marker = Some((Instant::now(), true));
            frontend_sound(c, "CHECKPOINT_NORMAL", "HUD_MINI_GAME_SOUNDSET");
            let balance = WALLET_CASH.fetch_add(500, Ordering::Relaxed) + 500;
            eprintln!("[economy] kill bounty: +$500 (balance: ${balance})");
            c.feed(&format!("~g~+$500~s~ [Takedown reward] | Wallet: ~g~${balance}~s~"));
            role_on_kill(c, victim);
        }
        c.c_str(S_TEXT, "STRING");
        c.c_str(S_NAME, &text);
        c.i("BeginTheFeedPost", &[c.ptr(S_TEXT)]);
        c.i("AddTextComponentSubStringPlayerName", &[c.ptr(S_NAME)]);
        c.i("EndTheFeedPostTicker", &[b(false), b(true)]);
    }

    if me_ok {
        let my_weapon = c.i("GetSelectedPedWeapon", &[i(ped)]) as u32;
        let melee = if my_weapon == weapon("weapon_unarmed") || my_weapon == 0 { 20 } else { 30 };
        for a in game.avatars.values_mut() {
            if my_weapon == weapon("weapon_stungun") && a.hit > 0 {
                a.hit = 1;
            }
            let bullet = std::mem::take(&mut a.bullet);
            if a.hit == 0 {
                a.hit = bullet;
            }
            if a.ped == 0 || a.dead || !c.exists(a.ped) {
                continue;
            }
            if c.i("HasEntityBeenDamagedByEntity", &[i(a.ped), i(ped), b(true)]) != 0 {
                if my_weapon == weapon("weapon_stungun") {
                    a.hit = 1;
                } else if a.hit == 0 {
                    a.hit = melee;
                }
                c.i("ClearEntityLastDamageEntity", &[i(a.ped)]);
            }
        }
    }
    let my_weapon = if me_ok { c.i("GetSelectedPedWeapon", &[i(ped)]) as u32 } else { 0 };
    let mut game_marker = game.marker;
    for (id, a) in game.avatars.iter_mut() {
        if !pvp_enabled() {
            a.hit = 0;
        }
        if a.hit > 0 {
            if my_weapon == weapon("weapon_unarmed") || my_weapon == 0 {
                a.hit = a.hit.min(15);
            } else if c.i("GetWeaponDamageType", &[i(my_weapon as i32)]) == 2 {
                a.hit = a.hit.min(30);
            }
            let mut p = vec![*id];
            p.extend(a.hit.to_le_bytes());
            p.extend(my_weapon.to_le_bytes());
            eprintln!("[mp] hit player {id}: {} damage (weapon {my_weapon:#x})", a.hit);
            if !matches!(game_marker, Some((_, true))) {
                game_marker = Some((Instant::now(), false));
            }
            send_reliable(net, proto::HIT, &p, Some(*id));
            a.hit = 0;
        }
        if a.car_hit != (0, 0, 0, 0) {
            let mut p = vec![*id];
            p.extend(a.car_hit.0.to_le_bytes());
            p.extend(a.car_hit.1.to_le_bytes());
            p.push(a.car_hit.2);
            p.extend(a.car_hit.3.to_le_bytes());
            p.push(0); // Vehicle death is authoritative in the owner's STATE.
            p.extend(a.veh_model.to_le_bytes());
            p.extend(a.veh_key.to_le_bytes());
            send_reliable(net, proto::VHIT, &p, Some(*id));
            a.car_hit = (0, 0, 0, 0);
        }
    }
    if game_marker.map(|m| m.0) != game.marker.map(|m| m.0) {
        frontend_sound(c, "NAV_UP_DOWN", "HUD_FRONTEND_DEFAULT_SOUNDSET");
        game.marker = game_marker;
    }

    let hits = std::mem::take(&mut *net.hits.lock().unwrap());
    if me_ok {
        let shielded = game.spawn_shield.is_some_and(|t| Instant::now() < t);
        for (from, target, dmg, w) in hits {
            if !pvp_enabled() || shielded || Some(target) != my_id || c.i("IsPedDeadOrDying", &[i(ped), b(true)]) != 0 {
                continue;
            }
            {
                let now = Instant::now();
                let mut guard = KNOCKDOWN.lock().unwrap();
                let k = guard.get_or_insert_with(Knockdown::default);
                let melee_hit = w == 0 || w == weapon("weapon_unarmed") || c.i("GetWeaponDamageType", &[i(w as i32)]) == 2;
                if melee_hit {
                    if k.immune_until.is_some_and(|t| now < t) { continue; }
                    if k.last_melee.iter().any(|(id, t)| *id == from && now.duration_since(*t) < MELEE_HIT_EVERY) { continue; }
                    k.last_melee.retain(|(id, t)| *id != from && now.duration_since(*t) < Duration::from_secs(5));
                    k.last_melee.push((from, now));
                }
                if w == weapon("weapon_stungun") {
                    k.allow_until = Some(now + Duration::from_millis(5500));
                    k.can_ragdoll = Some(true);
                    c.i("SetPedCanRagdoll", &[i(ped), b(true)]);
                }
            }
            game.hurt.retain(|(id, _)| *id != from);
            game.hurt.push((from, Instant::now()));
            eprintln!("[mp] got hit: {dmg} damage (weapon {w:#x}), health {}", c.i("GetEntityHealth", &[i(ped)]));

            if w == weapon("weapon_stungun") {
                if c.i("IsPedInAnyVehicle", &[i(ped), b(false)]) == 0 {
                    c.i("SetPedToRagdoll", &[i(ped), i(4000), i(5000), i(0), b(false), b(false), b(false)]);
                }
                continue;
            }

            const DAMAGE_MELEE: i32 = 2;
            if w != 0 && c.i("GetWeaponDamageType", &[i(w as i32)]) == DAMAGE_MELEE {
                c.c_str(S_NAME, "SMALL_EXPLOSION_SHAKE");
                c.i("ShakeGameplayCam", &[c.ptr(S_NAME), f(0.25)]);
                if w != weapon("weapon_unarmed") && dmg >= 25 && c.i("IsPedInAnyVehicle", &[i(ped), b(false)]) == 0 && c.i("IsPedRagdoll", &[i(ped)]) == 0 {
                    let mut guard = KNOCKDOWN.lock().unwrap();
                    let k = guard.get_or_insert_with(Knockdown::default);
                    k.allow_until = Some(Instant::now() + Duration::from_millis(1500));
                    k.can_ragdoll = Some(true);
                    drop(guard);
                    c.i("SetPedCanRagdoll", &[i(ped), b(true)]);
                    c.i("SetPedToRagdoll", &[i(ped), i(500), i(700), i(0), b(false), b(false), b(false)]);
                }
            }
            let mut dmg = dmg as i32;
            if w == weapon("weapon_unarmed") || w == 0 {
                dmg = dmg.clamp(5, 15);
            } else if c.i("GetWeaponDamageType", &[i(w as i32)]) == DAMAGE_MELEE {
                dmg = dmg.clamp(10, 30);
            }
            let armour = c.i("GetPedArmour", &[i(ped)]);
            let soak = armour.min(dmg);
            if soak > 0 {
                c.i("SetPedArmour", &[i(ped), i(armour - soak)]);
                dmg -= soak;
            }
            if dmg > 0 {
                let h = c.i("GetEntityHealth", &[i(ped)]) - dmg;

                c.i("SetEntityHealth", &[i(ped), i(if h < 100 { 0 } else { h }), i(0)]);
            }
        }
    }
    if me_ok && pvp_enabled() {
        knockdown_guard(c, game, ped, my_pos);
    }
    let car_hits = std::mem::take(&mut *net.car_hits.lock().unwrap());
    if my_car != 0 && pvp_enabled() && c.i("GetPedInVehicleSeat", &[i(my_car), i(-1), b(false)]) == ped {
        let model = c.i("GetEntityModel", &[i(my_car)]) as u32;
        for (target, de, db, tyres, dk, reported_model) in car_hits {
            if Some(target) != my_id {
                continue;
            }
            if !proto::vehicle_hit_targets_current_car(reported_model,model,my_car as u32) { continue; }
            if dk > 0 {
                let t = c.f("GetVehiclePetrolTankHealth", &[i(my_car)]);
                c.i("SetVehiclePetrolTankHealth", &[i(my_car), f(t - dk as f32)]);
            }
            let e = c.f("GetVehicleEngineHealth", &[i(my_car)]);
            c.i("SetVehicleEngineHealth", &[i(my_car), f(e - de as f32)]);
            let bh = c.f("GetVehicleBodyHealth", &[i(my_car)]);
            c.i("SetVehicleBodyHealth", &[i(my_car), f(bh - db as f32)]);
            for w in 0..6 {
                if tyres & (1 << w) != 0 {
                    c.i("SetVehicleTyreBurst", &[i(my_car), i(w), b(false), f(1000.0)]);
                }
            }
        }
    }

    let clock = c.i("GetClockHours", &[]) * 60 + c.i("GetClockMinutes", &[]);
    if let (Some(seen), false) = (game.clock_seen, states.is_empty()) {
        let jump = (clock - seen).rem_euclid(1440);
        if jump > 5 && jump < 1435 {
            c.i("SetClockTime", &[i(seen / 60), i(seen % 60), i(0)]);
            eprintln!("[mp] clock jumped {:02}:{:02} -> {:02}:{:02}: kept the session's", seen / 60, seen % 60, clock / 60, clock % 60);
        } else {
            game.clock_seen = Some(clock);
        }
    } else {
        game.clock_seen = Some(clock);
    }
    if let Some(me) = my_id {
        let lowest = states.iter().map(|(id, ..)| *id).chain(std::iter::once(me)).min().unwrap_or(me);
        if lowest == me && !states.is_empty() && game.last_time.elapsed() >= Duration::from_secs(1) {
            game.last_time = Instant::now();
            let w = c.i("GetNextWeatherTypeHashName", &[]) as u32;
            let wi = proto::WEATHERS.iter().position(|n| proto::joaat(n) == w).unwrap_or(255) as u8;
            let mut t = vec![c.i("GetClockHours", &[]) as u8, c.i("GetClockMinutes", &[]) as u8, c.i("GetClockSeconds", &[]) as u8, wi];

            let (prev, next, mix) = weather_state(c);
            t.extend([prev.clamp(0, 255) as u8, next.clamp(0, 255) as u8]);
            t.extend(mix.to_le_bytes());
            let _ = net.sock.send(&proto::packet(proto::TIME, &t));
        }
        let follow = net.time.lock().unwrap().take();
        if let Some((from, [h, m, sec, wi], state)) = follow {
            if from == lowest && from != me {
                let now = c.i("GetClockHours", &[]) * 60 + c.i("GetClockMinutes", &[]);
                let want = h as i32 * 60 + m as i32;
                let off = (now - want).rem_euclid(1440).min((want - now).rem_euclid(1440));
                if off > 1 {
                    c.i("SetClockTime", &[i(h as i32), i(m as i32), i(sec as i32)]);
                }
                game.clock_seen = Some(want);
                if let Some((prev, next, mix)) = state {
                    const STATE_SYNC: u8 = 254;
                    if game.weather != Some(STATE_SYNC) {
                        c.i("ClearWeatherTypePersist", &[]);
                        game.weather = Some(STATE_SYNC);
                    }
                    let (p0, n0, m0) = weather_state(c);
                    if p0 != prev as i32 || n0 != next as i32 || (m0 - mix).abs() > 0.03 {
                        c.i("SetWeatherState", &[i(prev as i32), i(next as i32), f(mix)]);
                    }
                } else if let Some(name) = proto::WEATHERS.get(wi as usize) {
                    if game.weather != Some(wi) {
                        c.c_str(S_NAME, name);
                        c.i("SetWeatherTypeNowPersist", &[c.ptr(S_NAME)]);
                        game.weather = Some(wi);
                    }
                }
            }
        }
    }

    OTHERS_HERE.store(!states.is_empty(), Ordering::Relaxed);
    if !states.is_empty() {
        c.i("SetTimeScale", &[f(1.0)]);
    }

    if !game.avatars.is_empty() {
        let _ = punch_anim(c);
    }

    let shots = std::mem::take(&mut *net.shots.lock().unwrap());
    for (id, shot) in shots {
        if let Some(a) = game.avatars.get_mut(&id) {
            fire(c, a, &shot, me_ok.then_some(my_pos));
        }
    }

    let explosions = std::mem::take(&mut *net.explosions.lock().unwrap());
    for (id, kind, pos) in explosions {
        let owner = game.avatars.get(&id).map(|a| a.ped).filter(|p| c.exists(*p));
        let at = c.vec_arg(1, pos);
        match owner {
            Some(p) => c.i("AddOwnedExplosion", &[i(p), at, i(kind), f(1.0), b(true), b(false), f(1.0)]),
            None => c.i("AddExplosion", &[at, i(kind), f(1.0), b(true), b(false), f(1.0), b(false)]),
        };
    }

    let kills = std::mem::take(&mut *net.kills.lock().unwrap());
    for (owner, key) in kills {
        let ent = key as i32;
        if Some(owner) != my_id || ent == my_car || !c.exists(ent) || c.i("IsEntityAMissionEntity", &[i(ent)]) != 0 {
            continue;
        }
        if c.i("IsEntityAPed", &[i(ent)]) != 0 {
            c.i("SetEntityHealth", &[i(ent), i(0), i(0)]);
        } else if c.i("IsEntityDead", &[i(ent), b(false)]) == 0 {
            c.i("ExplodeVehicle", &[i(ent), b(true), b(false)]);
        }
    }

    let taken = std::mem::take(&mut *net.taken.lock().unwrap());
    for (owner, key) in taken {
        let veh = key as i32;
        if Some(owner) != my_id || !c.exists(veh) || c.i("IsEntityAMissionEntity", &[i(veh)]) != 0 {
            continue;
        }
        if me_ok && c.i("GetVehiclePedIsIn", &[i(ped), b(false)]) == veh {
            continue;
        }

        if game.avatars.values().any(|a| a.veh == veh) {
            continue;
        }
        let driver = c.i("GetPedInVehicleSeat", &[i(veh), i(-1), b(false)]);
        for e in [driver, veh] {
            if c.exists(e) {
                c.i("SetEntityAsMissionEntity", &[i(e), b(true), b(true)]);
            }
        }
        delete_ped(c, driver);
        delete_vehicle(c, veh);
    }

    if me_ok {
        draw_hud(c, game);
    }

    let names: HashMap<u8, String> = net.peers.lock().unwrap().iter().map(|(id, p)| {
        let tag = match p.snaps.back() {
            Some((t, _)) if t.elapsed() > Duration::from_millis(1500) => format!("{} (paused)", p.name),
            Some((_, s)) => format!("{} - {}%", p.name, ((s.health as i32 - 100).clamp(0, 100))),
            None => p.name.clone(),
        };
        let role = peer_role(*id);
        let tag = if role.jailed { format!("{tag} [Jailed]") } else if role.wanted > 0 { format!("{tag} [Wanted {}]", stars(role.wanted)) } else { tag };
        (*id, tag)
    }).collect();
    for (id, a) in &game.avatars {
        if a.dead || !c.exists(a.ped) || c.i("IsEntityOnScreen", &[i(a.ped)]) == 0 {
            continue;
        }
        let at = c.v("GetEntityCoords", &[i(a.ped), b(false)]);
        if dist(at, my_pos) < TAG_RANGE {
            name_tag(c, at, names.get(id).map(String::as_str).unwrap_or("Player"));
        }
    }

    if me_ok && game.last_player_loc_feed.elapsed() >= Duration::from_secs(45) {
        game.last_player_loc_feed = Instant::now();
        let other_peers: Vec<(u8, String, [f32; 3])> = net.peers.lock().unwrap().iter().filter_map(|(id, p)| {
            if Some(*id) == my_id { return None; }
            let pos = p.snaps.back().map(|(_, s)| if s.in_vehicle() { s.veh_pos } else { s.pos })?;
            Some((*id, p.name.clone(), pos))
        }).collect();

        if !other_peers.is_empty() {
            let mut nearest: Option<(&str, f32)> = None;
            for (_, name, pos) in &other_peers {
                let d = dist(my_pos, *pos);
                if nearest.as_ref().map(|(_, cd)| d < *cd).unwrap_or(true) {
                    nearest = Some((name.as_str(), d));
                }
            }
            if let Some((n_name, n_dist)) = nearest {
                c.feed(&format!("~b~[Mugoat Online]~s~ Co ~y~{}~s~ nguoi choi! Gan nhat: ~g~{}~s~ (~w~{:.0}m~s~)", other_peers.len(), n_name, n_dist));
            }
        }
    }

    const INPUT_ENTER: i32 = 23;
    let enter_held = c.i("IsControlPressed", &[i(0), i(INPUT_ENTER)]) != 0;
    let just_enter = (enter_held && !game.was_enter_pressed) || WANT_ENTER.swap(false, Ordering::Relaxed);
    game.was_enter_pressed = enter_held;

    if me_ok && c.i("IsPedInAnyVehicle", &[i(ped), b(false)]) == 0 {
        let mut near: Option<i32> = None;
        let mut min_d = f32::MAX;
        for a in game.avatars.values() {
            if a.veh != 0 && c.exists(a.veh) {
                let d = dist(c_pos(c, a.veh), my_pos);
                if d < min_d {
                    min_d = d;
                    near = Some(a.veh);
                }
            }
        }

        let trying = c.i("GetVehiclePedIsTryingToEnter", &[i(ped)]);
        let trying_friend = trying != 0 && game.avatars.values().any(|a| a.veh == trying);
        let entering_seat = if trying_friend { c.i("GetSeatPedIsTryingToEnter", &[i(ped)]) } else { -2 };
        let hijack_attempt = trying_friend && entering_seat == -1 && c.i("IsVehicleSeatFree", &[i(trying), i(-1), b(false)]) == 0;

        let debounce_ok = game.last_enter_task.map(|t| t.elapsed() > Duration::from_millis(1200)).unwrap_or(true);

        if (just_enter || hijack_attempt) && debounce_ok {
            let target_veh = if trying_friend { Some(trying) } else if min_d < 8.0 { near } else { None };
            if let Some(veh) = target_veh {
                let driver = c.i("GetPedInVehicleSeat", &[i(veh), i(-1), b(false)]);
                if driver != 0 && driver != ped {
                    let mut free_seat: Option<i32> = None;
                    for s in 0..6 {
                        if c.i("IsVehicleSeatFree", &[i(veh), i(s), b(false)]) != 0 {
                            free_seat = Some(s);
                            break;
                        }
                    }
                    if let Some(seat) = free_seat {
                        game.last_enter_task = Some(Instant::now());
                        let d = dist(c_pos(c, veh), my_pos);
                        let moving = c.f("GetEntitySpeed", &[i(veh)]) > 1.2;
                        if d < 2.5 && (moving || enter_held) {
                            c.i("ClearPedTasksImmediately", &[i(ped)]);
                            c.i("SetPedIntoVehicle", &[i(ped), i(veh), i(seat)]);
                            eprintln!("[mp] instant passenger enter friend's car {veh}, seat {seat}");
                        } else {
                            c.i("ClearPedTasks", &[i(ped)]);
                            c.i("TaskEnterVehicle", &[i(ped), i(veh), i(10000), i(seat), f(2.0), i(1), Val::I64(0)]);
                            eprintln!("[mp] entering friend's car {veh}, seat {seat}");
                        }
                    }
                }
            }
        }
    }

    if me_ok {
        population(c, game, net, my_id, ped, my_pos);
    }
}

fn frontend_sound(c: &mut Cmd, name: &str, set: &str) {
    c.c_str(S_DICT, name);
    c.c_str(S_CLIP, set);
    c.i("PlaySoundFrontend", &[i(-1), c.ptr(S_DICT), c.ptr(S_CLIP), b(true)]);
}

fn rect(c: &mut Cmd, x: f32, y: f32, w: f32, h: f32, rgba: [i32; 4]) {
    c.i("DrawRect", &[f(x), f(y), f(w), f(h), i(rgba[0]), i(rgba[1]), i(rgba[2]), i(rgba[3]), b(false)]);
}

fn draw_hud(c: &mut Cmd, game: &mut Game) {
    const ASPECT: f32 = 16.0 / 9.0;
    if let Some((t, kill)) = game.marker {
        let shown = if kill { 600 } else { 220 };
        let age = t.elapsed().as_millis() as i32;
        if age < shown {
            let alpha = 255 - 200 * age / shown;
            let col = if kill { [230, 40, 40, alpha] } else { [255, 255, 255, alpha] };
            let d = 0.0035;
            for k in 2..=5 {
                let o = k as f32 * d;
                for (sx, sy) in [(-1.0, -1.0), (1.0, -1.0), (-1.0, 1.0), (1.0, 1.0)] {
                    rect(c, 0.5 + sx * o, 0.5 + sy * o * ASPECT, 0.0028, 0.0028 * ASPECT, col);
                }
            }
        } else {
            game.marker = None;
        }
    }
    game.hurt.retain(|(_, t)| t.elapsed() < Duration::from_millis(1400));
    if game.hurt.is_empty() {
        return;
    }
    let ped = c.i("PlayerPedId", &[]);
    let me = c_pos(c, ped);
    let cam_yaw = c.v("GetGameplayCamRot", &[i(2)])[2];
    let hurt = game.hurt.clone();
    for (id, t) in hurt {
        let Some(a) = game.avatars.get(&id) else { continue };
        let ent = if a.veh != 0 { a.veh } else { a.ped };
        if ent == 0 || !c.exists(ent) {
            continue;
        }
        let at = c_pos(c, ent);

        let bearing = (-(at[0] - me[0])).atan2(at[1] - me[1]).to_degrees();
        let rel = (bearing - cam_yaw).to_radians();
        let alpha = (220.0 * (1.0 - t.elapsed().as_secs_f32() / 1.4)).max(0.0) as i32;
        for k in -3..=3 {
            let r = rel + k as f32 * 0.07;
            let (x, y) = (0.5 - 0.085 * r.sin(), 0.5 - 0.085 * ASPECT * r.cos());
            rect(c, x, y, 0.007, 0.007 * ASPECT, [220, 20, 20, alpha]);
        }
    }
}

fn weather_state(c: &mut Cmd) -> (i32, i32, f32) {
    c.i("GetWeatherState", &[c.ptr(S_INT), c.ptr(S_INT2), c.ptr(S_V3)]);
    (c.read_i32(S_INT), c.read_i32(S_INT2), c.read_f32(S_V3))
}

fn name_tag(c: &mut Cmd, at: [f32; 3], name: &str) {
    let m = c.mem();
    crate::write_bytes(m, c.scratch + S_TEXT, b"STRING\0");
    let mut end = name.len().min(96);
    while !name.is_char_boundary(end) { end -= 1; }
    let mut bytes = name.as_bytes()[..end].to_vec();
    bytes.push(0);
    crate::write_bytes(m, c.scratch + S_NAME, &bytes);
    let origin = c.vec_arg(1, [at[0], at[1], at[2] + 1.15]);
    c.i("SetDrawOrigin", &[origin, b(false)]);
    c.i("SetTextFont", &[i(4)]);
    c.i("SetTextScale", &[f(0.0), f(0.4)]);
    c.i("SetTextColour", &[i(255), i(255), i(255), i(235)]);
    c.i("SetTextCentre", &[b(true)]);
    c.i("SetTextOutline", &[]);
    c.i("BeginTextCommandDisplayText", &[c.ptr(S_TEXT)]);
    c.i("AddTextComponentSubStringPlayerName", &[c.ptr(S_NAME)]);
    c.i("EndTextCommandDisplayText", &[f(0.0), f(0.0), i(0)]);
    c.i("ClearDrawOrigin", &[]);
}

fn c_pos(c: &mut Cmd, ent: i32) -> [f32; 3] {
    c.v("GetEntityCoords", &[i(ent), b(false)])
}

fn local_state(c: &mut Cmd, game: &Game, ped: i32, pos: [f32; 3]) -> State {
    let mut s = State {
        ped_model: c.i("GetEntityModel", &[i(ped)]) as u32,
        pos,
        heading: c.f("GetEntityHeading", &[i(ped)]),
        vel: c.v("GetEntityVelocity", &[i(ped)]),
        weapon: c.i("GetSelectedPedWeapon", &[i(ped)]) as u32,
        health: c.i("GetEntityHealth", &[i(ped)]).clamp(0, 65535) as u16,
        armour: c.i("GetPedArmour", &[i(ped)]).clamp(0, 255) as u8,
        ..Default::default()
    };
    if c.i("IsPedDeadOrDying", &[i(ped), b(true)]) != 0 {
        s.flags |= proto::FLAG_DEAD;
    }
    if c.i("GetInteriorFromEntity", &[i(ped)]) != 0 {
        s.flags |= proto::FLAG_INSIDE;
    }
    if c.i("IsPedRagdoll", &[i(ped)]) != 0 {
        s.flags |= proto::FLAG_RAGDOLL;
    }

    let entering = c.i("GetVehiclePedIsTryingToEnter", &[i(ped)]);
    if entering != 0 && c.exists(entering) && c.i("IsPedInAnyVehicle", &[i(ped), b(false)]) == 0 {
        s.flags |= proto::FLAG_ENTERING;
        s.veh_model = c.i("GetEntityModel", &[i(entering)]) as u32;
        s.veh_pos = c.v("GetEntityCoords", &[i(entering), b(false)]);
        s.seat = c.i("GetSeatPedIsTryingToEnter", &[i(ped)]).clamp(-1, 6) as i8;
    }
    let player = c.i("PlayerId", &[]);

    const INPUT_AIM: i32 = 25;

    let armed = c.i("IsPedArmed", &[i(ped), i(4)]) != 0;
    let aiming = (armed && c.i("IsPlayerFreeAiming", &[i(player)]) != 0)
        || (armed && c.i("IsControlPressed", &[i(0), i(INPUT_AIM)]) != 0)
        || (armed && game.last_shot.elapsed() < Duration::from_millis(600));
    if aiming {
        s.flags |= proto::FLAG_AIMING;
        let cam = c.v("GetGameplayCamCoord", &[]);
        let rot = c.v("GetGameplayCamRot", &[i(2)]);
        let (pitch, yaw) = (rot[0].to_radians(), rot[2].to_radians());
        let dir = [-yaw.sin() * pitch.cos(), yaw.cos() * pitch.cos(), pitch.sin()];
        s.aim = [cam[0] + dir[0] * 40.0, cam[1] + dir[1] * 40.0, cam[2] + dir[2] * 40.0];
    }
    let veh = if c.i("IsPedInAnyVehicle", &[i(ped), b(false)]) != 0 { c.i("GetVehiclePedIsIn", &[i(ped), b(false)]) } else { 0 };
    if veh != 0 {
        s.flags |= proto::FLAG_IN_VEHICLE;
        s.veh_key = veh as u32;
        s.veh_model = c.i("GetEntityModel", &[i(veh)]) as u32;
        s.veh_pos = c.v("GetEntityCoords", &[i(veh), b(false)]);
        s.veh_rot = c.v_packed("GetEntityRotation", &[i(veh), i(2)]);
        s.veh_vel = c.v("GetEntityVelocity", &[i(veh)]);
        s.seat = (-1..6).find(|seat| c.i("GetPedInVehicleSeat", &[i(veh), i(*seat), b(false)]) == ped).unwrap_or(-1) as i8;

        let driver_ped = c.i("GetPedInVehicleSeat", &[i(veh), i(-1), b(false)]);
        s.veh_owner = game.avatars.iter().find(|(_, a)| (driver_ped != 0 && a.ped == driver_ped) || (a.veh != 0 && a.veh == veh)).map(|(id, _)| *id).unwrap_or(0);
        let (p1, p2) = (c.ptr(S_INT), c.ptr(S_INT2));
        c.i("GetVehicleColours", &[i(veh), p1, p2]);
        s.veh_colours = [c.read_i32(S_INT).clamp(0, 255) as u8, c.read_i32(S_INT2).clamp(0, 255) as u8];
        let h = |v: f32| v.clamp(-4000.0, 1000.0) as i16;
        s.veh_engine = h(c.f("GetVehicleEngineHealth", &[i(veh)]));
        s.veh_body = h(c.f("GetVehicleBodyHealth", &[i(veh)]));
        s.veh_tank = h(c.f("GetVehiclePetrolTankHealth", &[i(veh)]));
        s.veh_tyres = (0..6).filter(|w| c.i("IsVehicleTyreBurst", &[i(veh), i(*w), b(false)]) != 0).fold(0, |m, w| m | 1 << w);
        s.veh_windows = (0..8).filter(|w| c.i("IsVehicleWindowIntact", &[i(veh), i(*w)]) == 0).fold(0, |m, w| m | 1 << w);
        s.veh_dead = c.i("IsEntityDead", &[i(veh), b(false)]) != 0;
    }
    s
}

fn read_look(c: &mut Cmd, ped: i32) -> Look {
    let mut look = Look::default();
    for (k, comp) in look.comps.iter_mut().enumerate() {
        let k = k as i32;
        *comp = (
            c.i("GetPedDrawableVariation", &[i(ped), i(k)]).clamp(0, 65535) as u16,
            c.i("GetPedTextureVariation", &[i(ped), i(k)]).clamp(0, 255) as u8,
            c.i("GetPedPaletteVariation", &[i(ped), i(k)]).clamp(0, 255) as u8,
        );
    }
    for (k, prop) in look.props.iter_mut().enumerate() {
        let anchor = proto::PROP_SLOTS[k];
        *prop = (
            c.i("GetPedPropIndex", &[i(ped), i(anchor)]).clamp(-1, 32767) as i16,
            c.i("GetPropTextureIndex", &[i(ped), i(anchor)]).clamp(0, 255) as u8,
        );
    }
    look
}

fn apply_look(c: &mut Cmd, ped: i32, look: &Look) {
    for (k, (d, t, p)) in look.comps.iter().enumerate() {
        c.i("SetPedComponentVariation", &[i(ped), i(k as i32), i(*d as i32), i(*t as i32), i(*p as i32)]);
    }
    for (k, (idx, t)) in look.props.iter().enumerate() {
        let anchor = proto::PROP_SLOTS[k];
        if *idx < 0 {
            c.i("ClearPedProp", &[i(ped), i(anchor)]);
        } else {
            c.i("SetPedPropIndex", &[i(ped), i(anchor), i(*idx as i32), i(*t as i32), b(true)]);
        }
    }
}

fn local_shot(c: &mut Cmd, ped: i32, pos: [f32; 3]) -> Shot {
    let zero = c.vec_arg(2, [0.0; 3]);
    let hand = c.v("GetPedBoneCoords", &[i(ped), i(BONE_RIGHT_HAND), zero]);
    let from = if dist(hand, pos) < 3.0 { hand } else { pos };
    let hit = c.i("GetPedLastWeaponImpactCoord", &[i(ped), c.ptr(S_V3)]) != 0;
    let impact = [c.read_f32(S_V3), c.read_f32(S_V3 + 4), c.read_f32(S_V3 + 8)];
    let to = if hit && dist(impact, from) < 1500.0 {
        impact
    } else {
        let h = c.f("GetEntityHeading", &[i(ped)]).to_radians();
        [from[0] - 100.0 * h.sin(), from[1] + 100.0 * h.cos(), from[2]]
    };
    Shot { weapon: c.i("GetSelectedPedWeapon", &[i(ped)]) as u32, from, to }
}

fn bullet_on_driver(c: &mut Cmd, game: &mut Game, weapon_hash: u32, at: [f32; 3]) {
    if weapon_hash == weapon("weapon_stungun") {
        return;
    }

    const BONE_SPINE3: i32 = 24818;
    const BONE_HEAD: i32 = 31086;
    for a in game.avatars.values_mut() {
        if a.ped == 0 || a.dead || !c.exists(a.ped) || c.i("IsPedInAnyVehicle", &[i(a.ped), b(false)]) == 0 {
            continue;
        }
        let zero = c.vec_arg(2, [0.0; 3]);
        let lo = c.v("GetPedBoneCoords", &[i(a.ped), i(BONE_SPINE3), zero]);
        let zero = c.vec_arg(2, [0.0; 3]);
        let hi = c.v("GetPedBoneCoords", &[i(a.ped), i(BONE_HEAD), zero]);
        let veh = c.i("GetVehiclePedIsIn", &[i(a.ped), b(false)]);
        let speed = if veh != 0 { c.f("GetEntitySpeed", &[i(veh)]) } else { 0.0 };

        if seg_dist(at, lo, hi) < 0.3 + speed * 0.03 && at[2] > lo[2] - 0.1 {
            let dmg = c.f("GetWeaponDamage", &[i(weapon_hash as i32), i(0)]).clamp(5.0, 200.0) as u16;
            a.bullet = a.bullet.saturating_add(dmg);
        }
    }
}

fn seg_dist(p: [f32; 3], a: [f32; 3], b: [f32; 3]) -> f32 {
    let ab = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
    let len2 = ab[0] * ab[0] + ab[1] * ab[1] + ab[2] * ab[2];
    let t = if len2 > 0.0 { (((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1] + (p[2] - a[2]) * ab[2]) / len2).clamp(0.0, 1.0) } else { 0.0 };
    dist(p, [a[0] + ab[0] * t, a[1] + ab[1] * t, a[2] + ab[2] * t])
}

fn fire(c: &mut Cmd, a: &mut Avatar, shot: &Shot, me: Option<[f32; 3]>) {
    if !c.exists(a.ped) || a.dead {
        return;
    }

    const DAMAGE_MELEE: i32 = 2;
    if c.i("GetWeaponDamageType", &[i(shot.weapon as i32)]) == DAMAGE_MELEE {
        swing(c, a, shot.to);
        return;
    }
    if a.veh == 0 && a.walk.since.is_none() {
        let tgt = c.vec_arg(1, shot.to);
        c.i("TaskAimGunAtCoord", &[i(a.ped), tgt, i(800), b(false), b(false)]);
        a.aim_until = Some(Instant::now() + Duration::from_millis(800));
    }

    if c.i("HasWeaponAssetLoaded", &[i(shot.weapon as i32)]) == 0 {
        c.i("RequestWeaponAsset", &[i(shot.weapon as i32), i(31), i(0)]);
    }

    let mut target = shot.to;
    if let Some(me) = me {
        if dist(target, me) < 2.5 {
            target = [me[0] + (me[0] - shot.from[0]).signum() * 1.5, me[1] + (me[1] - shot.from[1]).signum() * 1.5, me[2] + 1.6];
        }
    }
    let t = c.vec_arg(3, target);
    c.i("SetPedShootsAtCoord", &[i(a.ped), t, b(true)]);
}

const PUNCHES: &[(&str, &str)] = &[
    ("melee@unarmed@streamed_core", "heavy_punch_a"),
    ("melee@unarmed@streamed_core", "short_0_punch"),
    ("melee@unarmed@streamed_variations", "plyr_takedown_front_slap"),
    ("melee@unarmed@streamed_core", "plyr_running_att"),
    ("melee@unarmed@streamed_core", "ground_att_on_spot"),
];

fn punch_anim(c: &mut Cmd) -> Option<(&'static str, &'static str)> {
    static PICK: Mutex<(usize, Option<usize>)> = Mutex::new((0, None));
    let mut pick = PICK.lock().unwrap();
    if let Some(k) = pick.1 {
        let (dict, clip) = PUNCHES[k];
        c.c_str(S_DICT, dict);
        if c.i("HasAnimDictLoaded", &[c.ptr(S_DICT)]) == 0 {
            c.i("RequestAnimDict", &[c.ptr(S_DICT)]);
            return None;
        }
        return Some((dict, clip));
    }
    while let Some(&(dict, clip)) = PUNCHES.get(pick.0) {
        c.c_str(S_DICT, dict);
        if c.i("DoesAnimDictExist", &[c.ptr(S_DICT)]) == 0 {
            pick.0 += 1;
            continue;
        }
        if c.i("HasAnimDictLoaded", &[c.ptr(S_DICT)]) == 0 {
            c.i("RequestAnimDict", &[c.ptr(S_DICT)]);
            return None;
        }
        c.c_str(S_CLIP, clip);
        if c.f("GetAnimDuration", &[c.ptr(S_DICT), c.ptr(S_CLIP)]) > 0.0 {
            eprintln!("[mp] punch animation: {dict} {clip}");
            pick.1 = Some(pick.0);
            return Some((dict, clip));
        }
        pick.0 += 1;
    }
    if pick.0 == PUNCHES.len() {
        eprintln!("[mp] no punch animation found");
        pick.0 += 1;
    }
    None
}

fn swing(c: &mut Cmd, a: &mut Avatar, to: [f32; 3]) {
    if a.veh != 0 || a.ragdoll.is_some() || c.i("IsPedRagdoll", &[i(a.ped)]) != 0 {
        return;
    }
    let Some((dict, clip)) = punch_anim(c) else { return };
    let at = c.v("GetEntityCoords", &[i(a.ped), b(false)]);
    if dist(at, to) > 0.2 {
        c.i("SetEntityHeading", &[i(a.ped), f((-(to[0] - at[0])).atan2(to[1] - at[1]).to_degrees())]);
    }
    c.c_str(S_DICT, dict);
    c.c_str(S_CLIP, clip);
    const UPPER_BODY_SECONDARY: i32 = 16 | 32;
    c.i("TaskPlayAnim", &[i(a.ped), c.ptr(S_DICT), c.ptr(S_CLIP), f(8.0), f(-8.0), i(-1), i(UPPER_BODY_SECONDARY), f(0.0), b(false), i(0), b(false)]);
}

fn despawn(c: &mut Cmd, a: Avatar) {
    if a.blip != 0 {
        let r = c.ref_arg(a.blip);
        c.i("RemoveBlip", &[r]);
    }
    if c.exists(a.ped) {
        let r = c.ref_arg(a.ped);
        c.i("DeletePed", &[r]);
    }
    if c.exists(a.veh) {
        let r = c.ref_arg(a.veh);
        c.i("DeleteVehicle", &[r]);
    }
}

fn delete_vehicle(c: &mut Cmd, veh: i32) {
    if c.exists(veh) {
        if c.i("IsEntityAMissionEntity", &[i(veh)]) == 0 {
            c.i("SetEntityAsMissionEntity", &[i(veh), b(true), b(true)]);
        }
        let r = c.ref_arg(veh);
        c.i("DeleteVehicle", &[r]);
    }
}

static PARKED: Mutex<Vec<(i32, u32, Instant, u8)>> = Mutex::new(Vec::new());

const PARKED_KEEP: Duration = Duration::from_secs(300);

fn park(veh: i32, model: u32, owner: u8) {
    PARKED.lock().unwrap().push((veh, model, Instant::now(), owner));
}

fn unpark(veh: i32) {
    PARKED.lock().unwrap().retain(|p| p.0 != veh);
}

fn adopt_parked(c: &mut Cmd, model: u32, pos: [f32; 3]) -> Option<i32> {
    let list: Vec<(i32, u32, Instant, u8)> = PARKED.lock().unwrap().clone();
    let mut found = None;
    let mut keep = Vec::new();
    for (veh, m, t, owner) in list {
        if !c.exists(veh) || c.i("IsEntityDead", &[i(veh), b(false)]) != 0 {
            continue;
        }
        if t.elapsed() > PARKED_KEEP {
            release(c, veh);
            continue;
        }
        if found.is_none() && m == model && dist(c.v("GetEntityCoords", &[i(veh), b(false)]), pos) < 6.0 {
            found = Some(veh);
            continue;
        }
        keep.push((veh, m, t, owner));
    }
    *PARKED.lock().unwrap() = keep;
    found
}

fn tidy_parked(c: &mut Cmd, where_: &HashMap<u8, [f32; 3]>) {
    const KEEP_NEAR: f32 = 300.0;
    let list: Vec<(i32, u32, Instant, u8)> = PARKED.lock().unwrap().clone();
    let mut keep = Vec::new();
    for (veh, m, t, owner) in list {
        if !c.exists(veh) {
            continue;
        }
        if owner != 0 {
            let at = c.v("GetEntityCoords", &[i(veh), b(false)]);
            let far = where_.get(&owner).map(|p| dist(*p, at) > KEEP_NEAR).unwrap_or(true);
            if far && c.i("IsEntityOnScreen", &[i(veh)]) == 0 {
                delete_vehicle(c, veh);
                continue;
            }
        }
        keep.push((veh, m, t, owner));
    }
    *PARKED.lock().unwrap() = keep;
}

fn delete_ped(c: &mut Cmd, ped: i32) {
    if c.exists(ped) {
        let r = c.ref_arg(ped);
        c.i("DeletePed", &[r]);
    }
}

fn model_ready(c: &mut Cmd, model: u32) -> bool {
    if model == 0 {
        return false;
    }
    if c.i("HasModelLoaded", &[i(model as i32)]) != 0 {
        return true;
    }
    c.i("RequestModel", &[i(model as i32)]);
    false
}

fn players_group(c: &mut Cmd) -> i32 {
    static GROUP: std::sync::atomic::AtomicI32 = std::sync::atomic::AtomicI32::new(0);
    let mut g = GROUP.load(Ordering::Relaxed);
    if g == 0 || c.i("DoesRelationshipGroupExist", &[i(g)]) == 0 {
        c.c_str(S_NAME, "MP_PLAYERS");
        c.i("AddRelationshipGroup", &[c.ptr(S_NAME), c.ptr(S_INT)]);
        g = c.read_i32(S_INT);
        GROUP.store(g, Ordering::Relaxed);
    }
    let me = c.i("PlayerPedId", &[]);
    if g != 0 && c.exists(me) {
        let pvp = pvp_enabled();
        let rel: i32 = if pvp { 4 /* DISLIKE */ } else { 0 /* COMPANION */ };
        let mine = c.i("GetPedRelationshipGroupHash", &[i(me)]);
        c.i("SetRelationshipBetweenGroups", &[i(rel), i(g), i(mine)]);
        c.i("SetRelationshipBetweenGroups", &[i(rel), i(mine), i(g)]);

        c.i("SetRelationshipGroupAffectsWantedLevel", &[i(g), b(false)]);
        c.i("SetCanAttackFriendly", &[i(me), b(pvp), b(false)]);
    }
    g
}

fn obedient_ped(c: &mut Cmd, model: u32, pos: [f32; 3], heading: f32) -> i32 {
    let p = c.vec_arg(1, pos);
    let ped = c.i("CreatePed", &[i(4), i(model as i32), p, f(heading), b(false), b(false)]);
    if ped != 0 {
        c.i("SetBlockingOfNonTemporaryEvents", &[i(ped), b(true)]);
        c.i("SetPedKeepTask", &[i(ped), b(true)]);
        c.i("SetPedCanBeDraggedOut", &[i(ped), b(false)]);
    }
    ped
}

fn update_avatar(c: &mut Cmd, owner: u8, a: &mut Avatar, s: &State, look: Option<Look>, cars: &HashMap<u8, i32>) {
    let died_here = a.ped != 0 && !a.dead && !s.dead() && c.exists(a.ped) && c.i("IsPedDeadOrDying", &[i(a.ped), b(true)]) != 0;
    if a.ped != 0 && (!c.exists(a.ped) || a.ped_model != s.ped_model || (a.dead && !s.dead()) || died_here) {
        let mut hit = a.hit;
        if died_here {
            let me = c.i("PlayerPedId", &[]);
            if me != 0 && (c.i("GetPedSourceOfDeath", &[i(a.ped)]) == me || c.i("HasEntityBeenDamagedByEntity", &[i(a.ped), i(me), b(true)]) != 0) {
                let unarmed = c.i("GetSelectedPedWeapon", &[i(me)]) as u32 == weapon("weapon_unarmed");
                hit = hit.saturating_add(if unarmed { 15 } else { 35 });
                eprintln!("[mp] finished avatar {} here: hit {hit}", a.ped);
            }
        }
        let respawned = a.dead && !s.dead();
        let old = std::mem::take(a);
        despawn(c, Avatar { veh: 0, ..old });
        if respawned && old.veh != 0 {
            if old.veh_damage.5 || c.i("IsEntityDead", &[i(old.veh), b(false)]) != 0 {
                release(c, old.veh);
            } else {
                delete_vehicle(c, old.veh);
            }
        } else {
            a.veh = old.veh;
            a.veh_model = old.veh_model;
            a.veh_key = old.veh_key;
        }
        a.hit = hit;
    }
    // Maintain global radar and map blip for the avatar so players can always find each other
    if s.dead() {
        if a.blip != 0 {
            let r = c.ref_arg(a.blip);
            c.i("RemoveBlip", &[r]);
            a.blip = 0;
            a.blip_is_entity = false;
        }
    } else if a.ped != 0 && c.exists(a.ped) {
        if a.blip != 0 && !a.blip_is_entity {
            let r = c.ref_arg(a.blip);
            c.i("RemoveBlip", &[r]);
            a.blip = 0;
        }
        if a.blip == 0 {
            a.blip = c.i("AddBlipForEntity", &[i(a.ped)]);
            a.blip_is_entity = true;
            if a.blip != 0 {
                c.i("ShowHeadingIndicatorOnBlip", &[i(a.blip), b(true)]);
                c.i("SetBlipAsShortRange", &[i(a.blip), b(false)]);
                c.i("SetBlipAsShortRange2", &[i(a.blip), b(false)]);
                c.i("SetBlipColour", &[i(a.blip), i(3)]);
                c.i("SetBlipColour2", &[i(a.blip), i(3)]);
                c.i("SetBlipScale", &[i(a.blip), f(0.85)]);
                c.i("SetBlipScale2", &[i(a.blip), f(0.85)]);
            }
        }
    } else {
        // Ped not spawned yet or far away: maintain coordinate blip visible across whole map
        if a.blip != 0 && a.blip_is_entity {
            let r = c.ref_arg(a.blip);
            c.i("RemoveBlip", &[r]);
            a.blip = 0;
            a.blip_is_entity = false;
        }
        let target_pos = if s.in_vehicle() { s.veh_pos } else { s.pos };
        let pos_arg = c.vec_arg(0, target_pos);
        if a.blip == 0 {
            let mut blip = c.i("AddBlipForCoord", &[pos_arg]);
            if blip == 0 {
                blip = c.i("AddBlipForCoord2", &[pos_arg]);
            }
            if blip != 0 {
                c.i("SetBlipSprite", &[i(blip), i(1)]);
                c.i("SetBlipSprite2", &[i(blip), i(1)]);
                c.i("SetBlipAsShortRange", &[i(blip), b(false)]);
                c.i("SetBlipAsShortRange2", &[i(blip), b(false)]);
                c.i("SetBlipColour", &[i(blip), i(3)]);
                c.i("SetBlipColour2", &[i(blip), i(3)]);
                c.i("SetBlipScale", &[i(blip), f(0.85)]);
                c.i("SetBlipScale2", &[i(blip), f(0.85)]);
                a.blip = blip;
                a.blip_is_entity = false;
            }
        } else {
            c.i("SetBlipCoords", &[i(a.blip), pos_arg]);
            c.i("SetBlipCoords2", &[i(a.blip), pos_arg]);
        }
    }

    if a.ped == 0 {
        if s.dead() || !model_ready(c, s.ped_model) {
            return;
        }
        let ped = obedient_ped(c, s.ped_model, s.pos, s.heading);
        if ped == 0 {
            return;
        }
        a.ped = ped;
        a.dead = false;
        a.dead_since = None;
        a.ped_model = s.ped_model;
        c.i("SetPedDefaultComponentVariation", &[i(ped)]);

        c.i("SetPedMaxHealth", &[i(ped), i(AVATAR_HEALTH)]);

        c.i("SetEntityProofs", &[i(ped), b(false), b(true), b(true), b(false), b(false), b(true), b(false), b(false)]);
        c.i("SetEntityHealth", &[i(ped), i(AVATAR_HEALTH), i(0)]);
        c.i("SetPedCanRagdoll", &[i(ped), b(false)]);

        let group = players_group(c);
        if group != 0 {
            c.i("SetPedRelationshipGroupHash", &[i(ped), i(group)]);
        }
        c.i("SetPedCanBeTargetted", &[i(ped), b(true)]);

        if a.blip != 0 && !a.blip_is_entity {
            let r = c.ref_arg(a.blip);
            c.i("RemoveBlip", &[r]);
            a.blip = 0;
        }
        a.blip = c.i("AddBlipForEntity", &[i(ped)]);
        a.blip_is_entity = true;
        if a.blip != 0 {
            c.i("ShowHeadingIndicatorOnBlip", &[i(a.blip), b(true)]);
            c.i("SetBlipAsShortRange", &[i(a.blip), b(false)]);
            c.i("SetBlipAsShortRange2", &[i(a.blip), b(false)]);
            c.i("SetBlipColour", &[i(a.blip), i(3)]);
            c.i("SetBlipColour2", &[i(a.blip), i(3)]);
            c.i("SetBlipScale", &[i(a.blip), f(0.85)]);
            c.i("SetBlipScale2", &[i(a.blip), f(0.85)]);
        }
        eprintln!("[mp] spawned avatar ped {ped} (model {:#x})", s.ped_model);
    }
    let ped = a.ped;

    if look.is_some() && look != a.look {
        apply_look(c, ped, look.as_ref().unwrap());
        a.look = look;
    }
    if s.weapon != a.weapon {
        if s.weapon != weapon("weapon_unarmed") {
            c.i("GiveWeaponToPed", &[i(ped), i(s.weapon as i32), i(9999), b(false), b(true)]);
        }
        c.i("SetCurrentPedWeapon", &[i(ped), i(s.weapon as i32), b(true)]);
        a.weapon = s.weapon;
    }
    if !s.dead() && !a.dead {
        let h = c.i("GetEntityHealth", &[i(ped)]);
        if h < AVATAR_HEALTH && h > 0 {
            let my_pid = c.i("PlayerPedId", &[]);
            let my_weapon = c.i("GetSelectedPedWeapon", &[i(my_pid)]) as u32;
            let cap = if my_weapon == weapon("weapon_unarmed") || my_weapon == 0 {
                15
            } else if c.i("GetWeaponDamageType", &[i(my_weapon as i32)]) == 2 {
                30
            } else {
                150
            };
            a.hit = a.hit.saturating_add(((AVATAR_HEALTH - h) as u16).min(cap));
            c.i("SetEntityHealth", &[i(ped), i(AVATAR_HEALTH), i(0)]);
        }
    }
    if s.dead() {
        if !a.dead {
            a.dead = true;
            a.dead_since = Some(Instant::now());
            c.i("SetEntityInvincible", &[i(ped), b(false)]);
            c.i("SetPedCanRagdoll", &[i(ped), b(true)]);
            c.i("SetEntityHealth", &[i(ped), i(0), i(0)]);
        } else if a.dead_since.is_some_and(|t| t.elapsed() > Duration::from_secs(6)) {
            // The player respawns elsewhere: don't leave their body (and name) where they died.
            let body = std::mem::replace(&mut a.ped, 0);
            if c.exists(body) {
                let r = c.ref_arg(body);
                c.i("DeletePed", &[r]);
            }
            a.dead_since = None;
        }
        return;
    }

    if s.in_vehicle() && s.veh_owner != 0 {
        delete_vehicle(c, std::mem::take(&mut a.veh));
        if let Some(&car) = cars.get(&s.veh_owner) {
            let in_car = c.i("GetVehiclePedIsIn", &[i(ped), b(false)]);
            if in_car != car {
                let mut target_seat: Option<i32> = if c.i("IsVehicleSeatFree", &[i(car), i(s.seat as i32), b(false)]) != 0 {
                    Some(s.seat as i32)
                } else {
                    None
                };
                if target_seat.is_none() {
                    for seat in 0..6 {
                        if c.i("IsVehicleSeatFree", &[i(car), i(seat), b(false)]) != 0 {
                            target_seat = Some(seat);
                            break;
                        }
                    }
                }
                if let Some(ts) = target_seat {
                    c.i("SetPedIntoVehicle", &[i(ped), i(car), i(ts)]);
                }
            }
        } else {
            let pos = c.vec_arg(1, s.pos);
            c.i("SetEntityCoordsNoOffset", &[i(ped), pos, b(false), b(false), b(false)]);
        }
        return;
    }

    if s.in_vehicle() {
        if a.veh != 0 && (!c.exists(a.veh) || a.veh_model != s.veh_model || (s.veh_key != 0 && a.veh_key != s.veh_key)) {
            delete_vehicle(c, a.veh);
            a.veh = 0;
        }
        if a.veh == 0 {
            if !model_ready(c, s.veh_model) {
                let since = *a.veh_wait.get_or_insert_with(Instant::now);
                if since.elapsed() > Duration::from_secs(5) {
                    eprintln!("[mp] car model {:#x} still not loaded", s.veh_model);
                    a.veh_wait = Some(Instant::now());
                }
                return;
            }
            a.veh_wait = None;

            let sitting = c.i("GetVehiclePedIsIn", &[i(ped), b(false)]);
            let sitting = if sitting != 0 && c.exists(sitting) && c.i("GetEntityModel", &[i(sitting)]) as u32 == s.veh_model { Some(sitting) } else { None };
            if let Some(v) = sitting {
                unpark(v);
            }
            let veh = match sitting.or_else(|| adopt_parked(c, s.veh_model, s.veh_pos)) {
                Some(v) => v,
                None => {
                    let pos = c.vec_arg(1, s.veh_pos);
                    c.i("CreateVehicle", &[i(s.veh_model as i32), pos, f(s.veh_rot[2]), b(false), b(false), b(false)])
                }
            };
            if veh == 0 {
                return;
            }
            a.veh = veh;
            a.veh_model = s.veh_model;
            a.veh_key = s.veh_key;
            a.veh_colours = [255, 255];
            eprintln!("[mp] avatar car {veh} (model {:#x})", s.veh_model);
            a.veh_damage = (1000, 1000, 1000, 0, 0, false);
            a.car_hit = (0, 0, 0, 0);
            a.veh_look = None;
            a.vctl = None;
            c.i("SetVehicleEngineOn", &[i(veh), b(true), b(true), b(false)]);
        }
        let veh = a.veh;
        if a.veh_colours != s.veh_colours {
            c.i("SetVehicleColour", &[i(veh), i(s.veh_colours[0] as i32), i(s.veh_colours[1] as i32)]);
            a.veh_colours = s.veh_colours;
        }

        let climbing = a.entering.map(|(v, t)| v == veh && t.elapsed() < Duration::from_secs(3)).unwrap_or(false);
        if c.i("GetVehiclePedIsIn", &[i(ped), b(false)]) != veh && !climbing {
            c.i("SetPedIntoVehicle", &[i(ped), i(veh), i(s.seat as i32)]);
        }
        if !climbing {
            a.entering = None;
        }

        if !s.veh_dead && c.i("IsEntityDead", &[i(veh), b(false)]) != 0 {
            // Repair an observer-only wreck; never report it as owner death.
            c.i("SetVehicleFixed", &[i(veh)]);
            c.i("SetVehicleDeformationFixed", &[i(veh)]);
            a.veh_damage = (1000, 1000, 1000, 0, 0, false);
        }
        if !a.veh_damage.5 {
            let engine = c.f("GetVehicleEngineHealth", &[i(veh)]) as i16;
            let body = c.f("GetVehicleBodyHealth", &[i(veh)]) as i16;
            let tank = c.f("GetVehiclePetrolTankHealth", &[i(veh)]) as i16;
            let tyres = (0..6).filter(|w| c.i("IsVehicleTyreBurst", &[i(veh), i(*w), b(false)]) != 0).fold(0u8, |m, w| m | 1 << w);
            let me = c.i("PlayerPedId", &[]);
            let local_attack = pvp_enabled() && me != 0 && c.i("HasEntityBeenDamagedByEntity", &[i(veh), i(me), b(true)]) != 0;
            let [de, db, dk] = proto::vehicle_hit_delta([a.veh_damage.0, a.veh_damage.1, a.veh_damage.2], [engine,body,tank], local_attack);
            let dt = tyres & !a.veh_damage.3;
            if local_attack && (de > 5 || db > 5 || dk > 5 || dt != 0) {
                a.car_hit = (a.car_hit.0.saturating_add(de).min(5000), a.car_hit.1.saturating_add(db).min(5000), a.car_hit.2 | dt, a.car_hit.3.saturating_add(dk).min(5000));
            }
            if local_attack { c.i("ClearEntityLastDamageEntity", &[i(veh)]); }
            if (a.veh_damage.0 as i32 - engine as i32).abs() > 5 || (a.veh_damage.1 as i32 - body as i32).abs() > 5 || (a.veh_damage.2 as i32 - tank as i32).abs() > 5 {
                c.i("SetVehiclePetrolTankHealth", &[i(veh), f(a.veh_damage.2 as f32)]);

                c.i("SetVehicleEngineHealth", &[i(veh), f(a.veh_damage.0 as f32)]);
                c.i("SetVehicleBodyHealth", &[i(veh), f(a.veh_damage.1 as f32)]);
            }
        }
        apply_car_damage(c, veh, &mut a.veh_damage, (s.veh_engine, s.veh_body, s.veh_tank, s.veh_tyres, s.veh_windows, s.veh_dead));
        steer_vehicle(c, veh, s.veh_pos, s.veh_rot, s.veh_vel, a.veh_spin);
        return;
    }

    let leaving = a.leaving_until.map(|t| Instant::now() < t).unwrap_or(false);
    if !leaving && (a.veh != 0 || c.i("IsPedInAnyVehicle", &[i(ped), b(false)]) != 0) {
        let in_car = c.i("GetVehiclePedIsIn", &[i(ped), b(false)]);
        let slow = in_car != 0 && c.f("GetEntitySpeed", &[i(in_car)]) < 3.0;
        if slow && dist(c_pos(c, ped), s.pos) < 6.0 {
            c.i("TaskLeaveVehicle", &[i(ped), i(in_car), i(0)]);
            a.leaving_until = Some(Instant::now() + Duration::from_millis(2500));
        } else {
            let pos = c.vec_arg(1, s.pos);
            c.i("SetEntityCoordsNoOffset", &[i(ped), pos, b(false), b(false), b(false)]);
        }
        a.entering = None;
        let veh = std::mem::take(&mut a.veh);
        if a.veh_damage.5 {
            release(c, veh);
        } else if c.exists(veh) {
            park(veh, a.veh_model, owner);
        }
        a.walk.since = None;
    }
    if let Some(t) = a.leaving_until {
        if Instant::now() < t && c.i("IsPedInAnyVehicle", &[i(ped), b(false)]) != 0 && dist(c_pos(c, ped), s.pos) < 6.0 {
            return;
        }
        a.leaving_until = None;
    }

    if s.ragdoll() {
        let renew = a.ragdoll.map(|t| t.elapsed() > Duration::from_millis(400)).unwrap_or(true);
        if renew {
            let first = a.ragdoll.is_none();
            c.i("SetPedCanRagdoll", &[i(ped), b(true)]);
            c.i("SetPedToRagdoll", &[i(ped), i(600), i(800), i(0), b(false), b(false), b(false)]);
            if first {
                let v = c.vec_arg(1, s.vel);
                c.i("SetEntityVelocity", &[i(ped), v]);
            }
            a.ragdoll = Some(Instant::now());
        }
        a.walk.since = None;
        if dist(c_pos(c, ped), s.pos) > 6.0 {
            let pos = c.vec_arg(1, s.pos);
            c.i("SetEntityCoordsNoOffset", &[i(ped), pos, b(false), b(false), b(false)]);
        }
        return;
    }
    if a.ragdoll.take().is_some() {
        c.i("ClearPedTasksImmediately", &[i(ped)]);
        c.i("SetPedCanRagdoll", &[i(ped), b(false)]);
        a.walk.since = None;
    }
    if c.i("IsPedRagdoll", &[i(ped)]) != 0 {
        return;
    }

    if s.entering() {
        let busy = a.entering.map(|(v, t)| c.exists(v) && t.elapsed() < Duration::from_secs(6)).unwrap_or(false);
        if busy {
            return;
        }
        if let Some(v) = car_near(c, ped, s.veh_model, s.veh_pos) {
            if dist(c_pos(c, ped), c_pos(c, v)) < 10.0 {
                let speed = if s.vel[0].hypot(s.vel[1]) > 2.5 { 2.0 } else { 1.0 };
                c.i("TaskEnterVehicle", &[i(ped), i(v), i(6000), i(s.seat as i32), f(speed), i(1), Val::I64(0)]);
                a.entering = Some((v, Instant::now()));
                a.walk.since = None;
                return;
            }
        }
    } else if a.entering.take().is_some() {
        c.i("ClearPedTasks", &[i(ped)]);
        a.walk.since = None;
    }
    if s.aiming() {
        aim_walk(c, ped, &mut a.walk, s.pos, s.vel, s.aim);
        return;
    }
    if a.walk.aim.take().is_some() {
        c.i("ClearPedTasksImmediately", &[i(ped)]);
        a.walk.since = None;
    }
    let aiming = a.aim_until.map(|t| Instant::now() < t).unwrap_or(false);
    if !aiming {
        walk(c, ped, &mut a.walk, s.pos, s.vel, s.heading);
    }
}

fn car_near(c: &mut Cmd, ped: i32, model: u32, at: [f32; 3]) -> Option<i32> {
    let mut best: Option<(i32, f32)> = None;
    for v in c.nearby("GetNearbyVehicles", ped, S_VEHS, &[]) {
        if c.i("GetEntityModel", &[i(v)]) as u32 != model {
            continue;
        }
        let d = dist(c_pos(c, v), at);
        if d < 5.0 && best.map(|(_, bd)| d < bd).unwrap_or(true) {
            best = Some((v, d));
        }
    }
    best.map(|(v, _)| v)
}

fn read_vctl(c: &mut Cmd, veh: i32) -> [u8; 4] {
    c.i("GetVehicleLightsState", &[i(veh), c.ptr(S_INT), c.ptr(S_INT2)]);
    let lights = if c.read_i32(S_INT2) != 0 { 2 } else if c.read_i32(S_INT) != 0 { 1 } else { 0 };
    let doors = (0..6).filter(|d| c.f("GetVehicleDoorAngleRatio", &[i(veh), i(*d)]) > 0.15).fold(0u8, |m, d| m | 1 << d);
    let player = c.i("PlayerId", &[]);

    let horn = c.i("IsHornActive", &[i(veh)]) != 0 || c.i("IsPlayerPressingHorn", &[i(player)]) != 0 || crate::pad::horn_held();
    [lights, horn as u8, (c.i("IsVehicleSirenOn", &[i(veh)]) != 0) as u8, doors]
}

fn apply_vctl(c: &mut Cmd, a: &mut Avatar, want: [u8; 4]) {
    let veh = a.veh;
    let have = a.vctl.unwrap_or([255, 0, 255, 0]);
    if have[0] != want[0] {
        c.i("SetVehicleLights", &[i(veh), i(if want[0] > 0 { 2 } else { 1 })]);
        c.i("SetVehicleFullBeam", &[i(veh), b(want[0] == 2)]);
    }
    if have[2] != want[2] {
        c.i("SetVehicleSiren", &[i(veh), b(want[2] != 0)]);
    }

    let busy = a.entering.is_some() || a.leaving_until.is_some();
    for d in 0..6 {
        if busy {
            break;
        }
        let (was, now) = (have[3] & 1 << d != 0, want[3] & 1 << d != 0);
        if was != now {
            if now {
                c.i("SetVehicleDoorOpen", &[i(veh), i(d), b(false), b(false)]);
            } else {
                c.i("SetVehicleDoorShut", &[i(veh), i(d), b(false)]);
            }
        }
    }

    if want[1] != 0 && a.horn_at.map(|t| t.elapsed() > Duration::from_millis(250)).unwrap_or(true) {
        c.i("SoundCarHorn", &[i(veh), i(350), i(proto::joaat("HELDDOWN") as i32), b(false)]);
        a.horn_at = Some(Instant::now());
    }
    a.vctl = Some(want);
}

fn read_vlook(c: &mut Cmd, veh: i32) -> VehLook {
    let (p1, p2) = (c.ptr(S_INT), c.ptr(S_INT2));
    c.i("GetVehicleExtraColours", &[i(veh), p1, p2]);
    let mut l = VehLook {
        model: c.i("GetEntityModel", &[i(veh)]) as u32,
        extra_colours: [c.read_i32(S_INT).clamp(0, 255) as u8, c.read_i32(S_INT2).clamp(0, 255) as u8],
        livery: c.i("GetVehicleLivery", &[i(veh)]).clamp(-1, 127) as i8,
        window_tint: c.i("GetVehicleWindowTint", &[i(veh)]).clamp(-1, 127) as i8,
        wheel_type: c.i("GetVehicleWheelType", &[i(veh)]).clamp(-1, 127) as i8,
        ..Default::default()
    };
    for k in 0..50 {
        l.mods[k] = c.i("GetVehicleMod", &[i(veh), i(k as i32)]).clamp(-1, 127) as i8;
    }
    for t in 17..=22 {
        if c.i("IsToggleModOn", &[i(veh), i(t)]) != 0 {
            l.toggles |= 1 << (t - 17);
        }
    }
    l.radio = c.i("GetPlayerRadioStationIndex", &[]).clamp(0, 255) as u8;
    if let Some(Val::I64(p)) = call(c.caller, "mp:GetVehicleNumberPlateText", &[i(veh)]) {
        if p != 0 {
            let text = read_cstr(c.mem(), p as u64);
            for (k, ch) in text.bytes().take(8).enumerate() {
                l.plate[k] = ch;
            }
        }
    }
    l
}

fn apply_vlook(c: &mut Cmd, veh: i32, l: &VehLook) {
    c.i("SetVehicleExtraColours", &[i(veh), i(l.extra_colours[0] as i32), i(l.extra_colours[1] as i32)]);
    if l.livery >= 0 {
        c.i("SetVehicleLivery", &[i(veh), i(l.livery as i32)]);
    }
    if l.window_tint >= 0 {
        c.i("SetVehicleWindowTint", &[i(veh), i(l.window_tint as i32)]);
    }
    if l.mods.iter().any(|m| *m >= 0) || l.toggles != 0 {
        c.i("SetVehicleModKit", &[i(veh), i(0)]);
        if l.wheel_type >= 0 {
            c.i("SetVehicleWheelType", &[i(veh), i(l.wheel_type as i32)]);
        }
        for (k, m) in l.mods.iter().enumerate() {
            if *m >= 0 {
                c.i("SetVehicleMod", &[i(veh), i(k as i32), i(*m as i32), b(false)]);
            }
        }
        for t in 17..=22 {
            c.i("ToggleVehicleMod", &[i(veh), i(t), b(l.toggles & (1 << (t - 17)) != 0)]);
        }
    }
    let n = l.plate.iter().position(|b| *b == 0).unwrap_or(8);
    if n > 0 {
        c.c_str(S_NAME, &String::from_utf8_lossy(&l.plate[..n]));
        c.i("SetVehicleNumberPlateText", &[i(veh), c.ptr(S_NAME)]);
    }
}

fn apply_car_damage(c: &mut Cmd, veh: i32, have: &mut (i16, i16, i16, u8, u8, bool), want: (i16, i16, i16, u8, u8, bool)) {
    if want == *have {
        return;
    }

    if want.0 >= 990 && want.1 >= 990 && (have.0 < 900 || have.1 < 900 || have.3 & !want.3 != 0) {
        c.i("SetVehicleFixed", &[i(veh)]);
        c.i("SetVehicleDeformationFixed", &[i(veh)]);
        *have = (1000, 1000, 1000, 0, 0, false);
    }
    let close = |a: i16, b: i16| (a as i32 - b as i32).abs() < 5;
    if !close(want.0, have.0) {
        c.i("SetVehicleEngineHealth", &[i(veh), f(want.0 as f32)]);
    }
    if !close(want.1, have.1) {
        c.i("SetVehicleBodyHealth", &[i(veh), f(want.1 as f32)]);
    }
    if !close(want.2, have.2) {
        c.i("SetVehiclePetrolTankHealth", &[i(veh), f(want.2 as f32)]);
    }
    for w in 0..6 {
        if want.3 & !have.3 & (1 << w) != 0 {
            c.i("SetVehicleTyreBurst", &[i(veh), i(w), b(false), f(1000.0)]);
        }
    }
    for w in 0..8 {
        if want.4 & !have.4 & (1 << w) != 0 {
            c.i("SmashVehicleWindow", &[i(veh), i(w)]);
        }
    }
    if want.5 && !have.5 && c.i("IsEntityDead", &[i(veh), b(false)]) == 0 {
        c.i("ExplodeVehicle", &[i(veh), b(true), b(false)]);
    }
    *have = want;
}

fn release(c: &mut Cmd, ent: i32) {
    if c.exists(ent) {
        let r = c.ref_arg(ent);
        c.i("SetEntityAsNoLongerNeeded", &[r]);
    }
}

fn steer_vehicle(c: &mut Cmd, veh: i32, pos: [f32; 3], rot: [f32; 3], vel: [f32; 3], spin: f32) {
    let cur = c.v("GetEntityCoords", &[i(veh), b(false)]);
    let err = dist(cur, pos);
    if err > 6.0 {
        let p = c.vec_arg(1, pos);
        c.i("SetEntityCoordsNoOffset", &[i(veh), p, b(false), b(false), b(false)]);
        let r = c.vec_arg(2, rot);
        c.i("SetEntityRotation", &[i(veh), r, i(2), b(true)]);
        let v = c.vec_arg(3, vel);
        c.i("SetEntityVelocity", &[i(veh), v]);
        return;
    }
    let mut cur = cur;
    if err > 2.5 {
        let p = [cur[0] + (pos[0] - cur[0]) * 0.6, cur[1] + (pos[1] - cur[1]) * 0.6, cur[2] + (pos[2] - cur[2]) * 0.6];
        let pa = c.vec_arg(1, p);
        c.i("SetEntityCoordsNoOffset", &[i(veh), pa, b(false), b(false), b(false)]);
        cur = p;
    }

    const K: f32 = 5.0;
    let mut fix = [(pos[0] - cur[0]) * K, (pos[1] - cur[1]) * K, (pos[2] - cur[2]) * K];
    let len = (fix[0] * fix[0] + fix[1] * fix[1] + fix[2] * fix[2]).sqrt();
    if len > 12.0 {
        fix = fix.map(|v| v * 12.0 / len);
    }
    let v = c.vec_arg(3, [vel[0] + fix[0], vel[1] + fix[1], vel[2] + fix[2]]);
    c.i("SetEntityVelocity", &[i(veh), v]);

    let have = c.v_packed("GetEntityRotation", &[i(veh), i(2)]);
    let d = |a: f32, b: f32| (b - a + 540.0).rem_euclid(360.0) - 180.0;
    let (dp, dr, dy) = (d(have[0], rot[0]), d(have[1], rot[1]), d(have[2], rot[2]));
    if dy.abs() > 25.0 || dp.abs() > 12.0 || dr.abs() > 12.0 {
        let r = c.vec_arg(2, rot);
        c.i("SetEntityRotation", &[i(veh), r, i(2), b(true)]);
    } else {
        let yaw = (spin + dy * K).clamp(-360.0, 360.0).to_radians();
        let w = c.vec_arg(2, [dr.to_radians() * 2.0, dp.to_radians() * 2.0, yaw]);
        c.i("SetEntityAngularVelocity", &[i(veh), w]);
    }
}

fn aim_walk(c: &mut Cmd, ped: i32, w: &mut Walker, pos: [f32; 3], vel: [f32; 3], aim: [f32; 3]) {
    if c.i("IsPedRagdoll", &[i(ped)]) != 0 {
        return;
    }
    let cur = c.v("GetEntityCoords", &[i(ped), b(false)]);
    let err = dist(cur, pos);
    if err > 1.2 {
        let k = if err > 3.0 { 0.45 } else { 0.15 };
        let z = if (pos[2] - cur[2]).abs() > 0.8 { cur[2] + (pos[2] - cur[2]) * k } else { cur[2] };
        let p = c.vec_arg(1, [cur[0] + (pos[0] - cur[0]) * k, cur[1] + (pos[1] - cur[1]) * k, z]);
        c.i("SetEntityCoordsNoOffset", &[i(ped), p, b(false), b(false), b(false)]);
    }
    let speed = (vel[0].powi(2) + vel[1].powi(2)).sqrt();
    let moved = w.aim.map(|(a, t)| dist(a, aim) > 1.5 || t.elapsed() > Duration::from_millis(700)).unwrap_or(true);
    if !moved && (speed < 0.3) == w.since.is_none() {
        return;
    }
    let at = c.vec_arg(2, aim);
    if speed < 0.3 {
        c.i("TaskAimGunAtCoord", &[i(ped), at, i(1500), b(false), b(true)]);
        w.since = None;
    } else {
        let to = c.vec_arg(1, [pos[0] + vel[0] * 1.5, pos[1] + vel[1] * 1.5, pos[2]]);
        let blend = if speed > 2.2 { 2.0 } else { 1.0 };
        c.i("TaskGoToCoordWhileAimingAtCoord", &[i(ped), to, at, f(blend), b(false), f(0.5), f(4.0), b(false), i(0), b(true), i(proto::joaat("FIRING_PATTERN_FULL_AUTO") as i32)]);
        w.since = Some(Instant::now());
    }
    w.aim = Some((aim, Instant::now()));
}

/// Melee in PvP used to stun-lock: each hit could knock the player down, the next punches arrived
/// while they lay there, and an avatar pushed into them kept them down until they died.
#[derive(Default)]
struct Knockdown {
    /// Deliberate knockdowns (stun gun, heavy melee weapon) may ragdoll until then.
    allow_until: Option<Instant>,
    /// Melee hits are ignored until then (just got back up).
    immune_until: Option<Instant>,
    /// Last melee hit applied per attacker (spam limit).
    last_melee: Vec<(u8, Instant)>,
    ragdoll_since: Option<Instant>,
    can_ragdoll: Option<bool>,
}
static KNOCKDOWN: Mutex<Option<Knockdown>> = Mutex::new(None);
const MELEE_HIT_EVERY: Duration = Duration::from_millis(650);
const STAND_UP_AFTER: Duration = Duration::from_millis(2500);
const GET_UP_IMMUNITY: Duration = Duration::from_millis(2000);

/// Once per frame online: no ragdoll from other players' bodies pushing into this one (only from
/// deliberate knockdowns), and a player kept on the ground near another player gets back up.
fn knockdown_guard(c: &mut Cmd, game: &Game, ped: i32, my_pos: [f32; 3]) {
    let now = Instant::now();
    let mut guard = KNOCKDOWN.lock().unwrap();
    let k = guard.get_or_insert_with(Knockdown::default);
    let allowed = k.allow_until.is_some_and(|t| now < t);
    let in_car = c.i("IsPedInAnyVehicle", &[i(ped), b(false)]) != 0;
    let mut nearest = f32::MAX;
    for a in game.avatars.values() {
        if a.ped == 0 || a.veh != 0 || a.dead || !c.exists(a.ped) { continue; }
        nearest = nearest.min(dist(c_pos(c, a.ped), my_pos));
    }
    let want = in_car || allowed || nearest > 3.0;
    if k.can_ragdoll != Some(want) {
        c.i("SetPedCanRagdoll", &[i(ped), b(want)]);
        k.can_ragdoll = Some(want);
    }
    let down = !in_car && c.i("IsPedRagdoll", &[i(ped)]) != 0 && c.i("IsPedDeadOrDying", &[i(ped), b(true)]) == 0;
    if !down { k.ragdoll_since = None; return; }
    let since = *k.ragdoll_since.get_or_insert(now);
    let limit = if allowed { Duration::from_millis(5500) } else { STAND_UP_AFTER };
    if nearest < 10.0 && now.duration_since(since) > limit {
        c.i("ClearPedTasksImmediately", &[i(ped)]);
        k.ragdoll_since = None;
        k.allow_until = None;
        k.immune_until = Some(now + GET_UP_IMMUNITY);
        eprintln!("[mp] stood the player up after {:?} on the ground", now.duration_since(since));
    }
}

/// True when `pos` is inside the local player (an avatar moved there would shove them over).
fn on_local_player(c: &mut Cmd, pos: [f32; 3]) -> bool {
    let me = c.i("PlayerPedId", &[]);
    me != 0 && c.i("IsPedInAnyVehicle", &[i(me), b(false)]) == 0 && dist(c_pos(c, me), pos) < 1.1
}

fn walk(c: &mut Cmd, ped: i32, w: &mut Walker, pos: [f32; 3], vel: [f32; 3], heading: f32) {
    if c.i("IsPedRagdoll", &[i(ped)]) != 0 {
        return;
    }
    let cur = c.v("GetEntityCoords", &[i(ped), b(false)]);
    let speed = (vel[0].powi(2) + vel[1].powi(2)).sqrt();
    let err = dist(cur, pos);

    // Hard teleport only if out of bounds or desynced beyond 5m (never into the local player):
    if err > 5.0 && !on_local_player(c, pos) {
        let p = c.vec_arg(1, pos);
        c.i("SetEntityCoordsNoOffset", &[i(ped), p, b(false), b(false), b(false)]);
        w.since = None;
    }

    if speed < 0.3 {
        if err > 0.5 && err <= 5.0 {
            if w.since.is_none() || dist(pos, w.target) > 0.4 {
                let tgt = c.vec_arg(1, pos);
                c.i("TaskGoStraightToCoord", &[i(ped), tgt, f(1.0), i(-1), f(heading), f(0.1)]);
                w.target = pos;
                w.since = Some(Instant::now());
            }
            return;
        }
        if w.since.take().is_some() {
            c.i("ClearPedTasks", &[i(ped)]);
        }
        c.i("SetEntityHeading", &[i(ped), f(heading)]);
        return;
    }

    // Moving state (speed >= 0.3):
    // Smooth position correction without breaking ground collision / foot IK:
    if err > 1.2 {
        let k = if err > 3.0 { 0.35 } else { 0.1 };
        let z = if (pos[2] - cur[2]).abs() > 0.8 { cur[2] + (pos[2] - cur[2]) * k } else { cur[2] };
        let step = [cur[0] + (pos[0] - cur[0]) * k, cur[1] + (pos[1] - cur[1]) * k, z];
        if !on_local_player(c, step) {
            let p = c.vec_arg(2, step);
            c.i("SetEntityCoordsNoOffset", &[i(ped), p, b(false), b(false), b(false)]);
        }
    }

    let target = [pos[0] + vel[0] * 1.5, pos[1] + vel[1] * 1.5, pos[2]];
    let behind = err > 1.0 && ((pos[0] - cur[0]) * vel[0] + (pos[1] - cur[1]) * vel[1]) > 0.0;
    let blend: f32 = if speed > 5.5 { 3.0 } else if speed > 2.2 { 2.0 } else { 1.0 };
    let blend = if behind { (blend + 1.0).min(3.0) } else { blend };
    let stale = w.since.map(|t| t.elapsed() > Duration::from_millis(1000)).unwrap_or(true);
    if stale || dist(target, w.target) > 1.2 || w.blend != blend {
        let tgt = c.vec_arg(1, target);
        // Correctly pass remote player's heading, NOT 40000.0!
        c.i("TaskGoStraightToCoord", &[i(ped), tgt, f(blend), i(-1), f(heading), f(0.0)]);
        w.target = target;
        w.blend = blend;
        w.since = Some(Instant::now());
    }
}

fn population(c: &mut Cmd, game: &mut Game, net: &Net, my_id: Option<u8>, ped: i32, my_pos: [f32; 3]) {
    let Some(me) = my_id else { return };

    let near: Vec<(u8, f32, bool)> = {
        let peers = net.peers.lock().unwrap();
        peers.iter().filter_map(|(id, p)| {
            let s = p.snaps.back()?.1;
            let at = if s.in_vehicle() { s.veh_pos } else { s.pos };
            Some((*id, dist(at, my_pos), s.inside()))
        }).collect()
    };
    let range = |id: u8| if game.pop_owner == Some(id) { SHARE_FAR } else { SHARE_NEAR };

    let me_inside = c.i("GetInteriorFromEntity", &[i(ped)]) != 0;
    let owner = near.iter().filter(|(id, d, inside)| !inside && (me_inside || *id < me) && *d < range(*id)).map(|(id, ..)| *id).min();
    if owner != game.pop_owner {
        match owner {
            Some(o) => {
                eprintln!("[mp] traffic and pedestrians here are player {o}'s");

                let p = c.vec_arg(1, my_pos);
                c.i("ClearAreaOfVehicles", &[p, f(SHARE_FAR), b(false), b(false), b(false), b(false), b(false), b(false), b(false)]);

                if !me_inside {
                    let p = c.vec_arg(1, my_pos);
                    c.i("ClearAreaOfPeds", &[p, f(SHARE_FAR), b(false)]);
                }
            }
            None => eprintln!("[mp] traffic and pedestrians here are ours"),
        }
        let old: Vec<Mirror> = game.mirrors.drain().map(|(_, m)| m).collect();
        for m in old {
            remove_mirror(c, m);
        }
        game.pop_owner = owner;
    }

    match owner {
        None => {
            let someone_near = near.iter().any(|(_, d, _)| *d < SHARE_FAR);
            if someone_near && game.last_pop.elapsed() >= POP_EVERY {
                game.last_pop = Instant::now();
                let others: Vec<[f32; 3]> = {
                    let peers = net.peers.lock().unwrap();
                    peers.values().filter_map(|p| p.snaps.back()).map(|(_, s)| if s.in_vehicle() { s.veh_pos } else { s.pos }).filter(|at| dist(*at, my_pos) < SHARE_FAR).collect()
                };
                let entries = read_population(c, game, ped, my_pos, &others, false);
                send_pop(net, &entries);
            }
        }
        Some(_) => {
            if game.last_pop.elapsed() >= POP_EVERY {
                game.last_pop = Instant::now();
                let others: Vec<[f32; 3]> = {
                    let peers = net.peers.lock().unwrap();
                    peers.values().filter_map(|p| p.snaps.back()).map(|(_, s)| if s.in_vehicle() { s.veh_pos } else { s.pos }).filter(|at| dist(*at, my_pos) < SHARE_FAR).collect()
                };
                let entries = read_population(c, game, ped, my_pos, &others, true);
                let mut payload = Vec::new();
                proto::encode_pop(&entries, &mut payload);
                let _ = net.sock.send(&proto::packet(proto::POPX, &payload));
            }
        }
    }

    let sharing: Vec<u8> = near.iter().filter(|(_, d, _)| *d < SHARE_FAR).map(|(id, ..)| *id).collect();
    if owner.is_some() {
        c.i("SetVehicleDensityMultiplierThisFrame", &[f(0.0)]);
        c.i("SetRandomVehicleDensityMultiplierThisFrame", &[f(0.0)]);
        c.i("SetParkedVehicleDensityMultiplierThisFrame", &[f(0.0)]);
        c.i("SetPedDensityMultiplierThisFrame", &[f(0.0)]);
        c.i("SetScenarioPedDensityMultiplierThisFrame", &[f(0.0), f(0.0)]);
    }

    let lists: Vec<u8> = owner.into_iter().chain(sharing.iter().map(|o| o | EXTRAS)).collect();
    for o in lists {
        let entries = {
            let peers = net.peers.lock().unwrap();
            let list = |p: &Peer| if o & EXTRAS != 0 { p.extras.clone() } else { p.pop.clone() };
            peers.get(&(o & !EXTRAS)).and_then(list).filter(|(t, _)| t.elapsed() < Duration::from_secs(2)).map(|(t, e)| (t.elapsed(), e))
        };
        if let Some((age, mut entries)) = entries {
            let dt = age.as_secs_f32().min(0.3);
            for e in entries.iter_mut() {
                for k in 0..3 {
                    e.pos[k] += e.vel[k] * dt;
                }
            }
            mirror_population(c, game, net, o, &entries);
        }
    }

    let away: Vec<(u8, u32)> = game.mirrors.iter().filter(|(_, m)| m.seen.elapsed() > Duration::from_secs(6)).map(|(k, _)| *k).collect();
    for k in away {
        if let Some(m) = game.mirrors.remove(&k) {
            remove_mirror(c, m);
        }
    }
}

fn read_population(c: &mut Cmd, game: &Game, ped: i32, my_pos: [f32; 3], others: &[[f32; 3]], extras_only: bool) -> Vec<PopEntry> {
    let mine = c.i("GetVehiclePedIsIn", &[i(ped), b(false)]);
    let parked: Vec<i32> = if extras_only { PARKED.lock().unwrap().iter().map(|p| p.0).collect() } else { Vec::new() };
    let ours = |e: i32| e == ped || e == mine || game.avatars.values().any(|a| a.ped == e || a.veh == e) || game.mirrors.values().any(|m| m.ent == e || m.driver == e) || parked.contains(&e);

    let mut lookers = vec![ped];
    lookers.extend(game.avatars.values().filter(|a| a.ped != 0 && !a.dead && c.exists(a.ped) && dist(c.v("GetEntityCoords", &[i(a.ped), b(false)]), my_pos) < SHARE_FAR).map(|a| a.ped));
    let mut vehs: Vec<i32> = Vec::new();
    let mut peds: Vec<i32> = Vec::new();
    for l in &lookers {
        for v in c.nearby("GetNearbyVehicles", *l, S_VEHS, &[]) {
            if !vehs.contains(&v) {
                vehs.push(v);
            }
        }
        for p in c.nearby("GetNearbyPeds", *l, S_PEDS, &[i(-1)]) {
            if !peds.contains(&p) {
                peds.push(p);
            }
        }
    }
    let mut out = Vec::new();
    for veh in vehs {
        if ours(veh) || c.i("IsEntityAMissionEntity", &[i(veh)]) != 0 {
            continue;
        }
        let pos = c.v("GetEntityCoords", &[i(veh), b(false)]);
        let driver = c.i("GetPedInVehicleSeat", &[i(veh), i(-1), b(false)]);
        out.push(PopEntry {
            key: veh as u32,
            is_vehicle: true,
            model: c.i("GetEntityModel", &[i(veh)]) as u32,
            driver_model: if driver != 0 { c.i("GetEntityModel", &[i(driver)]) as u32 } else { 0 },
            pos,
            rot: c.v_packed("GetEntityRotation", &[i(veh), i(2)]),
            vel: c.v("GetEntityVelocity", &[i(veh)]),
            dead: c.i("IsEntityDead", &[i(veh), b(false)]) != 0,
            engine: c.f("GetVehicleEngineHealth", &[i(veh)]).clamp(-4000.0, 1000.0) as i16,
            body: c.f("GetVehicleBodyHealth", &[i(veh)]).clamp(-4000.0, 1000.0) as i16,
        });
    }
    for p in peds {
        if ours(p) || c.i("IsEntityAMissionEntity", &[i(p)]) != 0 || c.i("IsPedInAnyVehicle", &[i(p), b(false)]) != 0 {
            continue;
        }
        out.push(PopEntry {
            key: p as u32,
            is_vehicle: false,
            model: c.i("GetEntityModel", &[i(p)]) as u32,
            driver_model: 0,
            pos: c.v("GetEntityCoords", &[i(p), b(false)]),
            rot: [0.0, 0.0, c.f("GetEntityHeading", &[i(p)])],
            vel: c.v("GetEntityVelocity", &[i(p)]),
            dead: c.i("IsPedDeadOrDying", &[i(p), b(true)]) != 0,
            engine: 0,
            body: 0,
        });
    }

    let near = |p: [f32; 3]| others.iter().chain(std::iter::once(&my_pos)).map(|o| dist(p, *o)).fold(f32::MAX, f32::min);
    out.sort_by(|a, b| near(a.pos).total_cmp(&near(b.pos)));
    let total = if extras_only { proto::POP_MAX } else { proto::POP_MAX * POP_PARTS };
    let cars_max = total * 11 / 20;
    let (mut cars, peds): (Vec<PopEntry>, Vec<PopEntry>) = out.into_iter().partition(|e| e.is_vehicle);
    cars.truncate(cars_max);
    let room = total - cars.len();
    cars.extend(peds.into_iter().take(room));
    cars
}

const POP_PARTS: usize = 3;

fn send_pop(net: &Net, entries: &[PopEntry]) {
    let chunks: Vec<&[PopEntry]> = if entries.is_empty() { vec![&[][..]] } else { entries.chunks(proto::POP_MAX).collect() };
    let parts = chunks.len() as u8;
    for (k, chunk) in chunks.into_iter().enumerate() {
        let mut payload = Vec::new();
        proto::encode_pop(chunk, &mut payload);
        payload.extend([k as u8, parts]);
        let _ = net.sock.send(&proto::packet(proto::POP, &payload));
    }
}

const EXTRAS: u8 = 0x80;

fn mirror_population(c: &mut Cmd, game: &mut Game, net: &Net, owner: u8, entries: &[PopEntry]) {
    let now = Instant::now();
    let mut spawned = 0;
    for e in entries {
        let key = (owner, e.key);
        if game.taken.contains(&key) {
            continue;
        }
        let alive = game.mirrors.get(&key).map(|m| c.exists(m.ent)).unwrap_or(false);
        if !alive {
            if let Some(m) = game.mirrors.remove(&key) {
                remove_mirror(c, m);
            }

            if e.dead || spawned >= 2 || !model_ready(c, e.model) || (e.is_vehicle && e.driver_model != 0 && !model_ready(c, e.driver_model)) {
                continue;
            }
            spawned += 1;
            let m = if e.is_vehicle {
                let veh = match adopt_parked(c, e.model, e.pos) {
                    Some(v) => v,
                    None => {
                        let p = c.vec_arg(1, e.pos);
                        c.i("CreateVehicle", &[i(e.model as i32), p, f(e.rot[2]), b(false), b(false), b(false)])
                    }
                };
                if veh == 0 {
                    continue;
                }
                c.i("SetVehicleEngineOn", &[i(veh), b(true), b(true), b(false)]);
                let driver = if e.driver_model != 0 { obedient_ped(c, e.driver_model, e.pos, e.rot[2]) } else { 0 };
                if driver != 0 {
                    c.i("SetPedIntoVehicle", &[i(driver), i(veh), i(-1)]);
                }
                Mirror { is_vehicle: true, dead: false, ent: veh, driver, walk: Walker::default(), seen: now, still: false }
            } else {
                let p = obedient_ped(c, e.model, e.pos, e.rot[2]);
                if p == 0 {
                    continue;
                }
                c.i("SetPedDefaultComponentVariation", &[i(p)]);
                Mirror { is_vehicle: false, dead: false, ent: p, driver: 0, walk: Walker::default(), seen: now, still: false }
            };
            game.mirrors.insert(key, m);
        }
        let Some(m) = game.mirrors.get_mut(&key) else { continue };
        m.seen = now;
        m.still = e.vel.iter().map(|v| v * v).sum::<f32>() < 1.0;
        if m.dead {
            continue;
        }
        let dead_here = if e.is_vehicle { c.i("IsEntityDead", &[i(m.ent), b(false)]) != 0 } else { c.i("IsPedDeadOrDying", &[i(m.ent), b(true)]) != 0 };
        if e.dead || dead_here {
            m.dead = true;
            if e.dead && !dead_here {
                if e.is_vehicle {
                    c.i("ExplodeVehicle", &[i(m.ent), b(true), b(false)]);
                } else {
                    c.i("SetEntityHealth", &[i(m.ent), i(0), i(0)]);
                }
            } else if !e.dead && {
                let me = c.i("PlayerPedId", &[]);
                me != 0 && c.i("HasEntityBeenDamagedByEntity", &[i(m.ent), i(me), b(true)]) != 0
            } {
                let mut payload = vec![owner & !EXTRAS];
                payload.extend(e.key.to_le_bytes());
                send_reliable(net, proto::KILL, &payload, Some(owner & !EXTRAS));
            }
            continue;
        }
        if e.is_vehicle {
            let have = (c.f("GetVehicleEngineHealth", &[i(m.ent)]) as i16, c.f("GetVehicleBodyHealth", &[i(m.ent)]) as i16);
            if (have.0 - e.engine).abs() > 25 {
                c.i("SetVehicleEngineHealth", &[i(m.ent), f(e.engine as f32)]);
            }
            if (have.1 - e.body).abs() > 25 {
                c.i("SetVehicleBodyHealth", &[i(m.ent), f(e.body as f32)]);
            }
            steer_vehicle(c, m.ent, e.pos, e.rot, e.vel, 0.0);
        } else {
            let mut w = m.walk;
            walk(c, m.ent, &mut w, e.pos, e.vel, e.rot[2]);
            m.walk = w;
        }
    }

    let stale: Vec<(u8, u32)> = game.mirrors.iter().filter(|(k, m)| k.0 == owner && now.duration_since(m.seen) > Duration::from_secs(if m.still { 6 } else { 1 })).map(|(k, _)| *k).collect();
    for k in stale {
        if let Some(m) = game.mirrors.remove(&k) {
            remove_mirror(c, m);
        }
    }
}

static AVATAR_ENTS: Mutex<Vec<i32>> = Mutex::new(Vec::new());

fn remove_mirror(c: &mut Cmd, m: Mirror) {
    let keep = AVATAR_ENTS.lock().unwrap().clone();
    if keep.contains(&m.ent) {
        if !keep.contains(&m.driver) {
            delete_ped(c, m.driver);
        }
        return;
    }
    if m.dead && c.exists(m.ent) && c.i("IsEntityOnScreen", &[i(m.ent)]) != 0 {
        release(c, m.driver);
        release(c, m.ent);
        return;
    }
    delete_ped(c, m.driver);
    if m.is_vehicle {
        delete_vehicle(c, m.ent);
    } else {
        delete_ped(c, m.ent);
    }
}
