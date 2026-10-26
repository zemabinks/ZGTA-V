#include "WarmDispatchHarness.inc"
int main(){@autoreleasepool {
 namespace NW=NativeWarm;namespace NP=NativePreparedDraw;namespace NU=NativeUniforms;
 graphicsContext=[[JSContext alloc] init];NU::install(graphicsContext);NativePipeline::install(graphicsContext);NP::install(graphicsContext);NW::install(graphicsContext);
 JSContextRef c=graphicsContext.JSGlobalContextRef;JSValueRef error=nullptr;
 std::array<uint32_t,8192> memory{};engineMemory=memory.data();engineMemorySize=sizeof memory;
 uint32_t tail=64;auto append=[&](uint32_t op,std::initializer_list<uint32_t> values){uint32_t offset=tail;memory[tail/4]=op;memory[tail/4+1]=values.size();std::copy(values.begin(),values.end(),memory.begin()+tail/4+2);tail+=8+values.size()*4;return offset;};
 NP::DrawContext context;context.tail=1;context.epoch=1;context.frame=1;context.slot=0;context.slots=3;context.resourceGeneration=10;context.encoder=55;context.width=960;context.height=540;
 NativePipeline::state[0]=7;NativePipeline::state[2]=17;NP::layouts[17]=NativePipeline::Layout{};
 auto identity=NativePipeline::key(&NP::layouts[17],1);JSObjectRef owner=JSObjectMake(c,nullptr,nullptr);JSValueProtect(c,owner);NativePipeline::values[identity]=owner;
 NativeDraw::Plan plan;NP::Record record;record.owner=owner;record.pipeline=(WGPURenderPipeline)(uintptr_t)101;record.plan=&plan;record.generation=10;record.pipelineGeneration=NativePipeline::generation;
 uint8_t constants[64]={};NU::shadows[10]={constants,sizeof constants,0};
 auto *pack=new NU::Pack;pack->members={{0,16,0}};JSObjectRef packObject=JSObjectMake(c,NU::packClass(),pack);JSValueProtect(c,packObject);
 auto *cache=new NU::BindingCache;cache->sources={0,0,1,0};cache->epoch=1;cache->keys[0].emplace_back();cache->last[0]=0;
 JSObjectRef cacheObject=JSObjectMake(c,NU::cacheClass(),cache);JSValueProtect(c,cacheObject);auto &key=cache->keys[0][0];
 key.entry=JSObjectMake(c,nullptr,nullptr);JSValueProtect(c,key.entry);key.ids={10,0};key.versions={0,0};key.pack=pack;key.packObject=packObject;key.packSize=16;key.chunkId=0x40000000;key.dynamicCount=1;key.group=(WGPUBindGroup)(uintptr_t)201;
 record.needed[0]=true;record.caches[0]=cacheObject;record.nativeCaches[0]=cache;NP::records[identity]=record;NativePipeline::state[0]=0;
 append(18,{0,7});append(18,{2,91});append(19,{17});append(20,{4});append(21,{0,1,50,16,32});append(22,{60,57,8});append(23,{0,0,1,10,0,1});append(24,{1,2,1,30});append(25,{1,0,1,77});
 append(12,{10,0,4,0x12345678});append(32,{1,36,1,0,(uint32_t)-4,0});append(21,{0,1,50,16,96});append(47,{10,4,4,0x87654321});append(32,{1,72,1,0,0,0});uint32_t stop=append(26,{0});
 assert(NW::consume(c,0,64,tail,sizeof memory,context,512,&error)==14&&!error);
 assert(NW::output[0]==stop&&NW::output[2]==2&&NW::output[4]==0&&NW::output[5]&&NW::output[7]==1);
 assert(NW::output[8]==8&&NW::output[9]==1&&NW::output[12]==10&&NW::output[13]==2);
 assert(NW::auxiliary[0]==91&&NW::auxiliary[1]==96&&NW::auxiliary[17]==60&&NW::auxiliary[19]==8);
 assert(NU::state[0]==10&&NU::bindings[1*152+16+2]==30&&NU::bindings[1*152]==77&&NU::shadows[10].version==2);
 assert(NativeDraw::vertices[0].id==0&&NativeDraw::indexId==0); // preparation must not change replay state
 assert(NP::snapshots.size()==2&&NP::snapshots[0].offsets[0]==0&&NP::snapshots[1].offsets[0]==256);
 const auto &bytes=NU::ringChunks[0].stages[0].bytes;uint32_t first=0,second=0;memcpy(&first,bytes.data()+4,4);memcpy(&second,bytes.data()+260,4);assert(first==0&&second==0x87654321);
 NW::replay(0,(WGPURenderPassEncoder)(uintptr_t)42);
 assert(NativeDraw::replayTrace.size()==2&&NativeDraw::replayTrace[0][1]==32&&NativeDraw::replayTrace[1][1]==96&&NativeDraw::replayTrace[0][2]==8);
 NW::clear();NP::clearSnapshots(c);assert(NW::ranges.empty()&&pipelineRefs==pipelineReleases&&groupRefs==groupReleases);
 // A missing snapshot stops at the draw, preserving preceding state for JS.
 tail=64;append(21,{0,1,50,16,128});append(19,{999});uint32_t failed=append(32,{0,3,1,0,0,0});
 assert(NW::consume(c,0,64,tail,sizeof memory,context,512,&error)==2&&NW::output[0]==failed&&NW::output[10]==failed&&NW::output[11]==1);
 assert(NW::output[4]==0&&NP::snapshots.empty());NW::replay(0,(WGPURenderPassEncoder)(uintptr_t)42);assert(NativeDraw::vertices[0].offset==128);NW::clear();
 // Uploads with GPU storage, invalid destinations or unpublished bytes stay
 // with the original handler and do not change any shadow or version output.
 NU::shadows[999]={constants,sizeof constants,0};
 for(auto values:{std::array<uint32_t,4>{999,0,4,1},{10,64,4,1}}){tail=64;append(12,{values[0],values[1],values[2],values[3]});assert(NW::consume(c,0,64,tail,sizeof memory,context,512,&error)==0&&NW::output[9]==0);}
 assert(NU::shadows[999].version==0);
 tail=64;append(12,{10,0,4,1});uint32_t oldVersion=NU::shadows[10].version;assert(NW::consume(c,0,64,tail-4,sizeof memory,context,512,&error)==0&&NU::shadows[10].version==oldVersion);
 // Packet limits preserve the normal event-loop publication boundary.
 tail=64;for(unsigned i=0;i<513;i++)append(18,{2,i});assert(NW::consume(c,0,64,tail,sizeof memory,context,999,&error)==512&&NW::auxiliary[0]==511&&NW::output[0]==64+512*16);
 // A bounded unique-ID version output stops before consuming the next upload.
 tail=64;uint8_t one[4]={};for(uint32_t i=0;i<129;i++){NU::shadows[1000+i]={one,4,0};append(12,{1000+i,0,4,i});}
 assert(NW::consume(c,0,64,tail,sizeof memory,context,512,&error)==128&&NW::output[9]==128&&NU::shadows[1128].version==0);
 // Native replay capacity also leaves the next packet untouched.
 tail=64;append(21,{0,1,1,1,1});NW::replayWords.resize(NW::ReplayWordLimit);assert(NW::consume(c,0,64,tail,sizeof memory,context,512,&error)==0&&NW::output[0]==64);NW::clear();
 assert(!error);puts("PASS: production spans, exact tails/limits, state synchronization, deferred vertex/index order, immutable constants, miss-after-state, GPU upload rejection, version aggregation and bounded replay storage.");
}return 0;}
