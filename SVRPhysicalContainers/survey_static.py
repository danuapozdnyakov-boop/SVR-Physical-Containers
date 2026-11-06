import sys,struct,json
from pathlib import Path
sys.path.insert(0,'standalone-doors');from nif_io import Nif,node_offsets,children
for f in ('clutter/barrel01.nif','architecture/whiterun/wrclutter/wrcoffin01.nif','architecture/riften/clutter/rtcoffin01.nif','clutter/sack02.nif','clutter/sack03.nif'):
 p=Path('physical-containers/vanilla-models')/f
 if not p.exists():continue
 n=Nif(p.read_bytes());print(f)
 for i,(t,b) in enumerate(n.blocks):
  if t in ('NiNode','BSFadeNode','BSTriShape'):
   ix=struct.unpack_from('<i',b)[0];print(i,t,n.strings[ix] if ix>=0 else '', children(b) if t in ('NiNode','BSFadeNode') else '')
