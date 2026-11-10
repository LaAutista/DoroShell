# Verification status and historical checkpoints

## Current status — 2026-11-10

The published core archive passed 84 tests. The local, unpublished optional source archive passes 99 tests after extraction. The updated menu/helpers and Pin/Unpin panel are active on the development installation; wallpaper is staged only, disabled and muted. See [final optional verification](#final-optional-candidate-verification) for the runtime evidence and [installation/restore](optional-installation.md) for dependencies and reversible setup.

Still unverified: user-chosen normal login, clean CachyOS installation/upgrade/rollback, physical multi-monitor/mixed-DPI wallpaper operation, physical DPMS, broader locker compatibility and long-session performance. Private X11, temporary-home and mock-lock checks are not substitutes. No lock-screen animation is implemented.

The sections below record successive checkpoints. Counts, deployment states and remaining-work lists describe that checkpoint unless explicitly marked current; later evidence supersedes them without erasing it.

## Published core acceptance — 2026-11-09

The published core suite passed 84 automated tests. Global Print and open-Start Print use the same selection and annotation overlay. The native ScreenGrab importer was checked against every pixel of the finished crop. See [screenshot verification](screenshot-verification.md).

The updated native panel ran on the development desktop after an LXQt panel-module refresh. The same window manager and all five existing application windows remained. The 40-pixel bar showed the chevron and both clock lines with the existing icon size. On private X11, the calendar opened fully above the bar, and a synthetic notification app responded to mouse, keyboard and context actions in the overflow popup. Clock pixels and calendar bounds were also checked at scale factors 1, 1.5 and 2 with font DPI 96, 120 and 144. A real next-login check of this build and a clean CachyOS installation remain open.

The personal 28-frame GIF rebuilt the installed wait/progress Xcursor files byte for byte. A disposable X11 window loaded them at the configured 30 px size. XFixes returned every one of the 16 distinct visible poses over time for wait, watch, progress and left_ptr_watch. The source delays total 930 ms per cycle. Visual inspection showed a single turning character, or a single animated badge beside the arrow in progress. The source has an opaque white background. The ordinary arrow matched the inherited Breeze pixels and hotspot. Opting into pink changed the pointer color while preserving its alpha and hotspot. Disabling pink restored the original pixels, and rollback restored the temporary configuration bytes. A separate regression covers restoring a pre-existing pointer override and its mode. Personal artwork remained local, and the live cursor was not changed.

The approved transparent APNG was installed through the cursor module after a temporary-home upgrade/repeat/rollback check. The original GIF remains private and intact. The generated wait/progress cursors and aliases matched the private X11 candidate byte for byte at all five sizes, with the original timings, hotspots and ordinary-pointer choice. No live cursor refresh was requested.

## Current optional source packaging

`DoroShell-optional-desktop-candidate.zip` is built from an explicit source-file list in the working checkout, not from the older published Git revision. Each archived file is compared byte for byte with that checkout, then all 99 automated tests run from a fresh extraction. Personal paths/configuration, screenshots, media, credentials, caches and native binaries are excluded. This verification does not publish the archive or establish fresh-install acceptance.

## Published core source package acceptance

The source ZIP is made from the release revision with `git archive --format=zip --prefix=DoroShell/`. It contains the neutral SVG, pinned native build scripts, patches, upstream license notices, installer, runtime and tests. Build instructions are in the [README](../README.md) and [ScreenGrab importer notes](../screengrab/README.md). From a fresh extraction, run `python -m unittest discover -s tests -v`. The private X11 checks in `tests/check_core_x11.py`, `tests/check_screengrab_import_x11.py` and `tests/check_menu_clipboard_x11.py` exercise startup, native import, clipboard handoff and rollback using temporary homes. The builds need their development dependencies and network access to the pinned upstream repositories. The X11 checks also require Xvfb, xauth, Openbox and Python Xlib. The paste check uses LibreOffice and Python UNO.

## Earlier core checkpoint — 2026-11-09

The 69-test offscreen and temporary-home suite passed. A separate acceptance run used a fresh personal-prefix build of the pinned native panel, an authenticated private X11 display, Openbox and the LXQt shortcut daemon. It installed the menu, snapping and screenshot modules through the setup CLI, repeated the apply, staged the panel and started the installed LXQt session manager on the private display. With both the system and user autostart entries present, LXQt selected the user override. The only dock window belonged to the newly built panel executable. Real Super+Left/Right/Down keypresses positioned and restored a fixture window. Print cancellation retained the clipboard, and a completed region matched all 120×90 expected pixels. A separate private-display run pasted an open-menu capture into Writer and Draw and compared every pixel.

The native panel check exercised hidden-icon activation and dismissal, task restore, closed-pin launch, matching a reopened app, and drag order across panel restarts. Setup rollback restored the original Print action and Openbox file, kept unrelated shortcuts registered by the panel and recovered the profile edited by LXQt. Reproduce the combined test with `python tests/check_core_x11.py --run --xvfb /path/to/Xvfb --binary /path/to/lxqt-panel`.

On the existing CachyOS install, setup updated Start, configured snapping, changed the existing Print action through the running LXQt daemon and staged the replacement panel. The original panel file, personal Start image, favorites and unrelated shortcut settings were checked after installation. The active desktop continued running. Real next-login startup and clean-machine dependency testing are pending.

## Previous checkpoint

At this earlier checkpoint, the suite passed **61 automated tests**. Start navigation is installed from `13a1cc4`: real mouse/keyboard checks covered All Programs, typing into search, staged Escape retreat, click-away dismissal, pin dragging and persistence without launching a fixture app. Open-menu Print/cancel was rerun with a private output file and the existing clipboard remained unchanged.

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

## Historical remaining acceptance work — early prototype

This list predates unified native taskbar pins, the later screenshot checks and personal artwork installation. It is retained as historical evidence, not the current completion list. See Current status above for outstanding acceptance.

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

## Historical optional coordinated theme checkpoint

The optional-theme working candidate passes 91 automated tests, including four-palette switch/repeat/restore, preserved personal values, conflicting edits, simulated write failure recovery and portrait-click behavior. Temporary-home setup exercised installed menu/toolkit files and theme apply/switch/rollback. A private X11 test exercised the actual portrait chooser, accepted a synthetic picture and canceled a second selection without changing it.

Private X11 renders cover actual Dolphin, Kate, Openbox, Start and the separately built theme-capable panel for Windows, Polar, Heretic and Spring palettes, with a compositor. These checks do not imply clean installation, normal-login acceptance, or activation of the new panel on the personal desktop. Preview images include personal artwork and are not release assets.

## Historical optional wallpaper checkpoint

The combined working candidate passes 94 automated tests. The separately built PCManFM renderer passed the private-X11 acceptance check with moving video beneath clickable native icons, fullscreen and mock logind lock overlap, manual pause, private X screen-saver pause, synthetic GIF playback, a latched malformed-media error and pixel-checked restoration of the original static background. An actual Qt-controls smoke check verified Apply and Off saving choices in a temporary config directory. Setup staged the real candidate twice and restored it in a temporary home.

Heretic's active/inactive Openbox client padding now follows its dark palette; focused Kate and Dolphin renders were inspected. The theme/panel and wallpaper desktop builds are separate optional candidates. They were not activated on the personal desktop. Real lock/login, physical DPMS and multiple physical monitors remain untested; no lock-screen animation is claimed.

## Historical installed-controls and staged-panel checkpoint

The corrected coordinated-theme caption and Wallpaper controls button pass a focused UI regression and the existing large-font/narrow-window checks. The combined suite now passes 96 tests. Installed menu/settings/helper files were compared byte for byte and by mode with the candidate.

Start's already-open catalog staleness was reproduced with a disposable installed desktop entry. The fix uses Gio.AppInfoMonitor with a debounced Qt refresh, not application-directory polling. A real private-X11 install/remove/reinstall check preserved search/category/selection and missing pin records. Normal Start invocation still creates a fresh process; new installs do not become pins automatically.

The new native taskbar's private test passed closed-launcher, single-window, grouped-window and ungrouped Pin/Unpin paths, pin order and persistence across a disposable panel restart, surviving fixture windows and unchanged desktop files. An ambiguous desktop identity omitted Pin, confirmed in the actual menu render. The existing native popup/context/Open/launch/drag regression also passed on this build. The final candidate was staged without replacing the running glass panel or applying appearance choices.

The isolated Xvfb crash observed at 16:16 PST on 2026-11-09 belonged to a theme-rendering harness startup attempt in the restricted execution environment. That attempt failed before producing test evidence. The subsequently authorized private-display run completed successfully. The earlier failed attempt is not counted as a pass; no claim about the crash's low-level cause or GPU behavior follows from these logs.

## Historical 99-test optional candidate checkpoint

The combined source passes 99 automated tests. New regressions cover renderer status freshness/process identity, exact preservation and repeat/rollback of the existing Dolphin autostart hook, and printer management when print-manager/kcmshell6 are installed but systemsettings and system-config-printer are absent. Printer launch failures and missing management tools report errors.

Private X11 wallpaper testing established that the stock D-Bus owner prevents an in-place binary handoff even with a different profile. The native renderer removes its status report on desktop-off while preserving an open disposable file-manager window. The full private renderer acceptance check also passed. No live desktop handoff or real lock action was attempted.

The development wallpaper installation was staged with all four managed files verified and its exact original autostart baseline retained. Animation is disabled and muted. Media and the system PCManFM binary were unchanged; existing clients and monitored processes survived staging. A later independent check confirmed the staged files and binary stamp. This does not establish normal-login or clean-install acceptance.

The Pin/Unpin panel was activated separately through LXQt's panel-module API. Existing clients and monitored processes survived, configuration remained unchanged, and the real closed-pin menu displayed Open/Unpin. At this checkpoint the wallpaper remained staged only; see the later deployment status below.

The real private-X11 Printers check opened and rendered the KDE management window through Start. Its UI reported unavailable printing services and the optional system-config-printer support package; no service, package or printer configuration was changed. The initial probe exposed GIO rejecting the KCM desktop entry because systemsettings is absent. Detection now locates the installed module entry using Qt's standard data paths, then launches the fixed kcmshell6 command through GIO. The corrected probe passed. The installed menu was compared byte for byte with source after backup; personal pins, folders, panel and wallpaper settings were unchanged.

## Non-composited responsiveness checkpoint

A private X11 comparison rendered all four actual menu/panel palettes without a compositor, checked opaque samples against changing backgrounds, and recorded paired CPU, paint/damage activity and 100 synthetic search timings per palette/condition. An extra static highlight/bevel experiment was omitted after an uncertain Heretic tail-latency increase; the exact prior theme source was restored. No compositor was installed, configured or activated, and no personal theme/session was changed. The temporary package downloaded for inspection was removed; its version probe had failed on a missing library before any compositor could start. See [measurement evidence and limits](opaque-theme-verification.md). No physical input-latency guarantee is claimed.

## Drag, contrast and resource fixes — 2026-11-10

The final source and extracted optional archive pass 101 automated tests. An authenticated private X11 desktop verified actual Start drops onto empty taskbar space and existing task buttons, duplicate suppression, unsupported/remote/move-only rejection, cancellation, original launcher bytes/modes, unchanged Start pins and pin persistence across a disposable panel restart. PCManFM copied both pinned and searched application launchers to a desktop directory with spaces; filenames included spaces, apostrophes, ampersands and percent signs. The normal one-shot Start process also delivered both taskbar and desktop drops and exited successfully. No app was launched accidentally. Native Copy here confirmation and trust preferences were preserved.

The source keeps its drag data until Qt completes the target's deferred URI transfer. Successful external drops dismiss Start so its popup mouse grab does not consume the desktop confirmation click. Internal reorder, Escape cancellation and keyboard navigation regressions passed. Split power controls passed centered-glyph checks at three font sizes and private keyboard/confirmation checks with all power dispatch mocked.

The final native runtime passed existing closed/single/grouped/ungrouped Pin/Unpin checks. Synthetic white bell pixels met at least 4.5:1 contrast in normal, hover and keyboard-focus states with the native fallback and all four palettes, without a compositor. The new panel was activated through a guarded panel-only refresh: seven existing client windows and seven monitored processes survived, with settings unchanged. Menu installation was backed up and byte-checked.

The wallpaper resource correction passed the separate [resource acceptance](wallpaper-resource-verification.md). Its durable staged binary, four managed files, disabled/muted settings and original rollback baseline were independently checked. An older native renderer is currently active but disabled; the corrected binary is staged for its next normal startup. This is not a live renderer replacement or normal-login acceptance.

## Independent symbolic-icon review — 2026-11-10

Current compositor-free renders exposed dark system-theme control icons on Heretic's dark surfaces and the colored shutdown button. Only Start's symbolic search/navigation/session icons are now tinted to their control foreground; application artwork is untouched. All four presets and Back/session-menu icons have regression coverage. The full suite now passes 102 tests. Independent private-X11 checks cover open-Start Print/cancellation, exact clipboard paste, window capture at 100%/150%, native annotated import, wallpaper behavior and taskbar/desktop drag export. See the final acceptance matrix for reference comparison and remaining release gates.
