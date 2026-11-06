import json
from pathlib import Path
rows=json.loads(Path('physical-containers/survey.json').read_text())
for r in rows:
 if any(k in r['model'] for k in ('dwechest','apourn','tgbarrel','sovbarrel','sburialurn','wrburialurn','safeandlock','satchel','miscsack')):
  print(json.dumps(r,ensure_ascii=False))
