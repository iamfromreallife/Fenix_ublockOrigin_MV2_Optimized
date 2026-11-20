#!/usr/bin/env python3
"""Verified, stdlib-only extension packaging and validation helpers."""
from __future__ import annotations
import hashlib
import html.parser
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / 'extension'
DIST = ROOT / 'dist' / 'Fenix_uBO_MV2_Full_Performance_Optimized.zip'
MAX_ZIP_UNCOMPRESSED = 140 * 1024 * 1024
MAX_ZIP_MEMBERS = 3000
CRITICAL_PATHS = (
    'popup-fenix.html', 'js/popup-fenix.js', 'css/popup-fenix.css',
    'js/scriptlets/youtube-player.js', 'js/resources/scriptlets.js',
    'js/scriptlets/epicker.js', 'js/epicker-ui.js', 'js/storage.js',
    'js/scriptlet-filtering.js', 'web_accessible_resources/epicker-ui.html',
)


def sha256(buf: bytes) -> str:
    return hashlib.sha256(buf).hexdigest()


def load_zip(path: Path) -> dict[str, bytes]:
    if path.stat().st_size > 55 * 1024 * 1024:
        raise ValueError('Upstream ZIP unexpectedly large')
    files = {}
    total = 0
    with zipfile.ZipFile(path) as z:
        members = z.infolist()
        if len(members) > MAX_ZIP_MEMBERS:
            raise ValueError('Excessive archive member count')
        for item in members:
            if item.is_dir():
                continue
            name = item.filename
            posix = PurePosixPath(name)
            if not name or name.startswith('/') or '\\' in name or '..' in posix.parts or str(posix) != name:
                raise ValueError(f'Unsafe archive path: {name}')
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(f'Symlink not allowed: {name}')
            total += item.file_size
            if total > MAX_ZIP_UNCOMPRESSED:
                raise ValueError('Archive uncompressed size exceeds safety limit')
            if name in files:
                raise ValueError(f'Duplicate archive file: {name}')
            files[name] = z.read(item)
    if 'manifest.json' not in files:
        raise ValueError('ZIP does not contain root manifest.json')
    return files


def read_tree(directory: Path) -> dict[str, bytes]:
    return {p.relative_to(directory).as_posix(): p.read_bytes()
            for p in directory.rglob('*') if p.is_file() and not p.is_symlink()}


def write_tree(directory: Path, files: dict[str, bytes]):
    directory.mkdir(parents=True, exist_ok=True)
    old_paths = set(read_tree(directory))
    new_paths = set(files)
    for name in sorted(old_paths - new_paths):
        (directory / name).unlink()
    for name in sorted(new_paths):
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if name not in old_paths or path.read_bytes() != files[name]:
            path.write_bytes(files[name])
    # Clean empty directories, not meaningful resources.
    for p in sorted((p for p in directory.rglob('*') if p.is_dir()),key=lambda x:len(x.parts),reverse=True):
        try: p.rmdir()
        except OSError: pass


def create_zip(files: dict[str, bytes], dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=True) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, files[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(dest) as z:
        bad = z.testzip()
        if bad:
            raise AssertionError(f'Invalid ZIP member: {bad}')


class Refs(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'link', 'img'):
            for k, v in attrs:
                if k in ('src', 'href') and v:
                    self.refs.append(v)


def validate(files: dict[str, bytes], *, syntax=True) -> dict:
    manifest = json.loads(files['manifest.json'])
    assert manifest.get('manifest_version') == 2, 'MV2 manifest lost'
    assert manifest.get('browser_action',{}).get('default_popup') == 'popup-fenix.html', 'Fenix popup lost'
    assert manifest.get('permissions'), 'Permissions unexpectedly empty'
    assert all(p in files for p in CRITICAL_PATHS), 'Fenix critical file missing'
    js = [name for name in files if name.endswith('.js')]
    locale = [name for name in files if name.startswith('_locales/') and name.endswith('/messages.json')]
    assert len(locale) >= 72, f'Expected at least 72 translations, got {len(locale)}'
    for name in locale:
        json.loads(files[name])
    for name in (x for x in files if x.endswith('.wasm')):
        assert files[name].startswith(b'\x00asm'), f'WASM invalid: {name}'
    assert b'fenixOptimizeYouTubeQuickFix' in files['js/storage.js'], 'Fenix Quick Fix removed'
    assert b'fenix' in files['js/scriptlets/youtube-player.js'].lower() or b'muBlock' in files['js/scriptlets/youtube-player.js'], 'Fenix player scriptlet removed'
    assert b'streamWatchResponse' in files['js/resources/scriptlets.js'], 'Streaming rewrite removed'
    paths = []
    for cs in manifest.get('content_scripts',[]):
        paths.extend(p.lstrip('/') for p in cs.get('js',[]))
    paths.extend([manifest['background']['page'], manifest['options_ui']['page'], manifest['browser_action']['default_popup']])
    paths.extend(manifest.get('icons',{}).values())
    for p in paths:
        assert p in files, f'Missing manifest resource {p}'
    nimports = nhtml = 0
    regex = re.compile(r'''(?:\bimport\s*(?:\(|[^;\n]*?\bfrom\s*)|\bexport\s+[^;\n]*?\bfrom\s*)[\s\n]*["']([^"']+)["']''')
    import posixpath
    for name in js:
        source = files[name].decode('utf-8')
        for m in regex.finditer(source):
            target = m.group(1)
            if not target.startswith('.'): continue
            nimports += 1
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
            assert resolved in files, f'Missing JS import {name} -> {target}'
    for name in (n for n in files if n.endswith('.html')):
        parser = Refs()
        parser.feed(files[name].decode('utf-8'))
        for ref in parser.refs:
            if ref.startswith(('http:','https:','data:','blob:','#','javascript:','//')):
                continue
            path = ref.split('?',1)[0].split('#',1)[0].lstrip('/')
            if not path: continue
            nhtml += 1
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name),path))
            assert resolved in files, f'Missing HTML resource {name} -> {ref}'
    if syntax:
        with tempfile.TemporaryDirectory() as temp:
            for name in js:
                path=Path(temp)/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(files[name])
                p=subprocess.run(['node','--check',str(path)],capture_output=True,text=True)
                assert p.returncode == 0, f'{name}: {p.stderr}'
    return {'files': len(files), 'javascript': len(js), 'locales': len(locale),
            'imports': nimports, 'html_references': nhtml, 'manifest_version': 2,
            'version': manifest.get('version'), 'byte_size': sum(map(len,files.values()))}
