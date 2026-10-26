#pragma once
#include <cstdint>

// A bounded cursor over one published portion of the engine ring. WRAP stays
// with the existing dispatcher; this cursor never publishes or executes data.
namespace NativeRing {
enum class Status {Ready,End,Wrap,Invalid};
struct Packet {
 uint32_t op=0,words=0,offset=0,end=0;
 uint64_t wordIndex=0;
 const uint32_t *payload=nullptr;
};
class Cursor {
 const uint8_t *memory_;
 uint64_t base_;
 uint32_t tail_,head_,size_;
 bool valid_;
public:
 Cursor(const void *memory,uint64_t memorySize,uint64_t base,uint32_t tail,uint32_t head,uint32_t size):
  memory_((const uint8_t *)memory),base_(base),tail_(tail),head_(head),size_(size),
  valid_(memory&&!((uintptr_t)memory&3)&&base<=memorySize&&size<=memorySize-base&&!(base&3)&&!(size&3)&&size>=72&&tail>=64&&tail<size&&head>=64&&head<=size&&!(tail&3)&&!(head&3)){}
 uint32_t tail()const{return tail_;}
 Status peek(Packet &packet)const{
  packet={};if(!valid_)return Status::Invalid;if(tail_==head_)return Status::End;
  if(tail_>size_-8)return Status::Invalid;
  // An incomplete header is never read, even if its bytes fit the mapping.
  if(tail_<head_&&head_-tail_<8)return Status::Invalid;
  const uint32_t *header=(const uint32_t *)(memory_+base_+tail_);
  uint32_t op=header[0],words=header[1];
  if(op==1)return tail_<head_?Status::Invalid:Status::Wrap;
  if(words>(size_-tail_-8)/4)return Status::Invalid;
  uint32_t end=tail_+8+words*4;if(tail_<head_&&end>head_)return Status::Invalid;
  packet={op,words,tail_,end,(base_+tail_+8)/4,header+2};return Status::Ready;
 }
 bool consume(const Packet &packet){
  if(!valid_||packet.offset!=tail_||packet.end!=(uint64_t)tail_+8+(uint64_t)packet.words*4||packet.end>size_||(tail_<head_&&packet.end>head_)||packet.wordIndex!=(base_+tail_+8)/4||packet.payload!=(const uint32_t *)(memory_+base_+tail_+8))return false;
  tail_=packet.end;return true;
 }
};
// Validate the opcode payload before any state mutation. Unsupported packets
// stay in the original dispatcher. Upload bytes remain inside their packet.
static inline bool warmPayload(const Packet &p){
 const uint32_t *v=p.payload;uint64_t required=0;if(!v)return false;
 switch(p.op){
  case 18:if(p.words<2||v[0]>=3)return false;required=2;break;
  case 19:case 20:required=1;break;
  case 21:if(p.words<2||v[0]>=16||v[1]>16-v[0])return false;required=2+(uint64_t)v[1]*3;break;
  case 22:required=3;break;
  case 23:case 24:case 25:if(p.words<3||v[0]>=3)return false;required=3+(uint64_t)v[2]*(p.op==23?3:1);break;
  case 32:required=6;break;
  case 12:case 47:if(p.words<3)return false;return (uint64_t)v[2]<=(uint64_t)p.words*4-12;
  default:return false;
 }
 return required<=p.words;
}
}
