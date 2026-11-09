# DoroShell implementation and acceptance roadmap

DoroShell customizes an existing LXQt desktop. The Windows 7 layout with pink Doro styling is the target; it is not yet an exact reproduction or a completed Open-Shell replacement. See the [feature-family parity inventory](open-shell-parity.md) for supported Linux equivalents and Windows-specific gaps.

## Visual target from the End Result concept

The reference shows the desktop with Start open above the left end of the taskbar. The surrounding illustrated cards describe settings and workflows. Use the relative proportions, alignment and contrast as the target across font sizes and display scales.

| Component | Target shown in the concept | Current fit or remaining work |
| --- | --- | --- |
| Start menu | A pale, wide app list with a Pinned heading, large icons, All Programs and a bottom search box. The narrower berry-colored column has a framed portrait above folder and system links, with a split shutdown button at its foot. | The two columns, portrait, bottom controls and editable folders exist. Home opens on labeled pins in saved order. Recent programs open in a separate view. |
| Advanced Start settings | A left navigation rail groups general settings, appearance, pins, folders, search, power and behavior. The preview shows controls for glass, icon size, recent programs and Start artwork. | The toolkit has category pages. Recent count and recording controls live in Start’s Menu options. The illustrated advanced editor remains a target. |
| Menus and search | Folder, system-tool and custom-item groups sit alongside separate search scopes for apps, files, settings and custom paths. | App search and editable folder links exist. File and settings search and custom search roots remain future work. |
| Taskbar and snapping | Glossy pink bottom bar with a distinct Start tile, compact app icons, open space, then a separated notification area and two-line clock. The settings card shows grouping, icon size, auto-hide and a snap preview. | The native candidate includes grouped tasks, the requested hidden-icons arrow and Show Desktop. Private X11 previews verified the right-aligned two-line clock, calendar and compact chevron with a registered notification item. Openbox snapping works; the settings and snap-preview presentation need comparison. |
| Screenshots | Capture a full screen, window or area, preview and annotate, then save, copy or share. | Print supports full desktop or adjustable area, immediate annotation, PNG saving and clipboard copy. The optional native ScreenGrab importer displays the exact annotated result. App sharing and video recording are outside the core workflow. |
| Modular setup | Four distinct actions for installing and managing modules, exporting a backup and importing it to restore settings. | Preview, apply and per-module rollback exist. Portable export/import remains a separate feature. |
| Cursor and artwork | A plain arrow at rest and an animated Doro busy cursor. Personal Doro artwork appears on the Start tile and framed portrait. | At the configured 30 px size, private X11 sampling matched the ordinary Breeze pointer and all 16 distinct Doro poses across the 28-frame wait/watch cycle. Progress uses the arrow with a single animated badge. The approved transparent derivative is installed only in the personal theme. The neutral SVG remains the distributed default. |

## Implemented increments

- **Start:** two columns, GIO application search and actions, pinned and optional recent apps, drag ordering, editable standard-folder links, All Programs/Back navigation, search-first keyboard focus, Escape retreat, click-away dismissal and split power controls with Cancel-default confirmation. Personal artwork is installed locally and preserved by upgrades.
- **Native panel candidate:** unified pinned/running tasks, persistent pin dragging, graphical pin editor, hidden notification icons in an anchored popup, pink styling and a narrow far-right Show Desktop target. The separate candidate has a reversible next-login switch; a process check found the earlier core build running and the corrected clock/chevron build in the next-startup wrapper. The latter has passed isolated LXQt startup. [Build and switch instructions](../panel/README.md).
- **Desktop modules:** Openbox edge snapping and keyboard halves, saved single-desktop configuration, screenshot capture/cancellation, optional Kate/Dolphin defaults and per-app dark themes, and personal busy-cursor generation. The ordinary pointer is inherited unless pink is explicitly selected.
- **Print capture:** global Print and Print inside Start use the same frozen-desktop overlay. Start waits until the image is frozen before closing. Enter/Copy confirms, Escape preserves the clipboard, and Open in ScreenGrab imports the cropped and annotated pixels into the native window.
- **Setup safety:** preview, explicit module selection, original-setting backups, repeat installation and conflict-checked rollback. Live panel/shortcut restarts are refused. No automatic gaming installer is included.

## Verified scope

The current suite passes 79 automated tests using offscreen Qt, mocks and temporary homes. A private X11 pointer test also verified recent-count trimming and persistence after reopening Start. Separate X11 checks cover synthetic pin dragging, menu navigation and click-away, native task restore and pin launch/reopen, notification overflow, edge snapping, and screenshot capture/cancellation. Private X11 checks covered both Print entry points and the shared overlay. Writer and Draw pasted matching pixels after the editor exited. Cancellation retained the previous image. ScreenGrab’s own Copy command returned every annotated pixel after native import.

Kate/Dolphin default resolution and dark appearance were checked in temporary homes and separate application instances. The far-right Show Desktop target was visually inspected, then its hide/restore action and horizontal/vertical dimensions were verified on disposable windows in a private Xvfb/Openbox session. These are local checks, not clean-install or fresh-login acceptance. See [verification history](verification.md).

## Core release acceptance still open

- Observe the corrected panel on the development desktop after a user-chosen normal login. The earlier native panel is running there. The newer build, tray popup, two-line clock and rollback were exercised in a private LXQt session.
- Run dependency setup, installation, upgrade and rollback on a clean CachyOS LXQt machine. Existing-system and temporary-home checks cannot establish that result.

## Broader roadmap

1. Complete menu composition: program-tree and folder cascades, opt-in document/settings search, and configurable primary power actions. Keep destructive actions behind native confirmation and never execute them during tests.
2. Complete native taskbar behavior and visuals: broader real-application identity matching, grouped window previews, attention/auto-hide transitions, keyboard focus, tray accessibility and supported progress/overlay data. Preserve native icon activation and context menus.
3. Validate long labels, larger fonts, narrow screens, multiple monitors and scaling. Maintain readable normal/hover/selected/disabled states and system fonts.
4. Extend the isolated Show Desktop checks to live orientation changes, pre-minimized windows, multiple desktops and other window managers. Basic horizontal/vertical show/restore has passed; do not hide personal windows as a test.
5. Use a clean CachyOS LXQt test system for install, upgrade, rollback and dependency acceptance. Verify next-login panel/autostart and single-desktop persistence at a user-chosen login. Do not force logout or restart the working session.

## One-desktop contract

The existing optional module persists Openbox `desktops/number=1` and `desktops/firstdesk=1`, preserving the original configuration and refusing conflicting placement rules. It does not migrate live windows. The preference means one virtual desktop, not one physical monitor.

Any future live migration requires explicit intent: inventory clients, move ordinary windows to EWMH desktop 0, preserve sticky windows, select desktop 0, then reduce the count. Verify all original clients remain and minimized windows can be restored. Keep the panel and window manager running. Support for other window managers needs independent configuration and rollback validation.
