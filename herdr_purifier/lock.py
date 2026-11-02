# SPDX-License-Identifier: MIT
import base64,hashlib,json,re,tomllib
FIX='; run herdr-purifier lock'
NAME=r'[A-Za-z0-9][A-Za-z0-9_-]*'
SOURCE=r'([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)(/[^\s]+)?'
def canonical(data):return json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def seal(data):
 data={k:v for k,v in data.items() if k!='contentHash'}
 return {**data,'contentHash':hashlib.sha256(canonical(data).encode()).hexdigest()}
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def relative(value):return isinstance(value,str) and value and not value.startswith('/') and '\\' not in value and all(p not in ('','.','..') for p in value.split('/'))
def config(text):
 data=tomllib.loads(text);plugins=data.get('plugins')
 if not isinstance(plugins,list):raise ValueError('expected [[plugins]] declarations'+FIX)
 result=[];names=set()
 for item in plugins:
  if not isinstance(item,dict):raise ValueError('invalid plugin declaration'+FIX)
  name=item.get('name');source=item.get('source');reference=item.get('ref');enabled=item.get('enabled',True)
  if not isinstance(name,str) or not re.fullmatch(NAME,name) or name in names:raise ValueError('invalid or duplicate plugin name'+FIX)
  if not isinstance(source,str) or not re.fullmatch(SOURCE,source) or not relative(source):raise ValueError('invalid native GitHub plugin source'+FIX)
  parts=source.split('/');url=item.get('url','https://github.com/'+parts[0]+'/'+parts[1]+'.git')
  if not isinstance(url,str) or not re.fullmatch(r'(https?|git|file)://[^\s@]+',url):raise ValueError('unsupported plugin Git transport'+FIX)
  if reference is not None and (not isinstance(reference,str) or not reference or reference.startswith('-') or re.search(r'\s',reference)):raise ValueError('invalid Git reference'+FIX)
  if not isinstance(enabled,bool):raise ValueError('enabled must be a boolean'+FIX)
  names.add(name);result.append({'name':name,'source':source,'url':url,'ref':reference,'enabled':enabled})
 return sorted(result,key=lambda p:p['name'])
def normalize(info,item):
 result=json.loads(json.dumps(info));parts=item['source'].split('/');root='plugins/'+item['name']
 result['plugin_root']=root+('/'+'/'.join(parts[2:]) if len(parts)>2 else '')
 result['manifest_path']=result['plugin_root']+'/herdr-plugin.toml';result['enabled']=item['enabled']
 result['source']['managed_path']=root;result['source']['installed_unix_ms']=0
 if item['ref'] is None:result['source'].pop('requested_ref',None)
 else:result['source']['requested_ref']=item['ref']
 return result
def native(text):
 data=json.loads(text)
 if not isinstance(data,list) or any(not isinstance(p,dict) or not isinstance(p.get('plugin_id'),str) or p.get('source',{}).get('kind')!='github' or not re.fullmatch('[0-9a-f]{40}',p['source'].get('resolved_commit','')) for p in data):raise ValueError('invalid native Herdr registry lock'+FIX)
 return data
def problems(root,path,data):
 try:
  if not isinstance(data,dict) or data.get('version')!=1:return ['unsupported companion format'+FIX]
  if data.get('contentHash')!=seal(data)['contentHash']:return ['companion contentHash mismatch'+FIX]
  text=(root/'herdr-purifier.toml').read_text();items=config(text)
  if data.get('configHash')!=digest(root/'herdr-purifier.toml') or data.get('config')!=text:return ['plugin declarations changed'+FIX]
  pins=native(path.read_text())
  if data.get('nativeHash')!=digest(path) or data.get('nativeLock')!=path.read_text():return ['native registry lock changed'+FIX]
  plugins=data.get('plugins')
  if not isinstance(plugins,list) or len(plugins)!=len(items) or [p['plugin'] for p in plugins]!=pins:raise ValueError('incomplete native plugin graph')
  ids=set()
  for item,selected in zip(items,plugins):
   plugin=selected['plugin'];entry=selected['entry'];git=entry['git'];source=plugin['source'];parts=item['source'].split('/')
   if selected['name']!=item['name'] or normalize(plugin,item)!=plugin or plugin['plugin_id'] in ids:raise ValueError('native plugin declarations do not match')
   ids.add(plugin['plugin_id'])
   if source.get('owner')!=parts[0] or source.get('repo')!=parts[1] or source.get('subdir')!=('/'.join(parts[2:]) if len(parts)>2 else None):raise ValueError('native GitHub source changed')
   if entry['path']!=item['name'] or git['url']!=item['url'] or git['rev']!=source['resolved_commit'] or git['leaveDotGit'] is not True or git['submodules'] is not False:raise ValueError('native Git source changed')
   if not re.fullmatch('sha256-[A-Za-z0-9+/]{43}=',entry['hash']):raise ValueError('invalid source NAR hash')
   raw=base64.b64decode(git['commitObject']['object'],validate=True)
   if git['commitObject']['gitlinks']!=[] or hashlib.sha1(b'commit '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=git['rev']:raise ValueError('invalid raw Git commit')
  return []
 except (OSError,ValueError,TypeError,AttributeError,KeyError) as error:return [str(error)+FIX]
