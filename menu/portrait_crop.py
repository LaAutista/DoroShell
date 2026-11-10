"""Non-destructive square portrait framing. Only crop metadata is saved."""
from PySide6.QtCore import Qt, QRectF, QSize, Signal
from PySide6.QtGui import QImageReader, QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget, QDialog, QVBoxLayout, QLabel, QSlider, QPushButton, QDialogButtonBox


def validate_crop(value):
    if value is None:
        return None
    if (not isinstance(value, dict) or set(value) != {'x','y','zoom'} or
            any(type(value[k]) not in (int,float) for k in value) or
            not 0 <= value['x'] <= 1 or not 0 <= value['y'] <= 1 or not 1 <= value['zoom'] <= 4):
        raise ValueError('Invalid portrait crop')
    return dict(value)


def load_image(path):
    reader=QImageReader(str(path));reader.setAutoTransform(True)
    size=reader.size()
    if size.isValid() and max(size.width(),size.height())>4096:
        reader.setScaledSize(size.scaled(QSize(4096,4096),Qt.AspectRatioMode.KeepAspectRatio))
    image=reader.read()
    if image.isNull():
        raise ValueError('The selected picture could not be loaded: '+reader.errorString())
    return image


def source_rect(image, crop):
    crop=validate_crop(crop) or dict(x=.5,y=.5,zoom=1)
    side=min(image.width(),image.height())/crop['zoom']
    x=max(0,min(image.width()-side,crop['x']*image.width()-side/2))
    y=max(0,min(image.height()-side,crop['y']*image.height()-side/2))
    return QRectF(x,y,side,side)


def render_crop(image,crop,size=256):
    from PySide6.QtGui import QImage
    result=QImage(size,size,QImage.Format.Format_ARGB32_Premultiplied);result.fill(Qt.GlobalColor.transparent)
    painter=QPainter(result);painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.drawImage(QRectF(0,0,size,size),image,source_rect(image,crop));painter.end()
    return result


class CropPreview(QWidget):
    zoomRequested=Signal(int)
    def __init__(self,image,crop,parent=None):
        super().__init__(parent);self.image=image;self.crop=validate_crop(crop) or dict(x=.5,y=.5,zoom=1)
        self.setFixedSize(320,320);self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.OpenHandCursor);self.setAccessibleName('Portrait crop preview. Drag to reposition; use arrow keys to move.')
        self.last=None
    def normalize(self):
        rect=source_rect(self.image,self.crop)
        self.crop.update(x=rect.center().x()/self.image.width(),y=rect.center().y()/self.image.height());self.update()
    def paintEvent(self,event):
        painter=QPainter(self);painter.fillRect(self.rect(),QColor('#555555'))
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(QRectF(self.rect()),self.image,source_rect(self.image,self.crop))
        painter.setPen(QPen(QColor('white'),2));painter.drawRect(self.rect().adjusted(1,1,-2,-2))
    def move_image(self,dx,dy):
        side=source_rect(self.image,self.crop).width()
        self.crop['x']-=dx/self.width()*side/self.image.width()
        self.crop['y']-=dy/self.height()*side/self.image.height()
        self.crop['x']=max(0,min(1,self.crop['x']));self.crop['y']=max(0,min(1,self.crop['y']));self.normalize()
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:self.last=event.position();self.setCursor(Qt.CursorShape.ClosedHandCursor);event.accept()
    def mouseMoveEvent(self,event):
        if self.last is not None:
            delta=event.position()-self.last;self.last=event.position();self.move_image(delta.x(),delta.y());event.accept()
    def mouseReleaseEvent(self,event):
        self.last=None;self.setCursor(Qt.CursorShape.OpenHandCursor)
    def keyPressEvent(self,event):
        directions={Qt.Key.Key_Left:(-8,0),Qt.Key.Key_Right:(8,0),Qt.Key.Key_Up:(0,-8),Qt.Key.Key_Down:(0,8)}
        if event.key() in directions:self.move_image(*directions[event.key()]);event.accept()
        else:super().keyPressEvent(event)
    def wheelEvent(self,event):
        self.zoomRequested.emit(10 if event.angleDelta().y()>0 else -10);event.accept()


class PortraitCropDialog(QDialog):
    def __init__(self,path,crop=None,parent=None):
        super().__init__(parent);self.setWindowTitle('Adjust Start menu portrait')
        self.setModal(True);layout=QVBoxLayout(self)
        layout.addWidget(QLabel('Drag the picture to reposition it. Zoom to frame your portrait.\nThe original picture will not be changed.'))
        self.preview=CropPreview(load_image(path),crop,self);self.preview.normalize()
        layout.addWidget(self.preview,alignment=Qt.AlignmentFlag.AlignHCenter)
        self.zoom=QSlider(Qt.Orientation.Horizontal);self.zoom.setRange(100,400);self.zoom.setValue(round(self.preview.crop['zoom']*100));self.zoom.setAccessibleName('Portrait zoom')
        self.zoom_label=QLabel('Zoom '+str(self.zoom.value())+'%');layout.addWidget(self.zoom_label)
        layout.addWidget(self.zoom);self.zoom.valueChanged.connect(self.set_zoom)
        self.preview.zoomRequested.connect(lambda change:self.zoom.setValue(self.zoom.value()+change))
        reset=QPushButton('Reset framing');reset.clicked.connect(self.reset);layout.addWidget(reset)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Apply portrait')
        self.buttons.accepted.connect(self.accept);self.buttons.rejected.connect(self.reject);layout.addWidget(self.buttons)
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setDefault(True)
    def set_zoom(self,value):
        self.zoom_label.setText('Zoom '+str(value)+'%')
        self.preview.crop['zoom']=value/100;self.preview.normalize()
    def reset(self):
        self.preview.crop=dict(x=.5,y=.5,zoom=1);self.zoom.setValue(100);self.preview.normalize()
    def crop(self):
        return dict(self.preview.crop)
