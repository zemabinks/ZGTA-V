/* Adapted from glue5 a62e56a5 gamer_tags.rs (MIT); see THIRD_PARTY_NOTICES.md.
 * The original movie has 15 of 30 layout parts. Repeated zero entries must
 * become the absent part IDs, otherwise the name is measured/placed repeatedly.
 */
#ifndef ZEMA_GAMER_TAG_LAYOUT_H
#define ZEMA_GAMER_TAG_LAYOUT_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#define ZEMA_TAG_ORDER UINT64_C(19506224)
#define ZEMA_TAG_SORTED UINT64_C(19506092)
#define ZEMA_TAG_HUD UINT64_C(19561688)
static int ZemaGamerTagComplete(uint8_t* memory,uint64_t size) {
  if(!memory||size<ZEMA_TAG_ORDER+120||size<ZEMA_TAG_SORTED+1||size<ZEMA_TAG_HUD+8||!memory[ZEMA_TAG_SORTED])return 0;
  int32_t order[30];uint8_t seen[30]={0},repeat[30]={0};unsigned changes=0;
  memcpy(order,memory+ZEMA_TAG_ORDER,sizeof order);
  for(unsigned i=0;i<30;i++){
    if(order[i]<0||order[i]>=30)return 0;
    if(seen[order[i]]){repeat[i]=1;changes++;}seen[order[i]]=1;
  }
  if(!changes)return 0;
  uint64_t hud=0;memcpy(&hud,memory+ZEMA_TAG_HUD,8);
  if(!hud||hud>size||UINT64_C(52)*672>size-hud)return 0;
  unsigned next=0;
  for(unsigned i=0;i<30;i++)if(repeat[i]){
    while(next<30&&seen[next])next++;
    if(next>=30)return 0;
    order[i]=(int32_t)next++;
  }
  for(unsigned i=0;i<30;i++)if(repeat[i])memcpy(memory+ZEMA_TAG_ORDER+4*i,&order[i],4);
  for(unsigned i=0;i<52;i++)memory[hud+(uint64_t)i*672+264]=1;
  return (int)changes;
}
#endif
