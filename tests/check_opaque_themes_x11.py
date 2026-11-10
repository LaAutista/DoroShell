"""Render and measure opaque themes on a private X11 display with NO compositor.

Timing is synthetic XTest-to-Qt-paint completion, not physical input-to-photon latency.
"""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from x11_isolation import isolated


def worker(binary, output, baseline, reverse):
    assert Path.home() == Path(os.environ['TMPDIR']).parent
    assert os.environ['DISPLAY'] == os.environ['DOROSHELL_TEST_DISPLAY'] != ':0'
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from PySide6.QtCore import QObject, QEvent, QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication
    from Xlib import display, X, XK
    from Xlib.ext import xtest, damage
    from menu.start_menu import StartMenu, has_compositor
    from themes import PALETTES, theme_files
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    d = display.Display()
    root = d.screen().root
    assert not d.get_selection_owner(d.intern_atom('_NET_WM_CM_S0'))
    assert not has_compositor()
    home = Path.home()
    output.mkdir(parents=True, exist_ok=True)
    conf = home/'panel.conf'
    conf.write_text('panels=panel1\n[panel1]\nplugins=worldclock\nposition=Bottom\nwidth=100\nwidth-percent=true\nreserve-space=false\npanelSize=40\ndoroshellTheme=true\n[worldclock]\ntype=worldclock\n')
    wm = subprocess.Popen(['openbox', '--sm-disable'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    def wait(seconds):
        loop = QEventLoop()
        QTimer.singleShot(int(seconds*1000), loop.quit)
        loop.exec()
    def cpu(pid):
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return (int(fields[11]) + int(fields[12])) / os.sysconf('SC_CLK_TCK')
    class Paints(QObject):
        count = 0
        def eventFilter(self, obj, event):
            if event.type() == QEvent.Type.Paint:
                self.count += 1
            return False
    paints = Paints()
    app.installEventFilter(paints)
    results = {}
    baseline_styles = json.loads(baseline.read_text())
    order = ('final', 'baseline') if reverse else ('baseline', 'final')
    panel = None
    menu = None
    try:
        wait(.3)
        for name, variant in ((name, variant) for name in PALETTES for variant in order):
            palette = PALETTES[name]
            styles = theme_files(palette) if variant == 'final' else baseline_styles[name]
            assert set(styles) == set(theme_files(palette))
            for file, content in styles.items():
                path = home/file
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            panel = subprocess.Popen([str(binary), '--config', str(conf)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            wait(.6)
            assert panel.poll() is None
            clients = root.get_full_property(d.intern_atom('_NET_CLIENT_LIST'), X.AnyPropertyType)
            panel_window = None
            for wid in clients.value if clients else []:
                candidate = d.create_resource_object('window', int(wid))
                pid = candidate.get_full_property(d.intern_atom('_NET_WM_PID'), X.AnyPropertyType)
                if pid and int(pid.value[0]) == panel.pid:
                    panel_window = candidate
                    break
            assert panel_window is not None
            d.damage_query_version()
            damage_id = panel_window.damage_create(damage.DamageReportRawRectangles)
            d.sync()
            menu = StartMenu()
            menu.move(10, 50)
            menu.show()
            menu.search.setFocus()
            wait(.4)
            # Actual root-pixel changes must not show through the opaque surfaces.
            samples = []
            for color in (0xff0000, 0x0000ff):
                root.change_attributes(background_pixel=color)
                root.clear_area()
                d.sync()
                wait(.15)
                shot = app.primaryScreen().grabWindow(0).toImage()
                samples.append((shot.pixelColor(15, 200).name(), shot.pixelColor(600, 748).name()))
            assert samples[0] == samples[1], (name, 'surface is not opaque', samples)
            app.primaryScreen().grabWindow(0).save(str(output/(name+'-'+variant+'.png')))
            while d.pending_events():
                d.next_event()
            menu_before, panel_before = time.process_time(), cpu(panel.pid)
            before_paints = paints.count
            start = time.monotonic()
            wait(5)
            elapsed = time.monotonic() - start
            idle = dict(seconds=elapsed, menu_cpu_ms=(time.process_time()-menu_before)*1000,
                        panel_cpu_ms=(cpu(panel.pid)-panel_before)*1000, menu_paints=paints.count-before_paints)
            d.sync()
            damage_events = 0
            while d.pending_events():
                event = d.next_event()
                if getattr(event, 'damage', None) == damage_id:
                    damage_events += 1
            idle['panel_damage_rectangles'] = damage_events
            d.damage_destroy(damage_id)
            latency = []
            for _ in range(50):
                menu.search.clear()
                app.processEvents()
                before = paints.count
                code = d.keysym_to_keycode(XK.string_to_keysym('z'))
                started = time.perf_counter()
                xtest.fake_input(d, X.KeyPress, code)
                xtest.fake_input(d, X.KeyRelease, code)
                d.sync()
                deadline = time.monotonic()+2
                while (menu.search.text() != 'z' or paints.count == before) and time.monotonic()<deadline:
                    app.processEvents()
                    time.sleep(.001)
                assert menu.search.text() == 'z' and paints.count > before
                latency.append((time.perf_counter()-started)*1000)
            results[name+'-'+variant] = dict(idle=idle, search_samples_ms=latency,
                                 search_roundtrip_median_ms=statistics.median(latency),
                                 search_roundtrip_p95_ms=sorted(latency)[47], opaque_samples=samples[0])
            print('MEASURED', name, variant, flush=True)
            menu.close()
            import shiboken6
            shiboken6.delete(menu)
            menu = None
            panel.terminate()
            panel.wait(timeout=5)
            panel = None
            wait(.1)
        assert not d.get_selection_owner(d.intern_atom('_NET_WM_CM_S0'))
        (output/'measurements.json').write_text(json.dumps(results, indent=2)+'\n')
        print(json.dumps(results, indent=2), flush=True)
        print('PASS four actual opaque menu/panel renders, background independence and synthetic response measurements; no compositor', flush=True)
    finally:
        if menu:
            menu.close()
        if panel and panel.poll() is None:
            panel.terminate()
            panel.wait(timeout=5)
        wm.terminate()
        wm.wait(timeout=5)
        d.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', action='store_true')
    p.add_argument('--worker', action='store_true')
    p.add_argument('--xvfb', type=Path)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--baseline-styles', type=Path, required=True, help='JSON of baseline theme_files for each palette; compared with current styles')
    p.add_argument('--reverse', action='store_true', help='Interleave final before baseline on a repeated run')
    args = p.parse_args()
    if args.worker:
        worker(args.binary, args.output, args.baseline_styles, args.reverse)
    elif args.run and args.xvfb:
        isolated(args.xvfb, [sys.executable, str(Path(__file__).resolve()), '--worker', '--binary', str(args.binary.resolve()), '--output', str(args.output.resolve()), '--baseline-styles', str(args.baseline_styles.resolve()), *(['--reverse'] if args.reverse else [])])
    else:
        p.error('Opt in with --run --xvfb PATH')
