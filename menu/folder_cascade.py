"""Lazy, bounded folder menus. No recursive indexing, thumbnails or file reads."""
import json
import os
from pathlib import Path
import sys

MAX_SCAN = 2000
MAX_ITEMS = 200
MAX_DEPTH = 5
MAX_OUTPUT = 1024 * 1024
TIMEOUT_MS = 1500


def list_folder(path):
    items=[];limited=False
    try:
        with os.scandir(path) as entries:
            for index,entry in enumerate(entries):
                if index>=MAX_SCAN:
                    limited=True;break
                if entry.name.startswith('.') or entry.is_symlink():continue
                try:
                    directory=entry.is_dir(follow_symlinks=False)
                    if directory or entry.is_file(follow_symlinks=False):
                        items.append(dict(name=entry.name,directory=directory))
                except OSError:continue
        items.sort(key=lambda item:(not item['directory'],item['name'].casefold(),item['name']))
        return dict(items=items[:MAX_ITEMS],limited=limited or len(items)>MAX_ITEMS,error='')
    except OSError as error:
        return dict(items=[],limited=False,error=error.strerror or 'Folder is unavailable')


def validate_result(value):
    if not isinstance(value,dict) or type(value.get('limited')) is not bool or not isinstance(value.get('error'),str):
        raise ValueError('Invalid folder response')
    items=value.get('items')
    if not isinstance(items,list) or len(items)>MAX_ITEMS or len(value['error'])>1000:raise ValueError('Invalid folder response')
    for item in items:
        name=item.get('name') if isinstance(item,dict) else None
        if not isinstance(name,str) or not name or len(name)>512 or '/' in name or '\0' in name or name in ('.','..') or type(item.get('directory')) is not bool:
            raise ValueError('Invalid folder entry')
    return value


if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1]!='--list-hex':raise SystemExit(2)
    # A desktop/menu crash must not leave a stuck directory helper behind.
    import ctypes,signal
    parent=os.getppid()
    if sys.platform.startswith('linux'):
        if ctypes.CDLL(None).prctl(1,signal.SIGKILL,0,0,0)!=0 or os.getppid()!=parent or parent==1:raise SystemExit(3)
    result=list_folder(os.fsdecode(bytes.fromhex(sys.argv[2])));print(json.dumps(result,ensure_ascii=True));raise SystemExit(0)

from PySide6.QtCore import QProcess,QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication,QMenu


def label(name):
    return ''.join(ch if ch.isprintable() else '�' for ch in name).replace('&','&&')


class FolderCascadeMenu(QMenu):
    def __init__(self,path,open_path,parent=None,depth=0):
        super().__init__(parent)
        self.path=Path(os.path.abspath(path));self.open_path=open_path;self.depth=depth
        self.job={'process':None,'closed':False};self.buffer=bytearray();self.failed=False;self.submenus=[]
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(TIMEOUT_MS)
        self.timer.timeout.connect(lambda:self.fail('Folder took too long to respond. Open it in the file manager.'))
        self.aboutToShow.connect(self.load);self.aboutToHide.connect(self.cancel)
        job=self.job
        def destroyed(*_):
            job['closed']=True
            process=job['process'];job['process']=None
            if process:process.kill()
        self.destroyed.connect(destroyed)
    def header(self):
        for child in self.submenus:child.close();child.deleteLater()
        self.submenus=[]
        self.clear();self.addAction('Open this folder',lambda:self.open_path(str(self.path)));self.addSeparator()
    def cancel(self):
        self.timer.stop();process=self.job['process'];self.job['process']=None
        if process:
            process.kill()
            if process.state()==QProcess.ProcessState.NotRunning:process.deleteLater()
    def load(self):
        self.cancel();self.header();self.failed=False;self.buffer.clear()
        if self.depth>=MAX_DEPTH:
            self.addAction('Open the folder to browse deeper').setEnabled(False);return
        self.addAction('Loading…').setEnabled(False)
        process=QProcess(QApplication.instance());self.job['process']=process;job=self.job
        process.readyReadStandardOutput.connect(lambda:self.read(process) if not job['closed'] else None)
        process.finished.connect(lambda code,status:self.finished(process,code) if not job['closed'] else None)
        process.finished.connect(process.deleteLater)
        process.errorOccurred.connect(lambda error:self.fail('Could not read this folder.') if not job['closed'] and job['process'] is process else None)
        self.timer.start();process.start(sys.executable,[str(Path(__file__).resolve()),'--list-hex',os.fsencode(self.path).hex()])
    def read(self,process):
        if self.job['process'] is not process:return
        self.buffer.extend(bytes(process.readAllStandardOutput()))
        if len(self.buffer)>MAX_OUTPUT:self.fail('Folder response exceeded the safe limit.')
    def fail(self,message):
        self.cancel();self.failed=True;self.header();self.addAction(message).setEnabled(False)
    def finished(self,process,code):
        if self.job['process'] is not process:return
        self.read(process)
        if self.job['process'] is not process:return
        self.job['process']=None;self.timer.stop()
        try:
            if code:raise ValueError('Folder helper failed')
            result=validate_result(json.loads(self.buffer))
        except (ValueError,TypeError):
            self.fail('Could not read this folder.');return
        self.header()
        if result['error']:
            self.addAction(result['error']).setEnabled(False);return
        if not result['items']:self.addAction('No visible files or folders').setEnabled(False)
        for item in result['items']:
            path=self.path/item['name']
            if item['directory']:
                child=FolderCascadeMenu(path,self.open_path,self,self.depth+1)
                self.submenus.append(child)
                action=self.addMenu(child);action.setText(label(item['name']));action.setIcon(QIcon.fromTheme('folder'))
            else:
                action=self.addAction(QIcon.fromTheme('text-x-generic'),label(item['name']),lambda checked=False,p=str(path):self.open_path(p))
            action.setData(path.as_uri())
        if result['limited']:self.addSeparator();self.addAction('List limited. Open folder to see everything.').setEnabled(False)
