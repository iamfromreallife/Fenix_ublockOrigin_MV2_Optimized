#!/usr/bin/env python3
"""Poll official uBO releases and safely rebase the Fenix MV2 source tree.

Only official gorhill/uBlock release assets ending .chromium.zip are considered.
Every release published after the stored upstream cursor is processed in order.
An overlapping local/upstream change that cannot be merged stops the update.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

from fenix_common import ROOT, EXT, DIST, load_zip, read_tree, write_tree, validate, create_zip, sha256

API = 'https://api.github.com/repos/gorhill/uBlock/releases'
STATE = ROOT / '.fenix' / 'state.json'
REPORT = ROOT / '.fenix' / 'sync-report.json'
MAX_RELEASE_PAGES = 12
MAX_DOWNLOAD = 55 * 1024 * 1024


def github_headers():
    headers={'Accept':'application/vnd.github+json','User-Agent':'Fenix-MV2-Release-Synchronizer/1.0','X-GitHub-Api-Version':'2022-11-28'}
    token=os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if token:
        headers['Authorization']='Bearer '+token
    return headers


def get_json(url: str):
    with urllib.request.urlopen(urllib.request.Request(url,headers=github_headers()),timeout=35) as r:
        if r.status != 200: raise RuntimeError(f'GitHub API status {r.status}')
        return json.load(r)


def download_asset(release: dict, directory: Path):
    assets=[a for a in release.get('assets',()) if re.fullmatch(r'uBlock0_[0-9A-Za-z.]+\.chromium\.zip',a.get('name',''))]
    if len(assets)!=1:
        raise RuntimeError(f'Official Chromium MV2 ZIP asset count != 1: {release.get("tag_name")} ({len(assets)})')
    asset=assets[0]
    url=asset['browser_download_url']
    parsed=urllib.parse.urlsplit(url)
    prefix=f'/gorhill/uBlock/releases/download/{urllib.parse.quote(release["tag_name"],safe="")}/'
    if parsed.scheme!='https' or parsed.hostname!='github.com' or not parsed.path.startswith(prefix):
        raise RuntimeError(f'Invalid upstream asset URL {url}')
    if int(asset.get('size',0))<=0 or int(asset['size'])>MAX_DOWNLOAD:
        raise RuntimeError('Unexpected upstream asset size')
    name=directory/(release['tag_name'].replace('/','_')+'.zip')
    headers={'User-Agent':'Fenix-MV2-Release-Synchronizer/1.0'}
    with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=120) as response, name.open('wb') as out:
        copied=0
        while True:
            block=response.read(1024*1024)
            if not block: break
            copied+=len(block)
            if copied>MAX_DOWNLOAD: raise RuntimeError('Asset download larger than limit')
            out.write(block)
    if copied!=int(asset['size']):
        raise RuntimeError(f'Asset byte length mismatch {copied} != {asset["size"]}')
    digest=sha256(name.read_bytes())
    expected=(asset.get('digest') or '').removeprefix('sha256:')
    if expected and digest!=expected:
        raise RuntimeError('GitHub published SHA-256 does not match downloaded bytes')
    files=load_zip(name)
    if json.loads(files['manifest.json']).get('manifest_version')!=2:
        raise RuntimeError(f'{release["tag_name"]} upstream ZIP is not Manifest V2')
    return files, digest


def release_list(state):
    all_releases=[]
    for page in range(1,MAX_RELEASE_PAGES+1):
        releases=get_json(f'{API}?per_page=100&page={page}')
        if not isinstance(releases,list): raise RuntimeError('Unexpected GitHub releases response')
        all_releases.extend(releases)
        # Stop once the previously processed upstream release is visible.
        # Fetching every historical release is not necessary and eventually
        # exceeds the page bound (uBlock has over 1,000 releases).
        if len(releases)<100 or any(r.get('tag_name') == state['upstream_tag'] for r in releases):
            break
    else:
        raise RuntimeError('Release cursor is outside search window; refusing to skip unseen releases')
    return all_releases


def release_is_eligible(r):
    return (not r.get('draft') and r.get('published_at') is not None and
            any(a.get('name','').endswith('.chromium.zip') for a in r.get('assets',[])))


def next_release(releases, state, requested_tag=None):
    release_by_tag={r['tag_name']:r for r in releases if release_is_eligible(r)}
    if requested_tag:
        if requested_tag == state['upstream_tag']:
            return None
        if requested_tag not in release_by_tag:
            raise ValueError(f'Unknown/ineligible tag {requested_tag}; only published upstream Chromium ZIP releases are supported')
        result=release_by_tag[requested_tag]
        if result['published_at']<=state['published_at']:
            raise ValueError('Requested release predates the recorded sync cursor; refusing possible downgrade')
        return result
    options=[r for r in release_by_tag.values() if (r['published_at'],r['id'])>(state['published_at'],state.get('release_id',0))]
    return min(options,key=lambda r:(r['published_at'],r['id'])) if options else None


def is_text(data):
    return b'\0' not in data and len(data)<=2*1024*1024 and not any((c<9 or 13<c<32) for c in data[:256])


def three_way(path, local, base, incoming):
    if local==base: return incoming, 'upstream'
    if incoming==base: return local, 'local'
    if local==incoming: return local, 'equal'
    if local is None or base is None or incoming is None:
        raise ValueError('add/delete conflict')
    if not all(is_text(v) for v in (local,base,incoming)):
        raise ValueError('binary/large-file conflict')
    with tempfile.TemporaryDirectory() as temp:
        paths=[Path(temp)/n for n in ('ours','base','theirs')]
        for f,data in zip(paths,(local,base,incoming)):
            f.write_bytes(data)
        result=subprocess.run(['git','merge-file','-p','--diff3',
                               '-L','Fenix optimized','-L','Previous upstream','-L','New upstream',
                               *(str(x) for x in paths)],capture_output=True)
        if result.returncode:
            raise ValueError('overlapping edits or git merge-file failure')
        return result.stdout, 'merged'


def merge_files(previous, current, upcoming):
    merged={}
    counts={'upstream':0,'local':0,'equal':0,'merged':0}
    conflicts=[]
    all_keys=sorted(set(previous)|set(current)|set(upcoming))
    for path in all_keys:
        # Custom-only files remain untouched. Previously upstream-owned files
        # are updated via a true three-way merge rather than overlay copying.
        if path not in previous and path not in upcoming:
            if path in current: merged[path]=current[path]
            continue
        if path not in previous and path in upcoming and path not in current:
            merged[path]=upcoming[path]
            counts['upstream']+=1
            continue
        try:
            out, kind=three_way(path,current.get(path),previous.get(path),upcoming.get(path))
            if out is not None: merged[path]=out
            counts[kind]+=1
        except ValueError as e:
            conflicts.append({'path':path,'reason':str(e),'local_changed':current.get(path)!=previous.get(path),
                              'upstream_changed':upcoming.get(path)!=previous.get(path)})
    return merged, counts, conflicts


def workflow_output(**values):
    target=os.getenv('GITHUB_OUTPUT')
    if target:
        with open(target,'a') as f:
            for name,value in values.items():
                f.write(f'{name}={str(value).lower() if isinstance(value,bool) else value}\n')
    print('OUTPUT',values)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--tag',default='',help='Published upstream release tag to process, otherwise oldest unseen')
    args=parser.parse_args()
    if not STATE.is_file() or not EXT.joinpath('manifest.json').exists():
        print('Extension not bootstrapped yet; no update performed.')
        workflow_output(updated=False)
        return
    state=json.loads(STATE.read_text())
    assert state['repo']=='gorhill/uBlock'
    releases=release_list(state)
    new=next_release(releases,state,args.tag or None)
    if new is None:
        print('No new official Chromium MV2 releases')
        workflow_output(updated=False)
        return
    old=next((r for r in releases if r['tag_name']==state['upstream_tag']),None)
    if old is None:
        old=get_json(API+'/tags/'+urllib.parse.quote(state['upstream_tag'],safe=''))
    print('Rebasing Fenix',state['upstream_tag'],'->',new['tag_name'],
          '(prerelease)' if new.get('prerelease') else '(stable)',flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        previous,previous_sha=download_asset(old,Path(tmp))
        expected_old=state.get('upstream_zip_sha256')
        if expected_old and previous_sha!=expected_old:
            raise RuntimeError('Baseline upstream asset bytes changed; refusing unsafe rebase')
        upcoming,upcoming_sha=download_asset(new,Path(tmp))
    current=read_tree(EXT)
    result,counts,conflicts=merge_files(previous,current,upcoming)
    report={'upstream_repo':'gorhill/uBlock','old_tag':state['upstream_tag'],
            'new_tag':new['tag_name'],'new_prerelease':bool(new.get('prerelease')),
            'new_published_at':new['published_at'],'changed_paths':[
                p for p in sorted(set(current)|set(result)) if result.get(p)!=current.get(p)],
            'merge_counts':counts,'conflicts':conflicts,
            'upstream_zip_sha256':upcoming_sha}
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(report,indent=2)+'\n')
    if conflicts:
        print('UNRESOLVED MERGE CONFLICTS:',json.dumps(conflicts,indent=2),file=sys.stderr)
        workflow_output(updated=False,conflicts=True)
        sys.exit(2)
    try:
        stats=validate(result,syntax=True)
    except Exception as e:
        report['validation_error']=str(e)
        REPORT.write_text(json.dumps(report,indent=2)+'\n')
        raise
    # Apply only after all three-way merges and static validation pass.
    write_tree(EXT,result)
    create_zip(result,DIST)
    state.update(upstream_tag=new['tag_name'],release_id=new['id'],
                 published_at=new['published_at'],upstream_zip_sha256=upcoming_sha,
                 archive_sha256=sha256(DIST.read_bytes()))
    STATE.write_text(json.dumps(state,indent=2,sort_keys=True)+'\n')
    report.update(validation=stats,archive_sha256=state['archive_sha256'],
                  archive_size=DIST.stat().st_size)
    REPORT.write_text(json.dumps(report,indent=2)+'\n')
    workflow_output(updated=True,tag=new['tag_name'],prerelease=bool(new.get('prerelease')),
                    changed_files=len(report['changed_paths']))
    print('Updated, validated, packaged:',json.dumps(report,indent=2))

if __name__=='__main__': main()
