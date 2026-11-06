from pathlib import Path
import sys,struct,math
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'standalone-doors'))
from nif_io import Nif,node_offsets,children,set_children
IDENTITY=(1.,0.,0.,0.,1.,0.,0.,0.,1.)
def mul(a,b):return tuple(sum(a[3*j+k]*b[3*k+i] for k in range(3)) for j in range(3) for i in range(3))
def apply(a,v):return tuple(sum(a[3*j+k]*v[k] for k in range(3)) for j in range(3))
def geometry(n):
    result=[]
    def walk(index,rotation=IDENTITY,translation=(0,0,0),scale=1.,parents=()):
        kind,raw=n.blocks[index]
        if kind not in ('NiNode','BSFadeNode','BSTriShape','BSOrderedNode'):return
        o=node_offsets(raw);local=struct.unpack_from('<9f',raw,o['rotation']);t=struct.unpack_from('<3f',raw,o['translation'])
        at=apply(rotation,tuple(v*scale for v in t));tt=tuple(a+b for a,b in zip(at,translation));rr=mul(rotation,local);ss=scale*struct.unpack_from('<f',raw,o['scale'])[0]
        ni=struct.unpack_from('<i',raw)[0];name=n.strings[ni] if ni>=0 else ''
        if kind=='BSTriShape':
            e=o['collision']+4;desc,nt,nv,size=struct.unpack_from('<QHHI',raw,e+28);stride=(desc&15)*4
            points=[]
            for j in range(nv):
                v=struct.unpack_from('<3f',raw,e+44+j*stride)
                points.append(tuple(a+b for a,b in zip(apply(rr,tuple(q*ss for q in v)),tt)))
            triangles=[struct.unpack_from('<3H',raw,e+44+nv*stride+j*6) for j in range(nt)]
            result.append({'index':index,'name':name,'points':points,'triangles':triangles,'parents':parents,'stride':stride,'rotation':rr,'translation':tt,'scale':ss})
        else:
            for child in children(raw):walk(child,rr,tt,ss,parents+(name,))
    walk(0);return result

def boundary_loops(shapes):
    from collections import Counter,defaultdict
    edges=Counter()
    for shape in shapes:
        points=[tuple(round(v,4) for v in p) for p in shape['points']]
        for tri in shape['triangles']:
            a,b,c=(points[i] for i in tri)
            for x,y in ((a,b),(b,c),(c,a)):
                if x!=y:edges[tuple(sorted((x,y)))]+=1
    graph=defaultdict(set)
    for (a,b),count in edges.items():
        if count==1:graph[a].add(b);graph[b].add(a)
    loops=[];seen=set()
    for start in graph:
        if start in seen:continue
        todo=[start];component=[]
        while todo:
            p=todo.pop()
            if p in seen:continue
            seen.add(p);component.append(p);todo.extend(graph[p]-seen)
        if len(component)>=8 and all(len(graph[p])==2 for p in component):loops.append(component)
    return loops

if __name__=='__main__':
    root=Path(__file__).resolve().parent.parent
    for p in (root/'physical-containers/c27/meshes').rglob('*.nif'):
        if 'urn' not in p.name.lower() and 'canopic' not in p.name.lower():continue
        n=Nif(p.read_bytes());g=geometry(n)
        points=[v for s in g if any(name.startswith('SVC_Physical_') for name in s['parents']) for v in s['points']]
        z=min(v[2] for v in points);slice=[v for v in points if v[2]<=z+2]
        print(p.name,'lid minZ',round(z,2),'bottom slice bounds',[[round(min(v[j] for v in slice),2),round(max(v[j] for v in slice),2)] for j in range(3)])
        for s in g:
            if s['name'].startswith('SVC_DarkFill_'):
                print(' old filler',s['name'],'bounds',[[round(min(v[j] for v in s['points']),2),round(max(v[j] for v in s['points']),2)] for j in range(3)])
