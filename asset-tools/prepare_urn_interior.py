from pathlib import Path
import sys,json,struct,math,shutil,hashlib
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'physical-containers'))
from urn_geometry import *
BASE=ROOT/'physical-containers/c27';OUT=ROOT/'physical-containers/urn-interior-fix1'
OUT.mkdir(exist_ok=True)
profiles=[r for r in json.loads((ROOT/'physical-containers/build-report.json').read_text()) if 'error' not in r]
report=[]
for row in profiles:
    if not any(k in row['model'].replace('\\','/').rsplit('/',1)[-1].lower() for k in ('urn','canopic')):continue
    rel=Path('meshes')/row['physical_model'].replace('\\','/')
    data=(BASE/rel).read_bytes();n=Nif(data);scene=geometry(n)
    body=[s for s in scene if not s['name'].startswith('SVC_') and not any(p.startswith('SVC_Physical_') for p in s['parents'])]
    lid=[s for s in scene if any(p.startswith('SVC_Physical_') for p in s['parents'])]
    oldFill=[s for s in scene if s['name'].startswith('SVC_DarkFill_')]
    assert body and lid and oldFill
    bodyPoints=[p for s in body for p in s['points']];lidPoints=[p for s in lid for p in s['points']]
    mouthZ=max(p[2] for p in bodyPoints)
    rim=[p for p in bodyPoints if p[2]>=mouthZ-3]
    lo=[min(p[j] for p in rim) for j in range(2)];hi=[max(p[j] for p in rim) for j in range(2)]
    cx,cy=[(a+b)*.5 for a,b in zip(lo,hi)]
    # Rim dimensions come from the vessel, not protruding ornaments on its lid.
    lidWidths=[max(p[j] for p in lidPoints)-min(p[j] for p in lidPoints) for j in range(2)]
    rx,ry=[.94*min((b-a)*.5,width*.5) for a,b,width in zip(lo,hi,lidWidths)]
    assert rx>1 and ry>1 and rx<40 and ry<40
    top=mouthZ-3.5;depth=max(7.,min(15.,min(rx,ry)*.65));bottom=top-depth
    points=[];segments=48
    # A recessed sleeve and bottom, open at the neck. No fake lid silhouette at the opening.
    for z,factor in ((top,1.),(bottom,1.02)):
        points.extend((cx+math.cos(i*2*math.pi/segments)*rx*factor,cy+math.sin(i*2*math.pi/segments)*ry*factor,z) for i in range(segments))
    points.append((cx,cy,bottom));faces=[]
    for i in range(segments):
        j=(i+1)%segments
        faces.extend(((i,j,segments+j),(i,segments+j,segments+i),(2*segments,segments+i,segments+j)))
    donor=oldFill[0];raw=bytearray(n.blocks[donor['index']][1]);o=node_offsets(raw);e=o['collision']+4
    assert all(abs(a-b)<1e-6 for a,b in zip(struct.unpack_from('<9f',n.blocks[0][1],node_offsets(n.blocks[0][1])['rotation']),IDENTITY))
    assert all(abs(v)<1e-6 for v in struct.unpack_from('<3f',n.blocks[0][1],node_offsets(n.blocks[0][1])['translation']))
    assert struct.unpack_from('<f',n.blocks[0][1],node_offsets(n.blocks[0][1])['scale'])[0]==1
    desc,nt,nv,size=struct.unpack_from('<QHHI',raw,e+28);stride=(desc&15)*4
    record=bytes(raw[e+44:e+44+stride]);tail=raw[e+44+size:]
    vertices=[]
    for p in points:
        v=bytearray(record);struct.pack_into('<3f',v,0,*p);vertices.append(v)
    newSize=len(points)*stride+len(faces)*6
    header=raw[:e+44]
    struct.pack_into('<i',header,0,n.string('SVC_RecessedInterior'))
    struct.pack_into('<3f',header,o['translation'],0,0,0);struct.pack_into('<9f',header,o['rotation'],*IDENTITY);struct.pack_into('<f',header,o['scale'],1.)
    struct.pack_into('<HHI',header,e+36,len(faces),len(points),newSize)
    centre=(cx,cy,(top+bottom)*.5);radius=max(math.dist(p,centre) for p in points)
    struct.pack_into('<4f',header,e,*centre,radius)
    shape=n.add('BSTriShape',header+b''.join(vertices)+b''.join(struct.pack('<3H',*tri) for tri in faces)+tail)
    oldRoot=children(n.blocks[0][1]);removed={s['index'] for s in oldFill}
    assert removed<=set(oldRoot)
    set_children(n.blocks[0][1],[i for i in oldRoot if i not in removed]+[shape])
    encoded=n.encode();assert Nif(encoded).encode()==encoded
    before=Nif(data)
    for i in range(1,len(before.blocks)):assert n.blocks[i]==before.blocks[i],(row['model'],i)
    afterScene=geometry(n)
    assert not any(s['name'].startswith('SVC_DarkFill_') for s in afterScene)
    cap=next(s for s in afterScene if s['name']=='SVC_RecessedInterior')
    assert len(cap['points'])==97 and len(cap['triangles'])==144
    assert max(p[2] for p in cap['points'])<mouthZ-3.4
    # Every original visible shape remains exactly in place, including the removable lid.
    for old in scene:
        if old['index'] in removed:continue
        new=next(s for s in afterScene if s['index']==old['index'])
        assert old['points']==new['points'] and old['triangles']==new['triangles']
    dest=OUT/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(encoded)
    report.append({'path':rel.as_posix(),'model':row['model'],'removed_flat_shapes':sorted(removed),'new_shape':shape,'rimZ':mouthZ,'topZ':top,'bottomZ':bottom,'ellipse_radii':[rx,ry],'original_nonroot_blocks_unchanged':True,'sha256':hashlib.sha256(encoded).hexdigest()})
(OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'changed_models':len(report),'all_original_mesh_uv_material_physics_blocks_unchanged':True,'new_mesh_vertices_each':97,'new_mesh_triangles_each':144,'installed':False},indent=2))
