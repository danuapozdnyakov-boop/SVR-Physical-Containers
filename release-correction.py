from pathlib import Path
import json, shutil, struct, sys, hashlib

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'nexus-release' / 'candidate'
sys.path.insert(0, str(ROOT / 'standalone-doors'))
from nif_io import Nif, node_offsets

def removable(model):
    basename = model.replace('\\', '/').rsplit('/', 1)[-1].lower()
    return any(token in basename for token in ('urn', 'canopicjar', 'barrel'))

assert not removable('furniture/noble/noblewardrobe01.nif')
assert not removable('_byoh/furniture/byohupperendtable02.nif')
assert removable('dlc02/clutter/dlc2darkelfurn01.nif')
assert removable('clutter/barrel01.nif')

audit = []
for project, name in [('standalone-doors', 'SVRPhysicalDoors'), ('physical-containers', 'SVRPhysicalContainers')]:
    src = ROOT / project
    target = OUT / name
    for folder in ('meshes', 'textures', 'SKSE'):
        if (src / 'package' / folder).exists():
            shutil.copytree(src / 'package' / folder, target / folder, dirs_exist_ok=True)
    source = target / 'source'
    source.mkdir(parents=True, exist_ok=True)
    for pattern in ('*.cpp', '*.h'):
        for path in src.glob(pattern):
            shutil.copy2(path, source / path.name)
    shutil.copy2(src / 'build-report.json', source / 'model-profiles.json')

src = ROOT / 'physical-containers'
target = OUT / 'SVRPhysicalContainers'
profiles = [r for r in json.loads((src / 'build-report.json').read_text()) if 'error' not in r]
for row in profiles:
    path = target / 'meshes' / row['physical_model'].replace('\\', '/')
    current = Nif(path.read_bytes())
    before = Nif((src / 'before-removable-c25/models' / row['physical_model'].replace('\\', '/')).read_bytes())
    names = {current.strings[struct.unpack_from('<i', b)[0]]: i for i, (kind, b) in enumerate(current.blocks)
             if kind in ('NiNode', 'BSTriShape', 'BSFadeNode') and struct.unpack_from('<i', b)[0] >= 0}
    wrong = any(k in row['model'].lower() for k in ('urn', 'canopicjar', 'barrel')) and not removable(row['model'])
    restored = []
    for leaf in row['leaves']:
        node = names[leaf['leaf']]
        raw = current.blocks[node][1]
        collision = struct.unpack_from('<i', raw, node_offsets(raw)['collision'])[0]
        body = struct.unpack_from('<i', current.blocks[collision][1], 6)[0]
        if wrong:
            current.blocks[body] = before.blocks[body]
            restored.append(body)
        constraints = struct.unpack_from('<I', current.blocks[body][1], 244)[0]
        assert constraints == (0 if removable(row['model']) else 1), (row['model'], constraints)
    if wrong:
        old = Nif(path.read_bytes())
        assert len(old.blocks) == len(current.blocks)
        assert all(old.blocks[i] == current.blocks[i] for i in range(len(old.blocks)) if i not in restored)
        path.write_bytes(current.encode())
    assert Nif(path.read_bytes()).encode() == path.read_bytes()
    audit.append({'model': row['model'], 'removable': removable(row['model']), 'restored_bodies': restored})

header = target / 'source/models.generated.h'
lines = header.read_text(encoding='utf-8').splitlines()
for row in profiles:
    if any(k in row['model'].lower() for k in ('urn', 'canopicjar', 'barrel')) and not removable(row['model']):
        key = json.dumps(row['model'], ensure_ascii=False)
        lines = [line.replace(',true}', ',false}') if key in line else line for line in lines]
header.write_text('\n'.join(lines)+'\n', encoding='utf-8')
cpp = target / 'source/physical_containers.cpp'
text = cpp.read_text(encoding='utf-8').replace('C2.5 removable lids', 'C2.6 removable lids').replace('REL::Version{0,2,5,0}', 'REL::Version{0,2,6,0}')
cpp.write_text(text, encoding='utf-8')
(OUT / 'container-correction-audit.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
print(json.dumps({'models_checked':len(audit), 'removable_models':sum(r['removable'] for r in audit), 'restored_models':sum(bool(r['restored_bodies']) for r in audit)}, indent=2))
