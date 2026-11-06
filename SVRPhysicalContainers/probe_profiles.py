import sys,runpy
sys.path.insert(0,'standalone-doors')
globals().update(runpy.run_path('physical-containers/build_models.py'))
sys.path.insert(0,'physical-containers')
for model in ('clutter\\containers\\safeandlock01.nif','clutter\\dwemer\\dwechest01.nif','architecture\\whiterun\\wrclutter\\wrburialurn01.nif','clutter\\tgbarrel01.nif','clutter\\sovngarde\\sovbarrel01.nif'):
 n=Nif((ROOT/'vanilla-models'/model.replace('\\','/')).read_bytes())
 print(model,tracks(n),sliding_tracks(n))
 if 'barrel' in model:
  from split_barrel import split_barrel
  try:print(split_barrel(n))
  except Exception as e:print(str(e))
