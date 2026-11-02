#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Native Git plugins, offline build hooks and isolated native server sessions."""
import json,os,socket,subprocess,sys,tarfile,tempfile,time
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
def run(args,**kwargs):
 result=subprocess.run(list(map(str,args)),text=True,**kwargs)
 if result.returncode:
  if result.stdout:print(result.stdout,file=sys.stderr)
  if result.stderr:print(result.stderr,file=sys.stderr)
  result.check_returncode()
 return result
case=sys.argv[1]
with tempfile.TemporaryDirectory(prefix='herdr-conformance-') as temporary:
 temp=Path(temporary);cli=temp/'cli';sdk=temp/'sdk'
 run(['nix','build',str(REPO)+'#cli','--out-link',cli]);run(['nix','build',str(REPO)+'#native','--out-link',sdk])
 helper=cli/'bin/herdr-purifier';herdr=cli/'bin/herdr';ordinary=sdk/'bin/herdr';root=temp/'project';root.mkdir();repos=temp/'repos';repos.mkdir()
 env={k:v for k,v in os.environ.items() if not k.startswith(('HERDR_','GIT_CONFIG_'))}
 for key,relative in [('HOME','home'),('XDG_CONFIG_HOME','config'),('XDG_STATE_HOME','state'),('XDG_CACHE_HOME','cache'),('XDG_RUNTIME_DIR','runtime')]:
  path=temp/relative;path.mkdir(mode=0o700);env[key]=str(path)
 env.update(SHELL=str(cli/'bin/bash'),PATH=str(cli/'bin')+os.pathsep+env['PATH'])
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 daemon=subprocess.Popen(['git','daemon','--reuseaddr','--export-all','--listen=127.0.0.1','--port='+str(port),'--base-path='+str(repos),str(repos)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 servers=[];logs=[]
 def git(directory,*args):return run(['git','-C',directory,*args],capture_output=True).stdout.strip()
 def release(name,version,value):
  repo=repos/name
  if not repo.exists():repo.mkdir();git(repo,'init','-b','main')
  (repo/'herdr-plugin.toml').write_text('id="fixture.'+name+'"\nname="'+name+'"\nversion="'+version+'"\nmin_herdr_version="0.7.0"\nplatforms=["linux"]\n[[build]]\ncommand=["sh","build.sh"]\n[[actions]]\nid="hello"\ntitle="Hello"\ncontexts=["global"]\ncommand=["sh","hello.sh"]\n')
  (repo/'build.sh').write_text('printf \'printf "'+name+'-'+value+'\\\\n"\\n\' > hello.sh\n')
  git(repo,'add','.');git(repo,'-c','user.name=purifier-test','-c','user.email=fixture@example.invalid','commit','-m',version);git(repo,'tag','v'+version)
 def status(binary,selected_env):return json.loads(run([binary,'status','server','--json'],cwd=root,env=selected_env,capture_output=True).stdout)
 def start(binary,selected_env):
  log=tempfile.TemporaryFile(mode='w+');logs.append(log)
  process=subprocess.Popen([str(binary),'server'],cwd=root,env=selected_env,stdout=log,stderr=log);servers.append(process)
  for _ in range(120):
   if process.poll() is not None:
    log.seek(0);raise AssertionError('native server exited: '+log.read())
   if status(binary,selected_env)['running']:return process
   time.sleep(.1)
  log.seek(0);raise AssertionError('native server did not start: '+log.read())
 try:
  for name in ('first','second'):release(name,'1.0.0','one')
  for _ in range(100):
   try:
    with socket.create_connection(('127.0.0.1',port),timeout=.1):break
   except OSError:time.sleep(.05)
  (root/'herdr-purifier.toml').write_text(''.join('[[plugins]]\nname="'+name+'"\nsource="fixture/'+name+'"\nurl="git://127.0.0.1:'+str(port)+'/'+name+'"\n' for name in ('first','second')))
  args=[helper,'--project',root];native=root/'herdr-plugins.lock.json';companion=root/'herdr-purifier.lock.json'
  run([*args,'lock'],env=env);initial=companion.read_bytes();native_initial=native.read_bytes()
  run([*args,'lock'],env=env);assert companion.read_bytes()==initial and native.read_bytes()==native_initial
  for name in ('first','second'):release(name,'2.0.0','two')
  selected=companion;expected={'first':'one','second':'one'}
  if case=='update':
   run([*args,'update','first'],env=env);assert {p['plugin_id']:p['version'] for p in json.loads(native.read_text())}=={'fixture.first':'2.0.0','fixture.second':'1.0.0'}
   run([*args,'update'],env=env);expected={'first':'two','second':'two'}
  elif case=='relock':
   damaged=json.loads(initial);damaged['contentHash']='bad';companion.write_text(json.dumps(damaged));run([*args,'lock'],env=env);assert native.read_bytes()==native_initial
   native.write_text('invalid native JSON');run([*args,'lock'],env=env);assert native.read_bytes()==native_initial
  elif case=='external':
   external=temp/'external';external.mkdir();selected=external/'companion.json';selected_native=external/'registry.json'
   args=[helper,'--project',root,'--lockfile',selected,'--tool-lockfile',selected_native]
   run([*args,'lock'],env=env);assert companion.read_bytes()==initial and native.read_bytes()==native_initial
   companion.unlink();native.write_text('intentionally invalid working registry\n')
   env.update(HERDR_PURIFIER_LOCKFILE=str(selected),HERDR_PURIFIER_TOOL_LOCKFILE=str(selected_native))
  elif case!='native':raise ValueError(case)
  environment=Path(run([*args,'prefetch'],env=env,capture_output=True).stdout.strip());daemon.terminate();daemon.wait(timeout=10)
  listing=json.loads(run([herdr,'plugin','list','--json'],cwd=root,env=env,capture_output=True).stdout)['result']['plugins']
  assert {p['plugin_id'] for p in listing}=={'fixture.first','fixture.second'}
  for name in expected:
   assert run([cli/'bin/bash',environment/'plugins'/name/'hello.sh'],capture_output=True).stdout.strip()==name+'-'+expected[name]
  pure=status(herdr,env);normal=status(ordinary,env);assert pure['socket']!=normal['socket'] and len(pure['socket'].encode())<=107,(pure,normal)
  named=json.loads(run([herdr,'--session','work','status','server','--json'],cwd=root,env=env,capture_output=True).stdout)
  assert named['socket']!=pure['socket'] and len(named['socket'].encode())<=107,named
  if case=='external':assert native.read_text()=='intentionally invalid working registry\n'
  if case=='native':
   # An already running ordinary server must never supply the locked session.
   start(ordinary,env);assert not status(herdr,env)['running']
   start(herdr,env);assert status(ordinary,env)['running'] and status(herdr,env)['running']
   run([herdr,'plugin','disable','fixture.second'],cwd=root,env=env)
   toggled=json.loads(run([herdr,'plugin','list','--json'],cwd=root,env=env,capture_output=True).stdout)['result']['plugins']
   assert next(p for p in toggled if p['plugin_id']=='fixture.second')['enabled'] is False,toggled
   run([herdr,'plugin','enable','fixture.second'],cwd=root,env=env)
   global_plugins=json.loads(run([ordinary,'plugin','list','--json'],cwd=root,env=env,capture_output=True).stdout)['result']['plugins'];assert global_plugins==[],global_plugins
   run([herdr,'plugin','action','invoke','fixture.first.hello'],cwd=root,env=env)
   for _ in range(100):
    entries=json.loads(run([herdr,'plugin','log','list','--plugin','fixture.first'],cwd=root,env=env,capture_output=True).stdout)['result']['logs']
    if entries and entries[0]['status']!='running':break
    time.sleep(.1)
   assert entries[0]['status']=='succeeded' and entries[0]['stdout'].strip()=='first-one',entries
   run([herdr,'server','stop'],cwd=root,env=env);run([ordinary,'server','stop'],cwd=root,env=env)
   for process in servers:process.wait(timeout=20)
   (root/'herdr-purifier.toml').write_text((root/'herdr-purifier.toml').read_text()+'# changed\n')
   stale=subprocess.run([str(herdr),'plugin','list'],cwd=root,env=env,text=True,capture_output=True);assert stale.returncode and 'declarations changed' in stale.stderr,stale.stderr
   (root/'herdr-purifier.toml').write_text((root/'herdr-purifier.toml').read_text().removesuffix('# changed\n'))
   fake=temp/'gh';record=temp/'gh-calls.jsonl';fake.write_text('#!/usr/bin/env python3\nimport json,sys\nfrom pathlib import Path\na=sys.argv[1:]\np=Path('+repr(str(record))+')\nwith p.open("a") as f:f.write(json.dumps(a)+"\\n")\nif a[:2]==["release","view"]:sys.exit(0 if len(p.read_text().splitlines())>2 else 1)\n');fake.chmod(0o755)
   for _ in range(2):run([*args,'publish','--repo','fixture/project','--tag','v0.1.0'],env={**env,'HERDR_PURIFIER_GH':str(fake)})
   calls=[json.loads(line) for line in record.read_text().splitlines()];assert calls[1][:2]==['release','create'] and calls[3][:2]==['release','upload'],calls
   archive=Path(next(a for a in calls[1] if a.endswith('/project.tar.gz')))
   with tarfile.open(archive) as source:assert {'./herdr-purifier.toml','./herdr-plugins.lock.json','./herdr-purifier.lock.json'}<=set(source.getnames())
   empty=temp/'unlocked';empty.mkdir();fallback=run([herdr,'--version'],cwd=empty,env=env,capture_output=True);baseline=run([ordinary,'--version'],cwd=empty,env=env,capture_output=True)
   assert fallback.stdout==baseline.stdout and 'ordinary impure herdr' in fallback.stderr and not (empty/'herdr-purifier.lock.json').exists()
   (empty/'herdr-purifier.toml').write_text('plugins = []\n')
   run([helper,'--project',empty,'lock'],env=env)
   run([helper,'--project',empty,'prefetch'],env=env)
   assert json.loads(run([herdr,'plugin','list','--json'],cwd=empty,env=env,capture_output=True).stdout)['result']['plugins']==[]
  print('Herdr native conformance passed:',case)
 finally:
  for process in servers:
   if process.poll() is None:
    process.terminate()
    try:process.wait(timeout=15)
    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
  for log in logs:log.close()
  if daemon.poll() is None:daemon.terminate();daemon.wait(timeout=10)
