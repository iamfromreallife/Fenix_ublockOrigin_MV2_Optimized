#!/usr/bin/env python3
"""Source-only promotion of the previously validated Fenix Chromium 1.76.6 merge.

Downloads and verifies the EXISTING upstream ZIP in memory; never builds a ZIP.
All source changes and checksums must match the archived merge comparison.
"""
from __future__ import annotations
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
import urllib.request
from zipfile import ZipFile

RELEASE = '1.76.6'
OFFICIAL_SHA256 = '8831cad49eac3ac3d85d2c32d48a328c63e152ea890cdb2223c77f5b7c0e7837'
DOWNLOAD_URL = 'https://github.com/gorhill/uBlock/releases/download/1.76.6/uBlock0_1.76.6.chromium.zip'
PREFIX = 'uBlock0.chromium/'

# path : (source_before_SHA256, final_Fenix_SHA256)
CHANGES = {
    'assets/thirdparties/easylist/easylist.txt': ('1a6bba421ca89e3a8108600517bfa05ffdd396d37cb1148d066ac181ca50b4b5', '397f7762fae12c3ba251341ef43fb1e872ed3c8d89c291021442864202cb45e7'),
    'assets/thirdparties/easylist/easyprivacy.txt': ('55263bb27f781b3ee2faa5e39266f8524e341991e7ddba97c12c9f8be49cbf33', '57d30035e0db48f0efb71a5dfe6161c5c489d80d5e36f266ac0bc1cb7bc29952'),
    'assets/thirdparties/pgl.yoyo.org/as/serverlist': ('437ddb476f8a9417d114fa02892c7048ae762b42141561775128b3a3f336bde7', '31cec776f5210876c3db6c3f94f654e01d1efaebdf54349addbdd5584cc62c07'),
    'assets/thirdparties/publicsuffix.org/list/effective_tld_names.dat': ('809adae1a2cb1621b70165c11e0d14412d3f104f40a4ebed9a99e23c54f78d71', '0588ac64698535068470db495dbaef84f57b2598ab8c4d3f80d09860738291af'),
    'assets/thirdparties/urlhaus-filter/urlhaus-filter-online.txt': ('c5412d2c2f955903f182c4b49104b0ec5c6f3fd381edb0efa8a08f87b38713b6', '170573e34cc10f7d4a03f2166d103af49921ddb2cb9659ec2f6882cb74ced9f9'),
    'assets/ublock/badware.min.txt': ('efdaff62b66704b7e7534c6aaf3debe37f0603770d16b2b88f73e5be9e0d6483', '34ce4eafec4eeba844433adf4dbb8c92bd814a2adc53d6c8799ca052378568ca'),
    'assets/ublock/filters.min.txt': ('0dd583acd69b56e23c248442d2c7f1537b0c128755f532e5c79b212ed5f601d7', '6319901424a5e3b6b5d49d910a9cf21dae085ea1d327b5547366cccff1fdca7d'),
    'assets/ublock/privacy.min.txt': ('ccad8855035133f4d6cfa73174684825e95062ae050bb0be46e313a120c8ef5f', 'f5cfd434150939124828a4e50fd89f0e8a03388d4b1de3feb9d8f60daec74a1d'),
    'assets/ublock/quick-fixes.min.txt': ('14da95d93f50e6fbe2350a3e87f6029acd290bccf36d6932894298659bca0d48', 'afc71c3c8f7842800b2b94d3890d4c2f8c17e7c8d541ff91d73e164bea615d95'),
    'assets/ublock/unbreak.min.txt': ('6ba6d2f146afc25c46f0911567f3038ed94e03d03c9bd0a1805acc2c52bcdb2d', '88799cbe0dff7291888a336dd1ec64f1bc52dac809ac23749fab69bba66bafa6'),
    'js/scriptlets/epicker.js': ('2a52c2570763b8b9e4941cd8eb145d13510ccf9db4fbe323ed8a7ec807efc9aa', '7233bbf07972690ed11c2d991ce2856490ac770a34435b28e1efe83bd7f995db'),
    'manifest.json': ('490d80980d4e06645377a8df449736b2d474060d6b15576e3f09b14c13531833', '21d043498549246197317ce3653b4118f13bd108bfe1ae0b5ac2383c45dd4aa7'),
    'assets/assets.json': (None, 'e994253fe9987f987149bec99bf366e1e3636f166e6acf444bfe0702fc15cfcc'),
}

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--offline-zip', type=Path, default=None, help='Use a local copy of the official ZIP for offline testing')
    args = p.parse_args()
    root = args.root.resolve()
    extension = root / 'extension'
    current = {p.relative_to(extension).as_posix(): p.read_bytes()
               for p in extension.rglob('*') if p.is_file()}
    if not current: raise RuntimeError('Missing extension source')
    state_path = root / '.fenix/state.json'
    state = json.loads(state_path.read_text())
    if state['upstream_tag'] not in ('1.76.5b6','1.76.6'):
        raise RuntimeError('Unexpected upstream baseline; refusing to overwrite')
    print('Checking source preconditions...', flush=True)
    for path,(old,new) in CHANGES.items():
        actual = sha(current[path]) if path in current else None
        if actual not in (old,new):
            raise RuntimeError(f'Unexpected local modification, refusing to change: {path}: {actual}')
    if args.offline_zip:
        official = args.offline_zip.read_bytes()
    else:
        request = urllib.request.Request(DOWNLOAD_URL, headers={'User-Agent':'Fenix-source-only-1.76.6'})
        with urllib.request.urlopen(request, timeout=120) as res:
            official = res.read(32*1024*1024 + 1)
    if len(official) > 32*1024*1024 or sha(official) != OFFICIAL_SHA256:
        raise RuntimeError('Official release archive SHA256/size mismatch')
    pending = dict(current)
    with ZipFile(BytesIO(official)) as z:
        for path in CHANGES:
            if path.startswith('assets/'):
                pending[path] = z.read(PREFIX + path)
    manifest = pending['manifest.json'].decode('utf-8')
    if sha(pending['manifest.json']) != CHANGES['manifest.json'][1]:
        if manifest.count('"version": "1.76.5.6"') != 1:
            raise RuntimeError('Unexpected manifest version format')
        pending['manifest.json'] = manifest.replace('"version": "1.76.5.6"', '"version": "1.76.6"').encode('utf-8')
    picker = pending['js/scriptlets/epicker.js'].decode('utf-8')
    if sha(pending['js/scriptlets/epicker.js']) != CHANGES['js/scriptlets/epicker.js'][1]:
        needle = '[${pickerUniqueId}]'
        if picker.count(needle) != 3:
            raise RuntimeError('Picker CSS selector count changed unexpectedly')
        picker = picker.replace(needle, '[${CSS.escape(pickerUniqueId)}]')
        pending['js/scriptlets/epicker.js'] = picker.encode('utf-8')
    for path,(_,final_sha) in CHANGES.items():
        if sha(pending[path]) != final_sha:
            raise RuntimeError(f'Verified Fenix 1.76.6 checksum mismatch: {path}')
    sys.path.insert(0,str(root/'scripts'))
    from fenix_common import validate
    print('Validating unpacked source; NO new ZIP will be created.',flush=True)
    result = validate(pending,syntax=True)
    assert result['version'] == RELEASE
    for path in CHANGES:
        if pending[path] != current.get(path):
            f=extension/path
            f.parent.mkdir(parents=True,exist_ok=True)
            f.write_bytes(pending[path])
            print('Updated',path)
    state.update(upstream_tag=RELEASE,
                 release_id=452893709,
                 published_at='2026-11-20T16:00:36Z',
                 upstream_zip_sha256=OFFICIAL_SHA256)
    state_path.write_text(json.dumps(state,indent=2,sort_keys=True)+'\n')
    print('Verified Fenix 1.76.6 SOURCE tree:',result,flush=True)
    print('The old dist/ ZIP has NOT been rebuilt or altered.',flush=True)

if __name__=='__main__': main()
