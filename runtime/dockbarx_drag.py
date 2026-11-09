"""Recover internal icon drops swallowed by LXQt's Qt/GTK embedding boundary.

Loaded only for the installed DockBarX LXQt applet, through an opt-in user-site
hook. Native successful reorders, cancelled drags and drops outside the applet
are left alone. No package files or launcher lists are rewritten directly.
"""
import sys


def order(dockbar):
    return tuple(id(group) for group in dockbar.groups)


def begin(button, context):
    button._doroshell_cancelled = False
    button._doroshell_order = order(button.dockbar_r())


def recover(button, context):
    if getattr(button, '_doroshell_cancelled', True):
        return
    dockbar, source = button.dockbar_r(), button.group_r()
    if dockbar is None or source is None or order(dockbar) != button._doroshell_order:
        return
    device = context.get_device()
    if device is None:
        return
    _, x, y = device.get_position()
    for group in dockbar.groups:
        target = group.button
        if group is source or not target.get_mapped():
            continue
        top = target.get_toplevel()
        position = target.translate_coordinates(top, 0, 0)
        if position is None or top.get_window() is None:
            continue
        _, ox, oy = top.get_window().get_origin()
        left, upper = ox + position[0], oy + position[1]
        width, height = target.get_allocated_width(), target.get_allocated_height()
        if left <= x < left + width and upper <= y < upper + height:
            before = x < left + width / 2 if dockbar.orient in ('up', 'down') else y < upper + height / 2
            name = source.identifier or source.desktop_entry.getFileName()
            dockbar.groupbutton_moved(name, group, 'start' if before else 'end')
            return


def install(module):
    try:
        Gtk, GroupButton = module.Gtk, module.GroupButton
        if getattr(GroupButton, '_doroshell_drag_installed', False):
            return
        original = GroupButton.__init__

        def failed(button, context, result):
            button._doroshell_cancelled = result != Gtk.DragResult.NO_TARGET
            return False

        def ended(button, context):
            # GTK clears the selected action for Escape; an embedded cancelled
            # drag may report NO_TARGET instead of USER_CANCELLED.
            if context.get_selected_action() != module.Gdk.DragAction.MOVE:
                return
            try:
                recover(button, context)
            except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                print('DoroShell: taskbar drag recovery skipped: ' + str(error), file=sys.stderr)

        def initialized(self, *args, **kwargs):
            original(self, *args, **kwargs)
            self.connect('drag-begin', begin)
            self.connect('drag-failed', failed)
            self.connect('drag-end', ended)

        GroupButton.__init__ = initialized
        GroupButton._doroshell_drag_installed = True
    except (ImportError, AttributeError, ValueError) as error:
        print('DoroShell: taskbar drag compatibility unavailable: ' + str(error), file=sys.stderr)


def activate():
    # User .pth files run before system site-packages. Wait for DockBarX's normal
    # import rather than importing GTK early or changing Python's search path.
    from importlib.machinery import PathFinder
    class AppletHook:
        def find_spec(self, fullname, path=None, target=None):
            if fullname != 'dockbarx.groupbutton':
                return None
            sys.meta_path.remove(self)
            spec = PathFinder.find_spec(fullname, path)
            if spec is None or spec.loader is None:
                return spec
            execute = spec.loader.exec_module
            def loaded(module):
                execute(module)
                install(module)
            spec.loader.exec_module = loaded
            return spec
    sys.meta_path.insert(0, AppletHook())
