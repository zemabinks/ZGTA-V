#include "HostInternal.h"
#include <string.h>
f64 w2c_env_0x5Femscripten_receive_on_main_thread_js(struct w2c_env *h,u32 index,u64 code,u64 caller,u32 size,u64 args,u64 ctx,u64 ctxargs) {
  u64 values[12]={0};if(size>sizeof(values)*2 || size%16)wasm_rt_trap(WASM_RT_TRAP_OOB);
  for(unsigned i=0;i<size/16;i++){u64 *p=pg_pointer(h,args+i*16,16);if(p[0])values[i]=p[1];else {double v;memcpy(&v,p+1,8);values[i]=(u64)(int64_t)v;}}
  f64 result=0;
  if(code){pg_missing_import("proxied embedded expression");}else switch(index){
    case 0: w2c_wasi__snapshot__preview1_proc_exit(&(struct w2c_wasi__snapshot__preview1){.env=h}, (u32)values[0]);break;
    case 2: result=(f64)(int32_t)w2c_env_0x5F_pthread_create_js(h, (u64)values[0], (u64)values[1], (u64)values[2], (u64)values[3]);break;
    case 3: result=(f64)(int32_t)w2c_env_0x5F_syscall_accept4(h, (u32)values[0], (u64)values[1], (u64)values[2], (u32)values[3], (u32)values[4], (u32)values[5]);break;
    case 5: result=(f64)(int32_t)w2c_env_0x5F_syscall_connect(h, (u32)values[0], (u64)values[1], (u32)values[2], (u32)values[3], (u32)values[4], (u32)values[5]);break;
    case 6: result=(f64)(int32_t)w2c_env_0x5F_syscall_fcntl64(h, (u32)values[0], (u32)values[1], (u64)values[2]);break;
    case 7: result=(f64)(int32_t)w2c_env_0x5F_syscall_fstat64(h, (u32)values[0], (u64)values[1]);break;
    case 8: result=(f64)(int32_t)w2c_env_0x5F_syscall_ftruncate64(h, (u32)values[0], (u64)values[1]);break;
    case 9: result=(f64)(int32_t)w2c_env_0x5F_syscall_getcwd(h, (u64)values[0], (u64)values[1]);break;
    case 10: result=(f64)(int32_t)w2c_env_0x5F_syscall_getdents64(h, (u32)values[0], (u64)values[1], (u64)values[2]);break;
    case 11: result=(f64)(int32_t)w2c_env_0x5F_syscall_getsockname(h, (u32)values[0], (u64)values[1], (u64)values[2], (u32)values[3], (u32)values[4], (u32)values[5]);break;
    case 12: result=(f64)(int32_t)w2c_env_0x5F_syscall_getsockopt(h, (u32)values[0], (u32)values[1], (u32)values[2], (u64)values[3], (u64)values[4], (u32)values[5]);break;
    case 13: result=(f64)(int32_t)w2c_env_0x5F_syscall_ioctl(h, (u32)values[0], (u32)values[1], (u64)values[2]);break;
    case 15: result=(f64)(int32_t)w2c_env_0x5F_syscall_lstat64(h, (u64)values[0], (u64)values[1]);break;
    case 16: result=(f64)(int32_t)w2c_env_0x5F_syscall_mkdirat(h, (u32)values[0], (u64)values[1], (u32)values[2]);break;
    case 17: result=(f64)(int32_t)w2c_env_0x5F_syscall_newfstatat(h, (u32)values[0], (u64)values[1], (u64)values[2], (u32)values[3]);break;
    case 18: result=(f64)(int32_t)w2c_env_0x5F_syscall_openat(h, (u32)values[0], (u64)values[1], (u32)values[2], (u64)values[3]);break;
    case 19: result=(f64)(int32_t)w2c_env_0x5F_syscall_poll(h, (u64)values[0], (u32)values[1], (u32)values[2]);break;
    case 20: result=(f64)(int32_t)w2c_env_0x5F_syscall_recvfrom(h, (u32)values[0], (u64)values[1], (u64)values[2], (u32)values[3], (u64)values[4], (u64)values[5]);break;
    case 21: result=(f64)(int32_t)w2c_env_0x5F_syscall_renameat(h, (u32)values[0], (u64)values[1], (u32)values[2], (u64)values[3]);break;
    case 22: result=(f64)(int32_t)w2c_env_0x5F_syscall_rmdir(h, (u64)values[0]);break;
    case 23: result=(f64)(int32_t)w2c_env_0x5F_syscall_sendto(h, (u32)values[0], (u64)values[1], (u64)values[2], (u32)values[3], (u64)values[4], (u32)values[5]);break;
    case 24: result=(f64)(int32_t)w2c_env_0x5F_syscall_setsockopt(h, (u32)values[0], (u32)values[1], (u32)values[2], (u64)values[3], (u32)values[4], (u32)values[5]);break;
    case 25: result=(f64)(int32_t)w2c_env_0x5F_syscall_shutdown(h, (u32)values[0], (u32)values[1], (u32)values[2], (u32)values[3], (u32)values[4], (u32)values[5]);break;
    case 26: result=(f64)(int32_t)w2c_env_0x5F_syscall_socket(h, (u32)values[0], (u32)values[1], (u32)values[2], (u32)values[3], (u32)values[4], (u32)values[5]);break;
    case 27: result=(f64)(int32_t)w2c_env_0x5F_syscall_stat64(h, (u64)values[0], (u64)values[1]);break;
    case 28: result=(f64)(int32_t)w2c_env_0x5F_syscall_statfs64(h, (u64)values[0], (u64)values[1], (u64)values[2]);break;
    case 29: result=(f64)(int32_t)w2c_env_0x5F_syscall_unlinkat(h, (u32)values[0], (u64)values[1], (u32)values[2]);break;
    case 30: result=(f64)(int32_t)w2c_wasi__snapshot__preview1_environ_get(&(struct w2c_wasi__snapshot__preview1){.env=h}, (u64)values[0], (u64)values[1]);break;
    case 31: result=(f64)(int32_t)w2c_wasi__snapshot__preview1_environ_sizes_get(&(struct w2c_wasi__snapshot__preview1){.env=h}, (u64)values[0], (u64)values[1]);break;
    case 32: result=(f64)(int32_t)w2c_wasi__snapshot__preview1_fd_close(&(struct w2c_wasi__snapshot__preview1){.env=h}, (u32)values[0]);break;
    case 33: result=(f64)(int32_t)w2c_wasi__snapshot__preview1_fd_pread(&(struct w2c_wasi__snapshot__preview1){.env=h}, (u32)values[0], (u64)values[1], (u64)values[2], (u64)values[3], (u64)values[4]);break;
    case 34: result=(f64)(int32_t)w2c_wasi__snapshot__preview1_fd_pwrite(&(struct w2c_wasi__snapshot__preview1){.env=h}, (u32)values[0], (u64)values[1], (u64)values[2], (u64)values[3], (u64)values[4]);break;
    case 35: result=(f64)(int32_t)w2c_wasi__snapshot__preview1_fd_read(&(struct w2c_wasi__snapshot__preview1){.env=h}, (u32)values[0], (u64)values[1], (u64)values[2], (u64)values[3]);break;
    case 36: result=(f64)(int32_t)w2c_wasi__snapshot__preview1_fd_seek(&(struct w2c_wasi__snapshot__preview1){.env=h}, (u32)values[0], (u64)values[1], (u32)values[2], (u64)values[3]);break;
    case 37: result=(f64)(int32_t)w2c_wasi__snapshot__preview1_fd_write(&(struct w2c_wasi__snapshot__preview1){.env=h}, (u32)values[0], (u64)values[1], (u64)values[2], (u64)values[3]);break;
    default:pg_missing_import("unknown native host proxy index");
  }
  if(ctx){w2c_game_0x5Femscripten_run_js_on_main_thread_done(&h->game,ctx,ctxargs,result);return 0;}return result;
}
