#!/usr/bin/env python3
"""Small Openbox/X11 edge snap helper. Does not replace the window manager."""
import os
import sys
from Xlib import X, display, error, protocol
from PySide6.QtCore import QTimer, QCoreApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket


def half(area, side):
    x, y, w, h = area
    left = w // 2
    return (x, y, left, h) if side == 'left' else (x + left, y, w - left, h)


def workarea(rect, struts, width, height):
    x,y,w,h=rect
    right,bottom=x+w,y+h
    overlaps=lambda a,b,c,d: a<=d and c<=b
    for s in struts:
        l,r,t,b,ly1,ly2,ry1,ry2,tx1,tx2,bx1,bx2=s
        if l and overlaps(y,bottom-1,ly1,ly2): x=max(x,l)
        if r and overlaps(y,bottom-1,ry1,ry2): right=min(right,width-r)
        if t and overlaps(x,right-1,tx1,tx2): y=max(y,t)
        if b and overlaps(x,right-1,bx1,bx2): bottom=min(bottom,height-b)
    return (x,y,max(1,right-x),max(1,bottom-y))


class Snap:
    def __init__(self, app):
        self.app = app
        self.d = display.Display()
        self.root = self.d.screen().root
        self.saved = {}
        self.drag = None
        self.was_down = False
        wm = self.prop(self.root, '_NET_SUPPORTING_WM_CHECK')
        if not len(wm):
            raise RuntimeError('No EWMH window manager detected')
        name = self.prop(self.d.create_resource_object('window', wm[0]), '_NET_WM_NAME')
        if not len(name) or b'openbox' not in bytes(name).lower():
            raise RuntimeError('Edge snapping currently supports Openbox only')

    def prop(self, window, name):
        result = window.get_full_property(self.d.intern_atom(name), X.AnyPropertyType)
        return result.value if result is not None else []

    def active(self):
        value = self.prop(self.root, '_NET_ACTIVE_WINDOW')
        return self.d.create_resource_object('window', value[0]) if len(value) else None

    def geometry(self, window):
        g = window.get_geometry()
        p = self.root.translate_coords(window, 0, 0)
        ext = list(self.prop(window, '_NET_FRAME_EXTENTS')) or [0, 0, 0, 0]
        return (p.x-ext[0], p.y-ext[2], g.width+ext[0]+ext[1], g.height+ext[2]+ext[3])

    def eligible(self, window):
        kinds = self.prop(window, '_NET_WM_WINDOW_TYPE')
        normal = self.d.intern_atom('_NET_WM_WINDOW_TYPE_NORMAL')
        states = self.prop(window, '_NET_WM_STATE')
        excluded = {self.d.intern_atom('_NET_WM_STATE_FULLSCREEN'), self.d.intern_atom('_NET_WM_STATE_HIDDEN')}
        return (not len(kinds) or normal in kinds) and not excluded.intersection(states)

    def message(self, window, kind, values):
        event = protocol.event.ClientMessage(window=window, client_type=self.d.intern_atom(kind), data=(32, values))
        self.root.send_event(event, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
        self.d.flush()

    def resize(self, window, rect):
        ext = list(self.prop(window, '_NET_FRAME_EXTENTS')) or [0,0,0,0]
        self.message(window, '_NET_WM_STATE', [0, self.d.intern_atom('_NET_WM_STATE_MAXIMIZED_VERT'), self.d.intern_atom('_NET_WM_STATE_MAXIMIZED_HORZ'), 2, 0])
        x,y,w,h = rect
        self.message(window, '_NET_MOVERESIZE_WINDOW', [1 | (15<<8) | (2<<12), x, y, max(1,w-ext[0]-ext[1]), max(1,h-ext[2]-ext[3])])

    def apply(self, side, window=None, screen=None):
        window = window or self.active()
        if window is None or not self.eligible(window):
            return
        rect = self.geometry(window)
        if side == 'restore':
            old = self.saved.pop(window.id, None)
            if old:
                self.resize(window, old)
            return
        area = screen or self.area_at(rect[0]+rect[2]//2,rect[1]+rect[3]//2)[1]
        self.saved.setdefault(window.id, rect)
        self.resize(window, half(area, side))

    def area_at(self, x, y):
        from Xlib.ext import randr
        monitors = self.root.xrandr_get_monitors(True).monitors
        rects = [(m.x,m.y,m.width_in_pixels,m.height_in_pixels) for m in monitors]
        if not rects:
            g=self.root.get_geometry()
            rects=[(0,0,g.width,g.height)]
        rect=next((r for r in rects if r[0]<=x<r[0]+r[2] and r[1]<=y<r[1]+r[3]),rects[0])
        struts=[]
        for wid in self.prop(self.root,'_NET_CLIENT_LIST'):
            w=self.d.create_resource_object('window',wid)
            values=list(self.prop(w,'_NET_WM_STRUT_PARTIAL'))
            if len(values)==12:
                struts.append(values)
        g=self.root.get_geometry()
        return rect, workarea(rect,struts,g.width,g.height)

    def poll(self):
        try:
            p = self.root.query_pointer()
            down = bool(p.mask & X.Button1Mask)
            if down and not self.was_down:
                w = self.active()
                self.drag = (w, self.geometry(w)) if w is not None and self.eligible(w) else None
            if self.was_down and not down and self.drag:
                w, old = self.drag
                current = self.geometry(w)
                # Only a real move, not a click, resize, or drag inside the client.
                if current[:2] != old[:2] and current[2:] == old[2:]:
                    edge, area = self.area_at(p.root_x,p.root_y)
                    side = 'left' if p.root_x <= edge[0]+8 else 'right' if p.root_x >= edge[0]+edge[2]-9 else None
                    if side:
                        self.saved.setdefault(w.id, old)
                        self.apply(side,w,area)
                self.drag = None
            self.was_down = down
        except (error.XError, OSError):
            self.drag = None
            self.was_down = False


def main():
    if os.environ.get('XDG_SESSION_TYPE', 'x11') != 'x11':
        raise SystemExit('Openbox/X11 required')
    app = QCoreApplication(sys.argv[:1])
    name = 'doroshell-snap-' + str(os.getuid())
    command = sys.argv[1] if len(sys.argv)>1 else 'serve'
    socket = QLocalSocket()
    socket.connectToServer(name)
    if socket.waitForConnected(200):
        socket.write(command.encode())
        socket.waitForBytesWritten(500)
        return 0
    if command == 'stop':
        return 0  # No owner exists; rollback must not start a new helper.
    if command not in ('serve','left','right','restore'):
        raise SystemExit('Choose serve, left, right, restore or stop')
    snap = Snap(app)
    if command in ('left','right','restore'):
        snap.apply(command)
        return 0
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    QLocalServer.removeServer(name)
    if not server.listen(name):
        raise RuntimeError(server.errorString())
    clients = []
    def request():
        while server.hasPendingConnections():
            c = server.nextPendingConnection()
            clients.append(c)
            def read(c=c):
                action = bytes(c.readAll()).decode()
                if action == 'stop':
                    app.quit()
                if action in ('left','right','restore'):
                    try: snap.apply(action)
                    except error.XError: pass
                c.close()
                clients.remove(c)
                c.deleteLater()
            c.readyRead.connect(read)
    server.newConnection.connect(request)
    timer = QTimer()
    timer.timeout.connect(snap.poll)
    timer.start(30)
    return app.exec()

if __name__ == '__main__':
    sys.exit(main())
