#pragma once
#include "game.h"
#include "wasm-rt-exceptions.h"
#include "EngineHost.h"
#include <stdatomic.h>

struct w2c_env {
  wasm_rt_shared_memory_t memory;
  w2c_game game;
};
struct w2c_wasi__snapshot__preview1 { struct w2c_env *env; };
void pg_log(const char *message);
void pg_missing_import(const char *name);
void *pg_pointer(struct w2c_env *, uint64_t address, uint64_t size);

const char *pg_string(struct w2c_env *, uint64_t);
void pg_files_init(const char *root);
u32 pg_file_io(struct w2c_env *,u32,u64,u64,u64,u64,bool,bool);
void pg_assets_configure(const char *,const char *);
bool pg_assets_have_mod_packs(void);
#include "NativeAssetServer.h"
void pg_assets_prewarm(void);
void pg_threads_main(struct w2c_env *);
