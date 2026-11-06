from pathlib import Path
import sys,json,struct,math,shutil
sys.path.insert(0,'standalone-doors');from nif_io import Nif,node_offsets,children,set_children
r=Path('physical-containers');report=json.loads((r/'build-report.json').read_text());backup=r/'before-removable-c25/models';backup.mkdir(parents=True,exist_ok=True)
I=lambda x:struct.pack('<i',x)
identity=[1.,0.,0.,0.,1.,0.,0.,0.,1.]
def mul(a,b):return [sum(a[3*j+k]*b[3*k+i] for k in range(3)) for j in range(3) for i in range(3)]
def apply(a,v):return [sum(a[3*j+k]*v[k] for k in range(3)) for j in range(3)]
changed=[]
for item in report:
 if 'error' in item:continue
 p=r/'package/meshes'/item['physical_model'].replace('\\','/');old=p.read_bytes();bak=backup/p.relative_to(r/'package/meshes');bak.parent.mkdir(parents=True,exist_ok=True)
 if not bak.exists():bak.write_bytes(old)
 else:old=bak.read_bytes()
 n=Nif(old);names={n.strings[struct.unpack_from('<i',b)[0]]:i for i,(k,b) in enumerate(n.blocks) if k in ('NiNode','BSTriShape','BSFadeNode') and struct.unpack_from('<i',b)[0]>=0}
 free=any(k in item['model'].lower() for k in ('urn','canopicjar','barrel'))
 for leaf in item['leaves']:
  node=names[leaf['leaf']];co=struct.unpack_from('<i',n.blocks[node][1],node_offsets(n.blocks[node][1])['collision'])[0];rb=struct.unpack_from('<i',n.blocks[co][1],6)[0]
  if free:
   raw=n.blocks[rb][1];assert struct.unpack_from('<I',raw,244)[0]==1
   n.blocks[rb]=(n.blocks[rb][0],raw[:244]+struct.pack('<IH',0,0))
   struct.pack_into('<f',n.blocks[rb][1],180,2.0)
  # Gather original closed leaf geometry in model coordinates.
  entries=[]
  def walk(i,rotation,translation,scale):
   kind,raw=n.blocks[i];o=node_offsets(raw);local=struct.unpack_from('<9f',raw,o['rotation']);t=struct.unpack_from('<3f',raw,o['translation']);rr=mul(rotation,local);tt=apply(rotation,[q*scale for q in t]);tt=[a+b for a,b in zip(tt,translation)];ss=scale*struct.unpack_from('<f',raw,o['scale'])[0]
   if kind in ('NiNode','BSFadeNode','BSLeafAnimNode','BSOrderedNode'):
    for child in children(raw):walk(child,rr,tt,ss)
   elif kind=='BSTriShape':entries.append((i,rr,tt,ss))
  # Find accumulated transform at leaf via traversal from root, collect only that subtree.
  def locate(i,rr,tt,ss):
   if i==node:walk(i,rr,tt,ss);return
   kind,raw=n.blocks[i]
   if kind not in ('NiNode','BSFadeNode','BSLeafAnimNode','BSOrderedNode'):return
   o=node_offsets(raw);local=struct.unpack_from('<9f',raw,o['rotation']);t=struct.unpack_from('<3f',raw,o['translation']);at=apply(rr,[q*ss for q in t]);rt=mul(rr,local);tr=[a+b for a,b in zip(at,tt)];sc=ss*struct.unpack_from('<f',raw,o['scale'])[0]
   for c in children(raw):locate(c,rt,tr,sc)
  locate(0,identity,[0,0,0],1)
  points=[]
  for i,rr,tt,ss in entries:
   raw=n.blocks[i][1];e=node_offsets(raw)['collision']+4;desc,nt,nv,size=struct.unpack_from('<QHHI',raw,e+28);st=(desc&15)*4
   for j in range(nv):points.append([a+b for a,b in zip(apply(rr,[q*ss for q in struct.unpack_from('<3f',raw,e+44+j*st)]),tt)])
  if not points:continue
  lo=[min(v[k] for v in points) for k in range(3)];hi=[max(v[k] for v in points) for k in range(3)];thin=min(range(3),key=lambda k:hi[k]-lo[k]);plane=(lo[thin]+hi[thin])*.5
  if thin==2:plane=lo[2]-1.0 # beneath lids; keep visible rim
  for i,rr,tt,ss in entries:
   raw=bytearray(n.blocks[i][1]);o=node_offsets(raw);e=o['collision']+4;desc,nt,nv,size=struct.unpack_from('<QHHI',raw,e+28);st=(desc&15)*4
   struct.pack_into('<i',raw,0,n.string('SVC_DarkFill_'+str(i)));struct.pack_into('<i',raw,o['controller'],-1);struct.pack_into('<3f',raw,o['translation'],0,0,0);struct.pack_into('<9f',raw,o['rotation'],*identity);struct.pack_into('<f',raw,o['scale'],1);struct.pack_into('<i',raw,o['collision'],-1)
   transformed=[]
   for j in range(nv):
    at=e+44+j*st;v=[a+b for a,b in zip(apply(rr,[q*ss for q in struct.unpack_from('<3f',raw,at)]),tt)];v[thin]=plane;struct.pack_into('<3f',raw,at,*v);transformed.append(v)
   shader=struct.unpack_from('<i',raw,e+20)[0]
   if shader<0 or n.blocks[shader][0]!='BSLightingShaderProperty':
    donor=Nif((r/'package/meshes/svrphysicalcontainersc23/clutter/barrel01.nif').read_bytes())
    material=bytearray(next(b for k,b in donor.blocks if k=='BSLightingShaderProperty'))
   else:material=bytearray(n.blocks[shader][1])
   slot=40+4*struct.unpack_from('<I',material,8)[0]
   paths=[b'textures\\svrphysicalcontainersc23\\barrel_inside.dds']+[b'']*8
   tex=n.add('BSShaderTextureSet',struct.pack('<I',9)+b''.join(struct.pack('<I',len(t))+t for t in paths));struct.pack_into('<i',material,slot,tex)
   struct.pack_into('<3f',material,slot+4,0,0,0);struct.pack_into('<f',material,slot+24,1);struct.pack_into('<4f',material,slot+36,0,0,0,0)
   flags=16+4*struct.unpack_from('<I',material,8)[0];struct.pack_into('<I',material,flags,struct.unpack_from('<I',material,flags)[0]&~8);struct.pack_into('<I',material,flags+4,struct.unpack_from('<I',material,flags+4)[0]|16)
   struct.pack_into('<i',raw,e+20,n.add('BSLightingShaderProperty',material));struct.pack_into('<i',raw,e+24,-1)
   center=[(min(v[k] for v in transformed)+max(v[k] for v in transformed))*.5 for k in range(3)];struct.pack_into('<4f',raw,e,*center,max(math.dist(v,center) for v in transformed))
   new=n.add('BSTriShape',raw);set_children(n.blocks[0][1],children(n.blocks[0][1])+[new])
 data=n.encode();assert Nif(data).encode()==data;p.write_bytes(data);changed.append({'model':item['model'],'removable':free,'dark_fill':True})
(r/'removable-assets.json').write_text(json.dumps(changed,indent=2));print('Patched',len(changed),'models;',sum(x['removable'] for x in changed),'removable lid models')
