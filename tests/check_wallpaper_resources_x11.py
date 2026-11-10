"""Bounded CPU/RSS and repaint checks for native wallpaper, without a compositor.

Private X11 only. Does not measure physical input latency or GPU power.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
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
        env = dict(os.environ, DBUS_SYSTEM_BUS_ADDRESS=os.environ['DBUS_SESSION_BUS_ADDRESS'], QT_MEDIA_BACKEND='ffmpeg')
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
        def sample(label):
            wait(2)
            d.sync()
            while d.pending_events():
                d.next_event()
            first = state()
            before_cpu, before_rss, threads = usage()
            start = time.monotonic()
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
        full.showFullScreen()
        results['fullscreen_paused'] = sample('fullscreen_paused')
        assert 'fullscreen' in state()['reasons'] and not state()['playing']
        cfg['paused'] = True
        save()
        full.close()
        results['manual_paused'] = sample('manual_paused')
        assert 'manual' in state()['reasons'] and not state()['playing']
        assert results['manual_paused']['desktop_damage_rectangles'] == 0, 'Manual pause still repaints'
        cfg['enabled'] = False
        cfg['paused'] = False
        save()
        results['disabled_after_playback'] = sample('disabled_after_playback')
        assert 'disabled' in state()['reasons'] and not state()['playing']
        bad = home/'invalid.mp4'
        bad.write_text('not media')
        cfg.update(enabled=True, file=str(bad), generation=1)
        save()
        results['latched_error'] = sample('latched_error')
        assert 'renderer error' in state()['reasons']
        from PIL import Image
        gif = home/'fast-synthetic.gif'
        Image.new('RGB', (32, 32), 'red').save(gif, save_all=True, append_images=[Image.new('RGB', (32, 32), 'blue')], duration=20, loop=0)
        cfg.update(file=str(gif), generation=2, fps=15)
        save()
        results['gif_source_rate'] = sample('gif_source_rate')
        gif_result = results['gif_source_rate']
        assert (gif_result['after']['frames']-gif_result['before']['frames']) / gif_result['seconds'] > 20, 'GIF source cadence not observed'
        for label in ('disabled_initial', 'fullscreen_paused', 'manual_paused', 'disabled_after_playback', 'latched_error'):
            record = results[label]
            assert record['desktop_damage_rectangles'] == 0, (label, 'unnecessary repaint')
            for key in ('frames', 'paints', 'video_position_ms'):
                assert record['before'][key] == record['after'][key], (label, key, 'advanced while idle')
        for label in ('disabled_initial', 'disabled_after_playback'):
            assert not results[label]['before']['media_loaded'] and not results[label]['after']['media_loaded']
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
        print('PASS state checks, paused repaint stop, process/thread/status cleanup and unchanged media; no compositor', flush=True)
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
