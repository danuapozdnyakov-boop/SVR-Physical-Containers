from pathlib import Path
p=Path('physical-containers/build_models.py');s=p.read_text(encoding='utf-8');s=s.replace("n=Nif((ROOT/'vanilla-models'/model.replace('\\\\','/')).read_bytes());names=tracks(n);slides=sliding_tracks(n);parents=parent_map(n);leaves=[]", "n=Nif((ROOT/'vanilla-models'/model.replace('\\\\','/')).read_bytes());splits=[];synthetic={}\n if model.startswith('clutter\\\\barrel'):\n  from split_barrel import split_barrel\n  splits,synthetic=split_barrel(n)\n names=tracks(n);names.update(synthetic);slides=sliding_tracks(n);parents=parent_map(n);leaves=[]")
s=s.replace("('lid','top','door','drawer','head')", "('lid','top','door','drawer','head')")
s=s.replace('return data,leaves','return data,leaves,splits').replace('data,leaves=make(model)','data,leaves,splits=make(model)').replace("'leaves':leaves}","'leaves':leaves,'split_geometry':splits}")
p.write_text(s,encoding='utf-8')
