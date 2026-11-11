# Panel density and scaling acceptance

The hidden-icons popup previously used an unbounded four-column grid. With 60
icons on an 800×600 private X11 display at 150% scaling, its height was 921 pixels
and lower rows were outside the screen. Patch `0008-panel-density.patch` caps the
popup to the available screen space, allowing for the panel edge. Oversized
content uses a scroll area; ordinary popups retain their natural size. Keyboard
focus scrolls the focused icon into view.

Long task labels exposed a separate inherited-style issue: a tooltip reserved
space for wrapped text but its text was truncated to one line by the taskbar's
button-painting style. Right elision now applies only to buttons. Tooltips retain
their original text and wrapping flags. Tooltip text is saved before button
mnemonic escaping so a literal ampersand is not doubled.

The opt-in density regression uses synthetic StatusNotifier items and task
windows, a temporary 18pt stylesheet, an authenticated private 800×600 X11 server,
and its own Openbox session. It checks:

- Twelve long-titled task icons remain available and each restores its window.
- Three remaining long labels stay within the panel; their tooltip stays on-screen
  and renders wrapped text in its reserved lower lines.
- Sixty hidden icons fit within a scrollable popup. Tab/Return visits and activates
  every icon exactly once in order; Shift+Tab/Return traverses back to the first.
  Representative focused icons are visibly rendered in the viewport, and Escape
  closes the popup.

Both scaling cases and all 231 unit tests passed. Existing popup focus/auto-hide,
keyboard-menu, native tray/taskbar and all four palette contrast checks also
passed with the candidate.

```sh
python -m unittest discover -s tests -v
python tests/check_panel_density_x11.py --run --xvfb /path/to/Xvfb \
  --binary /path/to/lxqt-panel --evidence /private/output --scale 1.5
python tests/check_panel_density_x11.py --run --xvfb /path/to/Xvfb \
  --binary /path/to/lxqt-panel --evidence /private/output --scale 2
```

Use `--case tasks` or `--case overflow` to isolate either behavior. The popup is
opened by a pointer click before keyboard traversal; this test does not establish
a keyboard-only entry path to the panel. Screen scaling is simulated by Qt on one
Xvfb screen, not physical mixed-DPI or multi-monitor coverage. Other fonts, icon
counts, screen arrangements, Wayland and long-session behavior remain separate
acceptance work. No personal applications, session, settings or clipboard are
used, and this source release does not activate a live panel.
