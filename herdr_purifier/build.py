# SPDX-License-Identifier: MIT
"""Run native installation and linking using only the fetched Git trees."""
import json,os,shutil,subprocess,sys,tomllib
from pathlib import Path
def run(args,**kwargs):return subprocess.run(list(map(str,args)),check=True,**kwargs)
data=json.loads(Path(sys.argv[1]).read_text());sources=Path(sys.argv[2]);out=Path(sys.argv[3]);herdr=sys.argv[4]
registry=Path(os.environ['HERDR_PURIFIER_REGISTRY_FILE']);out.mkdir(exist_ok=True)
selected={p['name']:p for p in data['plugins']};items=sorted(tomllib.loads(data['config'])['plugins'],key=lambda item:item['name'])
for item in items:
 record=selected[item['name']];parts=item['source'].split('/');canonical='https://github.com/'+parts[0]+'/'+parts[1]+'.git'
 env={**os.environ,'GIT_CONFIG_COUNT':'1','GIT_CONFIG_KEY_0':'url.'+(sources/item['name']).as_uri()+'.insteadOf','GIT_CONFIG_VALUE_0':canonical,'GIT_ALLOW_PROTOCOL':'file'}
 run([herdr,'plugin','install',item['source'],'--ref',record['entry']['git']['rev'],'--yes'],env=env)
 installed=json.loads(registry.read_text());plugin=next(p for p in installed if p['plugin_id']==record['plugin']['plugin_id'])
 root=Path(plugin['source']['managed_path']);destination=out/'plugins'/item['name']
 shutil.copytree(root,destination,ignore=shutil.ignore_patterns('.git'))
 shutil.copytree(sources/item['name']/'.git',destination/'.git')
# Register final immutable locations with the native manifest validator.
if registry.exists():registry.unlink()
for item in items:
 parts=item['source'].split('/');plugin=out/'plugins'/item['name']
 if len(parts)>2:plugin=plugin/Path(*parts[2:])
 run([herdr,'plugin','link',plugin,'--enabled' if item.get('enabled',True) else '--disabled'])
if not registry.exists():registry.write_text('[]\n')
shutil.copyfile(registry,out/'registry.json')
run([herdr,'plugin','list','--json'])
