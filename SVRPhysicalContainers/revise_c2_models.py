from pathlib import Path
p=Path('physical-containers/build_models.py');s=p.read_text(encoding='utf-8');i=s.index('def make(model):')
s=s[:i]+'''def sliding_tracks(n):
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

'''+s[i:]
s=s.replace('names=tracks(n);parents=parent_map(n);leaves=[]','names=tracks(n);slides=sliding_tracks(n);parents=parent_map(n);leaves=[]')
s=s.replace("if name not in names or not any(part in name.lower() for part in ('lid','top','door')):continue", "if name not in names and name not in slides:continue\n  if not any(part in name.lower() for part in ('lid','top','door','drawer','head')):continue")
s=s.replace("if names[name][0] not in (0,2):continue\n  candidates.append((i,name,*names[name]))", "if name in names:candidates.append((i,name,*names[name],'hinge',1.4))\n  else:\n   delta,travel=slides[name];o=node_offsets(raw);r=struct.unpack_from('<9f',raw,o['rotation']);local=[sum(r[3*j+k]*delta[j] for j in range(3)) for k in range(3)];axis=max(range(3),key=lambda j:abs(local[j]))\n   if abs(local[axis])/travel<.99:continue\n   candidates.append((i,name,axis,1 if local[axis]>0 else -1,'slide',travel))")
s=s.replace('for ni,name,axis,sign in candidates:', 'for ni,name,axis,sign,mechanism,limit in candidates:')
s=s.replace("p[1 if axis==0 else 0]=1", "p[next(i for i in range(3) if i!=axis)]=1")
s=s.replace("joint=n.add('bhkLimitedHingeConstraint',U(2)+I(moving)+I(oldbody)+U(1)+b''.join(v4(v) for v in (a,p,q,(0,0,0),a,p,q,(0,0,0)))+struct.pack('<3fB',0.,1.8,2.,0))", "joint=n.add('bhkPrismaticConstraint' if mechanism=='slide' else 'bhkLimitedHingeConstraint',U(2)+I(moving)+I(oldbody)+U(1)+b''.join(v4(v) for v in (a,p,q,(0,0,0),a,p,q,(0,0,0)))+struct.pack('<3fB',-limit if mechanism=='slide' else 0.,limit,6.,0))")
s=s.replace("'perpendicular':p,'mass':mass", "'perpendicular':p,'mechanism':mechanism,'limit':limit,'mass':mass").replace('svrphysicalcontainersc1','svrphysicalcontainersc2')
p.write_text(s,encoding='utf-8')
p=Path('physical-containers/build_plugin.py');s=p.read_text(encoding='utf-8').replace('float perpendicular[3];','float perpendicular[3];bool sliding;float limit;')
s=s.replace("p['perpendicular'])+'}}'", "p['perpendicular'])+'},'+('true' if p['mechanism']=='slide' else 'false')+','+str(p['limit'])+'f}'")
p.write_text(s,encoding='utf-8')
p=Path('physical-containers/validate_models.py');s=p.read_text(encoding='utf-8').replace("assert abs(struct.unpack_from('<f',h,148)[0]-1.8)<1e-6 and struct.unpack_from('<f',h,144)[0]==0", "assert n.blocks[joint][0]==('bhkPrismaticConstraint' if l['mechanism']=='slide' else 'bhkLimitedHingeConstraint')\n  assert abs(struct.unpack_from('<f',h,148)[0]-l['limit'])<1e-6\n  assert abs(struct.unpack_from('<f',h,144)[0]-(-l['limit'] if l['mechanism']=='slide' else 0))<1e-6")
p.write_text(s,encoding='utf-8')
