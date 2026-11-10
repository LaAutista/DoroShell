"""DoroClipboard private-X11 acceptance; never use the personal clipboard."""
import argparse,os,sys,time,subprocess
from pathlib import Path
from x11_isolation import isolated
ROOT=Path(__file__).resolve().parents[1]

def worker():
    assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY']!=':0'
    sys.path.insert(0,str(ROOT))
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QMimeData,Qt
    from PySide6.QtGui import QClipboard,QImage,QColor
    from clipboard.clipboard import ClipboardWindow
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    window=ClipboardWindow(app);window.open()
    def wait(t=.15):
        end=time.monotonic()+t
        while time.monotonic()<end:app.processEvents();time.sleep(.005)
    def produce(kind='text'):
        code='''from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QMimeData,QTimer
from PySide6.QtGui import QClipboard,QImage,QColor
import sys
app=QApplication([]);mime=QMimeData();kind=sys.argv[1]
if kind=='image':
 image=QImage(40,30,QImage.Format.Format_ARGB32);image.fill(QColor('pink'));mime.setImageData(image)
else:
 mime.setText('secret' if kind=='secret' else kind)
 if kind=='secret':mime.setData('x-kde-passwordManagerHint',b'secret')
 if kind=='rich':mime.setHtml('<b>rich</b>')
app.clipboard().setMimeData(mime,QClipboard.Mode.Selection if kind=='primary' else QClipboard.Mode.Clipboard)
QTimer.singleShot(450,app.quit);app.exec()
'''
        process=subprocess.Popen([sys.executable,'-c',code,kind],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        while process.poll() is None:wait(.02)
        wait()
    produce('first');produce('second');assert len(window.history.entries)==2
    assert app.clipboard().text()=='second','Not retained after source exited'
    produce('primary');assert len(window.history.entries)==2 and app.clipboard().text()=='second'
    produce('secret');assert len(window.history.entries)==2
    produce('rich');assert app.clipboard().mimeData().html()=='<b>rich</b>'
    produce('image');assert window.history.entries[0].image.width()==40
    window.search.setText('first');window.activate();wait();assert app.clipboard().text()=='first'
    window.pause.setChecked(True);count=len(window.history.entries);produce('private');assert len(window.history.entries)==count
    window.pause.setChecked(False);window.open();window.search.clear();window.items.setCurrentRow(0);window.remove();assert len(window.history.entries)==count-1
    window.clear_history();assert not window.history.entries
    # A real nonresponding X11 owner must never stall the history event loop.
    slow_code='''from Xlib import display,X
import time
d=display.Display();w=d.screen().root.create_window(0,0,1,1,0,d.screen().root_depth)
w.set_selection_owner(d.intern_atom('CLIPBOARD'),X.CurrentTime);d.sync()
time.sleep(4)
'''
    slow=subprocess.Popen([sys.executable,'-c',slow_code],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    from PySide6.QtCore import QTimer
    ticks=[];heartbeat=QTimer();heartbeat.setInterval(25);heartbeat.timeout.connect(lambda:ticks.append(time.monotonic()));heartbeat.start()
    wait(1.9);assert len(ticks)>40,('UI stalled on slow X11 owner',len(ticks))
    assert window.capture is None,'Capture helper was not timed out'
    assert not window.history.entries
    window.search.setText('still responsive');window.search.clear()
    slow.terminate();slow.wait(timeout=2);heartbeat.stop();wait(.1)
    produce('newest');assert window.history.entries[0].text=='newest'
    slow=subprocess.Popen([sys.executable,'-c',slow_code],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    wait(.15);produce('superseding');wait(.2)
    assert window.history.entries[0].text=='superseding','Stale capture replaced newer copy'
    slow.terminate();slow.wait(timeout=2)
    slow=subprocess.Popen([sys.executable,'-c',slow_code],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    wait(.15);window.pause.setChecked(True);wait(.15);assert window.capture is None
    slow.terminate();slow.wait(timeout=2);window.pause.setChecked(False)
    window.clear_history()
    # Verify singleton and an actual hidden service across external sources.
    window.clipboard.changed.disconnect(window.changed);window.hide()
    service=subprocess.Popen([sys.executable,str(ROOT/'clipboard/clipboard.py')],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        wait(.6);assert service.poll() is None
        duplicate=subprocess.run([sys.executable,str(ROOT/'clipboard/clipboard.py'),'--show'],timeout=3,capture_output=True)
        assert duplicate.returncode==0,duplicate.stderr
        produce('singleton copy');assert app.clipboard().text()=='singleton copy'
        assert service.poll() is None
        def ticks():
            fields=Path(f'/proc/{service.pid}/stat').read_text().split(); return int(fields[13])+int(fields[14])
        before=ticks(); wait(2); after=ticks()
        assert after-before <= 2, ('Idle service unexpectedly busy',after-before)
        print('Idle CPU ticks:',after-before)
        slow=subprocess.Popen([sys.executable,'-c',slow_code],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        wait(.25)
        children=Path(f'/proc/{service.pid}/task/{service.pid}/children').read_text().split()
        captures=[int(pid) for pid in children if b'--capture' in Path(f'/proc/{pid}/cmdline').read_bytes()]
        assert captures,'No acquisition helper found for parent-crash test'
        service.kill();service.wait(timeout=2);wait(2.3)
        for pid in captures:
            path=Path(f'/proc/{pid}/stat')
            assert not path.exists() or path.read_text().split()[2]=='Z','Helper survived parent crash'
        slow.terminate();slow.wait(timeout=2)
        # Explicit stop/restore must end collection, not just hide its window.
        service=subprocess.Popen([sys.executable,str(ROOT/'clipboard/clipboard.py')],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        wait(.5);assert service.poll() is None
        stopped=subprocess.run([sys.executable,str(ROOT/'clipboard/clipboard.py'),'--stop'],timeout=3,capture_output=True)
        assert stopped.returncode==0;service.wait(timeout=3)
        assert subprocess.run([sys.executable,str(ROOT/'clipboard/clipboard.py'),'--stop'],timeout=3,capture_output=True).returncode==0

        print('PASS: retention, source exit, PRIMARY separation, rich text/image, secret marker, pause/search/reuse/delete/clear, slow-owner timeout/UI responsiveness, singleton')
    finally:
        if service.poll() is None: service.terminate();service.wait(timeout=3)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--worker',action='store_true');parser.add_argument('--xvfb',type=Path);args=parser.parse_args()
    if args.worker:worker()
    else:isolated(args.xvfb,[sys.executable,__file__,'--worker'])
