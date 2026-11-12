# SPDX-License-Identifier: MIT
import argparse,fcntl,hashlib,json,os,re,shutil,subprocess,sys,tempfile,stat
from pathlib import Path
from . import lock,capture
HERDR=os.environ.get('HERDR_PURIFIER_HERDR','herdr')
def run(args,**kwargs):return subprocess.run(list(map(str,args)),check=True,**kwargs)
def write(path,text):
 path.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('w',dir=path.parent,delete=False) as stream:stream.write(text);temporary=Path(stream.name)
 temporary.replace(path)
def environment():
 env=dict(os.environ)
 for key in ('HERDR_PURIFIER_CAPTURE','HERDR_PURIFIER_REGISTRY_FILE','HERDR_PURIFIER_SESSION_ROOT','HERDR_PURIFIER_SOCKET_ROOT','HERDR_PURIFIER_PROJECT_ROOT'):env.pop(key,None)
 return env
def versions():return {'herdr':os.environ['HERDR_PURIFIER_HERDR_VERSION'],'resolver':hashlib.sha256(b''.join(p.read_bytes() for p in sorted(Path(__file__).parent.glob('*.py')))).hexdigest()}
def do_lock(root,native,companion,update=False,names=()):
 items=lock.config((root/'herdr-purifier.toml').read_text());previous=None
 if companion.is_file():
  try:
   candidate=json.loads(companion.read_text())
   if isinstance(candidate,dict) and candidate.get('contentHash')==lock.seal(candidate)['contentHash']:previous=candidate
   if not update and candidate.get('toolVersions')==versions() and not lock.problems(root,native,candidate):
    print('Existing native Herdr selections retained',file=sys.stderr);return
  except (ValueError,OSError,TypeError,AttributeError):pass
 pins=[];prior=native if native.exists() else root/'herdr-plugins.lock.json'
 if prior.is_file():
  try:pins=lock.native(prior.read_text())
  except (ValueError,OSError,TypeError,AttributeError):pass
 if not pins and previous and previous.get('configHash')==lock.digest(root/'herdr-purifier.toml'):
  try:pins=lock.native(previous['nativeLock'])
  except (ValueError,KeyError,TypeError,AttributeError):pass
 if names:
  known={i['name'] for i in items}|{p['plugin_id'] for p in pins}
  if not pins or any(name not in known for name in names):raise ValueError('named updates require existing locked plugins'+lock.FIX)
 with tempfile.TemporaryDirectory(prefix='herdr-purifier-lock-') as temporary:
  temp=Path(temporary);env=environment();env.pop('HERDR_SOCKET_PATH',None);env.pop('HERDR_SESSION',None)
  env.update(GIT_CONFIG_GLOBAL='/dev/null',GIT_CONFIG_NOSYSTEM='1')
  for key,relative in [('HOME','home'),('XDG_CONFIG_HOME','config'),('XDG_STATE_HOME','state'),('XDG_CACHE_HOME','cache'),('XDG_RUNTIME_DIR','runtime')]:
   path=temp/relative;path.mkdir(mode=0o700);env[key]=str(path)
  selected=[]
  for item in items:
   parts=item['source'].split('/');reference=item['ref']
   old=next((p for p in pins if p['source'].get('owner')==parts[0] and p['source'].get('repo')==parts[1] and p['source'].get('subdir')==('/'.join(parts[2:]) if len(parts)>2 else None) and p['source'].get('requested_ref')==item['ref']),None)
   updating=update and (not names or item['name'] in names or (old and old['plugin_id'] in names))
   if old and not updating:reference=old['source']['resolved_commit']
   selected.append(capture.resolve(item,reference,temp,HERDR,env))
  records=[p['plugin'] for p in selected]
  if len({p['plugin_id'] for p in records})!=len(records):raise ValueError('multiple sources declare the same native plugin id')
  text=json.dumps(records,sort_keys=True,indent=2,ensure_ascii=False)+'\n'
  data={'version':1,'config':(root/'herdr-purifier.toml').read_text(),'configHash':lock.digest(root/'herdr-purifier.toml'),'nativeLock':text,'nativeHash':hashlib.sha256(text.encode()).hexdigest(),'plugins':selected,'toolVersions':versions()}
  write(native,text);write(companion,json.dumps(lock.seal(data),sort_keys=True,indent=2,ensure_ascii=False)+'\n')
  print('Locked native Herdr plugin selections',file=sys.stderr)
def checked(root,native,companion):
 data=json.loads(companion.read_text())
 if problems:=lock.problems(root,native,data):raise ValueError('\n'.join(problems))
 return data
def realize(root,native,companion,target):
 definition=Path(__file__).resolve().parents[1]/'pkgs/build-herdr-project/realize.nix'
 args=['nix','build','--impure','--file',definition,'--argstr','project',root,'--argstr','lockFile',companion,'--argstr','pluginLock',native,'--argstr','target',target,'--no-link','--print-out-paths']
 return Path(run(args,text=True,stdout=subprocess.PIPE).stdout.strip())
def prefetch(root,native,companion):
 data=checked(root,native,companion)
 outputs={target:realize(root,native,companion,target) for target in ('environment','runtime')}
 cache=companion.parent/'.herdr-purifier/roots'/hashlib.sha256(str(companion).encode()).hexdigest()[:16]/data['contentHash']/hashlib.sha256(str(outputs['environment']).encode()).hexdigest()[:16];cache.mkdir(parents=True,exist_ok=True)
 for target,output in outputs.items():run(['nix-store','--add-root',cache/target,'--indirect','--realise',output],stdout=subprocess.DEVNULL)
 return outputs['environment']
def socket_root():
 candidates=[]
 if os.environ.get('XDG_RUNTIME_DIR'):candidates.append(Path(os.environ['XDG_RUNTIME_DIR'])/'hp')
 candidates.append(Path(tempfile.gettempdir())/('hp-'+str(os.getuid())))
 for base in candidates:
  if len(os.fsencode(base))+51>107:continue
  try:
   base.mkdir(mode=0o700,parents=True,exist_ok=True);metadata=base.lstat()
   if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid!=os.getuid() or metadata.st_mode & 0o077:continue
   return base
  except OSError:continue
 raise ValueError('no short private socket directory is available; set TMPDIR to a shorter writable directory')
def runtime(root,native,companion,arguments):
 env=environment()
 if not companion.exists():
  print('herdr-purifier: no lockfile; using ordinary impure herdr',file=sys.stderr);os.execve(HERDR,[HERDR,*arguments],env)
 data=checked(root,native,companion)
 if any(a in ('--machine','--remote') or a.startswith(('--machine=','--remote=')) for a in arguments):raise ValueError('locked Herdr plugins require a local session; start the wrapper on the target machine')
 # Native session selectors can appear anywhere before --.
 command=[];i=0
 while i<len(arguments):
  a=arguments[i]
  if a=='--session':i+=2;continue
  if a.startswith('--session='):i+=1;continue
  command.append(a);i+=1
  if a=='--':break
 if command and command[0]=='update':raise ValueError('update the Herdr SDK through your Nix configuration')
 if len(command)>1 and command[0]=='plugin' and command[1] in ('install','update','uninstall','link','unlink'):raise ValueError('edit herdr-purifier.toml and use herdr-purifier lock or update')
 output=prefetch(root,native,companion)
 identity=hashlib.sha256((str(root)+'\0'+str(companion)+'\0'+data['contentHash']+'\0'+str(output)).encode()).hexdigest()[:24]
 state=root/'.herdr-purifier';registry=state/'registries'/(identity+'.json');registry.parent.mkdir(parents=True,exist_ok=True)
 with (state/'setup.lock').open('a') as guard:
  fcntl.flock(guard,fcntl.LOCK_EX)
  if not registry.exists():write(registry,(output/'registry.json').read_text())
 env.pop('HERDR_SOCKET_PATH',None)
 env.update(HERDR_PURIFIER_SOCKET_ROOT=str(socket_root()),HERDR_PURIFIER_PROJECT_ROOT=str(root),HERDR_PURIFIER_REGISTRY_FILE=str(registry),HERDR_PURIFIER_SESSION_ROOT=str(state/'sessions'/identity))
 os.execve(HERDR,[HERDR,*arguments],env)
def publish(root,native,companion,repository,tag):
 checked(root,native,companion);release=realize(root,native,companion,'release');gh=os.environ.get('HERDR_PURIFIER_GH','gh')
 if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*',tag):raise ValueError('publish requires OWNER/REPOSITORY and a release tag')
 present=subprocess.run([gh,'release','view',tag,'--repo',repository],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
 if present:run([gh,'release','upload',tag,'--repo',repository,release/'project.tar.gz','--clobber'])
 else:run([gh,'release','create',tag,'--repo',repository,'--title',tag,'--notes','Source release built by Nix.',release/'project.tar.gz'])
def project():
 root=Path.cwd();return next((p for p in [root,*root.parents] if (p/'herdr-purifier.toml').exists()),root)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--project');parser.add_argument('--lockfile',default=os.environ.get('HERDR_PURIFIER_LOCKFILE'));parser.add_argument('--native-lock','--plugin-lock','--tool-lockfile',dest='native_lock')
 sub=parser.add_subparsers(dest='command',required=True)
 for name in ('lock','prefetch'):sub.add_parser(name)
 p=sub.add_parser('update');p.add_argument('names',nargs='*');p=sub.add_parser('native');p.add_argument('args',nargs=argparse.REMAINDER)
 p=sub.add_parser('publish');p.add_argument('--repo',required=True);p.add_argument('--tag',required=True)
 args=parser.parse_args();arguments=args.args if args.command=='native' else []
 if arguments[:1]==['--']:arguments=arguments[1:]
 root=Path(args.project).expanduser().resolve() if args.project else project()
 selection=args.native_lock or os.environ.get('HERDR_PURIFIER_NATIVE_LOCKFILE') or os.environ.get('HERDR_PURIFIER_TOOL_LOCKFILE')
 native=Path(selection).expanduser().resolve() if selection else root/'herdr-plugins.lock.json';companion=Path(args.lockfile).expanduser().resolve() if args.lockfile else root/'herdr-purifier.lock.json'
 if args.command in ('lock','update'):do_lock(root,native,companion,args.command=='update',names=getattr(args,'names',[]))
 elif args.command=='prefetch':print(prefetch(root,native,companion))
 elif args.command=='publish':publish(root,native,companion,args.repo,args.tag)
 else:runtime(root,native,companion,arguments)
