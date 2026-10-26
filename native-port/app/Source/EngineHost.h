#pragma once
#include <stdint.h>
#include <stdbool.h>

typedef void (*PGLogCallback)(const char *, void *);
typedef struct {
  float leftX, leftY, rightX, rightY, leftTrigger, rightTrigger;
  uint32_t buttons;
  // Extra mouse pixels this poll (gyro look), added to the stick look.
  int32_t lookDX, lookDY;
} PGControllerState;
// buttons: A B X Y LB RB Menu Up Down Left Right in bits 0...10.
// Touch additions: Sprint (11), Weapon Wheel (12), Camera (13),
// Gas (14), Brake (15), Headlights (16). They use the game's PC bindings.
// Flight: Roll left/right (17/18), Pitch forward/back (19/20),
// Yaw left/right (21/22), Landing gear (23). Throttle uses Gas/Brake.
// Bit 24 identifies a vehicle touch layout: Tab cycles weapons rather than
// using the walking weapon-wheel cursor.
// Before PGStartEngine: engine quality options (e.g. "-shadowQuality=0"),
// back-buffer size and frame limit (0 none, 1 = 60, 2 = 30 FPS).
void PGConfigureEngine(const char *const *quality, unsigned count, int width, int height, int frameLimit);
// Changes the frame limit while the game runs (0 off, 1 60 FPS, 2 30 FPS).
void PGSetFrameLimit(int frameLimit);
// Settings › Memory cap in MB (0 automatic); call before the engine starts.
void PGSetMemoryCap(int mb);
// RAM the game may reserve, in MB (Settings › Graphics › RAM for the game). 0: the device's full RAM.
// Clamped to the engine's 3072..16384 MB. Call before PGStartEngine.
void PGSetEngineMemoryMB(int mb);
// Before PGStartEngine: 1 Story Mode (the release startup: continues the
// newest save in /userdata/Documents, else a new game from the Prologue),
// 2 Sandbox Mode (free roam on the GTA V map; its files go to
// /sandbox/Documents), 3 Sandbox Mode on the test level (env_test). Default 2.
void PGSetStartMode(int32_t mode);
// Live back-buffer resize after the engine has started.
void PGSetBackBufferSize(int width, int height);
// Base URL of your own game-file server, e.g. https://pc.tailnet.ts.net
void PGSetAssetServer(const char *url);
// Before PGStartEngine: a folder on this device that contains the game's data/
// files (the app holds security-scoped access to it); NULL streams from the server.
void PGSetLocalGameFolder(const char *dataPath);
bool PGUsingLocalGameFolder(void);
void PGStartEngine(const char *manifestPath, const char *filesRoot, PGLogCallback, void *context);
void PGUpdateController(PGControllerState state, double elapsedSeconds);
// Player context: 0 on foot, otherwise the vehicle type + 1 (see NativeTouchContext.h).
uint32_t PGCurrentTouchContext(void);
// Game state for the touch layout: 1 control off, 2 phone out, 4 cutscene, 8 warning screen, 16 no player.
uint32_t PGGameStatus(void);
// What the touch controls need to know to show a button only when it applies (all memory reads).
typedef struct {
  bool specialShown;   // the character has a usable special ability here
  bool specialReady;   // charged enough to start
  bool specialActive;  // running now
  float specialFill;   // meter, 0...1
  bool canDetonate;    // the player has sticky bombs placed
  bool helpShown;      // a help message is on screen
  bool helpContext;    // ...and it asks for the context input (D-pad right)
  bool radioWheelOpen; // the radio wheel is up
  uint32_t vehicleModel; // model name hash (joaat) of the vehicle the player is in, 0 on foot
  bool passenger;        // in a vehicle, not in the driver's seat (taxi rides)
  bool taxiMenu;         // the taxi ride script (taxiservice) is running
} PGControlHints;
PGControlHints PGReadControlHints(uint32_t touchContext);
// The next weapon of the aircraft the player flies (applied on the game thread).
void PGNextAircraftWeapon(void);
// Keyboard and mouse, through the game's own PC input (the block the browser build wrote): key
// state bytes indexed by Windows virtual-key code, and mouse words after them.
void PGSetKey(uint8_t virtualKey, bool down);
void PGSendChar(uint16_t ch);
void PGSendKeyAndChar(uint8_t virtualKey, bool down, uint16_t ch);
void PGApplyCheat(const char *code);
void PGApplyCheatConsole(const char *code);
void PGApplyCheatGamepad(const char *code);
bool PGIsCheatInProgress(void);
// The radio wheel's direction (stick-style, up positive). Its two inputs have no controller binding
// in this build, so the value is written into them directly while the wheel is held.
void PGSetRadioWheelDirection(float x, float y, bool active);
void PGReleaseAllKeys(void);
// Mouse movement in pixels since the last call, buttons (bit 0 left, 1 right, 2 middle).
void PGMouseInput(int32_t dx, int32_t dy, int32_t buttons);
void PGMouseWheel(int32_t notches);
// The window has focus / the pointer is captured for looking around.
void PGSetMouseFocus(bool focused, bool locked);
void PGSetMousePosition(int32_t x, int32_t y, int32_t buttons);
void PGGetRenderSize(int32_t *width, int32_t *height);
bool PGDebugReadMemory(uint64_t address, void *out, uint64_t length);
// Virtual controller fed into the engine's own pad 0 (see
// Scripts/prepare_virtual_pad.py). Buttons use the engine's pad bits:
// L2 1, R2 2, L1 4, R1 8, Y 16, B 32, A 64, X 128, Select 256, L3 512,
// R3 1024, Start 2048, D-pad up/right/down/left 4096/8192/16384/32768.
// Sticks -1...1 with up positive; triggers 0...1.
typedef struct {
  uint32_t buttons;
  float leftX, leftY, rightX, rightY, leftTrigger, rightTrigger;
} PGPadState;
void PGUpdateVirtualPad(PGPadState state);
// Relative touch motion, queued until the engine consumes its pad input.
void PGTouchCameraDrag(double x, double y);
void PGTouchCameraEnabled(bool enabled);
// Existing controller-swipe impulse bridge, consumed on engine input sampling.
void PGQueueCameraSwipe(float x, float y);
void PGClearCameraSwipe(void);
// The engine's last input device for the player: -4 keyboard/mouse,
// 0...3 pads, -3 unknown. Assisted aim needs a pad.
int32_t PGLastInputDevice(void);
// Targeting preference: 0 traditional lock, 1 assisted, 2 assisted free, 3 free.
int32_t PGTargetingMode(void);
// Applied on the engine thread once the local player exists.
void PGSetTargetingMode(int32_t mode);
// The engine's pause menu / frontend is open.
bool PGPauseMenuActive(void);
void PGFillAudio(float *left, float *right, uint32_t count);
// Health counters for the periodic log line.
uint64_t PGResourceBytesReleased(void);
uint64_t PGResourceBytesReused(void);
uint64_t PGResourceReclaimFailures(void);
uint64_t PGMemoryBudgetQueries(void);
uint64_t PGMemoryBudgetClamps(void);
uint64_t PGMemoryBudgetEvictions(void);
void PGAssetHealth(uint64_t out[6]);
// Mode 0 blocks world tools in the legacy online backend; 1 offline; 2 experimental LAN.
int PGWorldToolsMode(void);
typedef enum {
 PGWaypointIdle=0,PGWaypointPending=1,PGWaypointSuccess=2,
 PGWaypointNoWaypoint=-1,PGWaypointInvalidGround=-2,PGWaypointNoLocalPlayer=-3,
 PGWaypointNoControl=-4,PGWaypointTimedOut=-5,PGWaypointBusy=-6,
 PGWaypointUnavailable=-7,PGWaypointPlayerChanged=-8,PGWaypointStreamingBusy=-9
} PGWaypointTeleportResult;
// Admission only. The existing engine control update owns all native command calls.
bool PGTeleportToWaypoint(void);
int PGTeleportToWaypointStatus(void);
typedef enum {
 PGVehicleSpawnFailed=-1,PGVehicleSpawnTimedOut=-2,PGVehicleSpawnNoPlayer=-3,
 PGVehicleSpawnNoControl=-4,PGVehicleSpawnCreateFailed=-5,
 PGVehicleSpawnUnavailable=-6,PGVehicleSpawnInvalidPosition=-7,
 PGVehicleSpawnInvalidModel=-8,PGVehicleSpawnBusy=-9,PGVehicleSpawnModelMissing=-10
} PGVehicleSpawnResult;
// Immediate admission result; a rejected request never changes the last accepted request status.
// Read-only model registration probe: -1 unknown/not ready,0 missing,1 registered,2 checking,-2 unsupported.
// UIKit only queues/reads; all engine queries run in the existing PRIMARY control hook.
int PGVehicleModelAvailability(const char *modelName);
int PGQueueSpawnVehicle(const char *modelName);
bool PGSpawnVehicle(const char *modelName);
int PGSpawnVehicleStatus(void);
void PGEmergencyExitVehicle(int mode);
void PGForceSkipScene(void);

// Queued on the game control-update owner; never drives GTA menus.
bool PGRequestSessionRestart(void);
int PGSessionRestartStatus(void);
