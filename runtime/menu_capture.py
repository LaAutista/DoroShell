#!/usr/bin/env python3
"""Freeze the desktop before editing. Only confirmed images reach the clipboard."""
import argparse
import math
import os
import select
import subprocess
import sys
import tempfile
from pathlib import Path
from PySide6.QtCore import QEvent, QByteArray, QBuffer, QIODevice, QPoint, QRect, QSize, Qt, QTimer, QLockFile, QStandardPaths, QSaveFile
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygon, QRegion, QCursor, QIcon
from PySide6.QtWidgets import (QApplication, QDialog, QGridLayout, QLabel, QPushButton,
                               QWidget, QFileDialog, QMessageBox, QToolButton, QInputDialog, QColorDialog, QSpinBox)


def compose_screens(frames):
    bounds = QRect()
    scale = 1.
    for geometry, image in frames:
        if image.isNull() or geometry.isEmpty():
            raise ValueError('A screen could not be captured')
        bounds = bounds.united(geometry)
        scale = max(scale, image.width()/geometry.width(), image.height()/geometry.height())
    size = bounds.size()*scale
    if size.isEmpty() or size.width()*size.height() > 100_000_000:
        raise ValueError('Unsupported virtual desktop dimensions')
    if len(frames)==1:
        return frames[0][1], bounds
    result = QImage(size, QImage.Format.Format_RGB32)
    if result.isNull():
        raise MemoryError('Could not allocate the desktop image')
    result.fill(Qt.GlobalColor.black)
    with QPainter(result) as painter:
        for geometry, image in frames:
            local = geometry.translated(-bounds.topLeft())
            start = local.topLeft()*scale
            end = QPoint(local.x()+local.width(),local.y()+local.height())*scale
            painter.drawImage(QRect(start, QSize(end.x()-start.x(), end.y()-start.y())), image)
    return result, bounds


def snapshot_desktop():
    screen=QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
    return compose_screens([(s.geometry(), s.grabWindow(0).toImage()) for s in screen.virtualSiblings()])


def x11_window_rectangles():
    """Topmost first, in native root pixels, before the overlay is mapped."""
    from contextlib import closing
    try:
        from Xlib import X, display, error
    except ImportError:
        return []
    rectangles = []
    try:
        with closing(display.Display()) as server:
            root = server.screen().root
            def prop(window, name):
                value = window.get_full_property(server.intern_atom(name), X.AnyPropertyType)
                return value.value if value is not None else ()
            ignored = {server.intern_atom('_NET_WM_WINDOW_TYPE_' + kind) for kind in ('DOCK', 'DESKTOP')}
            for wid in reversed(prop(root, '_NET_CLIENT_LIST_STACKING')):
                try:
                    window = server.create_resource_object('window', int(wid))
                    if window.get_attributes().map_state != X.IsViewable or ignored.intersection(prop(window, '_NET_WM_WINDOW_TYPE')):
                        continue
                    geom = window.get_geometry()
                    pos = root.translate_coords(window, 0, 0)
                    rect = QRect(pos.x, pos.y, geom.width, geom.height)
                    extents = prop(window, '_NET_FRAME_EXTENTS')
                    if len(extents) == 4:
                        left, right, top, bottom = map(int, extents)
                        rect.adjust(-left, -top, right, bottom)
                    rectangles.append(rect)
                except error.XError:
                    continue  # A client may disappear while freezing the desktop.
    except (error.DisplayError, error.XError, OSError):
        return []
    return rectangles


class FrozenCapture(QDialog):
    def __init__(self, image, geometry, windows=()):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        if image.isNull() or geometry.isEmpty():
            raise ValueError('No completed screen image was supplied')
        self.image = QImage(image)
        self.selection = QRect()
        self.origin = None
        self.original = QRect()
        self.raw_selection = QRect()
        self.windows = [r.intersected(image.rect()) for r in windows if r.intersects(image.rect())]
        self.hover_window = QRect()
        self.drag = ''
        self.lens_pixel = None
        self.strokes = []
        self.redo_stack = []
        self.active_tool = 'Select'
        self.colors = {'ink': QColor('#f04761'), 'highlight': QColor('#ffda00')}
        self.widths = {'ink': 3, 'highlight': 15}
        self.setWindowTitle('DoroShell capture')
        self.setGeometry(geometry)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        self.screen_bounds = [geometry.intersected(s.geometry()).translated(-geometry.topLeft())
                              for s in screen.virtualSiblings()]
        self.viewport = geometry.intersected(screen.geometry()).translated(-geometry.topLeft())
        if self.viewport.isEmpty():
            self.viewport = self.rect()
        style = """
            QWidget { background: #eff0f1; color: #232629; border-radius: 4px; }
            QPushButton, QToolButton, QSpinBox { padding: 4px; border: 1px solid transparent; }
            QToolButton:checked { background: #c1e5f7; border-color: #3daee9; }
            QPushButton:hover, QToolButton:hover { background: #d5eaf5; }
            QPushButton:focus, QToolButton:focus, QSpinBox:focus { border-color: #2980b9; }
            QPushButton:disabled { color: #81868a; }
        """
        self.tools = QWidget(self)
        self.controls = QWidget(self)
        for bar in (self.tools,self.controls):
            bar.setCursor(Qt.CursorShape.ArrowCursor)
            bar.setStyleSheet(style)
        tools = QGridLayout(self.tools)
        tools.setContentsMargins(5,4,5,4)
        tools.setSpacing(2)
        self.tool_buttons = {}
        icons = [('Select','transform-move','↔'),('Pen','draw-freehand','✎'),
                 ('Highlight','draw-highlight','▰'),('Rectangle','draw-rectangle','□'),
                 ('Ellipse','draw-ellipse','○'),('Arrow','draw-arrow-forward','↗'),
                 ('Text','draw-text','T'),('Redact','edit-redact','■')]
        for i,(name,theme,fallback) in enumerate(icons):
            button = QToolButton()
            button.setCheckable(True)
            button.setToolTip(name)
            button.setAccessibleName(name)
            icon=QIcon.fromTheme(theme)
            if icon.isNull():
                button.setText(fallback)
            else:
                button.setIcon(icon)
            button.setMinimumSize(28,28)
            button.clicked.connect(lambda checked=False, tool=name: self.set_tool(tool))
            tools.addWidget(button,0,i)
            self.tool_buttons[name]=button

        self.color_button = QPushButton('Color')
        self.color_button.setAutoDefault(False)
        self.color_button.clicked.connect(self.choose_color)
        self.stroke_width = QSpinBox()
        self.stroke_width.setAccessibleName('Stroke width')
        self.stroke_width.setToolTip('Stroke width in pixels')
        self.stroke_width.setRange(1,64)
        self.stroke_width.setSuffix(' px')
        self.stroke_width.valueChanged.connect(self.set_width)
        narrow=self.viewport.width()<530
        tools.addWidget(self.color_button,int(narrow),0 if narrow else 8,1,4 if narrow else 1)
        tools.addWidget(self.stroke_width,int(narrow),4 if narrow else 9,1,4 if narrow else 1)

        actions = QGridLayout(self.controls)
        actions.setContentsMargins(5,4,5,4)
        self.help = QLabel()
        actions.addWidget(self.help,0,0)
        self.actions = {}
        columns = 4 if self.viewport.width() < 760 else 8
        for i,(label,action) in enumerate([('Window',self.pick_window),('Undo',self.undo),('Redo',self.redo),('Copy',self.accept),
                ('Save…',self.choose_save),('Open in ScreenGrab',self.native_window),('Cancel',self.reject)],1):
            button=QPushButton(label)
            self.actions[label]=button
            button.setAutoDefault(False)
            button.clicked.connect(action)
            actions.addWidget(button,i//columns,i%columns)
        window_button = self.actions['Window']
        window_button.setCheckable(True)
        window_button.setEnabled(bool(self.windows))
        window_button.setToolTip('Choose a visible window (W)' if self.windows else 'No visible X11 application windows')
        self.native_binary = Path.home()/'.local/share/doroshell/screengrab-import'
        native=self.actions['Open in ScreenGrab']
        native.setEnabled(os.access(self.native_binary,os.X_OK))
        native.setToolTip('Open these pixels in the native window' if native.isEnabled()
                          else 'Install the ScreenGrab PNG importer to open this image.')
        self.set_tool('Select')
        for child in self.findChildren(QWidget):
            child.installEventFilter(self)

    def pick_window(self):
        if self.windows:
            self.set_tool('Select' if self.active_tool == 'Window' else 'Window')

    def window_at(self, position):
        point = self.raw_point(position)
        return next((r for r in self.windows if r.contains(point)), QRect())

    def view_rect(self, rect):
        if rect.isEmpty():
            return QRect()
        x = self.width() / self.image.width()
        y = self.height() / self.image.height()
        left, top = math.floor(rect.x()*x), math.floor(rect.y()*y)
        right, bottom = math.ceil((rect.x()+rect.width())*x), math.ceil((rect.y()+rect.height())*y)
        return QRect(left, top, right-left, bottom-top)

    def ink_group(self):
        return 'highlight' if self.active_tool=='Highlight' else 'ink'

    def set_tool(self, name):
        self.lens_pixel = None
        self.active_tool=name
        self.hover_window = QRect()
        self.actions['Window'].setChecked(name == 'Window')
        self.actions['Save…'].setEnabled(name != 'Window')
        self.actions['Copy'].setEnabled(name != 'Window')
        self.actions['Open in ScreenGrab'].setEnabled(name != 'Window' and os.access(self.native_binary,os.X_OK))
        for tool,button in self.tool_buttons.items():
            button.setChecked(tool==name)
        group=self.ink_group()
        self.stroke_width.setValue(self.widths[group])
        self.stroke_width.setEnabled(name not in ('Select','Window','Redact','Text'))
        self.color_button.setEnabled(name not in ('Select','Window','Redact'))
        color=self.colors[group]
        self.color_button.setStyleSheet('border-bottom: 3px solid '+color.name())
        self.color_button.setAccessibleName('Annotation color '+color.name())
        self.updated()

    def set_width(self, width):
        self.widths[self.ink_group()]=width

    def choose_color(self):
        group=self.ink_group()
        color=QColorDialog.getColor(self.colors[group],self,'Annotation color')
        if color.isValid():
            self.colors[group]=color
            self.set_tool(self.active_tool)

    def native_window(self):
        try:
            transfer_png(self.rendered_image(),[str(self.native_binary),'--import-png'],b'IMPORTED\n')
        except (OSError,RuntimeError) as error:
            QMessageBox.warning(self,'Open in ScreenGrab',str(error))
            return
        self.accept()

    def choose_save(self):
        name,_ = QFileDialog.getSaveFileName(self, 'Save screenshot', 'Screenshot.png', 'PNG image (*.png)')
        if not name:
            return
        file = QSaveFile(name)
        if not file.open(QIODevice.OpenModeFlag.WriteOnly) or not self.rendered_image().save(file,'PNG') or not file.commit():
            QMessageBox.warning(self,'Save screenshot',file.errorString())
            return
        self.accept()

    def pixel_rect(self):
        return self.raw_selection if not self.selection.isEmpty() else self.image.rect()

    def raw_point(self, position):
        return QPoint(round(position.x()*self.image.width()/self.width()),
                      round(position.y()*self.image.height()/self.height()))

    def updated(self):
        size = self.pixel_rect().size()
        self.help.setText('Click a window' if self.active_tool == 'Window' else f'{size.width()} × {size.height()}')
        self.actions['Undo'].setEnabled(bool(self.strokes))
        self.actions['Redo'].setEnabled(bool(self.redo_stack))
        target=self.selection.intersected(self.viewport)
        center=target.center().x() if not target.isEmpty() else self.viewport.center().x()
        for bar,above in ((self.tools,True),(self.controls,False)):
            bar.adjustSize()
            x=max(self.viewport.left(),min(center-bar.width()//2,self.viewport.right()-bar.width()+1))
            if above:
                y=self.viewport.top()+6 if target.isEmpty() else target.top()-bar.height()-6
            else:
                y=self.viewport.bottom()-bar.height()-6 if target.isEmpty() else target.bottom()+6
            bar.move(x,max(self.viewport.top(),min(y,self.viewport.bottom()-bar.height()+1)))
        self.update()

    def handles(self):
        r=self.selection
        if r.isEmpty():
            return {}
        return {'lt':r.topLeft(),'rt':r.topRight(),'lb':r.bottomLeft(),'rb':r.bottomRight(),
                'l':QPoint(r.left(),r.center().y()),'r':QPoint(r.right(),r.center().y()),
                't':QPoint(r.center().x(),r.top()),'b':QPoint(r.center().x(),r.bottom())}

    def handle_at(self, point):
        return next((name for name,pos in self.handles().items() if (pos-point).manhattanLength()<=9), '')

    def draw_strokes(self, painter):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for tool, points, text, color, width in self.strokes:
            pen=QPen(color,width,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin)
            pen.setCosmetic(True)
            painter.setPen(pen)
            box = QRect(points[0],points[-1]).normalized()
            if tool=='Rectangle':
                painter.drawRect(box)
            elif tool=='Ellipse':
                painter.drawEllipse(box)
            elif tool=='Redact':
                painter.fillRect(box,Qt.GlobalColor.black)
            elif tool=='Text':
                painter.drawText(points[0],text)
            elif tool=='Arrow':
                start, end = points[0], points[-1]
                angle = math.atan2(start.y()-end.y(),start.x()-end.x())
                painter.drawLine(start,end)
                for offset in (-.5,.5):
                    painter.drawLine(end,end+QPoint(round(14*math.cos(angle+offset)),round(14*math.sin(angle+offset))))
            elif len(points)==1:
                painter.drawPoint(points[0])
            else:
                painter.drawPolyline(QPolygon(points))

    def lens_rect(self):
        if self.lens_pixel is None or self.active_tool != 'Select':
            return QRect()
        point = self.view_rect(QRect(self.lens_pixel, QSize(1, 1))).center()
        screen = next((r for r in self.screen_bounds if r.contains(point)), QRect())
        side = 77  # 11 source pixels at seven logical pixels per cell.
        if screen.width() < side or screen.height() < side:
            return QRect()
        blocked = [self.tools.geometry(), self.controls.geometry()]
        for handle in [point, *self.handles().values()]:
            blocked.append(QRect(handle - QPoint(6, 6), QSize(13, 13)))
        for y in (point.y() + 12, point.y() - side - 12, screen.top(), screen.bottom()-side+1):
            for x in (point.x() + 12, point.x() - side - 12, screen.left(), screen.right()-side+1):
                box = QRect(max(screen.left(), min(x, screen.right()-side+1)),
                            max(screen.top(), min(y, screen.bottom()-side+1)), side, side)
                if not any(box.intersects(obstacle) for obstacle in blocked):
                    return box
        return QRect()

    def paint_lens(self, painter):
        box = self.lens_rect()
        if box.isEmpty():
            return
        source = QRect(self.lens_pixel - QPoint(5, 5), QSize(11, 11))
        visible = source.intersected(self.image.rect())
        offset = (visible.topLeft() - source.topLeft()) * 7
        painter.fillRect(box, Qt.GlobalColor.black)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawImage(QRect(box.topLeft() + offset, visible.size() * 7), self.image, visible)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(Qt.GlobalColor.white)
        painter.drawRect(box.adjusted(0, 0, -1, -1))
        center = QRect(box.center() - QPoint(3, 3), QSize(6, 6))
        painter.drawRect(center)
        painter.setPen(Qt.GlobalColor.black)
        painter.drawRect(center.adjusted(-1, -1, 1, 1))

    def paintEvent(self, event):
        with QPainter(self) as painter:
            painter.drawImage(self.rect(), self.image)
            self.draw_strokes(painter)
            picking = self.active_tool == 'Window'
            target = self.view_rect(self.hover_window) if picking else self.selection
            painter.setClipRegion(QRegion(self.rect()).subtracted(QRegion(target)))
            opacity = 60 if target.isEmpty() else 120
            if picking or self.active_tool=='Select' or not target.isEmpty():
                painter.fillRect(self.rect(), QColor(0,0,0,opacity))
            painter.setClipping(False)
            if target.isEmpty() and self.active_tool=='Select' and not self.strokes:
                text = 'Drag to select an area  ·  Enter to copy the full desktop'
                hint = painter.fontMetrics().boundingRect(text).adjusted(-14,-8,14,8)
                hint.moveCenter(self.viewport.center())
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(35,38,42,230))
                painter.drawRoundedRect(hint,6,6)
                painter.setPen(Qt.GlobalColor.white)
                painter.drawText(hint,Qt.AlignmentFlag.AlignCenter,text)
            if not target.isEmpty():
                painter.setPen(QPen(QColor('#80cfff'),2))
                painter.drawRect(target.adjusted(0,0,-1,-1))
                painter.setBrush(QColor('white'))
                for point in (() if picking else self.handles().values()):
                    painter.drawEllipse(point,4,4)
            self.paint_lens(painter)

    def mousePressEvent(self, event):
        if event.button()!=Qt.MouseButton.LeftButton:
            return
        p = event.position().toPoint()
        if self.active_tool == 'Window':
            rect = self.window_at(event.position())
            if not rect.isEmpty():
                self.raw_selection = rect
                self.selection = self.view_rect(rect)
                self.set_tool('Select')
            return
        self.origin = p
        self.original = QRect(self.selection)
        self.raw_original = QRect(self.raw_selection)
        self.raw_origin = self.raw_point(event.position())
        if self.active_tool != 'Select':
            self.drag='draw'
            tool = self.active_tool
            text = ''
            if tool=='Text':
                text, ok = QInputDialog.getText(self,'Annotate screenshot','Text')
                self.origin = None
                self.drag = ''
                if not ok or not text:
                    return
            self.redo_stack.clear()
            group=self.ink_group()
            color=QColor(self.colors[group])
            if tool=='Highlight':
                color.setAlpha(115)
            self.strokes.append((tool,[p],text,color,self.widths[group]))
        else:
            self.lens_pixel = self.raw_origin
            self.drag=self.handle_at(p) or ('move' if self.selection.contains(p) else 'new')
            if self.drag=='new':
                self.selection=QRect()
        self.updated()

    def drag_to(self,position):
        p = position.toPoint()
        raw = self.raw_point(position)
        if self.active_tool == 'Select':
            self.lens_pixel = QPoint(max(0, min(raw.x(), self.image.width()-1)),
                                     max(0, min(raw.y(), self.image.height()-1)))
        if self.drag=='draw':
            self.strokes[-1][1].append(p)
        elif self.drag=='new':
            self.selection=QRect(self.origin,p).normalized().intersected(self.rect())
            self.raw_selection=QRect(self.raw_origin,raw).normalized().intersected(self.image.rect())
        elif self.drag=='move':
            x=max(0,min(self.width()-self.original.width(),self.original.x()+p.x()-self.origin.x()))
            y=max(0,min(self.height()-self.original.height(),self.original.y()+p.y()-self.origin.y()))
            self.selection.moveTopLeft(QPoint(x,y))
            target=self.raw_original.topLeft()+raw-self.raw_origin
            self.raw_selection.moveTopLeft(QPoint(max(0,min(self.image.width()-self.raw_selection.width(),target.x())),
                                                  max(0,min(self.image.height()-self.raw_selection.height(),target.y()))))
        else:
            for original, point, bounds, field in ((self.original,p,self.rect(),'selection'),
                                                    (self.raw_original,raw,self.image.rect(),'raw_selection')):
                rect=QRect(original)
                if 'l' in self.drag: rect.setLeft(point.x())
                if 'r' in self.drag: rect.setRight(point.x())
                if 't' in self.drag: rect.setTop(point.y())
                if 'b' in self.drag: rect.setBottom(point.y())
                setattr(self,field,rect.normalized().intersected(bounds))
        self.updated()

    def mouseMoveEvent(self,event):
        if self.active_tool == 'Window':
            self.hover_window = self.window_at(event.position())
            self.update()
        elif self.origin is not None:
            self.drag_to(event.position())
        elif self.active_tool=='Select':
            p=event.position().toPoint()
            edge=self.handle_at(p)
            cursors={'lt':Qt.CursorShape.SizeFDiagCursor,'rb':Qt.CursorShape.SizeFDiagCursor,
                     'lb':Qt.CursorShape.SizeBDiagCursor,'rt':Qt.CursorShape.SizeBDiagCursor,
                     't':Qt.CursorShape.SizeVerCursor,'b':Qt.CursorShape.SizeVerCursor,
                     'l':Qt.CursorShape.SizeHorCursor,'r':Qt.CursorShape.SizeHorCursor}
            self.setCursor(cursors.get(edge, Qt.CursorShape.SizeAllCursor if self.selection.contains(p) else Qt.CursorShape.CrossCursor))

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.origin is not None:
            self.drag_to(event.position())
            if self.selection.width()<2 or self.selection.height()<2:
                self.selection=QRect()
            self.lens_pixel = None
            self.origin=None
            self.drag=''
            self.updated()

    def undo(self):
        if self.strokes:
            self.redo_stack.append(self.strokes.pop())
            self.updated()

    def redo(self):
        if self.redo_stack:
            self.strokes.append(self.redo_stack.pop())
            self.updated()

    def adjust_crop(self, event):
        directions = {Qt.Key.Key_Left: (-1, 0), Qt.Key.Key_Right: (1, 0),
                      Qt.Key.Key_Up: (0, -1), Qt.Key.Key_Down: (0, 1)}
        direction = directions.get(event.key())
        modifiers = event.modifiers()
        shift, alt = Qt.KeyboardModifier.ShiftModifier, Qt.KeyboardModifier.AltModifier
        if (direction is None or modifiers & ~(shift | alt) or self.active_tool != 'Select'
                or self.selection.isEmpty() or self.origin is not None):
            return False
        dx, dy = direction
        if not modifiers & shift:
            dx *= max(1, math.floor(15 * self.image.width() / self.width() + 0.5))
            dy *= max(1, math.floor(15 * self.image.height() / self.height() + 0.5))
        crop = self.raw_selection
        if modifiers & alt:
            crop.setRight(max(crop.left(), min(self.image.width()-1, crop.right()+dx)))
            crop.setBottom(max(crop.top(), min(self.image.height()-1, crop.bottom()+dy)))
            target = crop.bottomRight()
        else:
            crop.moveTo(max(0, min(self.image.width()-crop.width(), crop.x()+dx)),
                        max(0, min(self.image.height()-crop.height(), crop.y()+dy)))
            target = crop.center()
            if dx:
                target.setX(crop.left() if dx < 0 else crop.right())
            if dy:
                target.setY(crop.top() if dy < 0 else crop.bottom())
        self.selection = self.view_rect(crop)
        self.lens_pixel = target if modifiers & shift else None
        self.updated()
        return True

    def release_lens(self, event):
        if event.key() == Qt.Key.Key_Shift and self.origin is None:
            self.lens_pixel = None
            self.update()

    def eventFilter(self, child, event):
        # Buttons normally consume arrow keys for focus traversal.
        if event.type() == QEvent.Type.KeyPress and self.adjust_crop(event):
            return True
        if event.type() == QEvent.Type.KeyRelease:
            self.release_lens(event)
        return super().eventFilter(child, event)

    def keyReleaseEvent(self, event):
        self.release_lens(event)
        super().keyReleaseEvent(event)

    def keyPressEvent(self,event):
        if self.adjust_crop(event):
            event.accept()
        elif event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):
            self.accept()
        elif event.key()==Qt.Key.Key_Escape:
            self.reject()
        elif event.key()==Qt.Key.Key_W and not event.modifiers():
            self.pick_window()
        elif event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key()==Qt.Key.Key_Z:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier: self.redo()
            else: self.undo()
        elif event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key()==Qt.Key.Key_S:
            if self.active_tool != 'Window': self.choose_save()
        elif event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key()==Qt.Key.Key_C:
            self.accept()
        else:
            super().keyPressEvent(event)

    def accept(self):
        if self.origin is None and self.active_tool != 'Window':
            super().accept()

    def selected_image(self):
        return self.rendered_image() if self.result()==QDialog.DialogCode.Accepted else None

    def rendered_image(self):
        result=self.image.copy()
        result.setDevicePixelRatio(1)
        if self.strokes:
            with QPainter(result) as painter:
                painter.scale(result.width()/self.width(),result.height()/self.height())
                self.draw_strokes(painter)
        return result.copy(self.pixel_rect())


def publish(image, app, output=None):
    if image is None or image.isNull():
        return False
    if output is not None:
        data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer, 'PNG'):raise RuntimeError('Could not encode capture')
        with open(output, 'xb') as stream:
            import os
            os.fchmod(stream.fileno(), 0o600)
            stream.write(bytes(data))
    else:
        app.clipboard().setImage(image)
    return True


def transfer_png(image, command, acknowledgement):
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, 'PNG'):
        raise RuntimeError('Could not encode the completed image')
    # A private, unlinked file keeps a failed/nonreading recipient from blocking the UI.
    with tempfile.TemporaryFile() as pixels:
        pixels.write(bytes(data))
        pixels.seek(0)
        proc = subprocess.Popen(command,stdin=pixels,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                                start_new_session=True)
    try:
        if not select.select([proc.stdout],[],[],10)[0] or proc.stdout.readline()!=acknowledgement:
            raise RuntimeError('The image recipient did not confirm the PNG import.')
    except (OSError, RuntimeError):
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)
        raise
    finally:
        proc.stdout.close()


def read_image():
    data = sys.stdin.buffer.read(256*1024*1024+1)
    if len(data)>256*1024*1024:
        raise ValueError('Capture exceeds the input limit')
    image=QImage.fromData(data,'PNG')
    if image.isNull():
        raise ValueError('Incomplete capture')
    return image


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--geometry',type=int,nargs=4,metavar=('X','Y','WIDTH','HEIGHT'))
    parser.add_argument('--output',type=Path,help='Save a new PNG instead of changing the clipboard')
    parser.add_argument('--notify',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--clipboard-owner',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    app=QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)
    if args.clipboard_owner:
        image=read_image()
        clipboard=app.clipboard()
        clipboard.setImage(image)
        if not clipboard.ownsClipboard():
            return 1
        print('OWNED', flush=True)
        def release():
            if not clipboard.ownsClipboard():
                app.quit()
        clipboard.dataChanged.connect(release)
        QTimer.singleShot(0,release)
        return app.exec()

    if args.geometry is None and app.platformName()=='xcb':
        screen = app.screenAt(QCursor.pos()) or app.primaryScreen()
        scales = {s.devicePixelRatio() for s in screen.virtualSiblings()}
        if len(scales)>1 and 'DOROSHELL_CAPTURE_UI_SCALE' not in os.environ:
            # X11 uses a physical-pixel root. Qt's mixed-DPI logical desktop can have gaps.
            env = dict(os.environ, QT_ENABLE_HIGHDPI_SCALING='0', QT_SCALE_FACTOR='1',
                       DOROSHELL_CAPTURE_UI_SCALE=str(screen.devicePixelRatio()))
            env.pop('QT_SCREEN_SCALE_FACTORS',None)
            os.execve(sys.executable,[sys.executable,*sys.argv],env)
        if 'DOROSHELL_CAPTURE_UI_SCALE' in os.environ:
            font=app.font()
            font.setPointSizeF(font.pointSizeF()*float(os.environ['DOROSHELL_CAPTURE_UI_SCALE']))
            app.setFont(font)

    directory=QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation)
    lock=QLockFile(str(Path(directory)/'doroshell-capture-overlay.lock'))
    if not lock.tryLock(0):
        if args.notify: print('BUSY',flush=True)
        return 0
    windows = []
    if args.geometry:
        image, geometry=read_image(), QRect(*args.geometry)
    else:
        if app.platformName() == 'xcb':
            windows = x11_window_rectangles()
        image, geometry=snapshot_desktop()
    if args.notify: print('FROZEN',flush=True)
    dialog=FrozenCapture(image,geometry,windows)
    dialog.exec()
    image=dialog.selected_image()
    if image is None:
        return 0
    if args.output:
        publish(image,app,args.output)
        return 0
    transfer_png(image,[sys.executable,__file__,'--clipboard-owner'],b'OWNED\n')
    return 0


if __name__=='__main__':
    sys.exit(main())
