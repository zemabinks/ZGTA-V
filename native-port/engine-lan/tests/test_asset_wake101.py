"""Run the native asset condition and real futex observer against wake races."""
from pathlib import Path
import subprocess
import tempfile
import unittest

APP = Path(__file__).resolve().parents[2] / "app"


class AssetWake101(unittest.TestCase):
    def test_notify_count_and_asset_scan_wait_races(self):
        fixture = r'''
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdatomic.h>
#include <unistd.h>
#include "NativeAssetWake.h"
#include "WasmFutex.c"
static PGAssetWake wake=PG_ASSET_WAKE_INITIALIZER;
static _Atomic uint32_t data[8];
static wasm_rt_shared_memory_t memory;
static _Atomic unsigned callbacks,ready,completed,claimed,pending;
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
static void waitCount(_Atomic unsigned *value,unsigned target){double end=now()+3;while(atomic_load(value)!=target&&now()<end)usleep(1000);assert(atomic_load(value)==target);}
static void observe(void *p){
 atomic_fetch_add(&callbacks,1);
 // Reentry proves the callback is outside the generic futex lock.
 assert(pg_atomic_notify(&memory,16,0)==0);pg_asset_wake_signal(p);
}
struct Worker {uint64_t seen;bool hint;};
static void *consumer(void *p){
 struct Worker *w=p;atomic_fetch_add(&ready,1);
 assert(pg_asset_wake_wait(&wake,w->seen,1000000000));
 if(!w->hint){unsigned expected=1;if(atomic_compare_exchange_strong(&pending,&expected,2))atomic_fetch_add(&claimed,1);}
 atomic_fetch_add(&completed,1);return NULL;
}
static void *futexConsumer(void *p){
 assert(pg_atomic_wait32(&memory,(uintptr_t)p,0,2000000000)==0);atomic_fetch_add(&completed,1);return NULL;
}
static unsigned countWaiters(void){unsigned n=0;pthread_mutex_lock(&queueLock);for(Waiter*w=waiters;w;w=w->next)n++;pthread_mutex_unlock(&queueLock);return n;}
int main(void){
 memory.data=(void*)data;memory.size=sizeof data;
 assert(!pg_atomic_observe_notify(&memory,1,observe,&wake));
 assert(!pg_atomic_observe_notify(&memory,sizeof data,observe,&wake));
 assert(pg_atomic_observe_notify(&memory,0,observe,&wake));
 assert(pg_atomic_observe_notify(&memory,0,observe,&wake));
 assert(!pg_atomic_observe_notify(&memory,4,observe,&wake));
 assert(pg_atomic_notify(&memory,4,1)==0&&callbacks==0);
 assert(pg_atomic_notify(&memory,0,0)==0&&callbacks==0);
 // A bell arriving after scan but before wait must not be lost.
 uint64_t seen=pg_asset_wake_snapshot(&wake);assert(pg_atomic_notify(&memory,0,1)==0);
 assert(pg_asset_wake_wait(&wake,seen,1000000000));assert(callbacks==1);
 // A hint completion can restart the scheduler without an engine bell.
 seen=pg_asset_wake_snapshot(&wake);pg_asset_wake_signal(&wake);
 assert(pg_asset_wake_wait(&wake,seen,1000000000)&&callbacks==1);
 // No engine is required to release a bounded idle wait.
 seen=pg_asset_wake_snapshot(&wake);double start=now();
 assert(!pg_asset_wake_wait(&wake,seen,20000000));assert(now()-start<1);
 // All six demand consumers and the hint consumer observe a sole notify(1).
 // The hint consumer can never steal the only opportunity to service demand.
 for(unsigned round=0;round<100;round++){
  ready=completed=claimed=0;pending=1;seen=pg_asset_wake_snapshot(&wake);
  pthread_t threads[7];struct Worker workers[7];
  for(unsigned i=0;i<7;i++){workers[i]=(struct Worker){.seen=seen,.hint=i==0};assert(!pthread_create(&threads[i],NULL,consumer,&workers[i]));}
  waitCount(&ready,7);assert(pg_atomic_notify(&memory,0,1)==0);
  waitCount(&completed,7);assert(claimed==1&&pending==2);
  for(unsigned i=0;i<7;i++)assert(!pthread_join(threads[i],NULL));
 }
 assert(callbacks==101);
 // Generic WASM futexes still honor exactly the original partial-wake count.
 for(uintptr_t offset=0;offset<=8;offset+=8){
  unsigned before=callbacks;completed=0;pthread_t a,b;
  assert(!pthread_create(&a,NULL,futexConsumer,(void*)offset));assert(!pthread_create(&b,NULL,futexConsumer,(void*)offset));
  double end=now()+3;while(countWaiters()!=2&&now()<end)usleep(1000);assert(countWaiters()==2);
  assert(pg_atomic_notify(&memory,offset,1)==1);waitCount(&completed,1);usleep(10000);assert(completed==1&&countWaiters()==1);
  assert(pg_atomic_notify(&memory,offset,UINT32_MAX)==1);waitCount(&completed,2);
  assert(!pthread_join(a,NULL)&&!pthread_join(b,NULL)&&callbacks==before+(offset==0?2:0));
 }
 assert(pg_atomic_wait32(&memory,8,1,1000000)==1); // value mismatch unchanged
 assert(pg_atomic_wait32(&memory,8,0,1000000)==2); // timeout unchanged
 puts("PASS: native asset notify observer, scan/wait races, seven-consumer notify(1), completion/idle wakes, generic partial wake counts.");
}
'''
        with tempfile.TemporaryDirectory(prefix="zgta-asset-wake101-") as tmp:
            root = Path(tmp)
            # Minimal runtime carrier; production WasmFutex.c is compiled as-is.
            (root / "wasm-rt.h").write_text(
                "#pragma once\n#include <stdint.h>\n#include <stdlib.h>\n"
                "typedef struct {void *data;uint64_t size;} wasm_rt_shared_memory_t;\n"
                "enum {WASM_RT_TRAP_UNALIGNED=1,WASM_RT_TRAP_OOB=2};\n"
                "static inline void wasm_rt_trap(int code){abort();}\n")
            src, exe = root / "probe.c", root / "probe"
            src.write_text(fixture)
            build = subprocess.run(
                ["xcrun", "clang", "-std=c11", "-O1", "-pthread",
                 "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                 "-I", str(root), "-I", str(APP / "Source"),
                 str(src), "-o", str(exe)], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
