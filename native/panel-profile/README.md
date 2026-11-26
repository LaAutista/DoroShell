# Next-login panel profile

Run these commands from the native runtime's `bin` directory on a fresh LXQt/X11
account. Register the Start and Wi-Fi desktop entries first.

```sh
./doroshell-setup --apply
./doroshell-panel-profile --plan
./doroshell-panel-profile --apply
```

Staging prepares a private panel configuration and a user autostart entry. The
next LXQt login selects it. The private panel runtime must stay at its selected
path. For a separate build tree, pass `--binary /path/to/runtime/bin/lxqt-panel`
to both panel commands. A missing binary or missing library at startup selects the
distribution's `/usr/bin/lxqt-panel` with its ordinary profile.

The source is the user's LXQt panel.conf, falling back to the first system LXQt
panel.conf in XDG_CONFIG_DIRS. The adapter uses panel1 automatically in a single-panel layout. For multiple panels, pass `--panel panelN` to both plan and apply. It
keeps custom widgets, existing taskbar pins and tray rules. A simple Quick Launch
widget containing plain application launchers can become grouped taskbar pins.
Mixed or ambiguous launcher widgets stay together. Start, grouped tasks, the
hidden-icon arrow, the legacy tray bridge, the network launcher, the two-line
calendar clock and the Show Desktop edge are configured in the private copy.
The user's stock panel.conf remains their rollback configuration.

`--undo` restores the previous autostart contents and permissions. If the user
reordered pins or otherwise edited the private profile, `--undo --keep-panel-edits`
saves a private copy under `~/.local/state/doroshell-native/` before switching back.
An interrupted stage or undo can be resumed with `--recover`. Edits to the
autostart entry are reported as conflicts. Existing RC2 panel ownership records,
DockBarX layouts, unknown custom autostart commands, and
nondefault XDG config, data or state roots require separate migration.

CTest `native-panel-profile-transaction` runs in disposable homes. The optional
`native-panel-staged-x11` test starts the actual patched and fallback panel in a
private Xvfb/Openbox session. Enable it by setting `DOROSHELL_PRIVATE_XVFB` and
`DOROSHELL_PANEL_TEST_BINARY` to their executable paths during CMake configuration.
