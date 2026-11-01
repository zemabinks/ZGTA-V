#include "ZemaVoice.h"
#include <math.h>
#include <pthread.h>
#include <stdatomic.h>
#include <string.h>
#include <time.h>

#define PEERS 32
#define RING 8192
#define FRAMES 5
#define SAMPLES 320
#define VOICE_NEAR 2.f
#define VOICE_RANGE 35.f
/* 50 ms time constant at the native mixer's fixed 48 kHz output rate. */
#define GAIN_SLEW 0.000416579873166f
typedef struct {
  float samples[RING], x, y, z, gain;
  uint32_t read, write;
  uint16_t sequence;
  uint64_t heard;
  bool seen, playing, gainValid;
} Speaker;
static struct {
  pthread_mutex_t lock;
  uint32_t vip;
  float x,y,z;
  uint64_t positionAt;
  bool positionValid;
  Speaker peers[PEERS];
  uint8_t outgoing[FRAMES][ZEMA_VOICE_FRAME_BYTES], capture[SAMPLES];
  uint64_t queuedAt[FRAMES];
  unsigned read,write,used,captured,downsample;
  float sum;
  uint16_t sequence;
  ZemaVoiceStats stats;
} state = {.lock=PTHREAD_MUTEX_INITIALIZER};
static atomic_bool connected, mic, speaker=true;
static uint64_t milliseconds(void) {
  struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t);
  return (uint64_t)t.tv_sec*1000+(uint64_t)t.tv_nsec/1000000;
}
static bool valid(float x,float y,float z) {
  return isfinite(x)&&isfinite(y)&&isfinite(z)&&fabsf(x)<=20000&&fabsf(y)<=20000&&fabsf(z)<=5000;
}
static bool localReady(uint64_t now) {
  return state.positionValid&&now-state.positionAt<=1000;
}
static float distanceGain(float distance) {
  if(distance<=VOICE_NEAR)return 1.f;
  if(distance>=VOICE_RANGE)return 0.f;
  float remaining=(VOICE_RANGE-distance)/(VOICE_RANGE-VOICE_NEAR);
  return remaining*remaining;
}
static void clearCapture(void) { state.used=state.read=state.write=state.captured=state.downsample=0;state.sum=0; }
static void clearSpeakers(void) { memset(state.peers,0,sizeof state.peers); }
static void put32(uint8_t *p,uint32_t v) { p[0]=v>>24;p[1]=v>>16;p[2]=v>>8;p[3]=v; }
static uint32_t get32(const uint8_t *p) { return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3]; }
/* IEEE float bits use network byte order, including coordinates far outside
 * the old bridge's +/-3.2 km saturated integer range. */
static void putFloat(uint8_t *p,float v) { uint32_t u;memcpy(&u,&v,4);put32(p,u); }
static float getFloat(const uint8_t *p) { uint32_t u=get32(p);float f;memcpy(&f,&u,4);return f; }
static uint8_t encode(float input) {
  int n=isfinite(input)?(int)(fmaxf(-1,fminf(1,input))*32767):0;
  int mask=n<0?0x7f:0xff;if(n<0)n=-n;n=(n>32635?32635:n)+132;
  int segment=0;for(int limit=255;n>limit&&segment<7;limit=(limit<<1)|1)segment++;
  return (uint8_t)((segment<<4|((n>>(segment+3))&15))^mask);
}
static float decode(uint8_t code) {
  unsigned u=(unsigned)(uint8_t)~code;
  int n=(((u&15)<<3)+132)<<((u>>4)&7);n-=132;
  return (float)((u&128)?-n:n)/32768.f;
}
void ZemaVoiceConfigure(uint32_t vip) {
  pthread_mutex_lock(&state.lock);
  state.vip=vip;state.positionValid=false;clearCapture();clearSpeakers();
  pthread_mutex_unlock(&state.lock);
}
void ZemaVoiceConnected(bool value) {
  atomic_store(&connected,value);
  pthread_mutex_lock(&state.lock);clearCapture();clearSpeakers();state.positionValid=false;
  if(!value)atomic_store(&mic,false);
  pthread_mutex_unlock(&state.lock);
}
bool ZemaVoiceIsMicEnabled(void) { return atomic_load(&mic); }
bool ZemaVoiceIsSpeakerEnabled(void) { return atomic_load(&speaker); }
void ZemaVoiceSetMicEnabled(bool value) {
  pthread_mutex_lock(&state.lock);atomic_store(&mic,value&&atomic_load(&connected));clearCapture();pthread_mutex_unlock(&state.lock);
}
void ZemaVoiceSetSpeakerEnabled(bool value) {
  pthread_mutex_lock(&state.lock);atomic_store(&speaker,value);clearSpeakers();pthread_mutex_unlock(&state.lock);
}
void ZemaVoiceSetPosition(float x,float y,float z,bool value) {
  pthread_mutex_lock(&state.lock);state.positionValid=value&&valid(x,y,z);
  state.x=x;state.y=y;state.z=z;state.positionAt=milliseconds();if(state.positionValid)state.stats.positionUpdates++;pthread_mutex_unlock(&state.lock);
}
void ZemaVoiceSubmitMicAudio(const float *samples,uint32_t count) {
  if(!samples||!atomic_load(&mic)||!atomic_load(&connected)||pthread_mutex_trylock(&state.lock))return;
  uint64_t now=milliseconds();
  if(!atomic_load(&mic)||!atomic_load(&connected)||!localReady(now)){clearCapture();pthread_mutex_unlock(&state.lock);return;}
  /* Fixed 3:1 box filter keeps state across arbitrary input callback sizes. */
  for(uint32_t i=0;i<count;i++){
    state.sum+=isfinite(samples[i])?samples[i]:0;
    if(++state.downsample!=3)continue;
    state.capture[state.captured++]=encode(state.sum/3);state.sum=0;state.downsample=0;
    if(state.captured!=SAMPLES)continue;state.captured=0;
    if(state.used==FRAMES){state.stats.dropped++;continue;}
    uint8_t *p=state.outgoing[state.write];memcpy(p,"G5\1\3",4);put32(p+4,state.vip);
    p[8]=p[14]=0xff;p[9]=p[15]=0xfe;put32(p+10,UINT32_MAX);
    memcpy(p+16,"ZV01",4);unsigned seq=++state.sequence;p[20]=seq>>8;p[21]=seq;p[22]=p[23]=0;
    putFloat(p+24,state.x);putFloat(p+28,state.y);putFloat(p+32,state.z);memcpy(p+36,state.capture,SAMPLES);
    state.queuedAt[state.write]=now;state.write=(state.write+1)%FRAMES;state.used++;
  }
  pthread_mutex_unlock(&state.lock);
}
int ZemaVoiceTakeOutgoing(uint8_t *bytes,size_t capacity) {
  if(!bytes||capacity<ZEMA_VOICE_FRAME_BYTES)return 0;
  pthread_mutex_lock(&state.lock);uint64_t now=milliseconds();int result=0;
  if(!atomic_load(&connected)||!atomic_load(&mic)||!localReady(now))clearCapture();
  while(state.used){
    unsigned at=state.read;state.read=(at+1)%FRAMES;state.used--;
    if(now-state.queuedAt[at]>100){state.stats.dropped++;continue;}
    memcpy(bytes,state.outgoing[at],ZEMA_VOICE_FRAME_BYTES);state.stats.sent++;result=ZEMA_VOICE_FRAME_BYTES;break;
  }
  pthread_mutex_unlock(&state.lock);return result;
}
bool ZemaVoiceDeliver(const uint8_t *p,size_t count) {
  if(!p||count<16||memcmp(p,"G5\1\3",4)||p[8]!=255||p[9]!=254||p[14]!=255||p[15]!=254)return false;
  if(count!=ZEMA_VOICE_FRAME_BYTES||memcmp(p+16,"ZV01",4)||p[22]||p[23])return true;
  uint32_t source=get32(p+4),destination=get32(p+10),slot=(source&65535);
  float x=getFloat(p+24),y=getFloat(p+28),z=getFloat(p+32);
  if((source&0xffff0000)!=0x0a4d0000||slot<1||slot>PEERS||!valid(x,y,z))return true;
  pthread_mutex_lock(&state.lock);uint64_t now=milliseconds();
  if(!atomic_load(&connected)||!atomic_load(&speaker)||source==state.vip||
     (destination!=UINT32_MAX&&destination!=state.vip)||!localReady(now)){pthread_mutex_unlock(&state.lock);return true;}
  Speaker *q=&state.peers[slot-1];uint16_t seq=(uint16_t)(p[20]<<8|p[21]);
  if(q->seen&&now-q->heard<1000&&(uint16_t)(seq-q->sequence)>=32768){pthread_mutex_unlock(&state.lock);return true;}
  if(q->seen&&now-q->heard<1000&&seq==q->sequence){pthread_mutex_unlock(&state.lock);return true;}
  if(!q->seen||now-q->heard>250){q->read=q->write=0;q->playing=q->gainValid=false;}
  q->sequence=seq;q->seen=true;q->heard=now;q->x=x;q->y=y;q->z=z;
  float dx=x-state.x,dy=y-state.y,dz=z-state.z;
  /* Do not retain speech from players outside the audible radius. */
  if(dx*dx+dy*dy+dz*dz>=VOICE_RANGE*VOICE_RANGE){q->read=q->write;q->playing=q->gainValid=false;pthread_mutex_unlock(&state.lock);return true;}
  if(q->write-q->read+960>RING){state.stats.dropped++;pthread_mutex_unlock(&state.lock);return true;}
  for(unsigned i=0;i<SAMPLES;i++){
    float a=decode(p[36+i]),b=i+1<SAMPLES?decode(p[37+i]):a;
    for(unsigned j=0;j<3;j++)q->samples[q->write++&(RING-1)]=a+(b-a)*(j/3.f);
  }
  state.stats.received++;pthread_mutex_unlock(&state.lock);return true;
}
void ZemaVoiceMixAudio(float *left,float *right,uint32_t count) {
  if(!left||!right||!atomic_load(&connected)||!atomic_load(&speaker)||pthread_mutex_trylock(&state.lock))return;
  uint64_t now=milliseconds();
  if(!localReady(now)){clearSpeakers();pthread_mutex_unlock(&state.lock);return;}
  bool mixed=false;
  for(unsigned n=0;n<PEERS;n++){
    Speaker *q=&state.peers[n];uint32_t available=q->write-q->read;
    float dx=q->x-state.x,dy=q->y-state.y,dz=q->z-state.z,d=sqrtf(dx*dx+dy*dy+dz*dz);
    if(!q->seen||now-q->heard>250||d>=VOICE_RANGE){q->read=q->write;q->playing=q->gainValid=false;continue;}
    if(!q->playing){if(available<1920)continue;q->playing=true;} // 40 ms jitter pre-roll
    if(available>7200){q->read=q->write-4800;available=4800;} // bounded latency
    float target=distanceGain(d);
    if(!q->gainValid){q->gain=target;q->gainValid=true;}
    uint32_t take=available<count?available:count;
    /* Smooth the 10 Hz position updates at audio rate, without allocations or
     * changing the immediate mute/stale/out-of-range discard rules. */
    for(uint32_t i=0;i<take;i++){q->gain+=(target-q->gain)*GAIN_SLEW;float v=q->samples[q->read++&(RING-1)]*q->gain;left[i]+=v;right[i]+=v;}
    if(take<count)q->playing=false;state.stats.mixed+=take;if(take)mixed=true;
  }
  if(mixed)for(uint32_t i=0;i<count;i++){left[i]=fmaxf(-1,fminf(1,left[i]));right[i]=fmaxf(-1,fminf(1,right[i]));}
  pthread_mutex_unlock(&state.lock);
}
ZemaVoiceStats ZemaVoiceReadStats(void) { pthread_mutex_lock(&state.lock);ZemaVoiceStats s=state.stats;pthread_mutex_unlock(&state.lock);return s; }
