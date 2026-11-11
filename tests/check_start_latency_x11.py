"""Private end-to-end cold/repeat Start timing and resident lifecycle acceptance.

No screenshots, clipboard access, physical clicks, or personal display connection.
"""
import argparse, os, sys, json, time, select, subprocess, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
parser=argparse.ArgumentParser();parser.add_argument('--run',action='store_true');parser.add_argument('--worker',action='store_true');parser.add_argument('--child',type=Path);parser.add_argument('--xvfb',type=Path);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--preferences',type=Path)
args=parser.parse_args()

def child():
    import runpy
    values=runpy.run_path(str(args.child),run_name='timed_start')
    cls=values['StartMenu'];paint=cls.paintEvent;hide=cls.hideEvent
    fd=int(os.environ['START_TIMING_FD'])
    def paint_event(menu,event):
        paint(menu,event)
        if not getattr(menu,'timing_recorded',False):
            menu.timing_recorded=True
            c=menu.wallpaper_glass.controller if menu.wallpaper_glass else None
            os.write(fd,(json.dumps(dict(at=time.monotonic(),pid=os.getpid(),glass=bool(c and c.active),
                launching=menu.launching,search=menu.search.text(),category=menu.category.currentText(),
                primary=menu.primary_action,window_id=id(menu),palette=c.palette['name'] if c else None))+'\n').encode())
    def hide_event(menu,event):
        menu.timing_recorded=False;hide(menu,event)
    cls.paintEvent=paint_event;cls.hideEvent=hide_event
    sys.argv=[str(args.child)];values['main']()

def worker():
    assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY']!=':0'
    home=Path.home();assert home==Path(os.environ['TMPDIR']).parent and home.name.startswith('doroshell-private-display-')
    import install
    from PIL import Image
    install.install(home,apply=True)
    cfg=home/'.config'
    if args.preferences:
        for part in ('lxqt-comfort/favorites.json','lxqt-comfort/folders.json','lxqt-comfort/recent.json',
                     'lxqt-comfort/session-button.json','doroshell/start-theme.qss','doroshell/theme.conf',
                     'doroshell/wallpaper-glass.json','pcmanfm-qt/lxqt/settings.conf'):
            source=args.preferences/part;target=cfg/part
            if source.is_file():target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    else:
        wall=home/'wall.png';Image.new('RGB',(3840,2160),'#37547d').save(wall)
        pc=cfg/'pcmanfm-qt/lxqt/settings.conf';pc.parent.mkdir(parents=True);pc.write_text('[Desktop]\nWallpaper='+str(wall)+'\nWallpaperMode=stretch\n')
        glass=cfg/'doroshell/wallpaper-glass.json';glass.parent.mkdir();glass.write_text('{"version":1,"enabled":true}')
    target=home/'.local/share/lxqt-comfort/start_menu.py';launcher=home/'.local/bin/lxqt-comfort-menu'
    read_fd,write_fd=os.pipe();env=dict(os.environ,START_TIMING_FD=str(write_fd))
    processes=[];buffer=b''
    def read_paint():
        nonlocal buffer
        deadline=time.monotonic()+5
        while b'\n' not in buffer:
            if not select.select([read_fd],[],[],max(0,deadline-time.monotonic()))[0]:raise RuntimeError('No first-paint notification')
            chunk=os.read(read_fd,8192)
            if not chunk:raise RuntimeError('Timing pipe closed')
            buffer+=chunk
        line,buffer=buffer.split(b'\n',1);return json.loads(line)
    def toggle():
        subprocess.run([sys.executable,str(launcher)],check=True,timeout=5,stdout=subprocess.DEVNULL)
    def ticks(pid):
        parts=Path(f'/proc/{pid}/stat').read_text().split();return int(parts[13])+int(parts[14])
    def memory(pid):
        vals={line.split(':')[0]:line.split(':')[1].strip() for line in Path(f'/proc/{pid}/status').read_text().splitlines() if ':' in line}
        return {key:vals[key] for key in ('VmRSS','RssAnon','VmHWM')}
    try:
        started=time.monotonic()
        p=subprocess.Popen([sys.executable,__file__,'--child',str(target),'--output',str(args.output)],env=env,pass_fds=(write_fd,));processes.append(p)
        cold=read_paint();cold_ms=(cold.pop('at')-started)*1000
        samples=[];identities=[]
        for _ in range(5):
            toggle()  # Hide; acknowledgement means the request was handled.
            started=time.monotonic();toggle();record=read_paint();samples.append((record.pop('at')-started)*1000);identities.append(record['window_id'])
            assert record['glass'] and not record['launching'] and record['search']=='' and record['category']=='Home'
        assert len(set(identities))==1 and record['pid']==p.pid
        toggle();before=ticks(p.pid)
        # One blocking event timeout measures idle; it is not a polling loop.
        assert not select.select([read_fd],[],[],1)[0]
        idle_ticks=ticks(p.pid)-before;resident_memory=memory(p.pid)
        primary=cfg/'lxqt-comfort/session-button.json';primary.write_text('{"version":1,"action":"lockscreen"}')
        toggle();changed=read_paint();assert changed['primary']=='lockscreen' and changed['window_id']!=identities[-1]
        toggle()
        theme=cfg/'doroshell/theme.conf';theme.write_text('[Theme]\nname=polar\n')
        toggle();rethemed=read_paint();assert rethemed['palette']=='Polar Doro' and rethemed['glass']
        toggle()
        # A helper upgrade retires this resident; the clicking process becomes the new one.
        target.touch()
        from Xlib import display,X
        d=display.Display();d.screen().root.change_attributes(event_mask=X.SubstructureNotifyMask);d.sync()
        replacement=subprocess.Popen([sys.executable,str(launcher)],stdout=subprocess.DEVNULL);processes.append(replacement)
        deadline=time.monotonic()+5;mapped=False
        while not mapped:
            while d.pending_events():
                if d.next_event().type==X.MapNotify:mapped=True
            if mapped:break
            if not select.select([d.fileno()],[],[],max(0,deadline-time.monotonic()))[0]:raise RuntimeError('Upgrade did not reopen Start')
        p.wait(timeout=5);assert p.returncode==0 and replacement.poll() is None
        d.close()
        result=dict(cold_first_paint_ms=cold_ms,cold=cold,repeated_first_paint_ms=samples,idle_cpu_ticks=idle_ticks,memory=resident_memory,
                    checks=['first-frame glass','same resident/window reused','reset state','preferences rebuilt','hidden theme change','code upgrade retired resident'])
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
        assert max(samples)<100, samples
        assert idle_ticks==0
    finally:
        for process in processes:
            if process.poll() is None:process.terminate()
            process.wait(timeout=5)
        os.close(read_fd);os.close(write_fd)

if args.child:child()
elif args.worker:worker()
elif args.run and args.xvfb:
    from x11_isolation import isolated
    command=[sys.executable,__file__,'--worker','--output',str(args.output.resolve())]
    if args.preferences:command+=['--preferences',str(args.preferences.resolve())]
    isolated(args.xvfb,command)
else:parser.error('Use --run --xvfb PATH')
