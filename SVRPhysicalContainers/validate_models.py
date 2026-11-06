from pathlib import Path
import sys,struct,json,math
from collections import Counter
sys.path.insert(0,'standalone-doors');from nif_io import Nif,node_offsets,children
from validate_models import render_transforms,mul,mv
def render_transforms(n):
    found={};identity=[[1,0,0],[0,1,0],[0,0,1]]
    def visit(i,r,t,s,seen):
        assert i not in seen,'Cycle in scene graph'
        kind,b=n.blocks[i]
        if kind not in ('NiNode','BSFadeNode','BSOrderedNode','BSTriShape','BSLODTriShape','NiTriShape'):return
        o=node_offsets(b);local=struct.unpack_from('<9f',b,o['rotation']);local=[local[j:j+3] for j in range(0,9,3)]
        pos=struct.unpack_from('<3f',b,o['translation']);offset=mv(r,[v*s for v in pos]);t=[a+c for a,c in zip(t,offset)]
        r=mul(r,local);s*=struct.unpack_from('<f',b,o['scale'])[0]
        if kind in ('BSTriShape','BSLODTriShape','NiTriShape'):
            assert i not in found,'Geometry drawn twice';found[i]=[v for row in r for v in row]+t+[s]
        else:
            for c in children(b):visit(c,r,t,s,seen|{i})
    roots=struct.unpack_from('<I',n.footer)[0]
    for i in struct.unpack_from('<'+'i'*roots,n.footer,4):visit(i,identity,[0,0,0],1,set())
    return found


root=Path('physical-containers');report=json.loads((root/'build-report.json').read_text());results=[]
for r in report:
 if 'error' in r:continue
 old=Nif((root/'vanilla-models'/r['model'].replace('\\','/')).read_bytes());n=Nif((root/'package/meshes'/r['physical_model'].replace('\\','/')).read_bytes())
 a=render_transforms(old);b=render_transforms(n)
 splits=r.get('split_geometry',[])
 assert set(b)==set(a)|{s[k] for s in splits for k in ('lid_shape','interior_shape')}
 def mesh_records(model,index):
  raw=model.blocks[index][1];end=node_offsets(raw)['collision']+4
  stride=(struct.unpack_from('<Q',raw,end+28)[0]&15)*4
  nt,nv=struct.unpack_from('<HH',raw,end+36);start=end+44
  verts=[bytes(raw[start+j*stride:start+(j+1)*stride]) for j in range(nv)]
  triangles=[tuple(verts[j] for j in struct.unpack_from('<3H',raw,start+nv*stride+k*6)) for k in range(nt)]
  return verts,Counter(triangles),raw[end+20:end+28]
 def world(record,transform):
  p=struct.unpack_from('<3f',record);rot=[transform[j:j+3] for j in range(0,9,3)]
  return [v+t for v,t in zip(mv(rot,[v*transform[12] for v in p]),transform[9:12])]
 for split in splits:
  source=split['source_shape'];lid=split['lid_shape']
  ov,ot,om=mesh_records(old,source);bv,bt,bm=mesh_records(n,source);lv,lt,lm=mesh_records(n,lid)
  assert bt+lt==ot and bm==om,('Triangle/attribute/material partition mismatch',r['model'])
  for oldref,newref in zip(struct.unpack('<2i',om),struct.unpack('<2i',lm)):
   if oldref<0:assert newref==oldref
   else:
    assert newref!=oldref,('Shader/alpha property shared with detached lid',r['model'])
    assert n.blocks[newref]==old.blocks[oldref],('Material clone differs',r['model'])
  for index,verts in ((source,bv),(lid,lv)):
   for vertex in verts:
    assert vertex in ov
    assert max(abs(x-y) for x,y in zip(world(vertex,a[source]),world(vertex,b[index])))<.001
  iv,it,im=mesh_records(n,split['interior_shape'])
  assert b[split['interior_shape']]==b[source]
  assert sum(it.values())==sum(bt.values())+sum(lt.values()) and len(iv)==len(bv)+len(lv)
  center=[(min(struct.unpack_from('<3f',v)[j] for v in ov)+max(struct.unpack_from('<3f',v)[j] for v in ov))/2 for j in range(3)]
  expected=[]
  for v in bv:
   record=bytearray(v);x,y,z=struct.unpack_from('<3f',v)
   struct.pack_into('<3f',record,0,center[0]+(x-center[0])*.985,center[1]+(y-center[1])*.985,z+.15);expected.append(bytes(record))
  assert iv[:len(bv)]==expected,'Interior is not an inset copy of the shell'
  cap=[]
  for v in lv:
   record=bytearray(v);x,y,z=struct.unpack_from('<3f',v)
   struct.pack_into('<3f',record,0,center[0]+(x-center[0])*.995,center[1]+(y-center[1])*.995,split['interior_cap_height']);cap.append(bytes(record))
  assert iv[len(bv):]==cap,'Opaque fill does not cover the original lid footprint'
  mapping=dict(zip(bv,iv[:len(bv)]));lidmap=dict(zip(lv,cap))
  assert it==Counter({(mapping[t[0]],mapping[t[2]],mapping[t[1]]):count for t,count in bt.items()})+Counter({tuple(lidmap[v] for v in t):count for t,count in lt.items()}),'Lining/fill triangle mismatch'
  refs=[struct.unpack('<2i',s)[0] for s in (bm,lm,im)];assert len(set(refs))==3,'Shared shader runtime state'
  mat=n.blocks[refs[2]][1];slot=40+4*struct.unpack_from('<I',mat,8)[0];tex=struct.unpack_from('<i',mat,slot)[0]
  assert struct.unpack('<2i',im)[1]==-1 and struct.unpack_from('<f',mat,slot+24)[0]==1
  flags=16+4*struct.unpack_from('<I',mat,8)[0]
  assert not(struct.unpack_from('<I',mat,flags)[0]&8) and struct.unpack_from('<I',mat,flags+4)[0]&16
  assert n.blocks[tex][0]=='BSShaderTextureSet' and b'textures\\svrphysicalcontainersc23\\barrel_inside.dds' in n.blocks[tex][1]
 assert a, ('No rendered geometry audited',r['model'],old.blocks[0][0]);error=max(abs(x-y) for i in a for x,y in zip(a[i],b[i]));assert error<.001,(r['model'],error)
 nodes={n.strings[struct.unpack_from('<i',raw)[0]]:i for i,(kind,raw) in enumerate(n.blocks) if kind=='NiNode' and struct.unpack_from('<i',raw)[0]>=0}
 for l in r['leaves']:
  node=n.blocks[nodes[l['leaf']]][1];ci=struct.unpack_from('<i',node,node_offsets(node)['collision'])[0];target,flags,moving=struct.unpack('<iHi',n.blocks[ci][1]);assert target==nodes[l['leaf']] and flags==129
  body=n.blocks[moving][1];assert n.blocks[moving][0]=='bhkRigidBody' and body[224]==3 and body[227]==4
  assert body[12]==1 and struct.unpack_from('<I',body,24)[0]==0x80000000
  assert all(struct.unpack_from('<I',body,o)[0]==4 for o in (4,36));assert struct.unpack_from('<f',body,180)[0]==l['mass']
  assert struct.unpack_from('<2f',body,212)[0]>.8 and struct.unpack_from('<2f',body,212)[1]>=2.,'Shared door cap regressed into containers'
  shape=struct.unpack_from('<i',body)[0];assert shape<moving and n.blocks[shape][0]=='bhkConvexVerticesShape'
  raw=n.blocks[shape][1];assert all(struct.unpack_from('<I',raw,o)[0]==0x80000000 for o in (16,28))
  joint=struct.unpack_from('<i',body,248)[0];h=n.blocks[joint][1];leaf,anchor=struct.unpack_from('<ii',h,4);assert leaf==moving and anchor<moving
  assert struct.unpack_from('<3f',h,16)==tuple(l['axis'])
  assert n.blocks[joint][0]==('bhkPrismaticConstraint' if l['mechanism']=='slide' else 'bhkLimitedHingeConstraint')
  assert abs(struct.unpack_from('<f',h,148)[0]-l['limit'])<1e-6
  assert abs(struct.unpack_from('<f',h,144)[0]-(-l['limit'] if l['mechanism']=='slide' else 0))<1e-6
  fixed=n.blocks[anchor][1];assert fixed[224]==5 and struct.unpack_from('<i',fixed)[0]<anchor
  assert all(struct.unpack_from('<I',fixed,o)[0]==15 for o in (4,36))
  # Verify hinge frame sits exactly on the source pivot and collider uses local render vertices.
  axis=[float(x) for x in l['axis']];assert sum(x*x for x in axis)==1
  ai=nodes[l['anchor']];ao=node_offsets(n.blocks[ai][1]);no=node_offsets(node)
  assert n.blocks[ai][1][ao['translation']:ao['collision']]==node[no['translation']:no['collision']]
 results.append({'model':r['model'],'leaves':len(r['leaves']),'closed_transform_error':error})
assert results
out={'models':len(results),'leaves':sum(r['leaves'] for r in results),'render_transforms_unchanged':True,'ordered_shapes_and_anchors':True,'runtime_verified':False,'results':results}
(root/'validation.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='results'}))

