# Verification checkpoint — 2026-11-08

## Current checkpoint

The current suite passes **61 automated tests**. Start navigation is installed from `13a1cc4`: real mouse/keyboard checks covered All Programs, typing into search, staged Escape retreat, click-away dismissal, pin dragging and persistence without launching a fixture app. Open-menu Print/cancel was rerun with a private output file and the existing clipboard remained unchanged.

The native panel candidate includes the Show Desktop edge target from `f2c66ae`; a separate X11 panel rendered it at 12 pixels on the far right. A later authenticated private-X11/Openbox check verified actual mouse-click show/restore of two disposable windows in both horizontal and vertical profiles. The edge target measured 12 pixels in both orientations. Live orientation changes, pre-minimized windows and other window managers remain outside that check. Show/restore was never activated on personal windows. The personal panel was not replaced or restarted. Fresh-login, clean-install and multi-monitor/Wayland acceptance remain outstanding. The [roadmap](roadmap.md) and [native panel scope](../panel/README.md) describe remaining work.

Personal Doro image and animated busy cursor were installed in a later increment; the early missing-artwork notes below are historical. Likewise, the separate native panel now provides unified pinned/running tasks, beyond the older taskbar module described below.

### Framed portrait and split power control

The personal Start portrait is framed above the folder column. The default menu is 680×610 so all six default folders remain visible; smaller layouts retain scrolling. Offscreen appearance and geometry were checked, followed by private-X11 dragging, navigation, click-away and open-menu capture/cancellation regression checks.

The adjacent power arrow and primary shutdown button were exercised with real mouse/keyboard input on private X11, while all session dispatch was mocked. Cancel was verified as the default, Escape preserved the menu, and confirmed fake dispatch occurred once without recent-app history. Missing and unknown actions are covered by automated tests. The actual system was never locked, suspended, logged out, restarted or shut down. Native hardware/capability handling and changing the primary action remain further work.

### Categorized Settings

Settings now has five sidebar pages with shared Preview/Apply controls and a pending-change count across pages. Defaults remain Keep unchanged. All five pages were rendered and visually inspected at 16-point system text against a dark palette; normal, hover and selected navigation colors pass the contrast regression checks. A separate private-X11 check exercised real mouse/keyboard navigation, retained selections, preview without writes, actual temporary-home Kate association apply, and exact restore of the original MIME configuration. No personal defaults were changed.

### Production menu-capture clipboard path

`tests/check_menu_clipboard_x11.py` passed on an authenticated private Xvfb display with TCP disabled and a private session bus. It used synthetic image data, temporary homes and separate LibreOffice profiles. Escape before selection preserved a sentinel; a confirmed region published a 120×90 image; Escape during a later drag preserved that completed image. Actual Writer and Draw Paste each inserted one graphic, and all exported pixels matched. The clipboard owner stayed alive after capture and exited after the private clipboard was replaced. The personal clipboard was never addressed.

For this check, the official Arch Xvfb package was downloaded, its packager signature verified, and only its executable extracted into a private test directory. No system package was installed or changed. This verifies the real production helper's clipboard lifecycle, not every desktop clipboard manager or display configuration.

## Earlier verification history


DoroShell is a modular LXQt customization toolkit for CachyOS/Arch, not a replacement shell or a validated fresh-install image.

## Automated checks

`python -m unittest discover -s tests -v`: **34 tests passed**. Qt is offscreen; installer/module tests use temporary homes. Coverage includes menu geometry/search, folder editing and persistence, URI/session dispatch mocks, installer conflicts and rollback, cursor animation timing and optional pink-pointer removal, screenshot process lifecycle, module selection, Kate/Dolphin associations and dark-theme rollback, one-desktop element scoping, taskbar style switching/repeated updates/rollback, and personal Start-image retention.

A regression test exposed lost taskbar ownership records after changing style on a newly created taskbar. Updates now retain prior owned edits and their insertion order, restoring the original configuration exactly when no unrelated changes occurred. Personal edits still cause a conflict instead of overwrite. The snap helper's `stop` request now exits when no owner exists, instead of accidentally starting a helper during rollback.

## Local X11 checks actually performed

Tests used temporary settings, synthetic content, dedicated test windows and (for KDE apps) a separate D-Bus session. No desktop logout/restart, package installation, session/power action, or closure of existing applications occurred.

| Check | Observed result |
| --- | --- |
| Start search keyboard | A nonmatching query produced no results; clearing it restored results. |
| Folder editor | Mouse Add/Save with a real Qt directory-picker dialog, keyboard path entry, and reloaded folder-link persistence passed. The platform-native KDE picker was not automated successfully; the successful check used Qt's built-in picker, without mocking its returned path. |
| Settings UI | Keyboard selection, mouse Apply and Restore ran the real setup subprocess against a temporary home; the Kate manifest was created then removed. The settings window was visually inspected. |
| ScreenGrab | Real region drag + Enter → Escape cancel → region drag + Enter produced 120×90 images of the expected synthetic color; cancel preserved the previous image. Temporary capture directories were cleaned. |
| Paste after tool exit | Two separate LibreOffice test profiles/instances, Writer and Draw, accepted the real clipboard image via their Paste command. Each inserted one 120×90 graphic; exported pixels matched the test canvas. No user documents were opened. |
| Native icon taskbar | A temporary LXQt panel on a private D-Bus session used the generated icon-taskbar configuration. Clicking a uniquely colored test icon restored and focused its minimized window. The personal panel was not restarted or reconfigured. |
| Edge snapping | Actual titlebar mouse drags to left/right edges produced (0,0,1280,1408) and (1280,0,1280,1408) on the local 2560×1440 screen, respecting the panel work area. Restoring returned the test window to its original geometry. |
| Default associations | Both `xdg-mime` and fresh-process GIO resolved `text/plain` to Kate and `inode/directory` to Dolphin after opt-in in a temporary home. |
| Kate/Dolphin appearance | Installed applications opened synthetic files/folders with temporary homes and a separate bus. Their test windows were visually inspected and were dark. Global/personal preferences were unchanged. |

The earlier ScreenGrab X11 startup failure was a sandbox-access limitation. Authorized execution outside the sandbox connected successfully without changing X server permissions. The first drag-only test did not finish: this ScreenGrab selection requires Enter to confirm. The first fixed-coordinate test did not capture the intended canvas; the successful test used the test window's actual X11 coordinates and verified pixels.

## Remaining acceptance work

- **Accurate Doro artwork:** the full-size earlier references and spinning GIF were not present in the supplied new project folder. The panel strip is insufficient for an accurate redraw. Personal image import and animated cursor support are implemented; no substitute character, third-party skin or unlicensed artwork was bundled.
- **Fresh login and clean install:** neither was performed. One-desktop persistence and autostart require a user-chosen login and a clean CachyOS LXQt VM check.
- **Taskbar:** configuration, switching and rollback are tested. A real click/restore test passed on an isolated native panel; the personal panel was not reconfigured in this checkpoint. It offers icons/grouping for running windows; closed-app launchers remain Start/Quick Launch, not a Plasma unified pinned-task widget.
- **Display/clipboard breadth:** no Wayland, mixed-DPI/multi-monitor, negative-origin, no-clipboard-manager, long-session or simultaneous-process stress acceptance. Real Escape-before-selection passed; mid-drag Escape, zero-size confirmation and every ScreenGrab mode still need checks.
- **Folder dispatch:** GIO URI dispatch is covered by mocks, real default resolution and actual GIO default-handler launching into an isolated Dolphin window were also verified. This does not claim a live click of every personal folder link.
- **Installation scope:** default XDG home layout and standard panel1/Openbox layouts only. Package availability was verified; gaming installation commands were not executed.

The updated menu and settings launcher were installed after preview and backup; installed menu bytes matched the checkout. The existing personal Start image and cursor were retained because the full-size replacement references were unavailable. The project now lives in the user-selected folder; the original checkout was retained as a backup.

No screenshots from the personal desktop or test captures are committed. Source licensing remains a release decision. Open-Shell was used as a behavioral reference; no code, icons, skins or documentation were imported from it. Doro reference assets remain local pending provenance and the user's files.


### DockBarX dragging follow-up

A real X11 test reproduced lost drops in the installed DockBarX LXQt embedding. With the opt-in compatibility hook, left-button dragging reordered three synthetic pinned launchers, Escape left their order unchanged, and restarting the isolated test panel visually restored the saved order. The test used a temporary home and private D-Bus session; personal launchers were not rearranged. Regression tests cover native successful moves, horizontal/vertical placement, outside drops and Escape's cleared drag action. This is applet-restart persistence, not a fresh-login test.

The follow-up suite passed 39 automated tests. The hook was then enabled on the personal taskbar: the DockBarX child restarted under the same LXQt panel process, launcher order and panel configuration remained byte-for-byte unchanged, and all existing X11 client windows remained present. A private launcher-order backup was saved before activation. Personal icons were not rearranged during testing.


### Correction: live applet refresh is unsafe

After activation, Discord reported `write EPIPE` from console logging. Read-only process inspection found its stdout/stderr pipes had writers but no reader; other running applications shared those pipes. The applet refresh is the likely cause. Checking that windows survived did not establish application health. Live DockBarX refresh is now disabled unconditionally, avoiding both inherited-pipe failures and a check-versus-restart race. Applying or restoring the hook saves files for the next normal login. No applications were closed to test recovery. The existing drag hook remains active; Discord recovery and future-login activation remain unverified.
