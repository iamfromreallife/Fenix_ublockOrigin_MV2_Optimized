#!/usr/bin/env python3
"""Native Firefox MV2 Fenix builder. Produce unsigned XPI; never forge Mozilla signing."""
import json,os,re,hashlib,subprocess,tempfile,urllib.request,sys
from pathlib import Path
from fenix_common import EXT, ROOT, load_zip, read_tree, validate, create_zip
API="https://api.github.com/repos/gorhill/uBlock"
HEADERS={"User-Agent":"Fenix-Firefox-Builder/1.0","Accept":"application/vnd.github+json"}
if os.environ.get("GH_TOKEN"): HEADERS["Authorization"]="Bearer "+os.environ["GH_TOKEN"]
STATE=json.loads((ROOT/".fenix/state.json").read_text())
ALLOWED_NEW={"js/scriptlets/youtube-player.js"}
PLATFORM={"js/vapi-background-ext.js","js/vapi-scripting.js","js/webext.js",
 "js/vapi.js","js/vapi-background.js","js/vapi-common.js","js/vapi-client.js",
 "js/vapi-contexts.js","manifest.json"}

def request_json(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers=HEADERS),timeout=35) as response:
  return json.load(response)

def release(tag):
 if tag: return request_json(API+"/releases/tags/"+tag)
 values=request_json(API+"/releases?per_page=100")
 items=[r for r in values if not r["draft"] and r.get("published_at")
        and any(a["name"].endswith(".chromium.zip") for a in r["assets"])
        and any(a["name"].endswith(".firefox.signed.xpi") for a in r["assets"])]
 if not items: raise ValueError("No official Chromium+Firefox release")
 return max(items,key=lambda x:(x["published_at"],x["id"]))

def download(r,kind,dest):
 tag=r["tag_name"]
 suffix=".chromium.zip" if kind=="chromium" else ".firefox.signed.xpi"
 options=[a for a in r["assets"] if re.fullmatch(r"uBlock0_[\w.]+",a["name"][:-len(suffix)]) and a["name"].endswith(suffix)]
 if len(options)!=1: raise ValueError("Official "+kind+" asset missing or ambiguous: "+tag)
 a=options[0];url=a["browser_download_url"]
 if url!=f"https://github.com/gorhill/uBlock/releases/download/{tag}/{a['name']}":
  raise ValueError("Unexpected official download location")
 if not (1000 < a["size"] < 55*1024*1024): raise ValueError("Unexpected archive size")
 path=dest/a["name"];digest=hashlib.sha256();total=0
 with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Fenix-Firefox-Builder/1.0"}),timeout=120) as source,open(path,"wb") as output:
  while chunk:=source.read(1024*1024):
   total+=len(chunk)
   if total>55*1024*1024:raise ValueError("Oversized archive")
   digest.update(chunk);output.write(chunk)
 if total!=a["size"]:raise ValueError("Truncated official download")
 if a.get("digest") and a["digest"]!="sha256:"+digest.hexdigest():
  raise ValueError("Official asset digest mismatch")
 return load_zip(path)

def merge(path,base,ours,theirs):
 if theirs==base:return ours
 if ours==base:return theirs
 if ours==theirs:return ours
 if any(b"\0" in s or len(s)>2_000_000 for s in [base,ours,theirs]):
  raise ValueError("Unsafe three-way merge for "+path)
 with tempfile.TemporaryDirectory() as temp:
  ps=[Path(temp)/k for k in ("ours","base","theirs")]
  for p,data in zip(ps,(ours,base,theirs)):p.write_bytes(data)
  p=subprocess.run(["git","merge-file","-p","--diff3",*map(str,ps)],capture_output=True)
  if p.returncode!=0:raise ValueError("Upstream/Fenix edit conflict in "+path)
  return p.stdout

def build(target,base,ours):
 official=dict((k,v) for k,v in target.items() if not k.startswith("META-INF/"))
 changed=[]
 for path in sorted(set(base)|set(ours)):
  old=base.get(path);local=ours.get(path)
  if local==old:continue
  if path in PLATFORM:continue
  if old is None:
   if path in ALLOWED_NEW:
    if path in official and official[path]!=local:raise ValueError("Custom file collides: "+path)
    official[path]=local;changed.append(path)
   continue
  if local is None:continue
  if path not in official:
   if path.startswith(("js/","css/")) and not path.startswith(("js/vapi","js/webext")):
    raise ValueError("Upstream Firefox common file removed: "+path)
   continue
  if not (path.startswith(("js/","css/")) or path.endswith(".html")):continue
  official[path]=merge(path,old,local,official[path])
  changed.append(path)
 if "js/scriptlets/youtube-player.js" not in changed:raise ValueError("Missing Fenix YouTube module")
 return official,changed

def main():
 previous=STATE["upstream_tag"]
 tag=os.environ.get("UPSTREAM_TAG") or ""
 desired=release(tag)
 print("Fenix baseline",previous,"to Firefox",desired["tag_name"],flush=True)
 with tempfile.TemporaryDirectory() as t:
  directory=Path(t)
  prior=download(release(previous),"chromium",directory)
  target=download(desired,"firefox",directory)
 out,changed=build(target,prior,read_tree(EXT))
 manifest=json.loads(out["manifest.json"])
 assert manifest["manifest_version"]==2 and "gecko" in manifest["browser_specific_settings"]
 assert all(k in manifest["permissions"] for k in ("dns","menus","publicSuffix","webRequestBlocking"))
 manifest["name"]="Fenix uBlock Origin (MV2)"
 manifest["browser_action"]["default_title"]="Fenix uBlock Origin"
 manifest["browser_specific_settings"]["gecko"]["id"]="fenix-ubo-mv2@iamfromreallife"
 if manifest.get("sidebar_action") and not re.fullmatch(r"\d+\.\d+\.\d+\.\d+",desired["tag_name"]):
  del manifest["sidebar_action"]
 version=desired["tag_name"]
 version=re.sub(r"(b|rc)(\d+)$",r".\2",version)
 if not re.fullmatch(r"\d+\.\d+\.\d+(?:\.\d+)?",version):
  raise ValueError("Unsupported addon version "+version)
 manifest["version"]=version
 out["manifest.json"]=(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n").encode()
 stats=validate(out,syntax=True)
 assert out["js/webext.js"]==target["js/webext.js"] and out["js/vapi-scripting.js"]==target["js/vapi-scripting.js"]
 assert out["js/vapi-background-ext.js"]==target["js/vapi-background-ext.js"]
 file="Fenix_uBO_Firefox_"+desired["tag_name"]+"_UNSIGNED.xpi"
 dst=ROOT/"dist"/file;create_zip(out,dst)
 result={"source_fenix_version":previous,"firefox_version":desired["tag_name"],
         "xpi_filename":file,"sha256":hashlib.sha256(dst.read_bytes()).hexdigest(),
         "signed":False,"changed":changed,"validation":stats}
 (ROOT/"dist"/"Fenix_Firefox_Report.json").write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps(result,indent=2),flush=True)

if __name__=="__main__":
 try:main()
 except Exception as exc:
  print("ERROR: FAIL-CLOSED Firefox build:",exc,file=sys.stderr);sys.exit(1)
