# Show Desktop acceptance on X11/Openbox

Show Desktop uses the window manager's standard showing-desktop request. The
panel does not maintain a second window list or restore windows independently.

The expanded private-X11 check verifies:

- Repeated hide/restore with ordinary and pre-minimized windows, including both
  ordinary and pre-minimized sticky windows.
- Two virtual desktops, switching desktops while showing desktop, and preserving
  other-desktop assignments and minimized state.
- Closing a window while showing desktop without disturbing surviving windows.
- Opening a new window while showing desktop, then repeated toggles. Openbox
  exits showing-desktop mode for the new window and minimizes the previously
  visible current-desktop windows, including sticky windows. The panel respects
  this window-manager policy rather than reviving those windows afterward.
- Changing the same running panel from Bottom to Left, Top, Right and Bottom
  through its real placement dialog. Each edge retains a 12-pixel target at the
  panel end and working hide/restore. Live geometry is checked directly; LXQt
  delays writing settings to disk, so a config-file read is not proof of current
  panel orientation.

These cases passed on the existing implementation; no window-restoration or
orientation production changes were necessary.

```sh
python -m unittest discover -s tests -v
python tests/check_show_desktop_x11.py --run --xvfb /path/to/Xvfb \
  --binary /path/to/lxqt-panel --evidence /private/output
```

The check uses an authenticated disposable X11 server, private D-Bus and home,
and its own Openbox instance. Only that instance gets two virtual desktops.
Screenshots, if requested with `--evidence`, contain disposable fixtures only.
The placement-dialog interaction targets the tested private Xvfb layout; it does
not establish arbitrary font/scaling or physical multi-monitor support. Other
window managers, Wayland, fresh login, clean install and long-session behavior
remain outside this evidence. The live user session is not modified.

## Drag-hover keeps the desktop exposed

A real Qt drag from a disposable desktop-type window exposed a separate bug:
hovering over the edge a second time restored applications over the desktop.
`0007-show-desktop-drag.patch` makes the hover timer request showing-desktop mode
explicitly. Before acting, the timer also checks that the pointer is still over
the target and a mouse button remains held. A rejecting target need not receive
Qt drag-leave/drop events, so the old timer could fire after an early departure
or quick drop. The target continues rejecting drops. Mouse clicks and the existing shortcut continue to toggle it.

The same test checks that leaving the edge before the hover delay does nothing,
that a quick drop does nothing and remains rejected, that two complete drag hovers leave the desktop exposed, and that a subsequent
click restores exactly the prior window state. It sends no drops to personal
applications and does not read or write the clipboard.
