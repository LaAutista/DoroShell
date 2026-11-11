# Legacy XEmbed and StatusNotifier coexistence

The pinned LXQt Panel 2.4.1 source builds the static `tray` plugin. On X11 it owns
`_NET_SYSTEM_TRAY_S0`, embeds legacy client windows and exports them as
StatusNotifier items. It has no separate visible widget: `statusnotifier` renders
those items. Both plugins must be enabled in the panel profile. DoroShell profile
preparation preserves an existing `tray` plugin; it does not automatically add one
when absent. This checkpoint does not change profile settings or add a new tray.

## Reproduced defect and fix

A legacy client can exit while a native notifier remains. Opening overflow and
then restarting the legacy client left the old popup snapshot open without its
new icon. The published eight-patch binary passed initial docking/rendering/input
but failed the restart assertion. `0009-tray-registration-popup.patch` closes the
snapshot when the new item's title arrives, matching the existing removal and
attention policy. Reopening then includes the new item. This also applies to new
native StatusNotifier registrations; the legacy bridge itself is unchanged.

## Bounded private acceptance

`tests/check_xembed_tray_x11.py` uses authenticated 800×600 Xvfb, Openbox, a temporary
home and a fresh D-Bus session. It creates a raw X11 client on its own connection,
sets `_XEMBED_INFO`, requests docking, and checks the embedded notification,
reparenting and mapped state. A bordered RGB24 glyph avoids upstream's heuristic
that treats an icon's edge color as transparent; a uniform color fixture was
unsuitable and was corrected without changing production rendering.

The fixture checks exact icon pixels, one left/right press-and-release pair per
legacy click, no accidental native-item activation, native SNI activation, client
connection exit/proxy removal, and restart while overflow is open. Two cycles
retain the native icon and bounded panel width. The candidate also runs existing
popup/attention/keyboard-menu and density checks. Evidence is private; only the
reusable fixture and source are published.

```sh
python tests/check_xembed_tray_x11.py --run --xvfb /path/to/Xvfb \
  --binary /path/to/runtime/bin/lxqt-panel --evidence /private/output/xembed
```

The full test requires the same Python Qt/Xlib/D-Bus/GLib dependencies as the other
native fixtures. Merely changing D-Bus without isolating X11 is not sufficient.

## Limits and deployment

This covers synthetic RGB24 XEmbed using the direct X-event input path. It does
not establish GTK/Wine real-client compatibility, the alternate XTest forwarding
path, ARGB variants, every notifier, long-session recovery, tray-manager replacement,
physical mixed-DPI or Wayland (the legacy plugin explicitly supports X11 only).
Keyboard-only entry into overflow remains unverified. Those gaps remain separate
from the passing bounded bridge case.

The ninth patch is staged source, not live. The attempted earlier live refresh
stopped at an ambiguous-idle guard before any signal; no activation was retried.
Existing personal panel, startup selection, settings, clipboard and applications
remain untouched. No logout, locker, reboot, compositor or desktop reset is needed
or performed for this private acceptance.
