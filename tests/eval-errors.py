#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Pure lock rejection before fetching or building dependencies."""
import hashlib,json,shutil,subprocess,tempfile
from pathlib import Path
repo=Path(__file__).resolve().parents[1]
def seal(data):
 data.pop('contentHash',None)
 data['contentHash']=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
 return data
with tempfile.TemporaryDirectory(prefix='herdr-eval-') as temporary:
 root=Path(temporary)/'source';shutil.copytree(repo/'examples/minimal',root,ignore=shutil.ignore_patterns('.herdr-purifier'))
 path=root/'herdr-purifier.lock.json';original=path.read_text();native=root/'herdr-plugins.lock.json';native_original=native.read_text()
 expression='let f=builtins.getFlake '+json.dumps(str(repo))+'; r=f.lib.herdr-purifier.readLock {src=/. + '+json.dumps(str(root))+';}; in {inherit (r) problems outputs entries;}'
 def evaluate():
  result=subprocess.run(['nix','eval','--impure','--json','--expr',expression],text=True,capture_output=True)
  result.check_returncode();return json.loads(result.stdout)
 assert evaluate()['problems']==[]
 for mutation in ('seal','hash','revision','cache','native','missing','manifest'):
  path.write_text(original);native.write_text(native_original);data=json.loads(original)
  if mutation=='seal':data['contentHash']='bad'
  elif mutation=='hash':data['plugins'][0]['entry']['hash']='not-a-hash';seal(data)
  elif mutation=='revision':data['plugins'][0]['entry']['git']['rev']='bad';seal(data)
  elif mutation=='cache':data['plugins'][0]['entry']['path']='../outside';seal(data)
  if mutation in ('seal','hash','revision','cache'):path.write_text(json.dumps(data))
  elif mutation=='native':native.write_text(native_original+'# changed\n')
  elif mutation=='missing':native.unlink()
  else:(root/'herdr-purifier.toml').write_text('plugins = []\n')
  result=evaluate();assert result['problems'] and result['outputs']=={} and result['entries']==[],(mutation,result)
 print('Pure Herdr lock rejection passed')
