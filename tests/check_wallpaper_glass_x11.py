"""Private installed Start/native-panel wallpaper-glass enable/change/restore acceptance."""
import argparse,importlib.util,json,os,subprocess,sys,time
from pathlib import Path
from x11_isolation import isolated
ROOT=Path(__file__).resolve().parents[1]

def worker(binary,output):
    assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY']!=':0'
    home=Path(os.environ['TMPDIR']).parent
    assert home==Path.home() and home.name.startswith('doroshell-private-display-') and home.parent==Path('/tmp')
    sys.path.insert(0,str(ROOT))
    import install,modules
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QEventLoop,QTimer
    from PIL import Image
    from Xlib import display
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    d=display.Display();assert not d.get_selection_owner(d.intern_atom('_NET_WM_CM_S0'))
    def wait(t):
        loop=QEventLoop();QTimer.singleShot(round(t*1000),loop.quit);loop.exec()
    def until(condition):
        end=time.monotonic()+5
        while not condition() and time.monotonic()<end:wait(.02)
        assert condition()
    wall=home/'fixture.png';Image.new('RGB',(1024,768),'red').save(wall)
    pc=home/'.config/pcmanfm-qt/lxqt/settings.conf';pc.parent.mkdir(parents=True)
    original='[Desktop]\nWallpaper='+str(wall)+'\nWallpaperMode=stretch\nBgColor=#000000\nPerScreenWallpaper=false\nSlideShowInterval=0\nTransformWallpaper=false\n[Private]\nKeep=untouched\n';pc.write_text(original)
    install.install(home,apply=True);install.install(home,apply=True)
    modules.run(home,'wallpaper-glass',apply=True);modules.run(home,'wallpaper-glass',apply=True)
    for filename in ('wallpaper_glass.py','portrait_crop.py','start_menu.py'):
        assert (home/'.local/share/lxqt-comfort'/filename).read_bytes()==(ROOT/'menu'/filename).read_bytes()
    spec=importlib.util.spec_from_file_location('installed_menu',home/'.local/share/lxqt-comfort/start_menu.py')
    installed=importlib.util.module_from_spec(spec);spec.loader.exec_module(installed)
    wm=subprocess.Popen(['openbox','--sm-disable'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);wait(.2)
    conf=home/'private-panel.conf';conf.write_text('panels=panel1\n[panel1]\nplugins=worldclock\nposition=Bottom\nwidth=100\nwidth-percent=true\nreserve-space=false\npanelSize=40\ndoroshellTheme=true\n[worldclock]\ntype=worldclock\n')
    panel=subprocess.Popen([str(binary),'--config',str(conf)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    menu=installed.StartMenu();menu.move(10,50);menu.show()
    def panel_color():return app.primaryScreen().grabWindow(0).toImage().pixelColor(850,750)
    def menu_color():return menu.wallpaper_glass.controller.backdrop.image.pixelColor(80,100)
    try:
        until(lambda:menu.wallpaper_glass is not None and menu.wallpaper_glass.controller is not None and menu.wallpaper_glass.controller.active)
        until(lambda:panel_color().red()>panel_color().blue()+20)
        assert menu_color().red()>menu_color().blue()+20
        output.mkdir(parents=True,exist_ok=True);app.primaryScreen().grabWindow(0).save(str(output/'installed-red.png'))
        replacement=wall.with_name('replacement.png');Image.new('RGB',(1024,768),'blue').save(replacement);replacement.replace(wall)
        until(lambda:menu_color().blue()>menu_color().red()+20 and panel_color().blue()>panel_color().red()+20)
        controller=menu.wallpaper_glass.controller
        other=home/'other.png';Image.new('RGB',(1024,768),'green').save(other)
        pc.write_text(original.replace(str(wall),str(other)))
        until(lambda:menu_color().green()>menu_color().red()+10 and panel_color().green()>panel_color().red()+10)
        assert menu.wallpaper_glass.controller is controller  # bounded one-worker reconfiguration
        pc.write_text(original.replace('WallpaperMode=stretch','WallpaperMode=tile'));wait(.3)
        assert not controller.active
        pc.write_text(original);until(lambda:controller.active)
        menu.search.clearFocus();wait(.2);before=controller.backdrop.paints;start=time.process_time();wait(3)
        idle=dict(seconds=3,menu_cpu_ms=(time.process_time()-start)*1000,backdrop_paints=controller.backdrop.paints-before)
        assert idle['backdrop_paints']==0
        modules.run(home,'wallpaper-glass',rollback=True);until(lambda:not controller.active)
        assert menu.styleSheet()==controller.baseline
        assert not (home/'.config/doroshell/wallpaper-glass.json').exists()
        assert pc.read_text()==original
        assert not d.get_selection_owner(d.intern_atom('_NET_WM_CM_S0'))
        menu.close();install.rollback(home)
        assert not (home/'.local/share/lxqt-comfort/wallpaper_glass.py').exists()
        assert pc.read_text()==original
        (output/'installed-glass.json').write_text(json.dumps(idle,indent=2))
        print('PASS installed Start/native panel enable/repeat, automatic PCManFM file and source-path changes, one worker, unsupported-mode fallback/recovery, exact config/menu rollback, no compositor',idle,flush=True)
    finally:
        menu.close();panel.terminate();panel.wait(timeout=5);wm.terminate();wm.wait(timeout=5);d.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--xvfb',type=Path);p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.worker:worker(a.binary,a.output)
    elif a.run and a.xvfb:isolated(a.xvfb,[sys.executable,__file__,'--worker','--binary',str(a.binary.resolve()),'--output',str(a.output.resolve())])
    else:p.error('Opt in with --run --xvfb PATH')
