#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Optional voice inside ordinary authenticated, room-scoped G5 DATA packets.
 * No extra listener, game socket, save format, identity or cloud dependency. */
#define ZEMA_VOICE_PORT 65534
#define ZEMA_VOICE_FRAME_BYTES 356
void ZemaVoiceConfigure(uint32_t vip);
void ZemaVoiceConnected(bool connected);
bool ZemaVoiceIsMicEnabled(void);
bool ZemaVoiceIsSpeakerEnabled(void);
void ZemaVoiceSetMicEnabled(bool enabled);
void ZemaVoiceSetSpeakerEnabled(bool enabled);
void ZemaVoiceSetPosition(float x, float y, float z, bool valid);
/* Capture and mix are 48 kHz. Wire audio is 20 ms / 320 G.711 mu-law samples
 * at 16 kHz, mono. No allocations or blocking locks in either audio callback. */
void ZemaVoiceSubmitMicAudio(const float *samples, uint32_t count);
void ZemaVoiceMixAudio(float *left, float *right, uint32_t count);
int ZemaVoiceTakeOutgoing(uint8_t *bytes, size_t capacity);
/* Returns true for the reserved voice envelope, even if its body is rejected,
 * so malformed voice can never become an engine datagram. */
bool ZemaVoiceDeliver(const uint8_t *bytes, size_t count);
typedef struct { uint64_t sent, received, dropped, mixed, positionUpdates; } ZemaVoiceStats;
ZemaVoiceStats ZemaVoiceReadStats(void);
