"""Separate the actual top-face triangles of a vanilla barrel; retain its UVs/materials."""
import struct,math
from nif_io import node_offsets,children,set_children,clean_node

def split_barrel(n):
 for index,(kind,raw) in list(enumerate(n.blocks)):
  if kind!='BSTriShape':continue
  o=node_offsets(raw);end=o['collision']+4;desc=struct.unpack_from('<Q',raw,end+28)[0];stride=(desc&15)*4
  if stride<12:continue
  nt,nv=struct.unpack_from('<HH',raw,end+36);start=end+44;size=struct.unpack_from('<I',raw,end+40)[0]
  if struct.unpack_from('<I',raw,start+size)[0]!=0:continue
  vertices=[bytes(raw[start+k*stride:start+(k+1)*stride]) for k in range(nv)]
  pos=[struct.unpack_from('<3f',v) for v in vertices];tri=[struct.unpack_from('<3H',raw,start+nv*stride+6*k) for k in range(nt)]
  top=max(v[2] for v in pos);bottom=min(v[2] for v in pos);band=(top-bottom)*.065;lid=[];body=[]
  for t in tri:
   a,b,c=(pos[j] for j in t);u=[b[j]-a[j] for j in range(3)];v=[c[j]-a[j] for j in range(3)];normal=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
   horizontal=abs(normal[2])>.65*math.sqrt(sum(x*x for x in normal))
   (lid if min(a[2],b[2],c[2])>top-band and horizontal else body).append(t)
  if len(lid)<4 or len(body)<4:continue
  rot=struct.unpack_from('<9f',raw,o['rotation']);scale=struct.unpack_from('<f',raw,o['scale'])[0]
  if any(abs(v-e)>1e-5 for v,e in zip(rot,(1,0,0,0,1,0,0,0,1))) or abs(scale-1)>1e-5:continue
  def make(triangles):
   used=sorted({i for t in triangles for i in t});mapping={j:k for k,j in enumerate(used)}
   data=b''.join(vertices[j] for j in used)+b''.join(struct.pack('<3H',*(mapping[j] for j in t)) for t in triangles)
   result=bytearray(raw[:start]);struct.pack_into('<HHI',result,end+36,len(triangles),len(used),len(data))
   center=[(min(pos[j][k] for j in used)+max(pos[j][k] for j in used))/2 for k in range(3)];radius=max(math.dist(pos[j],center) for j in used)
   struct.pack_into('<4f',result,end,*center,radius);return result+data+struct.pack('<I',0)
  used={j for t in lid for j in t};pivot=[(min(pos[j][0] for j in used)+max(pos[j][0] for j in used))/2,min(pos[j][1] for j in used),sum(pos[j][2] for j in used)/len(used)]
  original_translation=struct.unpack_from('<3f',raw,o['translation']);lid_raw=make(lid);struct.pack_into('<3f',lid_raw,o['translation'],*[-v for v in pivot])
  # Shader properties contain per-geometry runtime state: never share one with the new lid.
  for slot in (end+20,end+24):
   reference=struct.unpack_from('<i',lid_raw,slot)[0]
   if reference>=0:
    property_kind,property_raw=n.blocks[reference]
    assert property_kind in ('BSLightingShaderProperty','NiAlphaProperty'),property_kind
    new_reference=n.add(property_kind,bytearray(property_raw))
    struct.pack_into('<i',lid_raw,slot,new_reference)
  shape=n.add('BSTriShape',lid_raw);node=n.add('NiNode',clean_node(n.blocks[0][1],n.string('SVC_BarrelLid'),-1,[shape]))
  node_raw=n.blocks[node][1];no=node_offsets(node_raw);struct.pack_into('<3f',node_raw,no['translation'],*[pivot[j]+original_translation[j] for j in range(3)]);struct.pack_into('<9f',node_raw,no['rotation'],1,0,0,0,1,0,0,0,1);struct.pack_into('<f',node_raw,no['scale'],1)
  n.blocks[index]=('BSTriShape',make(body))
  # The vanilla shell has outward-facing polygons only. Add an inward-facing lining,
  # with its own shader runtime state, instead of sharing the body's shader or hiding it.
  inside=make([(a,c,b) for a,b,c in body]);struct.pack_into('<i',inside,0,n.string('SVC_BarrelInterior'))
  count=struct.unpack_from('<H',inside,end+38)[0]
  center=[(min(v[j] for v in pos)+max(v[j] for v in pos))/2 for j in range(3)]
  inset_positions=[]
  for j in range(count):
   at=start+j*stride;v=struct.unpack_from('<3f',inside,at)
   p=(center[0]+(v[0]-center[0])*.985,center[1]+(v[1]-center[1])*.985,v[2]+.15)
   struct.pack_into('<3f',inside,at,*p);inset_positions.append(p)
  # Seal the void below the opening with the complete original lid's footprint.
  # The lid itself remains separate and keeps its original geometry/materials.
  shell_vertices=count;shell_triangles=struct.unpack_from('<H',inside,end+36)[0]
  used=sorted({j for t in lid for j in t});mapping={j:shell_vertices+k for k,j in enumerate(used)}
  cap_height=top-band*.8;cap=[]
  for j in used:
   v=bytearray(vertices[j]);x,y,z=pos[j];p=(center[0]+(x-center[0])*.995,center[1]+(y-center[1])*.995,cap_height)
   struct.pack_into('<3f',v,0,*p);cap.append(bytes(v));inset_positions.append(p)
  original_vertices=bytes(inside[start:start+shell_vertices*stride])
  original_triangles=bytes(inside[start+shell_vertices*stride:start+shell_vertices*stride+shell_triangles*6])
  cap_triangles=b''.join(struct.pack('<3H',*(mapping[j] for j in t)) for t in lid)
  data=original_vertices+b''.join(cap)+original_triangles+cap_triangles
  inside=inside[:start]+data+struct.pack('<I',0)
  struct.pack_into('<HHI',inside,end+36,shell_triangles+len(lid),shell_vertices+len(cap),len(data))
  bounds=[(min(v[j] for v in inset_positions)+max(v[j] for v in inset_positions))/2 for j in range(3)]
  struct.pack_into('<4f',inside,end,*bounds,max(math.dist(v,bounds) for v in inset_positions))
  original_shader=struct.unpack_from('<i',inside,end+20)[0];kind,material=n.blocks[original_shader]
  assert kind=='BSLightingShaderProperty'
  material=bytearray(material);texture_slot=40+4*struct.unpack_from('<I',material,8)[0]
  old_texture=struct.unpack_from('<i',material,texture_slot)[0]
  assert n.blocks[old_texture][0]=='BSShaderTextureSet'
  texture=n.blocks[old_texture][1];count=struct.unpack_from('<I',texture)[0];p=4;paths=[]
  for j in range(count):
   size=struct.unpack_from('<I',texture,p)[0];p+=4;paths.append(bytes(texture[p:p+size]));p+=size
  assert p==len(texture)
  paths[0]=b'textures\\svrphysicalcontainersc23\\barrel_inside.dds'
  tex=n.add('BSShaderTextureSet',bytearray(struct.pack('<I',count)+b''.join(struct.pack('<I',len(s))+s for s in paths)))
  struct.pack_into('<i',material,texture_slot,tex)
  struct.pack_into('<3f',material,texture_slot+4,0,0,0) # no emissive colour
  struct.pack_into('<4f',material,texture_slot+36,0,0,0,0) # no specular colour/strength
  struct.pack_into('<f',material,texture_slot+24,1.) # fully opaque, no inherited fade
  flags_offset=16+4*struct.unpack_from('<I',material,8)[0]
  struct.pack_into('<I',material,flags_offset,struct.unpack_from('<I',material,flags_offset)[0]&~8) # no vertex alpha
  struct.pack_into('<I',material,flags_offset+4,struct.unpack_from('<I',material,flags_offset+4)[0]|16) # lining/cap visible from both sides
  struct.pack_into('<i',inside,end+20,n.add(kind,material))
  struct.pack_into('<i',inside,end+24,-1) # no alpha test/blending on the opaque fill
  interior=n.add('BSTriShape',inside)
  set_children(n.blocks[0][1],children(n.blocks[0][1])+[node,interior])
  return [{'source_shape':index,'lid_shape':shape,'interior_shape':interior,'interior_cap_height':cap_height,'triangles':len(lid),'pivot':pivot}],{'SVC_BarrelLid':(0,1)}
 raise ValueError('No separable top-face lid in this barrel')
