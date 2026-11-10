# DoroShell: Windows 7-style menu and modular setup plan

Status: investigation and proposal only. No live settings or menu behavior changed.

DoroShell remains an **LXQt customization/setup toolkit**, not a standalone desktop environment or replacement shell. Use Open-Shell's **Windows 7 menu style** as the interaction reference. Do not build a style selector or reproduce its Classic styles, Explorer extensions, Internet Explorer integration, or Windows 10-specific behavior.

## Evidence and scope

Inspected Open-Shell upstream commit `729c3686d093da88ac70095aff18d09f4f1352cf` and the current local DoroShell menu source. Primary references:

- [Windows 7 style, operation, customization, search and settings help](https://github.com/Open-Shell/Open-Shell-Menu/blob/729c3686d093da88ac70095aff18d09f4f1352cf/Src/Localization/English/StartMenu.html): Windows 7 style section around lines 85–95, settings around 130–175, search around 271–302.
- [Actual menu settings](https://github.com/Open-Shell/Open-Shell-Menu/blob/729c3686d093da88ac70095aff18d09f4f1352cf/Src/StartMenu/StartMenuDLL/SettingsUI.cpp): Windows 7 defaults around 4107–4111; ProgramsStyle, PinnedPrograms, RecentPrograms, ShutdownCommand and search settings around 4283–4396.
- [Installer feature definitions](https://github.com/Open-Shell/Open-Shell-Menu/blob/729c3686d093da88ac70095aff18d09f4f1352cf/Src/Setup/Setup.wxs#L57): separately selectable StartMenu, ClassicExplorer, ClassicIE and Update components.
- [Source and asset notices](https://github.com/Open-Shell/Open-Shell-Menu/blob/729c3686d093da88ac70095aff18d09f4f1352cf/Src/LICENSE.txt), plus [root license](https://github.com/Open-Shell/Open-Shell-Menu/blob/729c3686d093da88ac70095aff18d09f4f1352cf/LICENSE).

The generic wiki mixes styles. The style-specific help is more useful: Windows 7 has a defined left column for pinned/recent applications, All Programs and search; the right column is customizable. Search results and jump lists stay inside the menu. All Programs can be inline or cascading. Its customization editor does not offer the arbitrary nested menu construction described for Classic styles. Folder expansion is a separate behavior; do not equate it with unrestricted custom submenu design. The help explicitly limits additional search-provider subitems to Classic styles: exclude these from the Windows 7 parity target.

## Prioritized feature comparison

| Priority / feature | Open-Shell Windows 7 evidence | DoroShell today | Proposed LXQt behavior |
|---|---|---|---|
| P1: personal links | Customizable right column; item labels, commands, links and icons | Six hardcoded standard folders with correct user-directory resolution | Add/remove, rename, reorder and hide folder links through a small menu-settings dialog. Use standard-directory IDs for defaults and explicit paths for custom folders. |
| P1: home / All Programs | Pinned and recent/frequent applications on the initial view; All Programs inline/cascade setting | Opens alphabetical All applications; Pinned is a combo-box filter | Home view with ordered pinned items and optional recent/frequent list; All Programs / Back navigation in the left column. Preserve right column and search. Inline first; cascade optional later. |
| P1: pinning | Pinned applications and configurable recent/frequent lists | Pin/unpin persists IDs, but display iterates the alphabetical catalog rather than saved order | Honor saved pin order, provide keyboard-accessible move up/down; then drag reorder. Handle removed apps without deleting unrelated pins. |
| P2: usage history | None/recent/frequent modes and maximum item count in settings | No usage tracking | Track only successful DoroShell launches initially, with off/recent/frequent, count limit and clear-history control. Explicitly not system-wide usage parity. |
| P2: search | Programs, PATH entries and indexed files; results inline; configurable focus/keywords/subwords | Case-insensitive all-word substring filter over name, description, executable and keywords; restricted to current category | Search across applications from any view; rank exact names, then prefixes, then other matches. Preserve keyboard behavior. File search and PATH execution remain separate, optional investigations. |
| P2: session controls | Windows 7-specific main action, available logout/lock/sleep/etc. choices and confirmation settings | Opens LXQt Leave chooser; no one-click destructive action | Keep the chooser as default. Later add a configurable main action plus adjacent options, based on installed session services and capability checks. No assumed switch-user support. |
| P2: configuration | Basic/all settings, setting search, defaults and XML backup/load | Favorites JSON only; fixed UI; launcher opens LXQt system settings, not DoroShell settings | A compact DoroShell settings dialog for links, home view, history and search; validated versioned JSON import/export/reset. Use JSON, not Windows XML compatibility. |
| P3: folder contents | Folder-linked items can expand; Win7 editor is less general than Classic | Clicking opens the default file manager | Optional Open as link / Browse folder for supported folder items, lazy enumeration and Open folder action. Verify behavior and focus; no unrestricted nesting editor. |
| P3: recent documents / jump lists | In-menu jump lists and recent documents documented | None | Investigate desktop-entry actions and freedesktop recent-file records. These are partial Linux equivalents, not Windows Jump List compatibility. App support and privacy remain uncertain. |
| P3: appearance | Skins, custom Start button, dimensions and other settings | Hardcoded colors/dimensions; neutral icon in shareable checkout; personal artwork separate | Font/icon size, contrast, width and permitted custom button image. Preserve one Win7-style structure; no skin engine or Windows asset import in the first release. |

Current implementation findings come from `menu/start_menu.py`, especially `FOLDERS`, `applications`, `matches`, `refresh`, `context_menu` and `run_desktop`. The shareable and personal installation differ in title/icon; do not reinstall the neutral publishing copy over personal choices merely to implement this plan.

## Modularity: components versus menu options

Open-Shell's installer components are actual optional products; pinned items, search and skins are settings inside its menu. DoroShell should follow that distinction, without a general plugin framework or one package per checkbox.

| Independently selectable component | Dependencies / ownership | Present status and removal boundary |
|---|---|---|
| Menu | Python, Qt/PySide6, GIO; optional calls to LXQt settings/session dialogs | Implemented. Owns launcher/assets/desktop entry and menu preferences. Does not require taskbar, cursor, Dolphin or workspace modules. Retain user preferences by default on removal. |
| Panel and shortcut integration | Menu plus LXQt panel/global shortcuts; depends on supported existing layout | Implemented with narrow layout assumptions. Owns only its button/shortcut keys. Remove this before menu files; menu removal must refuse dangling integration or offer dependency-ordered removal. |
| Cursor | Xcursor tooling/library and a user-supplied permitted asset/base theme | Local uncommitted cursor module and tests exist; not re-audited or tested in this investigation. Own cursor assets and precise theme settings independently. Keep optional and asset-free by default. |
| Taskbar | Existing LXQt task widget; optional alternate widget only after checking packaging/maintenance | Planned. Own taskbar grouping/icon/visibility options only. No dependency on menu. Preserve other panel widgets and user launchers. |
| Window behavior | Detect actual window manager; separate toggles for single desktop and edge snapping | Planned setup module. Single-desktop live repair was separate; do not overwrite it. No automatic WM replacement. Unsupported snapping must be reported rather than faked. |
| File manager integration | User-selected installed file manager; Dolphin optional dependency | Planned. Own specific folder associations/launchers; do not remove the LXQt desktop manager. File-picker parity is not promised. |
| Screenshots | Selected installed capture utility and nonconflicting shortcuts | Separate later module from the original project scope. Not an Open-Shell menu feature or a dependency of the menu. |

A shared installer dispatcher can expose plan/apply/status/remove for named components, with an explicit Windows 7-oriented preset that previews its component selections before application. Those commands/preset do **not** exist yet. Preset preferences can include the requested one-desktop default while allowing users to select the menu alone. No automatic package installation, WM substitution, or hidden enablement of sibling modules.

Common contract: detect requirements; show dependency and setting changes; back up original contents/permissions and absence; record owned keys and installed hashes; make writes atomically; no-op if already configured; refuse conflicting personal edits; preserve preferences unless explicitly purged. Package removal must not uninstall shared dependencies automatically. Remove dependents first. Refresh only affected services when authorized, never the whole session. Export options without history, private paths or personal artwork by default; require explicit inclusion for machine-specific data.

## Phased implementation and acceptance gates

**Phase 1 — customizable right-side folders (recommended first).** Add a minimal Menu settings action and Links editor: add folder through a picker, edit label/icon, reorder, show/hide, restore defaults. Keep the exact working layout and current links initially. Store a versioned options file alongside existing favorites, not in LXQt panel config. Validate schema and paths, preserve malformed existing files, back up before migration and use atomic saves. Acceptance: default appearance unchanged, custom folder survives restart, missing/renamed folder reports an error, non-English/spaced paths work, keyboard editing works, reset affects only owned link options, and rollback restores the earlier menu/config.

**Phase 2 — the Windows 7 landing page.** Honor pin order, add Home ↔ All Programs, and optionally show recent/frequent successful menu launches. Preserve existing favorite IDs. Record no history when disabled; offer clear and item limits. Acceptance: pins and order survive restart; failed launches do not count; removed apps do not break rendering; search and Escape work from either view. Test actual pin/save/reorder persistence, not only launch mocks.

**Phase 3 — search and menu behavior.** Rank application matches and search across categories; support clear/back behavior, arrows, Enter and focus restoration. Verify click-outside dismissal, submenu/settings dialogs, repeated button activation, monitor positioning and large catalogs on X11. File indexing is not a prerequisite. Acceptance: predictable ranking, responsive typing, no duplicate menu processes, no accidental launch from category changes, correct positioning at tested panel edges.

**Phase 4 — session options and portable preferences.** Retain LXQt Leave fallback. Verify available session methods before adding optional quick actions; confirm logout/reboot/shutdown. Add menu-specific export/import/reset and basic appearance options. Switch user stays unavailable until the display-manager path is verified. Tests mock power actions; real logout/login is a separate user-scheduled check, never an automated destructive smoke test.

**Phase 5 — component installer and fresh-install validation.** Consolidate existing install/integrate scripts behind the small module contract; assess cursor work independently; add taskbar/window/file-manager modules only through their own scoped changes. Test combinations: menu-only, integration removal with menu retained, cursor-only, full selected preset, repeated application, rollback after unrelated user edits, missing dependencies and interrupted application. Perform clean CachyOS LXQt VM and user-initiated login checks before claiming repeatable fresh-install support.

**Phase 6 — optional richer integration.** Only after core acceptance: lazy folder browsing, desktop actions/recent-document experiments, optional file-search backend, additional panel layouts and window managers. Document partial equivalents. Do not promise Windows Search, Windows jump-list tasks, Explorer integration, or Windows skin-format compatibility.

## Recommended decision and exclusions

Proceed first with customizable right-side folder links: it directly addresses the original need and introduces only the configuration needed for that feature. If visual Win7 fidelity is the higher immediate priority, swap Phases 1 and 2, keeping recent-history collection optional. Neither choice requires a rewrite or a new desktop shell.

Uncertainties: system-wide app history, consistent per-app recent documents, file-index provider, display-manager switch-user support, popup anchoring on every panel layout, full accessibility and Wayland behavior. All remain research/test items, not promised parity. GitHub publication remains a separate task; this planning file has not been committed or uploaded. Existing uncommitted cursor/README work was left untouched.

## License and attribution boundary

The root license is MIT, and `Src/LICENSE.txt` identifies source-code copyrights for Ivo Beltchev and the Open-Shell Team. If source code is reused, retain applicable copyright/permission notices and document provenance. **Do not treat the root MIT label as blanket permission for assets:** the detailed source notice separately restricts bitmaps, icons, skins and HTML documentation, and addresses the Open-Shell name/logo. Use independently authored UI/assets and links to upstream documentation; do not copy its skins, Microsoft art, branding or documentation into DoroShell. No upstream code/assets were imported in this investigation. Unverified Doro artwork stays outside the shareable repository. DoroShell's original source is now GPL-2.0-or-later with existing component terms preserved; see ../LICENSING.md. Referencing Open-Shell does not assign its license to our code.

## Explicit follow-on requirements: snapping and screenshots

Keep Start-menu work first. These requirements extend DoroShell beyond Open-Shell's menu reference; they are not claims about Open-Shell features.

Read-only baseline: LXQt session configuration selects Openbox; installed package is Openbox 3.6.1. Print currently points to a custom `lxqt-region-to-clipboard` helper, not directly to the installed ScreenGrab 3.2.0 UI. The helper runs ImageMagick `import`, decodes PNG output with GdkPixbuf, and keeps a GTK process alive to own the X11 clipboard. This explains why the implementation needs a full clipboard/cancel lifecycle review, but does not by itself prove the cause of the reported failures. Before implementation, verify the actual running WM/compositor, effective config, installed capture tool behavior, clipboard manager, and all Print bindings. Do not publish personal helper paths or account configuration.

### Window-behavior component: edge-drag snapping

Required result: drag a normal resizable window to a monitor's left or right edge, release, and it occupies that half of the monitor's usable work area. Pair two windows without manual resizing. Preserve normal dragging, restore behavior, other monitors, panel visibility and the one-desktop setup.

First test whether the running WM supports the required drag behavior. Configure a verified native facility if available. If Openbox cannot provide it, present a concrete, separately tested optional WM integration/replacement choice with rollback before switching it. A keyboard-only half-screen shortcut is useful but does not meet this requirement. Do not silently add a second WM or compositor, change window decorators, or replace the session to simulate snapping.

Acceptance on X11:

- Mouse: snap two different applications left/right; verify window frames fit within work area and do not cover reserved panel space. Restore by dragging away; maximize, restore and snap again; repeated operations leave usable window geometry.
- Keyboard: offer documented nonconflicting left/right shortcuts, test focus and restore, and retain ordinary Alt-Tab. Do not replace existing user shortcuts without surfacing the conflict.
- Displays: primary/secondary monitors, unequal resolutions, negative monitor coordinates, top/bottom/side panels and auto-hide if supported. Test internal monitor seams versus outer edges, monitor hotplug and application movement between screens. Document mixed-scale limitations rather than promising universal correctness.
- Special windows: dialogs, fixed/minimum-size windows and fullscreen applications should be excluded or constrained predictably. Do not resize hidden/minimized apps unexpectedly.
- Lifecycle: single desktop remains intact; logout/login persistence is checked only at a user-chosen time; rollback restores only this component's previous config and does not lose existing windows. Validate WM replacement, if chosen, in a disposable session/VM before applying it live.

### Screenshot component: Print → capture UI → clipboard

Required result: Print opens the selected default screenshot UI, a successfully completed capture automatically becomes a pasteable clipboard image, and cancelling cleanly returns to the desktop without replacing the previous clipboard with a stale or partial image. Prefer verified native tool settings/API over another ad-hoc capture overlay. ScreenGrab is the first installed candidate to investigate; do not assume a particular flag or cancel signal exists until checked.

Define success as a new capture from the current invocation with a successfully decoded complete image. Use a unique invocation identifier/file if output files are necessary, never an old shared screenshot filename. Failure, zero-sized selection, Escape or Cancel must not modify clipboard ownership/data. Keep prior clipboard contents on cancellation; they may intentionally be an older image, but must not be presented as a newly captured result. Do not use clipboard clearing as a workaround.

Acceptance on X11:

- Print opens exactly one capture UI and existing conflicting shortcut bindings are resolved explicitly. Keyboard selection/Enter and mouse drag selection both work where supported by the chosen tool.
- Capture selected region, window and full screen using the supported UI. Paste into two independent applications after the overlay/tool exits and verify image content/dimensions, not merely clipboard MIME metadata.
- Escape before selecting, Escape mid-drag, Cancel in the UI, zero-sized selection and tool error leave the original clipboard unchanged and no overlay/input grab behind. No stale temp image is copied.
- Capture A → cancel B → capture C yields A unchanged after B and C after success. Rapid Print presses, repeated successful captures, overlapping invocations and late-arriving output cannot overwrite a newer result. Define second-press behavior explicitly: focus/cancel existing UI or ignore until it completes, rather than stacking overlays.
- Test each monitor, a selection crossing monitors, nonzero/negative origins, different resolutions/scales and panel regions. Confirm which full-screen mode means all monitors versus the active monitor.
- Verify clipboard persistence both with and without a clipboard manager. If an owner process is required, it must release/exit on replacement, avoid accumulating orphan processes and retain no unused temp files. Test pasting after several seconds and after switching applications.
- Installer changes only the selected Print binding and tool-specific owned options, preserving other screenshots/shortcuts. No duplicate compositor, capture daemon or shortcut registration. Rollback restores the previous binding and clipboard helper without touching unrelated session settings.
