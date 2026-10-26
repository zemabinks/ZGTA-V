"""Build a pinned, reversible minimap delta from verified official icon pixels.

Only the local generator uses the original engine's archive codec. Runtime
consumers apply a hashed binary delta and never need its static archive key.
"""
import argparse,base64,ctypes,hashlib,json,struct,sys,zlib
from pathlib import Path
APP=Path(__file__).resolve().parents[1]
ORIGINAL_GFX='25aeffea87255043828ade0ba5c7d05c64d474881ba47018af51edd427871382'
ORIGINAL_RPF='0f51cbf88739c7ac46779acfd7ef9e181aeeb54efee55ce721194b1e90463449'
CLASS_SHA='321c23bd578d7f7bdc8247a73b74f1dcdba165cce740eaa8ce71dff4da3be1a9'
ENGINE_SHA='11ca8d2c04c5e843d18ff4aea4899d72c86973c6b031df334e67c446b2ae83e0'
def sha(data):return hashlib.sha256(data).hexdigest()
def tag(kind,data=b''):
 return struct.pack('<H',kind<<6|63)+struct.pack('<I',len(data))+data if len(data)>=63 else struct.pack('<H',kind<<6|len(data))+data
def tags(data,start):
 p=start
 while p<len(data):
  at=p;v=struct.unpack_from('<H',data,p)[0];p+=2;n=v&63
  if n==63:n=struct.unpack_from('<I',data,p)[0];p+=4
  if p+n>len(data):raise ValueError('Truncated movie tag')
  yield at,v>>6,data[p:p+n],data[at:p+n];p+=n
def rgba(png):
 if png[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('PNG signature')
 p=8;compressed=[];header=None;palette=b'';alpha=b''
 while p<len(png):
  n=struct.unpack_from('>I',png,p)[0];kind=png[p+4:p+8];data=png[p+8:p+8+n]
  if n>65536 or p+n+12>len(png) or zlib.crc32(kind+data)!=struct.unpack_from('>I',png,p+8+n)[0]:raise ValueError('PNG chunk integrity')
  if kind==b'IHDR':header=struct.unpack('>IIBBBBB',data)
  if kind==b'IDAT':compressed.append(data)
  if kind==b'PLTE':palette=data
  if kind==b'tRNS':alpha=data
  p+=n+12
 if header not in [(32,32,8,6,0,0,0),(32,32,8,3,0,0,0)]:raise ValueError('Expected bounded 32px RGBA/palette icon')
 channels=4 if header[3]==6 else 1
 if channels==1 and (not palette or len(palette)%3):raise ValueError('Invalid PNG palette')
 raw=zlib.decompress(b''.join(compressed));stride=32*channels
 if len(raw)!=32*(stride+1):raise ValueError('PNG pixel size')
 previous=bytearray(stride);pixels=[]
 for y in range(32):
  f=raw[y*(stride+1)];row=bytearray(raw[y*(stride+1)+1:(y+1)*(stride+1)])
  for x in range(stride):
   left=row[x-channels] if x>=channels else 0;up=previous[x];corner=previous[x-channels] if x>=channels else 0
   if f==0:predict=0
   elif f==1:predict=left
   elif f==2:predict=up
   elif f==3:predict=(left+up)//2
   elif f==4:
    q=left+up-corner;a,b,c=abs(q-left),abs(q-up),abs(q-corner);predict=left if a<=b and a<=c else up if b<=c else corner
   else:raise ValueError('PNG filter')
   row[x]=(row[x]+predict)&255
  if channels==4:pixels.append([tuple(row[x:x+4]) for x in range(0,stride,4)])
  else:
   if any(index>=len(palette)//3 for index in row):raise ValueError('PNG palette index')
   pixels.append([tuple(palette[index*3:index*3+3])+(alpha[index] if index<len(alpha) else 255,) for index in row])
  previous=row
 return pixels
class Bits:
 def __init__(self):self.out=[]
 def put(self,value,n):self.out.extend((value>>i)&1 for i in reversed(range(n)))
 def signed(self,value,n):self.put(value&((1<<n)-1),n)
 def bytes(self):
  self.out.extend([0]*((-len(self.out))%8));return bytes(sum(self.out[p+i]<<(7-i) for i in range(8)) for p in range(0,len(self.out),8))
def signed_bits(*values):return max(2,max(abs(v).bit_length()+1 for v in values))
def rectangle():
 b=Bits();b.put(9,5)
 for value in [-160,160,-160,160]:b.signed(value,9)
 return b.bytes()
def bitmap_artwork(bitmap_id,shape_id,pixels):
 # The port renders these lossless bitmaps in both the map atlas and AS2 legend.
 # Row-run vector shapes rendered in the atlas but disappeared in UI passes.
 if len(pixels)!=32 or any(len(row)!=32 for row in pixels):raise ValueError('Icon pixel bounds')
 argb=bytes(v for row in pixels for r,g,b,a in row for v in (a,(r*a+127)//255,(g*a+127)//255,(b*a+127)//255))
 bitmap=tag(36,struct.pack('<HBHH',bitmap_id,5,32,32)+zlib.compress(argb,9))
 matrix=Bits();matrix.put(1,1);matrix.put(21,5)
 for _ in range(2):matrix.signed(10*65536,21)
 matrix.put(0,1);matrix.put(9,5)
 for _ in range(2):matrix.signed(-160,9)
 path=Bits();path.put(1,4);path.put(0,4);path.put(0,1);path.put(5,5);path.put(9,5)
 path.signed(-160,9);path.signed(-160,9);path.put(1,1)
 for delta,vertical in [(320,0),(320,1),(-320,0),(-320,1)]:
  path.put(1,1);path.put(1,1);path.put(8,4);path.put(0,1);path.put(vertical,1);path.signed(delta,10)
 path.put(0,6)
 shape=tag(32,struct.pack('<H',shape_id)+rectangle()+b'\x01\x41'+struct.pack('<H',bitmap_id)+matrix.bytes()+b'\0'+path.bytes())
 return bitmap+shape
def sprite(character,shape_id,name):
 body=struct.pack('<HH',character,1)+tag(26,b'\x06'+struct.pack('<HH',1,shape_id)+b'\0')+tag(1)+tag(0)
 return tag(39,body)+tag(56,struct.pack('<HH',1,character)+name.encode()+b'\0')
def sparse_members(icons):
 out=b''
 for row in icons:
  data=b'\x04\x01\x07'+struct.pack('<i',row['id'])+b'\0'+row['name'].encode()+b'\0'
  out+=b'\x96'+struct.pack('<H',len(data))+data+b'\x4f'
 return out
def expand_class(raw,icons):
 if sha(raw)!=CLASS_SHA:raise ValueError('Pinned original Blips class differs')
 start=0x21b0;size=7018;insert=start+size-6;extra=sparse_members(icons)
 if raw[insert:insert+6]!=b'\x96\x02\0\x04\x01\x3e':raise ValueError('Pinned array return differs')
 patched=bytearray(raw);struct.pack_into('<H',patched,start-2,size+len(extra))
 # Function bodies follow, rather than belong to, ActionLength. Adjust only
 # outer branches crossing the insertion; the pinned getter body has none.
 p=0
 while p<len(raw):
  off=p;op=raw[p];p+=1;n=struct.unpack_from('<H',raw,p)[0] if op>=128 else 0;p+=2 if op>=128 else 0;data_at=p;p+=n
  if op in (0x99,0x9d):
   target=p+struct.unpack_from('<h',raw,data_at)[0]
   change=(len(extra) if target>=insert else 0)-(len(extra) if p>=insert else 0)
   struct.pack_into('<h',patched,data_at,target-p+change)
  if op in (0x8e,0x9b):p+=struct.unpack_from('<H',raw,data_at+n-2)[0]
  if op==0:break
 return bytes(patched[:insert])+extra+bytes(patched[insert:])
def movie(original,icons,folder):
 if sha(original)!=ORIGINAL_GFX:raise ValueError('Original minimap movie differs')
 start=8+(5+(original[8]>>3)*4+7)//8+4;entries=list(tags(original,start));maximum=0;changed=0;out=[]
 for _,kind,data,encoded in entries:
  if kind in (2,22,32,39,83,37,1009):maximum=max(maximum,struct.unpack_from('<H',data)[0])
  if kind==59 and sha(data[2:])==CLASS_SHA:encoded=tag(59,data[:2]+expand_class(data[2:],icons));changed+=1
  out.append(encoded)
 if changed!=1:raise ValueError('Pinned class missing or duplicated')
 additions=b''
 for row in icons:
  raw=(folder/row['file']).read_bytes()
  if sha(raw)!=row['sha256'] or len(raw)!=row['bytes']:raise ValueError('Official artwork changed')
  maximum+=3;additions+=bitmap_artwork(maximum-2,maximum-1,rgba(raw))+sprite(maximum,maximum-1,row['name'])
 if entries[-2][1]!=1 or entries[-1][1]!=0:raise ValueError('Pinned final movie frame differs')
 result=bytearray(original[:start]+b''.join(out[:-2])+additions+b''.join(out[-2:]));struct.pack_into('<I',result,4,len(result));return bytes(result)
def codec(engine):
 sys.path.insert(0,str(APP/'Scripts'));import inspect_engine_lan as g
 raw=Path(engine).read_bytes()
 if sha(raw)!=ENGINE_SHA:raise ValueError('Original engine differs')
 r=g.Reader(dict(g.sections(raw))[11]);segments=[]
 for _ in range(r.count()):
  if r.uint()!=1:raise ValueError('Pinned engine segment type differs')
  segments.append(r.take(r.uint()))
 key=segments[620][156:188]
 cc=ctypes.CDLL('/usr/lib/system/libcommonCrypto.dylib');cc.CCCrypt.argtypes=[ctypes.c_uint,ctypes.c_uint,ctypes.c_uint,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)];cc.CCCrypt.restype=ctypes.c_int
 def crypt(data,decrypt):
  n=len(data)//16*16;out=ctypes.create_string_buffer(n);done=ctypes.c_size_t()
  if cc.CCCrypt(int(decrypt),0,2,key,32,None,data[:n],n,out,n,ctypes.byref(done))!=0:raise ValueError('Archive codec failed')
  return out.raw[:done.value]+data[n:]
 return crypt
def build(original,crypt,folder):
 if sha(original)!=ORIGINAL_RPF:raise ValueError('Original minimap archive differs')
 count,names_size=struct.unpack_from('<II',original,4);table=crypt(original[16:16+count*16],True);names=crypt(original[16+count*16:16+count*16+names_size],True)
 icons=json.loads((folder/'catalog.json').read_text())['icons'];found=[]
 for i in range(count):
  a,b,c,d=struct.unpack_from('<4I',table,i*16)
  if b==0x7fffff00:continue
  name_at=a&65535;name=names[name_at:names.index(0,name_at)].decode()
  if name!='minimap.gfx':continue
  packed=a|(b<<32);offset=((packed>>40)&0xffffff)*512;length=(packed>>16)&0xffffff
  if d!=1 or not length:raise ValueError('Pinned minimap entry format differs')
  gfx=zlib.decompress(crypt(original[offset:offset+length],True),-15);assert len(gfx)==c
  updated=movie(gfx,icons,folder);compress=zlib.compressobj(9,zlib.DEFLATED,-15);payload=crypt(compress.compress(updated)+compress.flush(),False)
  at=(len(original)+511)//512*512;new_packed=(a&65535)|(len(payload)<<16)|((at//512)<<40);entry=struct.pack('<QII',new_packed,len(updated),d)
  before=original[16+i*16:32+i*16];after=crypt(entry,False);append=bytes(at-len(original))+payload
  result=bytearray(original);result[16+i*16:32+i*16]=after;result.extend(append)
  patch={'format':'zgta-modern-map-delta-v1','path':'x64/data/cdimages/scaleform_minimap.rpf','base_sha256':sha(original),'base_bytes':len(original),'result_sha256':sha(result),'result_bytes':len(result),'edits':[{'offset':16+i*16,'before':before.hex(),'after':after.hex()}],'append_base64':base64.b64encode(append).decode(),'icons':[{'id':r['id'],'name':r['name'],'png_sha256':r['sha256']} for r in icons],'original_movie_sha256':sha(gfx),'updated_movie_sha256':sha(updated),'pixel_conversion':'PREMULTIPLIED_ARGB_TO_STOCK_DEFINE_BITS_LOSSLESS2','original_assets_changed':False}
  found.append((patch,result,updated))
 if len(found)!=1:raise ValueError('Missing minimap archive entry')
 return found[0]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--engine',type=Path,required=True);p.add_argument('--archive',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 patch,_,_=build(a.archive.read_bytes(),codec(a.engine),APP/'Resources/ModernBlips');a.output.write_text(json.dumps(patch,indent=2)+'\n');print(json.dumps({k:patch[k] for k in ['format','base_bytes','result_bytes','result_sha256','pixel_conversion']},indent=2))
if __name__=='__main__':main()
