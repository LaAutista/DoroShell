# DoroShell implementation and acceptance roadmap

DoroShell customizes an existing LXQt desktop. The Windows 7 layout with pink Doro styling is the target; it is not yet an exact reproduction or a completed Open-Shell replacement. See the [feature-family parity inventory](open-shell-parity.md) for supported Linux equivalents and Windows-specific gaps.

## Implemented increments

- **Start:** two columns, GIO application search and actions, pinned and optional recent apps, drag ordering, editable standard-folder links, All Programs/Back navigation, search-first keyboard focus, Escape retreat and click-away dismissal. Personal artwork is installed locally and preserved by upgrades.
- **Native panel candidate:** unified pinned/running tasks, persistent pin dragging, graphical pin editor, hidden notification icons in an anchored popup, pink styling and a narrow far-right Show Desktop target. The separate candidate has a reversible next-login switch; development has not enabled it on the personal desktop. [Build and switch instructions](../panel/README.md).
- **Desktop modules:** Openbox edge snapping and keyboard halves, saved single-desktop configuration, screenshot capture/cancellation, optional Kate/Dolphin defaults and per-app dark themes, and personal busy-cursor generation. The ordinary pointer is inherited unless pink is explicitly selected.
- **Screenshot of open Start:** freezes the visible menu before region selection. Enter/Copy confirms and Escape/Cancel leaves the clipboard unchanged. This is separate from the ordinary global screenshot helper.
- **Setup safety:** preview, explicit module selection, original-setting backups, repeat installation and conflict-checked rollback. Live panel/shortcut restarts are refused. No automatic gaming installer is included.

## Verified scope

The current suite passes 58 automated tests using offscreen Qt, mocks and temporary homes. Separate X11 checks cover synthetic pin dragging, menu navigation and click-away, native task restore and pin launch/reopen, notification overflow, edge snapping, and screenshot capture/cancellation. The original global ScreenGrab path was pasted into isolated Writer and Draw instances. The newer open-menu capture path was tested both with private PNG output on the desktop and with real clipboard publication on an authenticated private Xvfb display. Writer and Draw pasted matching pixels; mid-drag cancellation preserved the completed capture, and replacement released the helper.

Kate/Dolphin default resolution and dark appearance were checked in temporary homes and separate application instances. The far-right Show Desktop target was visually inspected without activating it on personal windows. These are local checks, not clean-install or fresh-login acceptance. See [verification history](verification.md).

## Next work

1. Complete menu composition: pinned/recent section presentation, program-tree and folder cascades, configurable recent limits, opt-in document/settings search, and the split power control. Keep destructive actions behind native confirmation and never execute them during tests.
2. Complete native taskbar behavior and visuals: broader real-application identity matching, grouped window previews, attention/auto-hide transitions, keyboard focus, tray accessibility and supported progress/overlay data. Preserve native icon activation and context menus.
3. Validate long labels, larger fonts, narrow screens, multiple monitors and scaling. Maintain readable normal/hover/selected/disabled states and system fonts.
4. Exercise Show Desktop show/restore in a disposable desktop session, and verify vertical positioning separately. Do not hide personal windows as a test.
5. Use a clean CachyOS LXQt test system for install, upgrade, rollback and dependency acceptance. Verify next-login panel/autostart and single-desktop persistence at a user-chosen login. Do not force logout or restart the working session.

## One-desktop contract

The existing optional module persists Openbox `desktops/number=1` and `desktops/firstdesk=1`, preserving the original configuration and refusing conflicting placement rules. It does not migrate live windows. The preference means one virtual desktop, not one physical monitor.

Any future live migration requires explicit intent: inventory clients, move ordinary windows to EWMH desktop 0, preserve sticky windows, select desktop 0, then reduce the count. Verify all original clients remain and minimized windows can be restored. Keep the panel and window manager running. Support for other window managers needs independent configuration and rollback validation.
