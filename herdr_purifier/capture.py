# SPDX-License-Identifier: MIT
import base64,json,os,subprocess
from pathlib import Path
from . import lock
def run(args,**kwargs):return subprocess.run(list(map(str,args)),check=True,**kwargs)
def git(root,*args,binary=False):return subprocess.check_output(['git','-C',str(root),*args],text=not binary)
def resolve(item,reference,temp,herdr,environment):
 registry=temp/'registry.json';env={**environment,'HERDR_PURIFIER_CAPTURE':'1','HERDR_PURIFIER_REGISTRY_FILE':str(registry),'HERDR_PURIFIER_SESSION_ROOT':str(temp/'sessions')}
 parts=item['source'].split('/');canonical='https://github.com/'+parts[0]+'/'+parts[1]+'.git'
 env.update(GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='url.'+item['url']+'.insteadOf',GIT_CONFIG_VALUE_0=canonical)
 command=[herdr,'plugin','install',item['source'],'--yes']
 if reference:command+=['--ref',reference]
 run(command,env=env,stdout=subprocess.DEVNULL)
 entries=json.loads(registry.read_text())
 matches=[p for p in entries if p['source'].get('owner')==parts[0] and p['source'].get('repo')==parts[1] and p['source'].get('subdir')==('/'.join(parts[2:]) if len(parts)>2 else None)]
 if len(matches)!=1:raise ValueError('native plugin source did not register uniquely')
 plugin=matches[0];repository=Path(plugin['source']['managed_path']);revision=plugin['source']['resolved_commit']
 clean=temp/'trees'/item['name'];clean.mkdir(parents=True)
 run(['git','--git-dir',repository/'.git','--work-tree',clean,'checkout',revision,'--','.'],cwd=repository,stdout=subprocess.DEVNULL)
 links=[line for line in git(repository,'ls-tree','-rz',revision,binary=True).split(b'\0') if line.startswith(b'160000 ')]
 if links:raise ValueError('Git submodules are not supported yet')
 sourcehash=subprocess.check_output(['nix','hash','path',str(clean)],text=True).strip();raw=git(repository,'cat-file','commit',revision,binary=True)
 return {'name':item['name'],'plugin':lock.normalize(plugin,item),'entry':{'path':item['name'],'hash':sourcehash,'git':{'url':item['url'],'rev':revision,'leaveDotGit':True,'submodules':False,'commitObject':{'object':base64.b64encode(raw).decode(),'gitlinks':[]}}}}
