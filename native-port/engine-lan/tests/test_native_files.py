"""Exercise the actual native file host with disposable files, pipes and OS entropy.

No app, network listener, player saves or phone is used.
"""
from pathlib import Path
import subprocess
import sys
import shutil
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[2]/'app/Source/NativeFiles.c'

class NativeFilesTests(unittest.TestCase):
    def test_entropy_aliases_and_real_poll_readiness(self):
        header=r'''
#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
typedef uint32_t u32; typedef uint64_t u64;
struct w2c_env {uint8_t bytes[32768];};
struct w2c_wasi__snapshot__preview1 {struct w2c_env *env;};
void *pg_pointer(struct w2c_env *,uint64_t,uint64_t);
const char *pg_string(struct w2c_env *,uint64_t);
void pg_log(const char *);
'''
        harness=r'''
#include "HostInternal.h"
#include <assert.h>
#include <stdlib.h>
#include <poll.h>
#include <pthread.h>
#include <time.h>
static int fixture_poll(struct pollfd *,nfds_t,int);
#define poll fixture_poll
#include "NativeFiles.c"
#undef poll
static pthread_mutex_t raceLock=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t raceChanged=PTHREAD_COND_INITIALIZER;
static int watchPoll=0,enteredPoll=0;
static int fixture_poll(struct pollfd *fds,nfds_t count,int timeout){
 pthread_mutex_lock(&raceLock);if(watchPoll){enteredPoll=1;pthread_cond_signal(&raceChanged);}pthread_mutex_unlock(&raceLock);
 return poll(fds,count,timeout);
}
void *pg_pointer(struct w2c_env *env,uint64_t at,uint64_t size){assert(at<=sizeof env->bytes&&size<=sizeof env->bytes-at);return env->bytes+at;}
const char *pg_string(struct w2c_env *env,uint64_t at){char *s=pg_pointer(env,at,1);assert(memchr(s,0,sizeof env->bytes-at));return s;}
void pg_log(const char *s){}
static struct w2c_env env;
static struct w2c_wasi__snapshot__preview1 wasi={.env=&env};
static void row(int n,int32_t fd,uint16_t events){memcpy(env.bytes+100+n*8,&fd,4);memcpy(env.bytes+104+n*8,&events,2);memset(env.bytes+106+n*8,255,2);}
static uint16_t observed(int n){uint16_t v;memcpy(&v,env.bytes+106+n*8,2);return v;}
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
static void *waiting(void *unused){return (void *)(uintptr_t)w2c_env_0x5F_syscall_poll(&env,100,1,200);}
int main(int argc,char **argv){
 assert(argc==2);pg_files_init(argv[1]);
 char fake[PATH_MAX];snprintf(fake,sizeof fake,"%s/dev/urandom",argv[1]);FILE *f=fopen(fake,"wb");assert(f);fputs("private fake entropy must never be read",f);fclose(f);
 for(int alias=0;alias<2;alias++){
  strcpy((char *)env.bytes+1000,alias?"/dev/random":"/dev/urandom");
  u32 fd=w2c_env_0x5F_syscall_openat(&env,(u32)-100,1000,0,0);assert(fd>=3&&fd<PG_FDS);
  struct stat s;assert(fstat(descriptors[fd].native,&s)==0&&S_ISCHR(s.st_mode));
  u64 vectors[2]={2000,52};memcpy(env.bytes+1500,vectors,16);
  assert(w2c_wasi__snapshot__preview1_fd_read(&wasi,fd,1500,1,1600)==0);u64 bytes;memcpy(&bytes,env.bytes+1600,8);assert(bytes==52);
  row(0,fd,1);assert(w2c_env_0x5F_syscall_poll(&env,100,1,0)==1&&observed(0)==1);
  assert(w2c_wasi__snapshot__preview1_fd_close(&wasi,fd)==0);
  for(unsigned flags=1;flags<=2;flags++)assert((int32_t)w2c_env_0x5F_syscall_openat(&env,(u32)-100,1000,flags,0)==-2);
  assert((int32_t)w2c_env_0x5F_syscall_openat(&env,(u32)-100,1000,64|512,0)==-2);
 }
 f=fopen(fake,"rb");assert(f);char retained[64]={0};fread(retained,1,sizeof retained-1,f);fclose(f);assert(!strcmp(retained,"private fake entropy must never be read"));
 row(0,-1,1);row(1,511,0);assert(w2c_env_0x5F_syscall_poll(&env,100,2,0)==1);assert(observed(0)==0&&observed(1)==32);
 assert((int32_t)w2c_env_0x5F_syscall_poll(&env,UINT64_MAX,PG_FDS+1,0)==-28);
 double start=now();assert(w2c_env_0x5F_syscall_poll(&env,UINT64_MAX,0,20)==0);assert(now()-start>=0.01);
 int pipes[2];assert(pipe(pipes)==0);descriptors[20].native=pipes[0];strcpy(descriptors[20].path,"/fixture");
 row(0,20,1|64);assert(w2c_env_0x5F_syscall_poll(&env,100,1,0)==0&&observed(0)==0);
 assert(write(pipes[1],"x",1)==1);assert(w2c_env_0x5F_syscall_poll(&env,100,1,0)==1);assert(observed(0)&1);char ch;assert(read(pipes[0],&ch,1)==1);
 // Closing/reusing the guest descriptor cannot redirect an in-flight poll.
 row(0,20,1);watchPoll=1;pthread_t thread;assert(pthread_create(&thread,NULL,waiting,NULL)==0);
 pthread_mutex_lock(&raceLock);while(!enteredPoll)pthread_cond_wait(&raceChanged,&raceLock);pthread_mutex_unlock(&raceLock);
 assert(w2c_wasi__snapshot__preview1_fd_close(&wasi,20)==0);int other[2];assert(pipe(other)==0);descriptors[20].native=other[0];
 assert(write(pipes[1],"y",1)==1);void *result;pthread_join(thread,&result);assert((uintptr_t)result==1&&observed(0)==1);watchPoll=0;
 close(pipes[1]);close(other[1]);row(0,20,1);assert(w2c_env_0x5F_syscall_poll(&env,100,1,0)==1&&(observed(0)&16));w2c_wasi__snapshot__preview1_fd_close(&wasi,20);
 row(0,0,1);row(1,1,4);row(2,2,1);assert(w2c_env_0x5F_syscall_poll(&env,100,3,0)==2);assert(observed(0)==1&&observed(1)==4&&observed(2)==0);
 puts("NATIVE_ENTROPY_AND_POLL_PASS");
}
'''
        with tempfile.TemporaryDirectory(prefix='zema-native-files-') as folder:
            root=Path(folder);(root/'NativeFiles.c').write_bytes(SOURCE.read_bytes());(root/'HostInternal.h').write_text(header);(root/'main.c').write_text(harness);(root/'files').mkdir()
            compile_result=subprocess.run(['/usr/bin/clang','-std=c11','-pthread','-Werror=implicit-function-declaration',str(root/'main.c'),'-o',str(root/'check')],capture_output=True,text=True)
            self.assertEqual(compile_result.returncode,0,compile_result.stderr)
            result=subprocess.run([str(root/'check'),str(root/'files')],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('NATIVE_ENTROPY_AND_POLL_PASS',result.stdout)
            # Regeneration must not leave a duplicate fail-fast poll definition.
            for name in ('Scripts','Source','Generated','Build'):(root/name).mkdir()
            shutil.copy2(SOURCE,root/'Source/NativeFiles.c')
            shutil.copy2(SOURCE.parent.parent/'Scripts/generate_imports.py',root/'Scripts/generate_imports.py')
            (root/'Generated/game.h').write_text("/* import: 'env' '__syscall_poll' */\nu32 w2c_env_0x5F_syscall_poll(struct w2c_env*, u64, u32, u32);\n")
            subprocess.run([sys.executable,'-B',str(root/'Scripts/generate_imports.py')],check=True,capture_output=True,text=True)
            self.assertIn('env.__syscall_poll\timplemented', (root/'Build/import-status.tsv').read_text())
            self.assertNotIn('pg_missing_import', (root/'Generated/Imports.c').read_text())


if __name__=='__main__':unittest.main()
