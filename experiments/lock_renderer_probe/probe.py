# SPDX-License-Identifier: GPL-2.0-or-later
"""Opt-in fake-host rendering probe. Not a locker or installable saver adapter."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys
import time


def fixture_home():
    home = Path.home().resolve()
    display = os.environ.get('DISPLAY', '')
    if (not home.name.startswith('doroshell-private-display-')
            or display != os.environ.get('DOROSHELL_TEST_DISPLAY')
            or not display.startswith(':') or not display[1:].isdigit()
            or not 120 <= int(display[1:]) < 220
            or not Path(os.environ.get('XAUTHORITY', '/nonexistent')).is_file()):
        raise ValueError('Authenticated private fixture required; refusing other displays')
    return home


def validate_media(value, home):
    path = Path(value)
    if not path.is_absolute() or not path.is_relative_to(home):
        raise ValueError('Only an explicit absolute fixture media path is accepted')
    path = path.resolve(strict=True)
    if not path.is_relative_to(home):
        raise ValueError('Media escapes fixture HOME')
    info = path.stat()
    if (not stat.S_ISREG(info.st_mode) or not info.st_mode & 0o444
            or not 6 <= info.st_size <= 1024*1024 or path.suffix.lower() != '.gif'):
        raise ValueError('Only bounded readable fixture GIF files are accepted')
    with path.open('rb') as stream:
        if stream.read(6) not in (b'GIF87a', b'GIF89a'):
            raise ValueError('Not a GIF; playlists and commands are not accepted')
    return path


def validate_target(connection, window_id, token):
    from Xlib import X, error
    root = connection.screen().root
    if not window_id or window_id == root.id:
        raise ValueError('Zero/root targets are forbidden')
    try:
        window = connection.create_resource_object('window', window_id)
        marker = window.get_full_property(connection.intern_atom('_DOROSHELL_FAKE_RENDER_HOST'), X.AnyPropertyType)
        geometry = window.get_geometry()
        if (marker is None or bytes(marker.value) != token.encode()
                or window.get_attributes().win_class != X.InputOutput
                or not 16 <= geometry.width <= 1024 or not 16 <= geometry.height <= 768):
            raise ValueError('Not the marked bounded fake host')
        return window
    except error.XError as exc:
        raise ValueError('Stale or unavailable target') from exc


def command(mpv, target, media, output='x11', comparison='fixture60'):
    # No shell, user scripts, audio, player control, IPC or screen-saver inhibition.
    # This mpv build detects invalid refresh on Xvfb; override in fixture only.
    extra = {'baseline': [], 'fixture60': ['--display-fps-override=60']}[comparison]
    return [str(mpv), '--no-config', '--load-scripts=no', '--ytdl=no', '--osc=no',
            '--osd-level=0', '--no-terminal', '--input-terminal=no',
            '--input-default-bindings=no', '--input-builtin-bindings=no',
            '--input-builtin-dragging=no', '--input-vo-keyboard=no', '--input-cursor=no',
            '--stop-screensaver=no', '--no-audio', '--sid=no', '--sub-auto=no',
            '--audio-file-auto=no', '--cover-art-auto=no', '--hwdec=no', '--vo='+output,
            '--loop-file=inf', '--keepaspect=yes', '--wid='+str(target)]+extra+['--', str(media)]


def worker(mpv, evidence, comparison='fixture60'):
    home = fixture_home()
    from PIL import Image, ImageDraw
    from Xlib import X, display
    evidence.mkdir(parents=True, exist_ok=True)
    connection = display.Display()
    root = connection.screen().root
    token = secrets.token_hex(16)
    processes = []
    logs = []
    results = {'scope': 'fake host only; no locker process or security claim', 'passed': [], 'measurements': {}}

    def check(condition, name):
        if not condition:
            raise AssertionError(name)
        results['passed'].append(name)

    def wait_for(predicate, seconds=3):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            connection.sync()
            if predicate():
                return True
            time.sleep(.025)
        return False

    def image(window):
        g = window.get_geometry()
        data = window.get_image(0, 0, g.width, g.height, X.ZPixmap, 0xffffffff)
        return Image.frombytes('RGB', (g.width, g.height), data.data, 'raw', 'BGRX')

    def colorful(window):
        colors = image(window).getdata()
        return sum(1 for r, g, b in colors if abs(r-b)>100 and max(r,b)>150)>1000

    def spawn(window_id, media, output='x11', executable=None):
        target = validate_target(connection, window_id, token)
        media = validate_media(str(media), home)
        log = open(evidence/('decoder-%d.log' % len(logs)), 'wb'); logs.append(log)
        argv = command(executable or mpv, target.id, media, output, comparison)
        process = subprocess.Popen(argv,
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   cwd=home, start_new_session=True)
        processes.append(process)
        return process

    def stop(process):
        started = time.monotonic()
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=3)
        return (time.monotonic()-started)*1000

    def rejected(action, name):
        before = len(processes)
        try:
            action()
        except (ValueError, FileNotFoundError, PermissionError):
            check(len(processes)==before, name)
        else:
            raise AssertionError('accepted '+name)

    def target(parent, x=20):
        w = parent.create_window(x, 45, 320, 180, 0, connection.screen().root_depth,
                                 X.InputOutput, X.CopyFromParent, background_pixel=0x000000)
        w.change_property(connection.intern_atom('_DOROSHELL_FAKE_RENDER_HOST'),
                          connection.intern_atom('UTF8_STRING'), 8, token.encode())
        w.map();connection.sync()
        return w

    frame = root.create_window(10, 10, 780, 250, 0, connection.screen().root_depth,
                               X.InputOutput, X.CopyFromParent, background_pixel=0x303030)
    frame.set_wm_name('Renderer preview - NOT A LOCK SCREEN')
    frame.map();connection.sync()
    gc=frame.create_gc(foreground=0xffffff)
    frame.draw_text(gc, 15, 25, 'RENDERER PREVIEW - NOT A LOCK SCREEN');gc.free()
    frame.set_input_focus(X.RevertToParent, X.CurrentTime);connection.sync()
    first = target(frame)
    second = None
    initial_focus = connection.get_input_focus().focus.id
    baseline_top = {w.id for w in root.query_tree().children}
    sentinel = home/'settings-sentinel';sentinel.write_bytes(b'unchanged fixture settings\n')
    sentinel_hash = hashlib.sha256(sentinel.read_bytes()).hexdigest()
    media = home/'synthetic.gif'
    frames=[]
    for index in range(8):
        bitmap=Image.new('RGB',(160,90),(230,20,35) if index%2==0 else (25,40,230))
        ImageDraw.Draw(bitmap).rectangle((index*18,30,index*18+12,55),fill=(20,230,60))
        frames.append(bitmap)
    frames[0].save(media,save_all=True,append_images=frames[1:],duration=100,loop=0)
    try:
        for value in (0, root.id):
            rejected(lambda value=value: spawn(value,media),'reject target '+str(value == 0 and 'zero' or 'root'))
        stale=target(frame);stale_id=stale.id;stale.destroy();connection.sync()
        rejected(lambda:spawn(stale_id,media),'reject stale target')
        rejected(lambda:spawn(frame.id,media),'reject unmarked target')
        rejected(lambda:spawn(first.id,home/'missing.gif'),'reject missing file')
        rejected(lambda:spawn(first.id,'https://invalid.example/media.gif'),'reject URL')
        rejected(lambda:spawn(first.id,'file:///tmp/media.gif'),'reject file URI')
        rejected(lambda:spawn(first.id,'relative.gif'),'reject relative path')
        playlist=home/'playlist.gif';playlist.write_text('#EXTM3U\nhttps://invalid.example\n')
        rejected(lambda:spawn(first.id,playlist),'reject playlist masquerading as GIF')
        unreadable=home/'unreadable.gif';unreadable.write_bytes(media.read_bytes());unreadable.chmod(0)
        rejected(lambda:spawn(first.id,unreadable),'reject unreadable file');unreadable.chmod(0o600)
        link=home/'outside.gif';link.symlink_to('/etc/passwd')
        rejected(lambda:spawn(first.id,link),'reject outside-home symlink')
        rejected(lambda:spawn(first.id,media,executable=home/'missing-mpv'),'reject absent decoder')
        started=time.monotonic();process=spawn(first.id,media)
        check(wait_for(lambda:colorful(first)),'first animated frame within 3s')
        results['measurements']['request_to_color_ms']=(time.monotonic()-started)*1000
        children=first.query_tree().children
        check(bool(children),'renderer creates child below explicitly supplied target')
        check(all(w.query_tree().parent.id==first.id for w in children),'render child hierarchy')
        new_top=[w for w in root.query_tree().children if w.id not in baseline_top]
        mapped=[w for w in new_top if w.get_attributes().map_state==X.IsViewable and w.get_attributes().win_class==X.InputOutput]
        check(not mapped,'no unrelated mapped toplevel renderer')
        results['measurements']['new_unmapped_or_input_only_root_windows']=len(new_top)
        check(connection.get_input_focus().focus.id==initial_focus,'input focus unchanged')
        # Probe for competing grabs; immediately release our private test grabs.
        grabbed=frame.grab_keyboard(False,X.GrabModeAsync,X.GrabModeAsync,X.CurrentTime)
        connection.ungrab_keyboard(X.CurrentTime)
        pointer=frame.grab_pointer(False,0,X.GrabModeAsync,X.GrabModeAsync,X.NONE,X.NONE,X.CurrentTime)
        connection.ungrab_pointer(X.CurrentTime);connection.sync()
        check(grabbed==X.GrabSuccess and pointer==X.GrabSuccess,'renderer holds no keyboard/pointer grab')
        time.sleep(2)  # Exclude startup before measuring steady-state looping.
        results['measurements']['comparison']=comparison
        results['measurements']['warmup_seconds']=2
        results['measurements']['decoder_thread_count']=len(list(Path('/proc/%s/task'%process.pid).iterdir()))
        hashes=[];start_ticks=int(Path('/proc/%s/stat'%process.pid).read_text().split()[13])+int(Path('/proc/%s/stat'%process.pid).read_text().split()[14])
        sample_start=time.monotonic()
        for _ in range(160):
            hashes.append(hashlib.sha256(image(first).tobytes()).hexdigest());time.sleep(.05)
        elapsed=time.monotonic()-sample_start
        ticks=Path('/proc/%s/stat'%process.pid).read_text().split()
        rss=next(line for line in Path('/proc/%s/status'%process.pid).read_text().splitlines() if line.startswith('VmRSS:'))
        results['measurements'].update(sample_seconds=elapsed,observed_frame_transitions=sum(a!=b for a,b in zip(hashes,hashes[1:])),unique_sample_hashes=len(set(hashes)),decoder_cpu_seconds=(int(ticks[13])+int(ticks[14])-start_ticks)/os.sysconf('SC_CLK_TCK'),decoder_rss=rss)
        check(len(set(hashes))>=4,'animation changes across sampled frames')
        transitions = results['measurements']['observed_frame_transitions']
        check(8 <= transitions/elapsed <= 12,'sampled cadence remains near synthetic 10 fps')
        first.configure(width=360,height=200);connection.sync()
        check(wait_for(lambda:any(w.get_geometry().width==360 and w.get_geometry().height==200 for w in first.query_tree().children)),'renderer follows parent resize')
        # The host remains mapped; only its supplied rendering target is hidden.
        first.unmap();connection.sync()
        check(first.get_attributes().map_state==X.IsUnmapped and
              all(w.get_attributes().map_state==X.IsUnviewable for w in first.query_tree().children),
              'unmapping target hides renderer descendants')
        host_box=(30,55,390,255)  # Root coordinates after the resize above.
        check(image(root).crop(host_box).getextrema()==((48,48),(48,48),(48,48)),
              'unmapped target reveals only synthetic host background')
        check(process.poll() is None,'renderer survives target unmap')
        started=time.monotonic();first.map();connection.sync()
        check(wait_for(lambda:colorful(first)),'target remap restores rendered pixels')
        results['measurements']['remap_to_color_ms']=(time.monotonic()-started)*1000
        remapped=[]
        for _ in range(12):
            remapped.append(hashlib.sha256(image(first).tobytes()).hexdigest());time.sleep(.05)
        check(len(set(remapped))>=3,'animation continues after target remap')
        check(connection.get_input_focus().focus.id==initial_focus,'unmap/remap preserves host focus')
        # A fixture-owned sibling above the renderer, explicitly not authentication UI.
        overlay=first.create_window(20,40,320,100,0,connection.screen().root_depth,
                                    X.InputOutput,X.CopyFromParent,background_pixel=0xffffff)
        overlay.set_wm_name('SYNTHETIC GRAPHICS OVERLAY - NOT AUTHENTICATION')
        overlay.map();overlay.configure(stack_mode=X.Above);connection.sync()
        gc=overlay.create_gc(foreground=0x000000)
        overlay.draw_text(gc,8,30,'SYNTHETIC GRAPHICS OVERLAY')
        overlay.draw_text(gc,8,55,'NOT AUTHENTICATION');gc.free();connection.sync()
        overlay_box=(50,95,370,195)
        expected_overlay=image(root).crop(overlay_box).tobytes()
        check(image(root).getpixel((52,97))==(255,255,255),'overlay covers renderer pixels')
        for _ in range(10):
            time.sleep(.05)
            check(image(root).crop(overlay_box).tobytes()==expected_overlay,
                  'overlay coverage stable sample %d'%_)
        check(first.query_tree().children[-1].id==overlay.id,'host overlay remains above render child')
        check(connection.get_input_focus().focus.id==initial_focus,'overlay does not take focus')
        grabbed=frame.grab_keyboard(False,X.GrabModeAsync,X.GrabModeAsync,X.CurrentTime)
        connection.ungrab_keyboard(X.CurrentTime)
        pointer=frame.grab_pointer(False,0,X.GrabModeAsync,X.GrabModeAsync,X.NONE,X.NONE,X.CurrentTime)
        connection.ungrab_pointer(X.CurrentTime);connection.sync()
        check(grabbed==X.GrabSuccess and pointer==X.GrabSuccess,'overlay phase holds no keyboard/pointer grab')
        image(root).save(evidence/'synthetic-overlay.png')
        second=target(frame,410);other=spawn(second.id,media)
        check(wait_for(lambda:colorful(second)) and colorful(first),'two synthetic targets animate independently')
        image(root).save(evidence/'fake-host.png')
        check(not Path('/proc/%s/task/%s/children'%(process.pid,process.pid)).read_text().strip(),'no decoder subprocess before termination')
        results['measurements']['sigterm_exit_ms']=stop(process)
        check(process.poll() is not None,'SIGTERM reaps decoder within 3s')
        check(wait_for(lambda:[w.id for w in first.query_tree().children]==[overlay.id]),
              'terminated renderer removes only its child')
        check(first.get_attributes().map_state==X.IsViewable,'target remains mapped after renderer termination')
        check(image(root).crop(overlay_box).tobytes()==expected_overlay,
              'host overlay survives renderer termination')
        overlay.destroy();connection.sync()
        check(image(root).crop(host_box).getextrema()==((0,0),(0,0),(0,0)),
              'mapped target provides black coverage without renderer or overlay')
        check(connection.get_input_focus().focus.id==initial_focus,'termination preserves host focus')
        image(root).save(evidence/'host-after-renderer-exit.png')
        # Natural parent destruction behavior is observed, not emulated by a watchdog.
        second.destroy();connection.sync();started=time.monotonic()
        check(wait_for(lambda:other.poll() is not None),'decoder exits after target destruction within 3s')
        results['measurements']['parent_destroy_exit_ms']=(time.monotonic()-started)*1000
        second=None
        # An unusual local filename is one argv element, never executable shell text.
        unusual=home/'$(touch SHOULD_NOT_EXIST); glyph.gif';unusual.write_bytes(media.read_bytes())
        first.clear_area();connection.sync()
        restarted=spawn(first.id,unusual);check(wait_for(lambda:bool(first.query_tree().children) and colorful(first)),'renderer restarts with quoted/shell-like filename')
        stop(restarted);check(not (home/'SHOULD_NOT_EXIST').exists(),'filename does not execute shell')
        invalid=spawn(first.id,media,output='nonexistent-fixture-output')
        check(wait_for(lambda:invalid.poll() is not None) and invalid.returncode!=0,'unsupported output exits with failure')
        check(not [w for w in root.query_tree().children if w.id not in baseline_top and w.get_attributes().map_state==X.IsViewable and w.get_attributes().win_class==X.InputOutput],'unsupported output leaves no fallback window')
        corrupt=home/'corrupt.gif';corrupt.write_bytes(b'GIF89a'+b'broken fixture')
        broken=spawn(first.id,corrupt)
        check(wait_for(lambda:broken.poll() is not None) and broken.returncode!=0,'decoder rejects corrupt fixture')
        check(first.get_attributes().map_state==X.IsViewable,'fake host survives renderer failures')
        check(hashlib.sha256(sentinel.read_bytes()).hexdigest()==sentinel_hash,'fixture settings sentinel unchanged')
        check(not any((home/p).exists() for p in ['.xscreensaver','.config/autostart','.config/mpv']), 'no locker/autostart/player config created')
        # Observe unmodified embedding with an overlay that predates both launches.
        early_overlay=first.create_window(20,40,320,100,0,connection.screen().root_depth,
                                         X.InputOutput,X.CopyFromParent,background_pixel=0xffffff)
        early_overlay.set_wm_name('SYNTHETIC OVERLAY BEFORE LAUNCH - NOT AUTHENTICATION')
        early_overlay.map();connection.sync()
        gc=early_overlay.create_gc(foreground=0x000000)
        early_overlay.draw_text(gc,8,30,'SYNTHETIC OVERLAY BEFORE LAUNCH')
        early_overlay.draw_text(gc,8,55,'NOT AUTHENTICATION');gc.free();connection.sync()
        early_pixels=image(root).crop(overlay_box).tobytes()
        image(root).save(evidence/'overlay-before-launch.png')
        ordering=[]
        results['overlay_before_launch']=ordering
        for phase in ('launch','restart'):
            started=time.monotonic();ordered=spawn(first.id,media)
            check(wait_for(lambda:colorful(first)),'overlay-first '+phase+' renders within 3s')
            latency=(time.monotonic()-started)*1000
            time.sleep(.25)
            children=first.query_tree().children
            visible=image(root).crop(overlay_box).tobytes()==early_pixels
            top=children[-1].id==early_overlay.id
            ordering.append({'phase':phase,'overlay_pixels_preserved':visible,
                             'overlay_is_top_child':top,'request_to_color_ms':latency})
            image(root).save(evidence/('overlay-after-'+phase+'.png'))
            check(connection.get_input_focus().focus.id==initial_focus,'overlay-first '+phase+' preserves focus')
            grabbed=frame.grab_keyboard(False,X.GrabModeAsync,X.GrabModeAsync,X.CurrentTime)
            connection.ungrab_keyboard(X.CurrentTime)
            pointer=frame.grab_pointer(False,0,X.GrabModeAsync,X.GrabModeAsync,X.NONE,X.NONE,X.CurrentTime)
            connection.ungrab_pointer(X.CurrentTime);connection.sync()
            check(grabbed==X.GrabSuccess and pointer==X.GrabSuccess,'overlay-first '+phase+' holds no input grab')
            ordering[-1]['sigterm_exit_ms']=stop(ordered)
            check(wait_for(lambda:[w.id for w in first.query_tree().children]==[early_overlay.id]),
                  'overlay-first '+phase+' removes only renderer child')
            ordering[-1]['overlay_pixels_restored_after_exit'] = image(root).crop(overlay_box).tobytes()==early_pixels
            image(root).save(evidence/('overlay-after-'+phase+'-exit.png'))
            check(first.get_attributes().map_state==X.IsViewable and
                  early_overlay.get_attributes().map_state==X.IsViewable,
                  'overlay-first '+phase+' retains mapped host and overlay windows after exit')
        results['overlay_before_launch']=ordering
        early_overlay.destroy();connection.sync()
        check(all(p.poll() is not None for p in processes),'all owned decoder processes exited')
        check(all(item['overlay_pixels_preserved'] and item['overlay_is_top_child'] for item in ordering),
              'pre-existing overlay remains visible across renderer launch and restart')
        results['result']='PASS'
    except Exception as exc:
        results['result']='FAIL'
        results['failure']=str(exc)
        raise
    finally:
        for process in processes:
            if process.poll() is None:
                try:stop(process)
                except subprocess.TimeoutExpired:
                    process.kill();process.wait();results['cleanup_forced_kill']=True
        results['process_returncodes']=[p.returncode for p in processes]
        (evidence/'results.json').write_text(json.dumps(results,indent=2)+'\n')
        for log in logs:log.close()
        frame.destroy();connection.sync();connection.close()
    print(json.dumps(results,indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true');parser.add_argument('--worker',action='store_true')
    parser.add_argument('--xvfb',type=Path);parser.add_argument('--mpv',type=Path,required=True)
    parser.add_argument('--comparison',choices=('baseline','fixture60'),default='fixture60')
    parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args()
    if args.worker:
        worker(args.mpv.resolve(),args.evidence.resolve(),args.comparison)
    elif args.run and args.xvfb:
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests'))
        from x11_isolation import isolated
        isolated(args.xvfb.resolve(),[sys.executable,str(Path(__file__).resolve()),'--worker','--mpv',str(args.mpv.resolve()),'--evidence',str(args.evidence.resolve()),'--comparison',args.comparison],geometry='800x600x24')
    else:parser.error('Opt in with --run --xvfb PATH; never supply a real display/window')
