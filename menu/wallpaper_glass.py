# SPDX-License-Identifier: MIT
"""Optional frozen-wallpaper glass for the Start menu, without a compositor.

Source decoding is asynchronous and cached. No desktop/app pixels are captured.
The native panel uses the companion C++ implementation in its build patch.
"""
from pathlib import Path
import json
import os
import time
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QPainter, QColor, QLinearGradient

class WallpaperGlass:
    def __init__(self, path, screen_size, mode='crop', background='#202028', transform=True):
        from PIL import Image, ImageFilter, ImageOps
        self.path = Path(path)
        self.width, self.height = screen_size
        if not (0 < self.width <= 16384 and 0 < self.height <= 16384 and self.width*self.height <= 40000000):
            raise ValueError('Unsupported screen bounds')
        start = time.perf_counter()
        reduced = (max(1,self.width//8), max(1,self.height//8))
        if self.path.stat().st_size > 64*1024*1024:
            raise ValueError('Wallpaper exceeds 64 MiB')
        with Image.open(self.path) as source:
            if source.width*source.height > 40000000:
                raise ValueError('Wallpaper exceeds 40 megapixels')
            # Animated image input intentionally uses its first frame only.
            source.seek(0)
            source = (ImageOps.exif_transpose(source) if transform else source).convert('RGBA')
            if mode == 'crop':
                full = ImageOps.fit(source, reduced, Image.Resampling.LANCZOS)
            elif mode == 'fit':
                full = Image.new('RGBA', reduced, background)
                fit = ImageOps.contain(source, reduced, Image.Resampling.LANCZOS)
                full.alpha_composite(fit, ((reduced[0]-fit.width)//2, (reduced[1]-fit.height)//2))
            elif mode == 'stretch':
                full = source.resize(reduced, Image.Resampling.LANCZOS)
            else:
                raise ValueError('Unsupported wallpaper mode')
        full = Image.alpha_composite(Image.new('RGBA', reduced, background), full).convert('RGB')
        small = full.filter(ImageFilter.GaussianBlur(2.0))
        self.blurred = self._qimage(small)
        self.build_ms = (time.perf_counter()-start)*1000
        self.renders = 0
        self.cache = {}

    @staticmethod
    def _qimage(im):
        raw = im.tobytes('raw', 'RGB')
        return QImage(raw, im.width, im.height, im.width*3, QImage.Format.Format_RGB888).copy()

    def surface(self, rect, palette, panel=False):
        """rect is in screen-local device pixels. Caller owns DPR conversion."""
        x, y, w, h = rect
        if not 0 < w*h <= 16000000 or w <= 0 or h <= 0:
            raise ValueError('Unsupported surface bounds')
        key = (rect, tuple(sorted(palette.items())), panel)
        if key in self.cache:
            return self.cache[key]
        # Bound moved-menu cache. Real integration should invalidate on screen changes.
        if len(self.cache) >= 8:
            self.cache.clear()
        image = QImage(w, h, QImage.Format.Format_RGB32)
        image.fill(QColor(palette['window']))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(QRect(-x, -y, self.width, self.height), self.blurred)
        tint = QColor(palette['window'])
        tint.setAlpha(170 if palette['name'].startswith('Heretic') else 115)
        painter.fillRect(image.rect(), tint)
        # Soft reflection bands plus a bright bevel; alpha is composited into opaque pixels.
        highlight = QLinearGradient(0, 0, w*.65, h)
        for at, alpha in ((0,95),(.20,18),(.42,42),(.47,8),(.52,32),(1,0)):
            highlight.setColorAt(at, QColor(255,255,255,alpha))
        painter.fillRect(image.rect(), highlight)
        sheen = QLinearGradient(0, 0, 0, h)
        sheen.setColorAt(0, QColor(255,255,255,70))
        sheen.setColorAt(.49, QColor(255,255,255,10))
        sheen.setColorAt(.50, QColor(0,0,0,16))
        sheen.setColorAt(1, QColor(0,0,0,25))
        painter.fillRect(image.rect(), sheen)
        painter.end()
        self.renders += 1
        while self.cache and sum(v.sizeInBytes() for v in self.cache.values()) + image.sizeInBytes() > 16*1024*1024:
            self.cache.pop(next(iter(self.cache)))
        if image.sizeInBytes() <= 16*1024*1024:
            self.cache[key] = image
        return image


def rgba(color, alpha):
    c=QColor(color)
    return f'rgba({c.red()},{c.green()},{c.blue()},{alpha})'

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QEvent, QFileSystemWatcher, QTimer, Qt, QPoint
from PySide6.QtGui import QPainter,QPainterPath
from PySide6.QtWidgets import QWidget

class Backdrop(QWidget):
    def __init__(self,parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.image=None
        self.paints=0
    def paintEvent(self,event):
        self.paints+=1
        if self.image is None:return
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path=QPainterPath();path.addRoundedRect(self.rect(),15,15);p.setClipPath(path)
        p.drawImage(0,0,self.image)

class MenuGlassController(QObject):
    decoded=Signal(object,object,int)
    def __init__(self,menu,path,palette,mode='stretch',background='#202028',transform=True):
        super().__init__(menu)
        self.menu=menu;self.path=Path(path);self.palette=palette;self.mode=mode;self.background=background;self.transform=transform
        self.baseline=menu.styleSheet();self.atlas=None;self.generation=0;self.busy=False;self.pending=False;self.closed=False;self.enabled=True;self.active=False;self.signature=None
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='doro-glass')
        self.backdrop=Backdrop(menu.frame);self.backdrop.hide()
        self.presentation=QTimer(self);self.presentation.setSingleShot(True)
        self.presentation.setInterval(250);self.presentation.timeout.connect(self.finish_presentation)
        self.show_pending=False
        self.watcher=QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(self.source_changed);self.watcher.fileChanged.connect(self.source_changed)
        self.watcher.addPath(str(self.path.parent))
        if self.path.exists():self.watcher.addPath(str(self.path))
        self.decoded.connect(self.ready,Qt.ConnectionType.QueuedConnection)
        menu.installEventFilter(self);menu.frame.installEventFilter(self)
        self.coalesce=QTimer(self);self.coalesce.setSingleShot(True);self.coalesce.setInterval(0);self.coalesce.timeout.connect(self.geometry_changed)
        menu.destroyed.connect(self.shutdown)
        self.source_changed()
    def eventFilter(self,obj,event):
        if obj is self.menu and event.type()==QEvent.Type.ShowToParent:
            # Mapping can adjust global coordinates; sample them before the first paint.
            self.geometry_changed()
        if event.type() in (QEvent.Type.Show,QEvent.Type.Move,QEvent.Type.Resize,QEvent.Type.ScreenChangeInternal):
            self.coalesce.start()
        if obj is self.menu and event.type()==QEvent.Type.Hide:self.backdrop.hide()
        return False
    def source_changed(self,*_,force=False):
        if self.closed or not self.enabled:return
        try:
            stat=self.path.stat();signature=(stat.st_ino,stat.st_mtime_ns,stat.st_size)
        except OSError:signature=('missing',)
        if not force and signature==self.signature:return
        self.signature=signature
        self.generation+=1;self.pending=True
        if self.path.exists() and str(self.path) not in self.watcher.files():self.watcher.addPath(str(self.path))
        self.start_decode()
    def screen_spec(self):
        screen=self.menu.screen();dpr=screen.devicePixelRatio();size=screen.geometry().size()
        return (round(size.width()*dpr),round(size.height()*dpr)),dpr,screen.geometry().topLeft()
    def start_decode(self):
        if self.closed or not self.enabled or self.busy or not self.pending:return
        self.busy=True;self.pending=False;generation=self.generation
        size,dpr,origin=self.screen_spec()
        future=self.pool.submit(WallpaperGlass,self.path,size,self.mode,self.background,self.transform)
        def complete(future):
            try:value,error=future.result(),None
            except Exception as e:value,error=None,str(e)
            if not self.closed:
                try:self.decoded.emit(value,error,generation)
                except RuntimeError:pass  # Qt parent destruction can race completion.
        future.add_done_callback(complete)
    def ready(self,value,error,generation):
        if self.closed:return
        self.busy=False
        if generation==self.generation and self.enabled:
            self.atlas=value
            if error:
                self.backdrop.hide();self.menu.setStyleSheet(self.baseline);self.active=False
            else:self.geometry_changed()
            if self.show_pending and (self.active or error):self.finish_presentation()
        self.start_decode()
    def geometry_changed(self):
        if self.closed or not self.enabled or not self.atlas:return
        size,dpr,origin=self.screen_spec()
        if size != (self.atlas.width,self.atlas.height):self.source_changed(force=True);return
        rect=self.menu.frame.rect();point=self.menu.frame.mapToGlobal(QPoint(0,0))-origin
        try:
            image=self.atlas.surface((round(point.x()*dpr),round(point.y()*dpr),round(rect.width()*dpr),round(rect.height()*dpr)),self.palette)
        except (ValueError, MemoryError, RuntimeError):
            self.backdrop.hide();self.menu.setStyleSheet(self.baseline);self.active=False
            return
        image.setDevicePixelRatio(dpr)
        self.backdrop.image=image;self.backdrop.setGeometry(rect);self.backdrop.lower()
        if not self.active:
            self.menu.setStyleSheet(self.baseline+f'''QWidget#glassFrame {{ background: transparent; }}
QWidget#placesPanel {{ background: {rgba(self.palette['side'],135)}; }}
QWidget#applicationsPanel {{ background: {rgba(self.palette['base'],236)}; }}''')
            self.active=True
        self.backdrop.show();self.backdrop.update()
    def present(self):
        """Keep the first visible frame coherent without blocking the event loop."""
        self.menu.ensurePolished();self.menu.layout().activate()
        self.show_pending=True
        if self.atlas or not self.busy:
            self.finish_presentation()
        else:
            self.presentation.start()
    def finish_presentation(self):
        if self.closed or not self.show_pending:return
        self.show_pending=False;self.presentation.stop()
        if self.atlas:
            self.geometry_changed()
        if not self.active:
            # A late decode must not change an already visible fallback this opening.
            self.suspend()
        self.menu.show()
    def configure(self,path,mode='stretch',background='#000000',transform=False):
        if self.closed:return
        self.path=Path(path);self.mode=mode;self.background=background;self.transform=transform
        self.enabled=True;self.signature=None
        watched=self.watcher.directories()+self.watcher.files()
        if watched:self.watcher.removePaths(watched)
        if self.path.parent.is_dir():self.watcher.addPath(str(self.path.parent))
        self.source_changed(force=True)
    def suspend(self):
        if self.closed:return
        self.enabled=False;self.generation+=1;self.pending=False;self.atlas=None
        self.backdrop.hide();self.menu.setStyleSheet(self.baseline);self.active=False
        watched=self.watcher.directories()+self.watcher.files()
        if watched:self.watcher.removePaths(watched)
    def shutdown(self):
        self.closed=True;self.presentation.stop();self.show_pending=False
        self.pool.shutdown(wait=False,cancel_futures=True)
    def stop(self):
        self.shutdown();self.watcher.removePaths(self.watcher.directories()+self.watcher.files());self.coalesce.stop()
        self.backdrop.hide();self.menu.setStyleSheet(self.baseline);self.active=False


def resolve_wallpaper(home,config_root=None):
    """Read the standard PCManFM-Qt lxqt profile. Unsupported layouts stay opaque."""
    from PySide6.QtCore import QSettings
    home=Path(home)
    root=Path(config_root) if config_root else home/'.config'
    config=root/'doroshell/wallpaper-glass.json'
    try:
        if config.stat().st_size>16384:return None
        spec=json.loads(config.read_text())
        if not isinstance(spec,dict) or spec.get('version')!=1 or spec.get('enabled') is not True:return None
    except (OSError,ValueError,TypeError):return None
    source=root/'pcmanfm-qt/lxqt/settings.conf'
    try:
        if source.stat().st_size>2*1024*1024:return None
    except OSError:return None
    values=QSettings(str(source),QSettings.Format.IniFormat)
    if values.status()!=QSettings.Status.NoError:return None
    def boolean(key):return str(values.value('Desktop/'+key,'false')).lower()=='true'
    try:
        if boolean('PerScreenWallpaper') or int(values.value('Desktop/SlideShowInterval',0))>0:return None
    except (TypeError,ValueError):return None
    mode={'stretch':'stretch','fit':'fit','zoom':'crop'}.get(str(values.value('Desktop/WallpaperMode','none')))
    if mode is None:return None
    path=Path(str(values.value('Desktop/Wallpaper','')))
    if not path.is_absolute():return None
    color=str(values.value('Desktop/BgColor','#000000'))
    color=QColor(color).name() if QColor(color).isValid() else '#000000'
    transform=boolean('TransformWallpaper') and path.suffix.lower() in ('.jpg','.jpeg')
    return dict(path=path,mode=mode,background=color,transform=transform)


class ManagedGlass(QObject):
    def __init__(self,menu,home,config_root=None):
        super().__init__(menu)
        from PySide6.QtCore import QSettings
        from themes import PALETTES
        self.home=Path(home);self.root=Path(config_root) if config_root else self.home/'.config';self.menu=menu;self.controller=None;self.last=None
        theme=QSettings(str(self.root/'doroshell/theme.conf'),QSettings.Format.IniFormat)
        # Themes are coordinated at normal startup; do not recolor one surface mid-session.
        self.palette=PALETTES.get(str(theme.value('Theme/name','windows')),PALETTES['windows'])
        self.files=[self.root/'doroshell/wallpaper-glass.json',self.root/'pcmanfm-qt/lxqt/settings.conf']
        self.watcher=QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(self.schedule);self.watcher.directoryChanged.connect(self.schedule)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(0);self.timer.timeout.connect(self.reload)
        self.reload()
    def schedule(self,*_):self.timer.start()
    def reload(self):
        for path in self.files:
            for parent in (path.parent,path.parent.parent):
                if parent.is_dir() and str(parent) not in self.watcher.directories():self.watcher.addPath(str(parent))
            if path.is_file() and str(path) not in self.watcher.files():self.watcher.addPath(str(path))
        spec=resolve_wallpaper(self.home,self.root)
        if spec==self.last:return
        self.last=spec
        if spec:
            if self.controller:self.controller.configure(**spec)
            else:self.controller=MenuGlassController(self.menu,palette=self.palette,**spec)
        elif self.controller:self.controller.suspend()


def maybe_attach(menu):
    root=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))
    config=root/'doroshell/wallpaper-glass.json'
    if not config.is_file():return None  # Opt-in only; next menu open sees a new setting.
    return ManagedGlass(menu,Path.home(),root)
