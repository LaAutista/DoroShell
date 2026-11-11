# Configurable keyboard entry to hidden notification icons

Patch `0010-tray-shortcut.patch` registers an LXQt client action named **Show/hide
hidden notification icons**, at `/panel/<notifier-group>/show_hidden_icons`.
It uses the existing LXQt global-shortcut daemon; no polling helper, compositor or
new installed service is introduced. The panel keeps its intentional no-focus
window flag and normal taskbar minimize/restore behavior.

## Configuration and safe deployment

The action has **no default key binding**. After selecting a runtime containing
this patch at an explicitly chosen safe point, open LXQt **Shortcut Keys**
(`lxqt-config-globalkeyshortcuts`), find this client action and assign an unused
chord. Existing explicit assignments are preserved when the action reconnects.
The action requires the DoroShell hidden-icons popup (`doroshellPopup=true`).
It does nothing when no icons are hidden. Separate notifier instances have
separate action paths; do not assign the same chord to multiple instances.

DoroShell never calls the shortcut-changing API or supplies a default chord.
LXQt handles registration, persistence and keyboard grabs. Its daemon can allow
multiple actions on the same chord according to its configured policy; this is
not an automatic conflict-rejection guarantee. Review existing assignments in
Shortcut Keys before choosing one. No personal shortcut or startup selection is
changed by building or publishing this source.

The action queues opening on the Qt event loop, with no fixed wait or polling.
The initial 200 ms menu-style delay was removed after private verification.
A popup owns the keyboard grab, so focused overflow buttons also handle the
configured chord locally to close it. This local handler ignores auto-repeat and
tracks the native binding-change signal: LXQt 2.4.0's action getter can retain an
old value after an external edit. Normal single-chord Qt key names with modifiers
are covered; unusual native key names or bare modifier bindings are not verified.

## Private native acceptance

`tests/check_tray_lifecycle_x11.py --case global` starts an existing LXQt shortcut
daemon with an explicit empty temporary config on authenticated Xvfb/Openbox and
a private D-Bus session. It verifies initial unbound registration and the action
label, then assigns/reassigns test chords **only in that temporary session**.
From a disposable app, without pointer events, it checks:

- Opening and focus on the first icon; Tab/Shift+Tab, Return activation and Menu.
- Exactly one imported-menu action, without also activating the application.
- Escape restoring typing focus to the original app; repeated invocation/toggle.
- A binding edit while the popup is open; a held chord without item activation.
- Notifier disconnect, no hidden items, and shortcut-daemon restart with the saved
  assignment and a successful subsequent invocation.
- Unchanged pointer coordinates and the panel's no-focus window hint.

The five recorded opening samples were 44–46 ms. Measurement starts before XTest
chord injection plus XSync and ends at first observed mapped popup, using a
monotonic clock and 10 ms polling. Each request has a 2-second failure bound.
These are synthetic local observations, not physical input latency, a percentile
benchmark or a guarantee under arbitrary system load.

```sh
python tests/check_tray_lifecycle_x11.py --run --xvfb /path/to/Xvfb \
  --binary /path/to/runtime/bin/lxqt-panel --evidence /private/output --case global
```

Existing popup focus/auto-hide, keyboard-menu, XEmbed restart, dense tray/taskbar,
long-tooltip and native pin/task-restore regressions are checked on the same
candidate. All ten patches apply to the pinned clean upstream and match the built
source; runtime notices retain every patch and component license. The full unit
suite and source-export inventory/checksums are also checked.

## Accessibility and remaining limits

The arrow's **Show hidden icons** accessible name is verified through AT-SPI.
Popup/icon names are set in native code, but the inspected AT-SPI application tree
and cache omit them on this Qt setup. The strict `--case global-labels` probe
retains that failing assertion. A pointer-opened version of the label probe also
fails against the unchanged nine-patch runtime: this is an inherited export
limitation, not a passing accessibility result. Screen-reader compatibility is
not claimed. The tests start an existing accessibility registry only inside the
private session; they do not install or alter live accessibility services.

Physical multi-monitor/mixed-DPI, Wayland, unusual key names, real notifier/menu
diversity and long-session acceptance remain outside this bounded check. The
10-patch runtime is staged. No live refresh is authorized by this source checkpoint;
wait for the user's explicit safe point before deployment. The private plan retains
the parent-reported active nine-patch runtime as the immediate fallback, while older
process/config observations remain historical and must be revalidated later.
