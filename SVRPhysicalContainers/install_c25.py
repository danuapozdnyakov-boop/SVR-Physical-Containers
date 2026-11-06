from pathlib import Path
import shutil,json,zipfile,hashlib,subprocess
r=Path('physical-containers');dest=Path(r'F:\MO2\mods\SVRPhysicalContainers');backup=r/'installed-backup-c25';backup.mkdir(exist_ok=True)
if 'skyrimvr.exe' in subprocess.run(['tasklist','/FI','IMAGENAME eq SkyrimVR.exe'],capture_output=True,text=True).stdout.lower():raise SystemExit('SkyrimVR running: no files replaced')
files=[(r/'package/SKSE/Plugins/SVRPhysicalContainers.dll',Path('SKSE/Plugins/SVRPhysicalContainers.dll'))]
for entry in json.loads((r/'build-report.json').read_text()):
 if 'error' not in entry:
  rel=Path('meshes')/entry['physical_model'].replace('\\','/');files.append((r/'package'/rel,rel))
rel=Path('textures/svrphysicalcontainersc23/barrel_inside.dds');files.append((r/'package'/rel,rel))
manifest=[]
with zipfile.ZipFile(backup/'files.zip','a',zipfile.ZIP_DEFLATED) as z:
 existing=set(z.namelist())
 for src,rel in files:
  target=dest/rel
  if target.exists() and str(rel) not in existing:z.writestr(str(rel),target.read_bytes())
  target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target)
  digest=hashlib.sha256(src.read_bytes()).hexdigest();assert hashlib.sha256(target.read_bytes()).hexdigest()==digest
  manifest.append({'file':str(rel),'sha256':digest})
(r/'c25-install.json').write_text(json.dumps({'version':'0.2.5','files':manifest,'gameplay_tested':False,'removable_models':16,'interior_models':41},indent=2))
print('Installed and hashes verified:',len(manifest),'files; backup',backup)
