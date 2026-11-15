# Open-Shell parity plan

Requested scope: account for all Open-Shell functionality, with Windows 7 as the current menu layout scope. The user explicitly selected Windows 7, not the other menu styles; Classic and other layouts are deferred unless explicitly requested. Keep the broader functionality inventory and reference comparisons below without treating other layouts as current delivery work. This is a feature-family inventory and implementation plan, not a claim of full parity or an exhaustive audit of every upstream setting. DoroShell is an LXQt toolkit, not a Windows shell implementation.

## Reference baseline

Reviewed 2026-11-08: [Open-Shell upstream](https://github.com/Open-Shell/Open-Shell-Menu), revision `729c3686d093da88ac70095aff18d09f4f1352cf`; [upstream overview/wiki](https://github.com/Open-Shell/Open-Shell-Menu/wiki); [predecessor feature reference](https://www.classicshell.net/features/). The predecessor page describes historical Windows-specific behavior; it does not prove that every feature works on current Windows. Before claiming exhaustive parity, enumerate the baseline's settings definitions and help topics into individual acceptance cases. This inventory is deliberately not a percentage-complete score.

## Menu coverage

| Feature family | DoroShell evidence / gap | Next acceptance condition |
| --- | --- | --- |
| Windows 7 layout | Pink two-column menu, Home and All programs; geometry tests exist. Not pixel-identical. | Mouse/keyboard review at supported DPI, screen edges and sizes. |
| Classic / other menu styles | Reference comparison only; other layouts are absent and outside the current Windows 7 layout scope. | Deferred pending an explicit request; the broad functionality goal does not authorize additional layouts. |
| Program discovery / search | GIO catalog and cached ranking; [real disposable desktop-entry acceptance](app-search.md#real-catalog-fixture-acceptance--2026-11-15) covers override visibility, duplicate IDs/names, localized/Unicode text, metadata updates and bounded install/remove notifications with focus/pin retention. | Real package transactions, fresh-login/distribution environments and larger-catalog responsiveness remain unverified. |
| Expanded search | Document/content/settings/provider search absent. | Explicit opt-in providers, cancellation and bounds; no unsolicited indexing of private files. |
| Pins / organization | Ordered pins, Home/Pinned drag reordering and context-menu movement; conflict-safe saved order. Taskbar dragging is a separate feature. | Verified with synthetic real pointer dragging, Escape cancellation, keyboard move commands and reopening persistence; broader DPI/accessibility coverage remains. |
| Recency / frequency | Recent apps with count, recording toggle, clear-history and optional [time-based retention](recent-apps.md); default has no age limit. | Frequency ranking and broader privacy controls; old backups/portable undo are outside active-history expiry. |
| Recent documents | Absent. | Opt-in desktop recent-file store, unavailable-file handling and clear-history semantics. |
| App tasks / jump lists | New desktop actions through GIO. This is only the common-task portion; Windows jump-list data is not read. | Real action dispatch plus action-less apps; later per-app documents with explicit backend support. |
| Folder cascades | [Lazy nested browsing](folder-cascades.md) is implemented with bounded helpers, cancellation, standard Qt keyboard traversal and separate folder-label opening. Symlinks/special files are omitted. | Existing synthetic/private checks do not establish actual handler, slow network-mount or clean-session acceptance. |
| Custom shortcuts / commands | Folder-link add/rename/reorder/hide, standard XDG directories and [configurable separators](start-separators.md) with path-free portability. Arbitrary menu structure absent. | Composed submenus and desktop-entry-backed commands; no shell parsing of Exec strings. |
| Item context operations | Pin/unpin/reorder and app tasks; rename/delete/sort/properties incomplete. | Edit only user-owned shortcuts; deleting a shortcut must never delete the application. |
| Keyboard / activation | Bounded [search/results and cross-column navigation](start-keyboard.md): Right enters usable places/controls; Left returns to results/search, with focus retention, Home/End and native popup ownership. Synthetic offscreen/installed tests. | Mnemonics, broader directional layouts, AT-SPI/screen-reader and live X11 acceptance remain unverified. |
| Original menu access | Integration preserves configuration for rollback; no Shift-click alternate-menu gesture. | Keep a reachable LXQt menu and configurable alternate gesture without overriding personal bindings. |
| Session controls | Configurable primary, Cancel-default confirmation, GIO LXQt dispatch/native fallback and [read-only logind capability states](power-capabilities.md). Unknown/denied/unsupported actions are disabled; saved primary retained. | Live service/authorization and hardware acceptance remain unverified; tests use fake capability/dispatch responses and offscreen widgets only. |
| Button customization | Local image import with backup; multiple hover/pressed states absent. | Separate button-state assets, sizing and small-icon legibility. |
| Skinning | Pink stylesheet and inherited desktop behavior; no Open-Shell skin-file compatibility. | Versioned native theme schema, preview/revert, metrics and contrast tests; audit any future importer. |
| Localization / RTL | English strings; complete translation and RTL behavior unverified. | Translation catalogs, RTL layout, input-method tests. |
| Accessibility | Qt widgets supply a foundation; no accessibility parity established. | Accessible names, focus order, high contrast and actual AT-SPI/screen-reader checks. MSAA is Windows-specific. |
| Settings / portability | Independent opt-ins, preview, backups, repeat application, scoped rollback and validated portable Start preferences excluding private history/paths. | Broader policy/portability coverage beyond the existing bounded Start allowlist. |
| Taskbar appearance | LXQt native taskbar option and optional DockBarX compatibility; not upstream taskbar skinning. | Native theme controls with rollback; never refresh a live panel to apply them. |
| Store apps / architecture | Real GIO discovers synthetic user/system Flatpak exports when their share roots are in XDG_DATA_DIRS; unregistered roots are excluded. | Actual Flatpak installation/launch remains unverified. No claim of UWP, COM or 32/64-bit Windows ABI compatibility. |

## Explorer and browser coverage

The upstream project includes **Classic Explorer** and **Classic IE**, not only a menu. Their DLLs, Explorer hooks, Windows copy-dialog interception, COM interfaces and Internet Explorer security zones have no direct host in LXQt. Running Windows software in Wine does not add these integrations to Dolphin or a Linux browser.

| Upstream area | Practical Linux disposition |
| --- | --- |
| Explorer toolbar, Up and file operations | Plan an optional Dolphin profile using supported settings/actions; currently only default association and dark-theme opt-ins are implemented. Test on temporary files. |
| Status information | Audit Dolphin's size/free-space displays and configuration; not yet configured or verified by DoroShell. |
| Address/navigation appearance | Evaluate editable paths, tree behavior and expansion controls individually against Dolphin; no Explorer-patching promise. |
| Properties and shortcuts | Test Dolphin keyboard equivalents including navigation-pane focus; do not assume every Windows shortcut is identical. |
| Classic copy conflicts | Native file-manager conflict dialogs are the candidate equivalent. No copy engine or global dialog interceptor is implemented. Test duplicate names, skip/replace/keep-both and cancellation with disposable data. |
| Historical Explorer repairs | Windows-specific overlays, pane fixes and titlebar buttons require per-item disposition, not Linux patches to nonexistent Explorer behavior. |
| IE title/progress display | Browser-native controls are candidate equivalents, not implemented DoroShell extensions. |
| IE security zones | No direct equivalent promised. Modern browser site permissions/security UI require a separately designed behavior mapping. |

## Delivery order and definition of done

1. Preserve session safety and establish independent acceptance cases from the pinned upstream help/settings inventory. Record supported, partial, absent or incompatible for each case; don't mark a Windows-only feature implemented because a Linux tool has a similar name.
2. Complete Windows 7 menu interactions: app actions (first increment here), keyboard behavior, program-tree/cascades, pin organization, configurable recent items, search providers and editable menu composition. Each needs offscreen regression tests and isolated real mouse/keyboard checks.
3. Complete native themes, button states, translations/accessibility and preference import/export for the Windows 7 experience. Other menu layouts remain deferred pending an explicit request.
4. Build opt-in Dolphin/browser equivalents where public APIs exist. Unsupported Windows-specific behavior remains documented; exact full Windows binary compatibility would be a separate Windows product, not a CachyOS module.
5. Verify clean CachyOS LXQt installation, repeat install, upgrade/rollback and a user-chosen fresh login. Test supported monitor/DPI layouts and dependencies. None of these release gates is satisfied merely by unit tests.

## Artwork gate

The supplied concept sheet was visually inspected: it shows a Start button, four illustrated tumble poses and a menu composition. It is not an animated GIF and contains no original publisher URL or asset license. It is a visual reference, not verified official art. [Good Smile's licensed DORO product](https://www.goodsmile.com/en/product/1138582/DORO%2BDorothy) provides an official product reference and credits SHIFT UP; that page does not grant permission to bundle its photographs as software artwork.

Use the exact official image/animation when its original source and applicable permission are supplied or verified. Preserve the current personal image and cursor meanwhile. Do not crop the concept into a supposedly official asset, invent an animation, or redistribute a product photograph. The neutral repository SVG remains the default under project guidance. Open-Shell's upstream MIT source license does not license Doro artwork, Windows assets or third-party skins; no upstream implementation/assets were copied in this increment.


## Verification of this increment

42 automated tests passed (Qt offscreen, mocks and temporary homes). New checks exercise task selection without changing favorites, invalid-action rejection and duplicate dispatch prevention. A separate real GIO desktop-action check launched a synthetic Python helper and verified its output file in a temporary directory. It did not launch a personal application. No real pointer/keyboard acceptance of the new context items, fresh-login or clean-install test was performed. No panel, applet, desktop session or personal application was restarted.


### Personal artwork resolution

Subsequent user-supplied assets enabled personal installation of the chosen Doro image and the visually matching original spinning animation recovered from Tenor. See [asset provenance and validation](assets.md#personal-assets-installed--follow-up). Redistribution permission remains unverified, but no longer blocks that personal installation. The full Open-Shell parity gaps above remain open.


### Start pin dragging follow-up

50 automated tests passed. A real X11 check with disposable desktop entries verified drag ordering, Escape cancellation, keyboard Move pin up, reopening persistence, and no accidental application launch. Existing favorites use the same backup and conflict checks for mouse and context-menu changes. No live panel or session was restarted.
