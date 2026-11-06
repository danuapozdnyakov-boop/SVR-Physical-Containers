from pathlib import Path
import sys,struct,json,math
sys.path.insert(0,'standalone-doors')
from nif_io import Nif,node_offsets,children,clean_node,set_children
from build_models import convex_box,body,render_bounds,parent_map,v4,U,I
ROOT=Path('physical-containers')

def tracks(n):
 result={}
 for kind,seq in n.blocks:
  if kind!='NiControllerSequence':continue
  name=struct.unpack_from('<i',seq)[0]
  if name<0 or n.strings[name].lower()!='open':continue
  for k in range(struct.unpack_from('<I',seq,4)[0]):
   ix=struct.unpack_from('<i',seq,21+29*k)[0];interp=struct.unpack_from('<i',seq,12+29*k)[0]
   if ix<0 or interp<0 or n.blocks[interp][0]!='NiTransformInterpolator':continue
   data=struct.unpack_from('<i',n.blocks[interp][1],32)[0]
   if data<0 or n.blocks[data][0]!='NiTransformData':continue
   b=n.blocks[data][1]
   if struct.unpack_from('<2I',b)[0]==0 or struct.unpack_from('<I',b,4)[0]!=4:continue
   p=8;changes=[]
   for axis in range(3):
    count=struct.unpack_from('<I',b,p)[0];p+=4
    if not count:changes.append(0);continue
    kind=struct.unpack_from('<I',b,p)[0];p+=4;stride={1:8,2:16,3:20}.get(kind)
    if not stride:raise ValueError('Unsupported Euler keys')
    values=[struct.unpack_from('<f',b,p+i*stride+4)[0] for i in range(count)]
    changes.append(values[-1]-values[0]);p+=stride*count
   axis=max(range(3),key=lambda a:abs(changes[a]))
   if abs(changes[axis])>.01:result[n.strings[ix]]=(axis,1 if changes[axis]>0 else -1)
 return result

def sliding_tracks(n):
 result={}
 for kind,seq in n.blocks:
  if kind!='NiControllerSequence' or n.strings[struct.unpack_from('<i',seq)[0]].lower()!='open':continue
  for k in range(struct.unpack_from('<I',seq,4)[0]):
   ix=struct.unpack_from('<i',seq,21+29*k)[0];inter=struct.unpack_from('<i',seq,12+29*k)[0]
   if ix<0 or inter<0 or n.blocks[inter][0]!='NiTransformInterpolator':continue
   data=struct.unpack_from('<i',n.blocks[inter][1],32)[0]
   if data<0:continue
   b=n.blocks[data][1];count=struct.unpack_from('<I',b)[0];at=4
   if count:
    kind=struct.unpack_from('<I',b,at)[0];at+=4
    if kind!=4:continue
    for axis in range(3):
     c=struct.unpack_from('<I',b,at)[0];at+=4
     if c:
      key=struct.unpack_from('<I',b,at)[0];at+=4;at+=c*{1:8,2:16,3:20}[key]
   count=struct.unpack_from('<I',b,at)[0];at+=4
   if count<2:continue
   key=struct.unpack_from('<I',b,at)[0];at+=4;stride={1:16,2:40,3:28}[key]
   values=[struct.unpack_from('<3f',b,at+stride*j+4) for j in range(count)]
   delta=[(values[-1][j]-values[0][j])/69.99125 for j in range(3)];travel=math.sqrt(sum(v*v for v in delta))
   if .025<travel<1.5:result[n.strings[ix]]=(delta,travel)
 return result

def make(model):
 # Hanging cooking pots move as a complete suspended assembly. A fixed lid anchor
 # tears their original mechanism apart. Leave both vanilla pot variants untouched.
 if model in ('clutter\\woodfires\\spitpotclosed01.nif','clutter\\woodfires\\spitpotclosedloose01.nif'):
  raise ValueError('Hanging cooking pot: original activation and suspension retained')
 n=Nif((ROOT/'vanilla-models'/model.replace('\\','/')).read_bytes());splits=[];synthetic={}
 if model in ('clutter\\barrel01.nif','clutter\\tgbarrel01.nif','clutter\\sovngarde\\sovbarrel01.nif'):
  from split_barrel import split_barrel
  splits,synthetic=split_barrel(n)
 names=tracks(n);names.update(synthetic);slides=sliding_tracks(n);parents=parent_map(n);leaves=[]
 # These vanilla two-door models animate only one door. Give the other its own mirrored hinge.
 if model in ('architecture\\winterhold\\winterholdbookcase01.nif','clutter\\dwemer\\dwedresser01.nif'):
  doorNodes={n.strings[struct.unpack_from('<i',raw)[0]]:(i,raw) for i,(kind,raw) in enumerate(n.blocks) if kind=='NiNode' and struct.unpack_from('<i',raw)[0]>=0 and 'door' in n.strings[struct.unpack_from('<i',raw)[0]].lower()}
  mapped=next((name for name in doorNodes if name in names),None)
  if mapped:
   axis,sign=names[mapped];raw=doorNodes[mapped][1];rot=struct.unpack_from('<9f',raw,node_offsets(raw)['rotation']);world=[rot[3*j+axis]*sign for j in range(3)]
   for name,(i,raw) in doorNodes.items():
    if name in names:continue
    rot=struct.unpack_from('<9f',raw,node_offsets(raw)['rotation']);local=[-sum(rot[3*j+k]*world[j] for j in range(3)) for k in range(3)];a=max(range(3),key=lambda j:abs(local[j]))
    if abs(local[a])<.999:raise ValueError('Unmapped mirrored axis')
    names[name]=(a,1 if local[a]>0 else -1)
 controlled=set()
 for kind,seq in n.blocks:
  if kind=='NiControllerSequence' and n.strings[struct.unpack_from('<i',seq)[0]].lower()=='open':
   for k in range(struct.unpack_from('<I',seq,4)[0]):
    ix=struct.unpack_from('<i',seq,21+29*k)[0]
    if ix>=0:controlled.add(n.strings[ix])
 candidates=[]
 for i,(kind,raw) in enumerate(n.blocks):
  if kind!='NiNode':continue
  ix=struct.unpack_from('<i',raw)[0];name=n.strings[ix] if ix>=0 else ''
  if name not in names and name not in slides:continue
  dedicated_safe_leaf=model=='clutter\\containers\\safeandlock01.nif' and name=='Object01'
  if not dedicated_safe_leaf and not any(part in name.lower() for part in ('lid','top','door','drawer','head')):continue
  if any(part in name.lower() for part in ('hook','roof','bone')):continue
  if name in names:candidates.append((i,name,*names[name],'hinge',1.4))
  else:
   delta,travel=slides[name];o=node_offsets(raw);r=struct.unpack_from('<9f',raw,o['rotation']);local=[sum(r[3*j+k]*delta[j] for j in range(3)) for k in range(3)];axis=max(range(3),key=lambda j:abs(local[j]))
   if abs(local[axis])/travel<.99:continue
   candidates.append((i,name,axis,1 if local[axis]>0 else -1,'slide',travel))
 for ni,name,axis,sign,mechanism,limit in candidates:
  ancestor=parents.get(ni)
  while ancestor is not None:
   raw=n.blocks[ancestor][1];ix=struct.unpack_from('<i',raw)[0]
   if ix>=0 and n.strings[ix] in controlled:raise ValueError('Animated parent requires a dedicated mechanical profile')
   ancestor=parents.get(ancestor)
 if not candidates:raise ValueError('No independently hinged lid/door')
 template=next((b for t,b in n.blocks if t.startswith('bhkRigidBody') and len(b)>=250),None)
 if template is None:raise ValueError('No rigid body template')
 for ni,name,axis,sign,mechanism,limit in candidates:
  parent=parents.get(ni)
  if parent is None:raise ValueError('Missing parent')
  original=n.blocks[ni][1];off=node_offsets(original);saved=bytes(original);struct.pack_into('<3f',original,off['translation'],0,0,0);struct.pack_into('<9f',original,off['rotation'],1,0,0,0,1,0,0,0,1);struct.pack_into('<f',original,off['scale'],1)
  lo,hi=render_bounds(n,ni);original[:]=saved
  if any(not math.isfinite(x) for x in lo+hi) or any(b-a<.003 for a,b in zip(lo,hi)):raise ValueError('Invalid geometry bounds')
  # Keep the source's opening pivot and closed transform; do not move the container body.
  ci=struct.unpack_from('<i',original,off['collision'])[0]
  if ci>=0:
   if n.blocks[ci][0]!='bhkCollisionObject':raise ValueError('Nonstandard collision')
   oldbody=struct.unpack_from('<i',n.blocks[ci][1],6)[0]
   source=bytes(n.blocks[oldbody][1]);oldshape=struct.unpack_from('<i',source)[0]
   if oldshape>=oldbody:raise ValueError('Unordered source shape')
   if sum(t.startswith('bhkRigidBody') and struct.unpack_from('<i',b)[0]==oldshape for t,b in n.blocks)!=1:raise ValueError('Shared shape')
  else:
   source=bytes(template);oldshape=n.add('bhkBoxShape',b'');oldbody=n.add('bhkRigidBody',b'');ci=n.add('bhkCollisionObject',b'')
  anchor=n.add('NiNode',b'');leaf=n.add('NiNode',b'')
  shape=n.add('bhkConvexVerticesShape',convex_box(lo,hi,0));moving=n.add('bhkRigidBody',b'')
  ac=n.add('bhkCollisionObject',I(anchor)+struct.pack('<H',129)+I(oldbody))
  a=[0,0,0];a[axis]=sign;p=[0,0,0];p[next(i for i in range(3) if i!=axis)]=1
  q=[a[1]*p[2]-a[2]*p[1],a[2]*p[0]-a[0]*p[2],a[0]*p[1]-a[1]*p[0]]
  joint=n.add('bhkPrismaticConstraint' if mechanism=='slide' else 'bhkLimitedHingeConstraint',U(2)+I(moving)+I(oldbody)+U(1)+b''.join(v4(v) for v in (a,p,q,(0,0,0),a,p,q,(0,0,0)))+struct.pack('<3fB',-limit if mechanism=='slide' else 0.,limit,1.5,0))
  n.blocks[oldshape]=('bhkBoxShape',bytearray(U(0)+struct.pack('<f',.001)+bytes(8)+struct.pack('<4f',.001,.001,.001,0)))
  n.blocks[oldbody]=('bhkRigidBody',body(source,oldshape,0,[-.001]*3,[.001]*3))
  mass=4. if axis==0 else 6.
  n.blocks[moving]=('bhkRigidBody',body(source,shape,mass,lo,hi,joint))
  struct.pack_into('<2f',n.blocks[moving][1],212,1.2,2.)
  n.blocks[ci]=('bhkCollisionObject',bytearray(I(leaf)+struct.pack('<H',129)+I(moving)))
  n.blocks[anchor]=('NiNode',clean_node(original,n.string('SVC_Anchor_'+str(ni)),ac,[]))
  n.blocks[leaf]=('NiNode',clean_node(original,n.string('SVC_Physical_'+str(ni)),ci,children(original)))
  struct.pack_into('<i',original,off['collision'],-1);set_children(original,[])
  set_children(n.blocks[parent][1],children(n.blocks[parent][1])+[anchor,leaf])
  leaves.append({'leaf':'SVC_Physical_'+str(ni),'anchor':'SVC_Anchor_'+str(ni),'animated_node':name,'axis':a,'perpendicular':p,'mechanism':mechanism,'limit':limit,'mass':mass})
 for kind,b in n.blocks:
  if kind=='BSXFlags':struct.pack_into('<I',b,4,struct.unpack_from('<I',b,4)[0]|202)
 data=n.encode();assert Nif(data).encode()==data;return data,leaves,splits

if __name__=='__main__':
 # Opaque black BC1 texture, one complete 4x4 block. Included in the MO2 package.
 texture=ROOT/'package/textures/svrphysicalcontainersc23/barrel_inside.dds';texture.parent.mkdir(parents=True,exist_ok=True)
 header=[124,0x81007,4,4,8,0,1]+[0]*11+[32,4,int.from_bytes(b'DXT1','little'),0,0,0,0,0]+[0x1000,0,0,0,0]
 assert len(header)==31
 texture.write_bytes(b'DDS '+struct.pack('<31I',*header)+bytes(8))
 report=[]
 for model in sorted({r['model'] for r in json.loads((ROOT/'catalog.json').read_text()) if r['model']}):
  try:
   data,leaves,splits=make(model);physical='svrphysicalcontainersc23\\'+model;p=ROOT/'package/meshes'/physical.replace('\\','/');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
   report.append({'model':model,'physical_model':physical,'leaves':leaves,'split_geometry':splits})
  except Exception as e:report.append({'model':model,'error':str(e)})
 (ROOT/'build-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'generated':sum('error' not in r for r in report),'leaves':sum(len(r.get('leaves',[])) for r in report),'profiles':[r['model'] for r in report if 'error' not in r]}))

