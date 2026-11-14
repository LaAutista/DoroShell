#!/usr/bin/env python3
"""Personal animated loading cursors. Artwork stays outside the checkout."""
import argparse
import base64
import hashlib
import json
import re
import struct
from pathlib import Path
from PIL import Image, ImageSequence
from install import safe, set_ini, atomic, validate_backup

THEME = 'DoroShell-Loading'
SIZES = (24, 30, 32, 48, 64)
ALIASES = {'wait': ('watch',), 'progress': ('left_ptr_watch', 'half-busy', '00000000000000020006000e7e9ffc3f', '08e8e1c95fe2fc01f976f1e063a24ccd', '3ecb610c1bf2410f44200f48c40d3599'), 'default': ('left_ptr', 'arrow', 'top_left_arrow')}


def decode_cursor(path, size):
    data = path.read_bytes()
    magic, header, version, count = struct.unpack_from('<4I', data)
    if magic != 0x72756358:
        raise ValueError('Not an Xcursor')
    entries = [struct.unpack_from('<3I', data, header + i * 12) for i in range(count)]
    _, nominal, offset = min((e for e in entries if e[0] == 0xfffd0002), key=lambda e: abs(e[1]-size))
    h, typ, sub, ver, w, height, xhot, yhot, delay = struct.unpack_from('<9I', data, offset)
    pixels = struct.unpack_from(f'<{w*height}I', data, offset+h)
    im = Image.new('RGBA', (w, height))
    # Xcursor uses premultiplied ARGB.
    im.putdata([(min(255, ((p>>16)&255)*255//a), min(255, ((p>>8)&255)*255//a), min(255, (p&255)*255//a), a) if (a:=p>>24) else (0,0,0,0) for p in pixels])
    ratio = size / nominal
    return im.resize((round(w*ratio), round(height*ratio)), Image.Resampling.LANCZOS), (round(xhot*ratio),round(yhot*ratio))


def encode_cursor(frames):
    chunks, toc = [], []
    offset = 16 + 12 * len(frames)
    for nominal, im, hot, delay in frames:
        pixels = [(a<<24)|((r*a//255)<<16)|((g*a//255)<<8)|(b*a//255) for r,g,b,a in im.getdata()]
        chunk = struct.pack('<9I', 36, 0xfffd0002, nominal, 1, im.width, im.height, *hot, delay) + struct.pack(f'<{len(pixels)}I', *pixels)
        toc.append(struct.pack('<3I', 0xfffd0002, nominal, offset))
        chunks.append(chunk)
        offset += len(chunk)
    return struct.pack('<4I', 0x72756358, 16, 0x10000, len(frames)) + b''.join(toc+chunks)


def build(gif, base, pink=False):
    with Image.open(gif) as source:
        poster = int(source.info.get('default_image', False))
        if getattr(source, 'n_frames', 1) - poster < 2:
            raise ValueError('An animated image is required')
        canvas = (0, 0, *source.size) if source.format == 'PNG' else None
        frames = [(f.convert('RGBA'), max(10, round(f.info.get('duration', 100))))
                  for i, f in enumerate(ImageSequence.Iterator(source)) if i >= poster]
    # APNG's authored canvas retains positioning. Preserve existing GIF/WebP crop behavior.
    boxes = [im.getbbox() for im,_ in frames if im.getbbox()]
    if not boxes:
        raise ValueError('Animation is empty')
    crop = canvas or (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    busy, progress, pointers = [], [], []
    for size in SIZES:
        arrow, hot = decode_cursor(base/'cursors/default', size)
        if pink:
            # Preserve alpha, silhouette, dark outline and pointer hotspot.
            arrow.putdata([(min(255,r+int((255-r)*.65)), int(g*.55), min(255,b+int((220-b)*.45)),a) if max(r,g,b)>100 else (r,g,b,a) for r,g,b,a in arrow.getdata()])
            pointers.append((size,arrow,hot,0))
        for frame, delay in frames:
            doro = frame.crop(crop)
            doro.thumbnail((size,size), Image.Resampling.LANCZOS)
            canvas = Image.new('RGBA', (size,size))
            canvas.alpha_composite(doro, ((size-doro.width)//2,(size-doro.height)//2))
            busy.append((size,canvas,(size//2,size//2),delay))
            # Original pointer and hotspot, with Doro beside it instead of a circle.
            badge = doro.resize((max(1,round(doro.width*.75)),max(1,round(doro.height*.75))),Image.Resampling.LANCZOS)
            x,y = round(size*.5), round(size*.4)
            combined = Image.new('RGBA',(max(arrow.width,x+badge.width),max(arrow.height,y+badge.height)))
            combined.alpha_composite(badge,(x,y))
            combined.alpha_composite(arrow)
            progress.append((size,combined,hot,delay))
    result = {'wait':encode_cursor(busy),'progress':encode_cursor(progress)}
    if pink:
        result['default'] = encode_cursor(pointers)
    return result



def targets(home, gif, base, pink=False):
    files = {}
    root = home/'.icons'/THEME
    files[root/'index.theme'] = f'[Icon Theme]\nName=DoroShell Loading\nComment=Personal animated loading cursors\nInherits={base.name}\n'.encode()
    for name,data in build(gif,base,pink).items():
        for alias in (name,*ALIASES[name]):
            files[root/'cursors'/alias] = data
    configs = {home/'.config/lxqt/session.conf':('Mouse','cursor_theme',THEME), home/'.icons/default/index.theme':('Icon Theme','Inherits',THEME)}
    for path,(section,key,value) in configs.items():
        safe(path, home)
        files[path]=set_ini(path.read_text() if path.exists() else '',section,key,value).encode()
    path=home/'.Xresources'
    safe(path,home)
    text=path.read_text() if path.exists() else ''
    pattern=r'(?m)^Xcursor\.theme\s*:.*$'
    files[path]=(re.sub(pattern,'Xcursor.theme: '+THEME,text) if re.search(pattern,text) else text.rstrip()+'\nXcursor.theme: '+THEME+'\n').encode()
    return files


def run(home, gif=None, base=Path('/usr/share/icons/breeze_cursors'), apply=False, rollback=False, pink=False):
    manifest=home/'.local/state/lxqt-comfort/cursor-install.json'
    safe(manifest,home)
    record=json.loads(manifest.read_text()) if manifest.exists() else {}
    if not isinstance(record, dict): raise ValueError('Invalid cursor manifest; preserve it for recovery')
    for entry in record.values():
        validate_backup(entry, 'before')
        if type(entry['mode']) is not int or not 0 <= entry['mode'] <= 0o777:
            raise ValueError('Invalid cursor file mode')
        if 'pending_from' in entry and 'pending_mode' not in entry:
            raise ValueError('Missing cursor recovery mode')
        for key in ('installed', 'pending_from'):
            value = entry.get(key)
            if value is not None and (not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value)):
                raise ValueError('Invalid cursor recovery hash')
        if 'installed' not in entry: raise ValueError('Missing cursor installed hash')
        if entry.get('pending_mode') is not None and (type(entry['pending_mode']) is not int or not 0 <= entry['pending_mode'] <= 0o777):
            raise ValueError('Invalid cursor recovery mode')
    if rollback:
        files={home/key:base64.b64decode(item['before']) if item['before'] is not None else None for key,item in record.items()}
    else:
        if not gif:
            raise ValueError('Provide --gif /path/to/animation.gif')
        files=targets(home,gif,base,pink)
        # Return optional pointer overrides to their original contents or absence.
        for key in record:
            if home/key not in files:
                before = record[key]['before']
                files[home/key] = base64.b64decode(before) if before is not None else None
    for path,data in files.items():
        safe(path,home)
        current=path.read_bytes() if path.exists() else None
        key=str(path.relative_to(home))
        current_hash = hashlib.sha256(current).hexdigest() if current is not None else None
        current_mode = path.stat().st_mode & 0o777 if current is not None else None
        if key in record:
            entry = record[key]
            allowed = {(entry['installed'], entry['mode'] if entry['installed'] is not None else None)}
            if 'pending_from' in entry: allowed.add((entry['pending_from'], entry['pending_mode']))
            if rollback:
                before = base64.b64decode(entry['before'], validate=True) if entry['before'] is not None else None
                allowed.add((hashlib.sha256(before).hexdigest() if before is not None else None, entry['mode'] if before is not None else None))
            if (current_hash, current_mode) not in allowed:
                raise RuntimeError(f'Edited or missing managed file; no changes made: {path}')
        if key not in record:
            record[key]={'before':base64.b64encode(current).decode() if current is not None else None,'mode':path.stat().st_mode & 0o777 if current is not None else 0o644}
        if not rollback:
            record[key]['pending_from'] = current_hash
            record[key]['pending_mode'] = current_mode
            record[key]['installed']=hashlib.sha256(data).hexdigest() if data is not None else None
        print('Restore:' if rollback else 'Write:',path.relative_to(home))
    if not (apply or rollback):
        print('Plan only. Add --apply. No package changes.')
        return
    if not rollback:
        manifest.parent.mkdir(parents=True,exist_ok=True)
        atomic(manifest,(json.dumps(record,indent=2)+'\n').encode())
    for path,data in files.items():
        if data is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True,exist_ok=True)
            atomic(path,data,record[str(path.relative_to(home))]['mode'])
    if rollback and manifest.exists():
        manifest.unlink()
    if not rollback:
        for entry in record.values():
            entry.pop('pending_from',None);entry.pop('pending_mode',None)
        atomic(manifest,(json.dumps(record,indent=2)+'\n').encode())
    print('Saved. Restart affected applications; log out/in later for consistent session-wide pickup. No session was restarted.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gif',type=Path)
    parser.add_argument('--pink-pointer',action='store_true',help='Opt in to a pink ordinary pointer; default inherits the base pointer')
    parser.add_argument('--base',type=Path,default=Path('/usr/share/icons/breeze_cursors'))
    parser.add_argument('--home',type=Path,default=Path.home())
    actions=parser.add_mutually_exclusive_group()
    actions.add_argument('--apply',action='store_true')
    actions.add_argument('--rollback',action='store_true')
    args=parser.parse_args()
    run(args.home,args.gif,args.base,args.apply,args.rollback,args.pink_pointer)
