#pragma once
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

typedef struct { uint32_t type, reserved; uint64_t bits; } MugoatValue;
// Tags: 1 i32, 2 i64, 3 f32, 4 f64. No untyped function-pointer casts.
int mugoat_command_info(const char *name, uint32_t *params, uint32_t capacity, uint32_t *result);
bool mugoat_command_call(void *instance, const char *name, const MugoatValue *args, uint32_t count, MugoatValue *result);
uint8_t *mugoat_memory_data(void *instance, uint64_t *size);
void mugoat_script_tick(void *instance, uint64_t thread, uint64_t tls);
void mugoat_explosion(uint64_t args);
uint32_t mugoat_time_warp(uint32_t direction);
// Configuration is immutable after starting the engine. Change servers by restarting the app.
bool MugoatOnlineConfigure(const char *server, const char *name, const char *room, int32_t mode);
size_t MugoatOnlineStatus(char *output, size_t capacity);
bool MugoatOnlineEnabled(void);
void MugoatOnlineShutdown(void);

// Voice Chat (Loa & Mic)
bool MugoatVoiceIsMicEnabled(void);
void MugoatVoiceSetMicEnabled(bool enabled);
bool MugoatVoiceIsSpeakerEnabled(void);
void MugoatVoiceSetSpeakerEnabled(bool enabled);
void MugoatVoiceSubmitMicAudio(const float *samples, uint32_t count);
void MugoatVoiceMixAudio(float *left, float *right, uint32_t count);
size_t MugoatVoiceActiveSpeakers(char *output, size_t capacity);

// Economy & Anti-Cheat
int32_t MugoatGetWalletCash(void);
void MugoatAddWalletCash(int32_t amount);
void MugoatTriggerAmmuBuy(void);
