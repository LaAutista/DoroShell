# Tray popup attention transitions

The hidden-icons popup contains a snapshot of the tray items that are hidden when
it opens. If an auto-hidden item requests attention, its real panel button becomes
visible. The popup now closes on that attention transition rather than retaining
a second actionable copy. The attention timer returning an item to overflow also
invalidates an open snapshot, so the next opening reflects current membership.
The configured attention timeout and Active/Passive icon handling are unchanged.

The popup also registers with the panel’s existing window-visibility tracker,
like the clock and taskbar menus. This keeps an auto-hiding panel visible while
the popup is open and releases it when the popup closes. Previously the panel
could slide off-screen underneath the open overflow popup.

The native regression uses a real synthetic StatusNotifier service, disposable
text fields, Openbox, private D-Bus and authenticated private X11. It verifies
Escape and disconnect restore typing focus, repeated single-click reopen,
keyboard activation dispatch, panel auto-hide hold/release, and real one-minute
attention expiry followed by reopening. It also verifies Qt's current outside
click policy: the dismissing click is consumed and focus returns to the prior
application; the next deliberate click can focus another window. No synthetic
click is replayed into another application by the panel.

Both defects were reproduced on the published panel baseline: attention left a
stale duplicate popup, and auto-hide moved the panel off-screen under overflow.
The corrected native checks and all 231 unit tests passed with the candidate.

```sh
python -m unittest discover -s tests -v
python tests/check_tray_lifecycle_x11.py --run --xvfb /path/to/Xvfb \
  --binary /path/to/candidate/lxqt-panel --evidence /private/output --case popup
python tests/check_tray_lifecycle_x11.py --run --xvfb /path/to/Xvfb \
  --binary /path/to/candidate/lxqt-panel --evidence /private/output --case attention
```

The attention case waits for the real one-minute timeout; it does not shorten
production timers. No personal tray services, applications or clipboard are
used. Real application diversity, physical monitor placement, Wayland, login and
long-session coverage remain separate acceptance work. This source change does
not activate or replace a live panel.

## Keyboard context menus

`0006-tray-keyboard-context.patch` enables the Menu key and Shift+F10 for a
focused overflow icon. Both use the existing imported D-Bus menu when available,
or the notifier's `ContextMenu` method otherwise. Keyboard menus anchor to the
focused icon; mouse menus retain their pointer position and release behavior.
Previously the button discarded keyboard context events. An icon also now
requires its own matching key press before acting on Return/Space release; a
Return used to choose a menu action must not additionally activate the app.
Losing focus clears that pending activation. Shift+F10 has an
explicit overflow-key handler because this Qt path does not generate that event.

The `context` and `context-fallback` cases of the same private-X11 test check both
shortcuts, exactly one dispatch per shortcut, reopening and typing focus after
Escape. Use the command above with either value for `--case`. The fallback test
checks protocol dispatch; it cannot establish the behavior of menus drawn by an
external real application.

## Keyboard-only entry: historical native limitation

At source checkpoint `d525ae4`, the pinned LXQt Panel 2.4.1 sets `Qt::WindowDoesNotAcceptFocus` deliberately to
preserve taskbar minimize/restore behavior. The overflow arrow has the accessible
name “Show hidden icons”, but a name alone does not provide keyboard access.
Unlike the main-menu and taskbar plugins, `plugin-statusnotifier` registers no
LXQt GlobalKeys action for showing overflow, and the panel exposes no inspected
command/IPC entry point for that action. There is no existing notifier shortcut
setting to enable in this source. Removing the focus restriction or assigning a
new global shortcut would be feature/design work, not a tested configuration fix.

The opt-in `--case entry-limit` probe confirms this boundary on private X11/Openbox:
the dock's WM_HINTS input flag is false; Tab, Return, Space, Menu and Escape in a
disposable app do not enter overflow; normal Alt+Tab cycling stays in the fixture
apps. It injects no pointer events and verifies that pointer coordinates remain
unchanged. It reports **LIMIT CONFIRMED**, not an accessibility pass. This does not
claim to enumerate every window-manager override or assistive-technology action.

Once the arrow is opened with a pointer, existing tests cover Tab/Shift+Tab
navigation, Return activation, Menu/Shift+F10, no duplicate activation and Escape
back to the prior app. The popup, imported-menu and protocol-fallback cases were
rerun against the unchanged nine-patch runtime; the earlier density test covers
multi-icon forward/reverse traversal. This is not an end-to-end pointer-free path,
and screen-reader usability is not established by accessible labels alone.

No production change, global shortcut, service installation or personal binding
change is made for this acceptance checkpoint. The known entry gap remains open;
all nine native patches and live-session safeguards are preserved.

The [configurable native action](tray-shortcut.md) added afterward provides entry
without changing the panel focus policy. It is unbound by default, so the historical
probe still describes ordinary Tab/window cycling without a configured action.
