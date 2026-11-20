#!/usr/bin/env python3
"""One-time byte-exact reconstruction of the optimised Fenix release."""
from pathlib import Path
import json
from fenix_common import ROOT, EXT, DIST, load_zip, read_tree, sha256, validate, write_tree

CHUNKS = ROOT / '.fenix' / 'bootstrap'
EXPECTED_SHA = 'cc59465d71b5baca2b6d18a745a15c4e504c0092c0e72faeb319452014026a14'
BASE_RELEASE = {
    'repo':'gorhill/uBlock', 'upstream_tag':'1.76.5b6',
    'release_id':451743883,
    'published_at':'2026-11-19T18:22:10Z',
    'upstream_zip_sha256':'87d8661e29103a95aeb163f1ddc09736428fbcab5c491e51065e97afed46dba5',
}

def main():
    parts=sorted(CHUNKS.glob('part-*.bin'))
    if not parts:
        print('No bootstrap chunks; source already materialized or bootstrap not staged.')
        assert EXT.joinpath('manifest.json').exists(), 'No bootstrapped source found'
        return
    assert len(parts)==31, f'Expected 31 archive chunks, got {len(parts)}'
    full=b''.join(p.read_bytes() for p in parts)
    assert sha256(full)==EXPECTED_SHA, 'Exact archive digest mismatch. Refusing to proceed.'
    files=load_zip_bytes(full)
    print('ZIP integrity verified, SHA-256:',EXPECTED_SHA)
    print('Extension verification:',validate(files))
    DIST.parent.mkdir(parents=True,exist_ok=True)
    DIST.write_bytes(full)
    write_tree(EXT,files)
    state=dict(BASE_RELEASE, archive_sha256=EXPECTED_SHA)
    state_path=ROOT/'.fenix'/'state.json'
    state_path.write_text(json.dumps(state,indent=2,sort_keys=True)+'\n')
    for p in parts:
        p.unlink()
    CHUNKS.rmdir()
    print('Exact optimized ZIP and unpacked extension materialized.')

def load_zip_bytes(data):
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        p=Path(directory)/'extension.zip'
        p.write_bytes(data)
        return load_zip(p)

if __name__=='__main__': main()
