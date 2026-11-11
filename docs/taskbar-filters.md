# Pinned launchers and task filters

Pinned launchers stay visible when all of their windows are excluded by the
workspace, current-screen or minimized-only task filters. Unpinned tasks still
follow those filters.

A pin distinguishes a closed application from an application whose windows are
filtered out. With no windows, click or **Open** launches its desktop entry using
GIO. With filtered windows, click, **Show existing window** or Meta+number
activates an existing group member through the normal backend and honors
`raiseOnCurrentDesktop`. It does not launch a duplicate. When all members are
filtered, the first member in the group's internal hash is used; this is not an MRU policy.
The X11 backend's existing preference brings a minimized window to the current
workspace when enabled; otherwise it follows the window's workspace.

Filtered pins retain their launcher icon and indicate that their windows are
hidden by taskbar filters in the tooltip. Their context menu offers the existing
window action and Unpin, without actions to close or manipulate filtered windows.
Middle-click and wheel input do not act on filtered windows. Returning to visible
tasks restores a visible representative, including when multiple windows return
at once. Closing the last window clears running, checked and urgent state.

Build with the normal `panel/build.py` workflow, which applies the fourth patch
after the identity and wallpaper-glass patches. No installed panel is replaced.

```sh
python -m unittest discover -s tests -v
python tests/check_taskbar_filters_x11.py --run --xvfb /path/to/Xvfb \
  --binary /path/to/candidate/lxqt-panel --evidence /private/output
```

This opt-in regression runs disposable windows, Openbox and the LXQt shortcut
daemon on an authenticated private X11 display and private D-Bus session. The
launcher fixture only touches a temporary marker, making accidental duplicate
launches observable. It never opens personal applications or reads a clipboard.
The workspace and minimized-only paths are tested. Synthetic off-screen coverage
was deferred after Openbox clamping/reparenting interfered with the fixture;
current-screen behavior follows the shared filter path but is not runtime-verified.
Physical monitor transitions, Wayland, normal login and long-session acceptance
remain untested. No live activation is part of this fix.
