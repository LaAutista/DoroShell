"""Opt-in NVIDIA decoder diagnosis using private Xvfb and per-process monitoring.
Requires nvidia-smi plus the wallpaper resource-test dependencies. Decoder logs
are diagnostic evidence, not proof of physical display/input latency. Output
logs may contain the supplied local media path; do not publish them unreviewed.
A temporary QT_FFMPEG_DECODING_HW_DEVICE_TYPES=, provides a software control.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
from x11_isolation import isolated


def worker(binary, media, output):
    home = Path.home()
    assert home == Path(os.environ['TMPDIR']).parent and home.name.startswith('doroshell-private-display-')
    assert os.environ['DISPLAY'] == os.environ['DOROSHELL_TEST_DISPLAY'] != ':0'
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from wallpaper.control import DEFAULT
    from PySide6.QtWidgets import QApplication, QWidget
    from PySide6.QtCore import QEventLoop, QTimer, Qt
    from Xlib import display, X
    from Xlib.ext import damage
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    d = display.Display()
    root = d.screen().root
    assert not d.get_selection_owner(d.intern_atom('_NET_WM_CM_S0'))
    media_hash = hashlib.sha256(media.read_bytes()).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    def wait(seconds):
        loop = QEventLoop()
        timer = QTimer()
        timer.setTimerType(Qt.TimerType.PreciseTimer)
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(int(seconds*1000))
        loop.exec()
    (home/'Desktop').mkdir()
    (home/'.config/pcmanfm-qt/lxqt').mkdir(parents=True)
    (home/'.config/user-dirs.dirs').write_text('XDG_DESKTOP_DIR="$HOME/Desktop"\n')
    (home/'.config/pcmanfm-qt/lxqt/settings.conf').write_text('[Desktop]\nDesktopShortcuts=\nWallpaperMode=none\nBgColor=#234567\n')
    config = home/'.config/doroshell/wallpaper.json'
    config.parent.mkdir()
    cfg = dict(DEFAULT, file=str(media))
    def save():
        temp = config.with_suffix('.tmp')
        temp.write_text(json.dumps(cfg))
        temp.replace(config)
    save()
    mock = home/'mock-login.py'
    mock.write_text('''from gi.repository import Gio, GLib
c = Gio.bus_get_sync(Gio.BusType.SESSION, None)
Gio.bus_own_name_on_connection(c, 'org.freedesktop.login1', Gio.BusNameOwnerFlags.NONE, None, None)
xml = '<node><interface name="org.freedesktop.DBus.Properties"><method name="Get"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/></method></interface></node>'
def call(c, sender, path, iface, method, args, invocation):
    invocation.return_value(GLib.Variant('(v)', (GLib.Variant('b', False),)))
c.register_object('/org/freedesktop/login1/session/auto', Gio.DBusNodeInfo.new_for_xml(xml).interfaces[0], call, None, None)
GLib.MainLoop().run()
''')
    log = open(output/'renderer.log', 'w')
    wm = subprocess.Popen(['openbox', '--sm-disable'], stdout=log, stderr=log)
    bus = subprocess.Popen([sys.executable, str(mock)], stdout=log, stderr=log)
    p = None
    full = QWidget()
    try:
        wait(.5)
        env = dict(os.environ, DBUS_SYSTEM_BUS_ADDRESS=os.environ['DBUS_SESSION_BUS_ADDRESS'], QT_MEDIA_BACKEND='ffmpeg',QT_LOGGING_RULES='qt.multimedia.*=true',QT_FFMPEG_DEBUG='1',QT_FORCE_STDERR_LOGGING='1')
        p = subprocess.Popen(['/usr/bin/pcmanfm-qt', '--desktop', '--profile=lxqt'], env=env, stdout=log, stderr=log)
        wait(3)
        assert p.poll() is None
        status = Path(os.environ['XDG_RUNTIME_DIR'])/('doroshell-wallpaper-'+app.primaryScreen().name()+'.json')
        def state():
            return json.loads(status.read_text()) if status.exists() else {}
        def desktop_window():
            clients = root.get_full_property(d.intern_atom('_NET_CLIENT_LIST'), X.AnyPropertyType)
            for wid in clients.value if clients else []:
                w = d.create_resource_object('window', int(wid))
                pid = w.get_full_property(d.intern_atom('_NET_WM_PID'), X.AnyPropertyType)
                if pid and int(pid.value[0]) == p.pid:
                    return w
            raise AssertionError('Desktop window missing')
        desktop = desktop_window()
        d.damage_query_version()
        damage_id = desktop.damage_create(damage.DamageReportRawRectangles)
        def usage():
            fields = Path(f'/proc/{p.pid}/stat').read_text().rsplit(')', 1)[1].split()
            ticks = int(fields[11])+int(fields[12])
            mem = dict(line.split(':', 1) for line in Path(f'/proc/{p.pid}/status').read_text().splitlines() if ':' in line)
            return ticks/os.sysconf('SC_CLK_TCK'), int(mem['VmRSS'].split()[0]), int(mem['Threads'])
        def helpers():
            result={}
            for pid in Path(f'/proc/{p.pid}/task/{p.pid}/children').read_text().split():
                proc=Path('/proc')/pid
                if proc.joinpath('exe').resolve().name != 'doroshell-video-worker': continue
                fields=proc.joinpath('stat').read_text().rsplit(')',1)[1].split()
                mem=dict(line.split(':',1) for line in proc.joinpath('status').read_text().splitlines() if ':' in line)
                result[pid]=dict(cpu=(int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK'),rss=int(mem['VmRSS'].split()[0]),threads=int(mem['Threads']))
            return result
        def sample(label):
            wait(2)
            d.sync()
            while d.pending_events():
                d.next_event()
            first = state()
            before_cpu, before_rss, threads = usage()
            helpers_before=helpers()
            start = time.monotonic()
            monitor=subprocess.Popen(['nvidia-smi','pmon','-s','u','-c','6','-d','1'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) if label=='playing_30fps' else None
            wait(6)
            elapsed = time.monotonic()-start
            after_cpu, after_rss, after_threads = usage()
            d.sync()
            damaged = 0
            while d.pending_events():
                event = d.next_event()
                if getattr(event, 'damage', None) == damage_id:
                    damaged += 1
            last = state()
            record = dict(seconds=elapsed, cpu_ms=(after_cpu-before_cpu)*1000,
                          cpu_one_core_percent=(after_cpu-before_cpu)/elapsed*100,
                          rss_start_kib=before_rss, rss_end_kib=after_rss,
                          threads_start=threads, threads_end=after_threads,
                          desktop_damage_rectangles=damaged, before=first, after=last)
            helpers_after=helpers()
            if monitor:
                stdout,stderr=monitor.communicate(timeout=5)
                record['gpu_process_samples']=[line for line in stdout.splitlines() if line.startswith('#') or any(pid in line.split() for pid in helpers_after)]
                record['gpu_monitor_error']=stderr
            record['helpers_before']=helpers_before
            record['helpers_after']=helpers_after
            record['combined_rss_kib']=after_rss+sum(h['rss'] for h in helpers_after.values())
            record['combined_cpu_percent']=record['cpu_one_core_percent']+sum((h['cpu']-helpers_before[pid]['cpu'])/elapsed*100 for pid,h in helpers_after.items() if pid in helpers_before)
            if label in ('disabled_initial','disabled_after_playback','latched_error','gif_source_rate'):
                assert not helpers_after,(label,'decoder helper survived Off/error/GIF')
            print('MEASURED', label, json.dumps(record), flush=True)
            return record
        results = {'stock_static': sample('stock_static')}
        d.damage_destroy(damage_id)
        d.sync()  # Destroy before the other client closes its desktop window.
        subprocess.run(['/usr/bin/pcmanfm-qt', '--desktop-off'], env=env, stdout=log, stderr=log, check=True, timeout=5)
        p.wait(timeout=5)
        p = subprocess.Popen([str(binary), '--desktop', '--profile=lxqt'], env=env, stdout=log, stderr=log)
        wait(3)
        desktop = desktop_window()
        damage_id = desktop.damage_create(damage.DamageReportRawRectangles)
        results['disabled_initial'] = sample('disabled_initial')
        assert 'disabled' in state()['reasons'] and not state()['playing']
        cfg['enabled'] = True
        save()
        results['playing_30fps'] = sample('playing_30fps')
        assert state()['playing'] and results['playing_30fps']['desktop_damage_rectangles'] > 0
        cfg['enabled']=False;save()
        results['disabled_after_playback']=sample('disabled_after_playback')
        assert results['disabled_after_playback']['desktop_damage_rectangles']==0
        d.damage_destroy(damage_id)
        d.sync()  # Destroy before the other client closes its desktop window.
        subprocess.run([str(binary), '--desktop-off'], env=env, stdout=log, stderr=log, check=True, timeout=5)
        p.wait(timeout=5)
        assert not status.exists(), 'Renderer left an active status file'
        assert not Path(f'/proc/{p.pid}').exists(), 'Renderer process/threads remain'
        assert not d.get_selection_owner(d.intern_atom('_NET_WM_CM_S0'))
        assert hashlib.sha256(media.read_bytes()).hexdigest() == media_hash
        # Personal paths and media names are not part of the result artifact.
        for record in results.values():
            for key in ('before','after'):
                record[key].pop('binary', None)
        (output/'measurements.json').write_text(json.dumps(results, indent=2)+'\n')
        print('PASS bounded playback/Off, decoder diagnostics, process cleanup and unchanged media; no compositor', flush=True)
    finally:
        full.close()
        for process in (p, bus, wm):
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
        d.close()
        log.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', action='store_true')
    p.add_argument('--worker', action='store_true')
    p.add_argument('--xvfb', type=Path)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--media', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.worker:
        worker(args.binary, args.media, args.output)
    elif args.run and args.xvfb:
        isolated(args.xvfb, [sys.executable, str(Path(__file__).resolve()), '--worker', '--binary', str(args.binary.resolve()), '--media', str(args.media.resolve()), '--output', str(args.output.resolve())])
    else:
        p.error('Opt in with --run --xvfb PATH')
