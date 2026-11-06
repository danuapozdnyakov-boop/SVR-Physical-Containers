from pathlib import Path
import sys,json,struct,math
sys.path.insert(0,'standalone-doors');from nif_io import Nif,node_offsets
r=Path('physical-containers');records=json.loads((r/'removable-assets.json').read_text());report=json.loads((r/'build-report.json').read_text());by={i['model']:i for i in report if 'error' not in i}
for item in records:
 p=r/'package/meshes'/by[item['model']]['physical_model'].replace('\\','/');n=Nif(p.read_bytes());old=Nif((r/'before-removable-c25/models'/p.relative_to(r/'package/meshes')).read_bytes());assert n.strings[:len(old.strings)]==old.strings
 changed=[]
 for i,((kind,a),(kind2,b)) in enumerate(zip(old.blocks,n.blocks)):
  assert kind==kind2
  if a!=b:
   if i==0:
    at=node_offsets(a)['children'];assert a[:at]==b[:at];continue
   assert item['removable'] and kind=='bhkRigidBody' and struct.unpack_from('<I',b,244)[0]==0
   assert a[:180]==b[:180] and a[184:244]==b[184:244];changed.append(i)
 assert bool(changed)==item['removable']
 fills=0
 for kind,b in n.blocks[len(old.blocks):]:
  if kind!='BSTriShape':continue
  fills+=1;o=node_offsets(b);e=o['collision']+4;assert struct.unpack_from('<i',b,o['collision'])[0]==-1
  desc,nt,nv,size=struct.unpack_from('<QHHI',b,e+28);st=(desc&15)*4;assert size==nv*st+nt*6
  for j in range(nv):assert all(math.isfinite(x) for x in struct.unpack_from('<3f',b,e+44+j*st))
  for j in range(nt):assert max(struct.unpack_from('<3H',b,e+44+nv*st+j*6))<nv
  shader=n.blocks[struct.unpack_from('<i',b,e+20)[0]][1];assert struct.unpack_from('<I',shader,20)[0]&16
 assert fills>0,item['model']
print('PASS:',len(records),'models; only removable-body constraints/mass changed; other original blocks preserved; every fill non-collidable, valid indices/finite bounds, double-sided')

