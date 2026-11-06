from pathlib import Path
import json,hashlib,zipfile,subprocess,sys
sys.path.insert(0,'work');from pe_utils import PE
root=Path('physical-containers');package=root/'package';rows=json.loads((root/'build-report.json').read_text());profiles=[r for r in rows if 'error' not in r];validation=json.loads((root/'validation.json').read_text());catalog=json.loads((root/'catalog.json').read_text());models={r['model'] for r in profiles};matched=[r for r in catalog if r['model'] in models]
dll=package/'SKSE/Plugins/SVRPhysicalContainers.dll';pe=PE(dll);assert b'C2.4 registered' in dll.read_bytes(), 'Stale DLL';assert pe.machine==0x8664 and {'SKSEPlugin_Load','SKSEPlugin_Query','SKSEPlugin_Version'}<=pe.exports()
probe=subprocess.run([str(Path('work/loader_probe.exe').resolve()),str(dll.resolve()),'--loadonly'],capture_output=True,text=True)
assert probe.returncode==0 and 'LOAD=1 named=0 registrations=1' in probe.stdout,(probe.returncode,probe.stdout)
(root/'loader-check.txt').write_text(probe.stdout,encoding='utf-8')
summary={k:v for k,v in validation.items() if k!='results'};summary.update(dll_sha256=hashlib.sha256(dll.read_bytes()).hexdigest(),mock_load=True,named_module_lookups=0,gameplay_tested=False)
(package/'validation.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
coverage={'models':len(profiles),'physical_parts':validation['leaves'],'catalog_records_using_models':len(matched),'catalog_records':len(catalog),'supported':profiles,'unsupported_models':[r['model'] for r in rows if 'error' in r],'runtime_verified':False}
(package/'coverage.json').write_text(json.dumps(coverage,indent=2),encoding='utf-8')
readme=f'''SVR Physical Containers C2.4 — Skyrim VR 1.4.15.0 / HIGGS 1.10.10

ИЗМЕНЕНИЯ
Защёлка: в последних трёх градусах закрывания (для ящиков — 6 мм)
крышка/дверца доводится до закрытого положения и удерживается там.
Новый grab именно этой физической части снимает защёлку.
Продолжающийся grab, толчки и отскок не снимают уже закрытую защёлку.
Из широко открытого положения возврата нет. Сознательное открывание не перехватывается.
После нового grab можно сразу открывать; защёлка не срабатывает снова,
пока часть не была открыта либо отпущена.
Закрытые части остаются динамическими для настоящего выбора и подсветки HIGGS.
Программное удержание выполняется до физики и после HIGGS с проверкой
текущего мира, UID тела и принадлежности загруженной модели.

Модели и текстуры побайтно сохранены из C2.3: {len(profiles)} моделей,
{validation['leaves']} физических частей. Пути svrphysicalcontainersc23 внутри
архива правильные: новый DLL использует прежние проверенные модели.
Чёрные непрозрачные внутренности бочек, независимые shader properties,
исключение подвесных котелков и защита от повторного открытия инвентаря сохранены.
Масса, сопротивление и геометрия контейнеров в C2.4 не менялись.

УСТАНОВКА
Закрыть игру. Отключить C2.3 и другие прежние SVR Physical Containers.
Установить SVRPhysicalContainers-C2.4-MO2.zip отдельным модом и включить его.
Оставить выключенным OpenContainerVR и прежние его фиксы.
Одновременно должна загружаться только одна SVRPhysicalContainers.dll.
Другие рабочие DLL и настройки HIGGS не менять. Новое сохранение не требуется.

ПРОВЕРКИ
Тесты защёлки: закрывание удерживаемой крышки, отпускание, толчок после
закрытия, новый grab, повторное закрывание, шарниры и выдвижные ящики.
Проверены исходные модели, коллизии, материал бочек и независимость shader properties.
Модели и текстуры побайтно совпадают с ранее выданным C2.3.
DLL x64; изолированный SKSE-загрузчик принял LOAD=1, named=0, registrations=1.
Эти проверки не выполняют DataLoaded, физику в шлеме или игровые меню.
Игровая проверка новой версии ещё не выполнена.

ЛОГ
Documents/My Games/Skyrim VR/SKSE/SVRPhysicalContainers.log
Строка запуска: C2.4 registered.

ОТКАТ
Закрыть игру, отключить C2.4, включить прежний C2.3 и перезапустить.
'''
(package/'README-RU.txt').write_text(readme,encoding='utf-8-sig')
allowed={'meshes/'+r['physical_model'].replace('\\','/') for r in profiles}
out=Path('outputs/SVRPhysicalContainers-C2.4-MO2.zip')
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
 for f in package.rglob('*'):
  if not f.is_file():continue
  name=f.relative_to(package).as_posix()
  if name.startswith('meshes/') and name not in allowed:continue
  if name.startswith('textures/') and not name.startswith('textures/svrphysicalcontainersc23/'):continue
  z.write(f,name)
with zipfile.ZipFile(out) as z:
 assert z.testzip() is None and len([s for s in z.namelist() if s.endswith('.nif')])==len(profiles)
 assert len([s for s in z.namelist() if s.endswith('.dll')])==1
print(json.dumps({'zip':str(out),'bytes':out.stat().st_size,'models':len(profiles),'physical_parts':validation['leaves'],'catalog_records':len(matched),'runtime_verified':False}))
