#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
/* Exact-length, transactional gameconfig overlay. Never changes asset files. */
int ZemaBroadcastPatch(uint8_t* bytes,size_t length){
  if(!bytes||length>16*1024*1024||memchr(bytes,0,length))return 0;
  char* text=malloc(length+1);if(!text)return 0;memcpy(text,bytes,length);text[length]=0;
  char* begin=strstr(text,"<PlayerBroadcastData>"),*end=begin?strstr(begin,"</PlayerBroadcastData>"):NULL;
  const int sizes[]={3600,2500,150,80,40},counts[]={3,4,12,12,16};int ok=begin&&end;
  for(int i=0;i<5&&ok;i++){
    char tag[64],value[8];snprintf(tag,sizeof tag,"<SizeOfData value=\"%d\"/>",sizes[i]);snprintf(value,sizeof value,"%d",counts[i]);
    char* item=strstr(begin,tag),*field=item?strstr(item,"<NumInstances value=\""):NULL;
    char* close=item?strstr(item,"</Item>"):NULL;
    char* duplicate=item?strstr(item+strlen(tag),tag):NULL;
    if(!field||!close||close>=end||field>=close||(duplicate&&duplicate<end)){ok=0;break;}char* digits=field+21,*quote=strchr(digits,'"');
    if(!quote||quote>=end||quote==digits){ok=0;break;}size_t old=(size_t)(quote-digits),n=strlen(value);
    if(old>9||quote>=close){ok=0;break;}
    unsigned current=0;for(size_t j=0;j<old;j++){if(digits[j]<'0'||digits[j]>'9'){ok=0;break;}current=current*10+(unsigned)(digits[j]-'0');}
    if(!ok)break;if(current>=(unsigned)counts[i])continue;
    if(n<old||n-old>(size_t)(field-begin)){ok=0;break;}size_t delta=n-old;
    for(size_t j=0;j<delta;j++)if(field[-1-(ptrdiff_t)j]!='\t')ok=0;
    if(ok){memmove(field-delta,field,(size_t)(digits-field));memcpy(digits-delta,value,n);}
  }
  if(ok)memcpy(bytes,text,length);free(text);return ok;
}
