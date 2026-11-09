import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
from runtime import dockbarx_drag as drag


class TaskbarDragTests(unittest.TestCase):
    def setUp(self):
        self.source = NS(identifier='source')
        top = NS(get_window=lambda: NS(get_origin=lambda: (True, 0, 0)))
        target = NS(get_mapped=lambda: True, get_toplevel=lambda: top,
                    translate_coordinates=lambda *a: (40, 0),
                    get_allocated_width=lambda: 40, get_allocated_height=lambda: 40)
        self.target = NS(button=target)
        self.source.button = target
        self.dock = NS(groups=[self.source, self.target], orient='down', groupbutton_moved=Mock())
        self.button = NS(dockbar_r=lambda: self.dock, group_r=lambda: self.source)
        self.context = NS(get_device=lambda: NS(get_position=lambda: (None, 75, 10)))
        drag.begin(self.button, self.context)

    def test_drop_after_target(self):
        drag.recover(self.button, self.context)
        self.dock.groupbutton_moved.assert_called_once_with('source', self.target, 'end')

    def test_vertical_drop_before_target(self):
        self.dock.orient = 'left'
        drag.recover(self.button, self.context)
        self.dock.groupbutton_moved.assert_called_once_with('source', self.target, 'start')

    def test_native_move_not_repeated(self):
        self.dock.groups.reverse()
        drag.recover(self.button, self.context)
        self.dock.groupbutton_moved.assert_not_called()

    def test_cancel_and_outside_drop_do_nothing(self):
        self.button._doroshell_cancelled = True
        drag.recover(self.button, self.context)
        self.button._doroshell_cancelled = False
        self.context.get_device = lambda: NS(get_position=lambda: (None, 100, 100))
        drag.recover(self.button, self.context)
        self.dock.groupbutton_moved.assert_not_called()

    def test_escape_with_no_target_is_not_recovered(self):
        class Button:
            def __init__(self): self.signals = {}
            def connect(self, name, callback): self.signals[name] = callback
        module = NS(GroupButton=Button, Gtk=NS(DragResult=NS(NO_TARGET=1)),
                    Gdk=NS(DragAction=NS(MOVE=4)))
        drag.install(module)
        drag.install(module)
        button = Button()
        with patch.object(drag, 'recover') as recover:
            button.signals['drag-failed'](button, None, 1)
            button.signals['drag-end'](button, NS(get_selected_action=lambda: 0))
            recover.assert_not_called()
            button.signals['drag-end'](button, NS(get_selected_action=lambda: 4))
            recover.assert_called_once()

    def test_live_refresh_never_stops_applet(self):
        import modules
        with patch('os.kill') as kill:
            with self.assertRaisesRegex(RuntimeError, 'EPIPE'):
                modules.refresh_dockbarx()
            kill.assert_not_called()
