#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
/* Exact-length, transactional gameconfig overlay. Never changes asset files.
 * Host pool sizing follows glue5 5d761642: medium pools, not the earlier
 * broad increase that pressured the network heap. Player sizing is retained. */
static int patch_block(char* text,const char* name,const int* sizes,const int* counts,size_t count){
  char opening[64],closing[64];
  snprintf(opening,sizeof opening,"<%s>",name);snprintf(closing,sizeof closing,"</%s>",name);
  char* begin=strstr(text,opening);char* end=begin?strstr(begin,closing):NULL;
  if(!begin||!end||strstr(begin+strlen(opening),opening)||strstr(text,closing)!=end||strstr(end+strlen(closing),closing))return 0;
  for(size_t i=0;i<count;i++){
    char tag[64],value[8];snprintf(tag,sizeof tag,"<SizeOfData value=\"%d\"/>",sizes[i]);snprintf(value,sizeof value,"%d",counts[i]);
    char* item=strstr(begin,tag),*field=item?strstr(item,"<NumInstances value=\""):NULL;
    char* close=item?strstr(item,"</Item>"):NULL;
    char* duplicate=item?strstr(item+strlen(tag),tag):NULL;
    if(!field||!close||close>=end||field>=close||(duplicate&&duplicate<end))return 0;
    char* duplicate_field=strstr(field+21,"<NumInstances value=\"");
    if(duplicate_field&&duplicate_field<close)return 0;
    char* digits=field+21,*quote=strchr(digits,'"');
    if(!quote||quote>=close||quote==digits)return 0;
    size_t old=(size_t)(quote-digits),n=strlen(value);if(old>9)return 0;
    unsigned current=0;for(size_t j=0;j<old;j++){if(digits[j]<'0'||digits[j]>'9')return 0;current=current*10+(unsigned)(digits[j]-'0');}
    if(current>=(unsigned)counts[i])continue;
    if(n<old||n-old>(size_t)(field-begin))return 0;size_t delta=n-old;
    for(size_t j=0;j<delta;j++)if(field[-1-(ptrdiff_t)j]!='\t')return 0;
    memmove(field-delta,field,(size_t)(digits-field));memcpy(digits-delta,value,n);
  }
  return 1;
}
int ZemaBroadcastPatch(uint8_t* bytes,size_t length){
  if(!bytes||length>16*1024*1024||memchr(bytes,0,length))return 0;
  char* text=malloc(length+1);if(!text)return 0;memcpy(text,bytes,length);text[length]=0;
  const int host_sizes[]={7500,4000},host_counts[]={3,6};
  const int player_sizes[]={3600,2500,150,80,40},player_counts[]={3,4,12,12,16};
  int ok=patch_block(text,"HostBroadcastData",host_sizes,host_counts,2)&&patch_block(text,"PlayerBroadcastData",player_sizes,player_counts,5);
  if(ok)memcpy(bytes,text,length);free(text);return ok;
}
