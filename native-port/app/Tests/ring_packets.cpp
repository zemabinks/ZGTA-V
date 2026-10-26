#include "NativeRingPackets.h"
#include <array>
#include <cassert>
#include <cstdio>
int main(){
 using namespace NativeRing;std::array<uint32_t,128> memory{};Packet p;
 auto packet=[&](uint32_t offset,uint32_t op,uint32_t words){memory[offset/4]=op;memory[offset/4+1]=words;return offset+8+words*4;};
 uint32_t head=packet(64,18,2);memory[18]=1;memory[19]=200;
 head=packet(head,23,6);memory[22]=0;memory[23]=0;memory[24]=1;memory[25]=10;memory[26]=0;memory[27]=4;
 head=packet(head,32,6);
 Cursor cursor(memory.data(),sizeof memory,0,64,head,sizeof memory);
 assert(cursor.peek(p)==Status::Ready&&p.op==18&&p.wordIndex==18&&warmPayload(p));assert(cursor.consume(p));assert(!cursor.consume(p));
 assert(cursor.peek(p)==Status::Ready&&p.op==23&&warmPayload(p));assert(cursor.consume(p));
 assert(cursor.peek(p)==Status::Ready&&p.op==32&&warmPayload(p));assert(cursor.consume(p));assert(cursor.peek(p)==Status::End);
 Cursor partialHeader(memory.data(),sizeof memory,0,64,68,sizeof memory);assert(partialHeader.peek(p)==Status::Invalid);
 Cursor partialBody(memory.data(),sizeof memory,0,64,76,sizeof memory);assert(partialBody.peek(p)==Status::Invalid);
 packet(480,1,0);Cursor wrap(memory.data(),sizeof memory,0,480,96,sizeof memory);assert(wrap.peek(p)==Status::Wrap&&wrap.tail()==480);
 packet(64,1,0);Cursor prematureWrap(memory.data(),sizeof memory,0,64,96,sizeof memory);assert(prematureWrap.peek(p)==Status::Invalid);
 packet(64,32,UINT32_MAX);Cursor oversized(memory.data(),sizeof memory,0,64,96,sizeof memory);assert(oversized.peek(p)==Status::Invalid);
 for(uint32_t tail:{0u,63u,65u,512u}){Cursor invalid(memory.data(),sizeof memory,0,tail,96,sizeof memory);assert(invalid.peek(p)==Status::Invalid);}
 Cursor badBase(memory.data(),sizeof memory,4,64,96,sizeof memory);assert(badBase.peek(p)==Status::Invalid);
 Cursor nullMemory(nullptr,sizeof memory,0,64,96,sizeof memory);assert(nullMemory.peek(p)==Status::Invalid);
 Cursor unaligned((uint8_t *)memory.data()+1,sizeof memory-1,0,64,96,128);assert(unaligned.peek(p)==Status::Invalid);
 // A mapped ring base can differ from zero; payload indices remain absolute.
 packet(128,32,6);Cursor shifted(memory.data(),sizeof memory,64,64,96,448);assert(shifted.peek(p)==Status::Ready&&p.wordIndex==34&&warmPayload(p));
 Packet forged=p;forged.end+=4;assert(!shifted.consume(forged));forged=p;forged.payload++;assert(!shifted.consume(forged));forged=p;forged.wordIndex++;assert(!shifted.consume(forged));assert(shifted.consume(p));
 uint32_t words[64]={};p.payload=words;
 p.op=12;p.words=4;words[2]=4;assert(warmPayload(p));words[2]=5;assert(!warmPayload(p));p.op=47;words[2]=0;assert(warmPayload(p));p.words=2;assert(!warmPayload(p));
 p.op=21;p.words=5;words[0]=15;words[1]=1;assert(warmPayload(p));words[1]=2;assert(!warmPayload(p));words[0]=0;words[1]=UINT32_MAX;assert(!warmPayload(p));
 p.op=23;p.words=6;words[0]=2;words[1]=0;words[2]=1;assert(warmPayload(p));words[2]=UINT32_MAX;assert(!warmPayload(p));words[2]=1;words[0]=3;assert(!warmPayload(p));
 p.op=24;p.words=4;words[0]=1;assert(warmPayload(p));p.op=25;assert(warmPayload(p));p.words=3;assert(!warmPayload(p));
 p.op=32;p.words=6;assert(warmPayload(p));p.words=5;assert(!warmPayload(p));p.op=26;p.words=37;assert(!warmPayload(p));
 p.op=18;p.words=2;p.payload=nullptr;assert(!warmPayload(p));
 puts("PASS: published ring bounds, partial headers/payloads, absolute indices, wrap, invalid offsets, overflow and warm opcode widths.");return 0;
}
