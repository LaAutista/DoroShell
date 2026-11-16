# Changelog

## 0.2.0-dev — 2026-11-14

- Mouse & Touchpad: disable acceleration on libinput mice that offer the flat
  profile, using the same saved-choice, login reapply and exact-restore flow as
  evdev profile -1. Receipt validation now accepts the libinput property. Mock and
  read-only device checks pass; not applied live, and hotplug still needs Refresh.

- Mark US federal holidays (US locale) and daylight-saving begin/end days in the
  clock calendar with bold underline and tooltips (`0012` panel patch). Native Qt
  offscreen checks and a real-flag compile pass; no full rebuild or live check.

- Validate both supplied and resolved build/prefix paths; refuse symlink aliases
  introducing CMake separators or control characters before build writes.

- Select pinned build-tools 2.4/2.5 from liblxqt development metadata before
  acquisition. Add actionable read-only preflight, prepared-prefix selection,
  build provenance and dependency-aware deployment cache reuse. A real private
  2.5 build/staging passes; no host installation, version bypass or runtime claim.

- Fix compact calendar popup bounds: reserve space for a required scrollbar and
  respect the available work area without expanding it to the panel edge. Add
  native Qt offscreen source regressions. A later full build passes with matching
  cached liblxqt 2.4/build-tools 2.4 in a private prefix; default host liblxqt 2.5
  still needs compatible dependencies. No system install, version bypass or live
  update. A separate independent full build also passed all 1,367 steps without
  installing or executing the panel.

- Document already-shipped automatic fullscreen wallpaper pause: default-on with
  opt-out, monitor/workspace scope, independent reasons and polling delay. Correct
  stale unpublished-isolation wording using source history; retain historical
  private-test and live-deployment boundaries. No runtime behavior change.

- Add read-only application Properties with selectable bounded GIO metadata,
  explicit missing/stale status and native keyboard-context invocation. Preserve
  native popup/modal ownership, preferences and return focus; no Exec/file access
  or new helper dependency. Clarify setup versus bootstrap/deploy package behavior.

- Add a default-off Recent Documents submenu reading bounded shared desktop XBEL
  metadata on explicit open. Use a cancellable worker, omit private/unsupported
  entries, keep availability unverified and launch only through GIO on selection.
  No target scans, shared-history changes or portable history export. Install the
  helper in runtime/toolkit with existing conflict-aware lifecycle handling.

- Add actual GIO disposable catalog acceptance for desktop overrides, duplicate
  names, Unicode/localized search, registered Flatpak export roots and event-driven
  updates with pin/focus retention. Verify installed helpers and repeat/removal;
  no runtime defect reproduced and no catalog/installer behavior changed.

- Connect Start results to right-hand places/options/session controls with bounded
  Right/Left focus traversal. Skip unavailable/separator rows, preserve surviving
  folder focus across rebuilds and reveal scrolled targets. Keep text editing,
  Tab, native popup/modal ownership and existing action dispatch; no new layout.

- Refresh Start's cached wallpaper surface after Qt's initial show completes so
  the first backdrop paint uses the mapped popup coordinates. Add first-paint and
  fractional-alpha/texture tests; retain decode fallback, themes and X11 mask.
  Synthetic evidence does not establish the cause of reported live color/edge issues.

- Record combined cross-revision upgrade/recovery/removal and installed-toolkit
  acceptance on `660de77`, without runtime changes. Clarify old-program retention
  limits, full-source versus reduced-toolkit entrypoints and current publication
  versus historical live evidence. Restore the requested Windows 7-only layout
  priority while keeping the full functionality/reference inventory.

- Add bounded read-only power capability checks, truthful disabled/authorization
  states and primary-button consistency without changing native session dispatch.

- Add editable Start folder-link separators, noninteractive collapsed rendering,
  versioned path-free portability and disposable/offscreen lifecycle checks.

- Complete bounded Start search/results keyboard navigation: Up enters the last
  usable result, list-edge arrows return to search, Home/End skip unusable rows,
  Tab includes results, and focused rebuilds retain selection. Preserve text editing,
  nested menu/Escape behavior and fake-tested Enter; guard disabled/stale rows.

- Add optional recent-app age retention, off by default, with local launch timestamps,
  event-driven expiry, bounded legacy validation and visible save failures. Portable
  preferences carry the policy only; history/timestamps stay private. No background
  polling or new history backups for timed operations; older backups remain intact.

- Extend explicit custom config roots to snapping and combined single-desktop,
  relocating only XML/autostart config. Share writer locks, preserve unrelated XML
  and exact original programs/modes, refuse root/path/ownership conflicts, and keep
  conservative interrupted shared-file recovery. No live activation or XDG migration.

- Fix custom config-root symlink-ancestor refusal in module/setup paths: an in-home
  alias could redirect XML writes into reserved storage. Check root, target and
  ownership path components before writes; retain strict environment mismatch checks.
  Make three temporary-home fixtures bind their own config environment.

- Add bounded explicit config-root support for the config-only single-desktop adapter
  through deploy/setup/local bootstrap, with recorded choice, root/path conflict refusal,
  phased recovery and exact undo. Preserve default configs and unrelated XML; no
  runtime/data/state relocation or live activation. Other custom-root combinations refuse.

- Add optional `start-shortcut` deployment/bootstrap/setup support for Alt+F1, with
  current/proposed preview, explicit custom replacement, recorded review/ownership,
  interrupted recovery and exact restoration. Preserve unrelated bytes and refuse
  subsequent shortcut-file edits; no live shortcut reload or default takeover.

- Reject invalid options and conflicting actions before prerequisite authentication
  in bootstrap and the README downloader. Keep the downloader's option set small;
  local bootstrap/deploy retain advanced operations. Test zero external commands
  for malformed requests and catalog compatibility for valid module selections.
- Restore automatic, explicitly approved prerequisite stages in the copy-paste
  installer: curl, Git/Python and missing PySide6/GIO validation imports. Print plans,
  keep normal sudo/pacman confirmation, stop on cancellation/failure and revalidate
  before module/configuration writes. Plan/`--no-packages` never install. Add scoped
  `deploy.py --prerequisites` guidance and actionable import diagnostics.
- Carry explicit `--panel panelN` through bootstrap/deploy, record it for repeat and
  recovery, and validate selection before package/build/managed writes. Resume saved
  first-profile staging after interruption. Retain exact undo and legacy single-panel
  records; newer explicit-choice schemas are refused by older installers.
  Acquisition needs Git/Python already available; explicit validation needs PySide6/GIO.
- Add explicit `panel/profile.py prepare --panel panelN` for standard multi-panel
  profiles through the existing prepared-plan/setup workflow. Preserve other INI
  sections and selected geometry; refuse shared/ambiguous widgets instead of guessing.
  Package the layout helper and target sizing, clipboard and Quick Launch changes
  to the unique DoroShell panel. Deploy/bootstrap now reuse this adapter explicitly.
- Recover a completed native-panel step after the unrelated stock LXQt layout gains
  a second panel. Verify the recorded output bytes/modes first and retain the stock
  layout; unfinished work still requires a valid supported preparation.
- Update bootstrap and handoff instructions for the public repository: curl/Git need
  no GitHub CLI, account or token. Anonymous fetch disables credential helpers and
  terminal prompts per command. Preserve complete-download-before-execution checks.
- Document single-desktop's next-login boundary and verify repeat, scoped XML edits,
  conflict refusal and exact restoration in disposable files.

- Install the existing `single-desktop` module by default: Openbox gets one desktop, so
  Ctrl+Alt+arrows, Win+F1–F4 and the desktop scroll wheel no longer switch desktops.
  Re-enable in DoroShell Settings → Taskbar & Windows → One desktop → Restore previous
  settings, or `deploy.py --modules single-desktop --remove --apply`. Existing installs
  keep their recorded modules; add it with `deploy.py --modules single-desktop --apply`.
- Accept LXQt's default single-panel layout, which has `[panel1]` but no `panels=` key.
  The capability check refused it, blocking updates on stock CachyOS LXQt setups.
- Move stock Quick Launch applications into native taskbar pins on first install, so a
  pinned app and its running window share one button instead of appearing twice.
  Folder links, custom commands, missing files and ambiguous window identities stay in
  Quick Launch. Existing installs can opt in with `panel/profile.py merge-quicklaunch`
  (preview with `preview-merge-quicklaunch`); the previous profile is backed up first.
- Upgrade a Start button that still shows the plain stock `start.svg` to the bundled Doro
  artwork, as fresh installs already do. A personal picture is never replaced.
- Separate read-only runtime profile capability, bounded system-rule intent and
  unverified current initialization on Mouse & Touchpad. Flag incomplete/conflicting
  evidence; never infer disabled acceleration from a missing property or stale log.
- Integrate the DoroShell Mouse & Touchpad page with the installed toolkit, declared
  Xlib/udev dependencies, stable opt-in login helper, recorded autostart ownership,
  explicit stop/restoration and guarded program removal/undo. Preserve inactive
  preferences and archive ended-session receipts before retirement. No native LXQt
  UI patch, driver/system-rule change, physical input or login acceptance is claimed.
- Fix recovery adopting user edits to completed modules and then overwriting them
  on undo. Persist and verify completed-step bytes/modes in format-2 journals.
- Validate journal versions, progress, requests and snapshots before CLI recovery,
  finalization or undo. Keep completed legacy undo; refuse legacy pending journals
  without historical evidence and ambiguous interrupted shared-file changes.
- Preserve complete current source and owner-requested Doro artwork, original GIF,
  transparent APNG and selected wallpapers in a hash-catalogued baseline (`dee97b4`).
  Retain newer upstream provenance and design work (`36929b2`).
- Use authenticated GitHub CLI acquisition for the existing private repository; no visibility change or tokens in URLs.
- Add a download-first bootstrap and capability-aware Arch/LXQt/X11 orchestration
  over existing installers, official package checks, versioned native builds,
  scoped updates/removal and explicit development/stable distinction.
- Preserve panel profiles during native runtime upgrades. Retain first-install
  originals and add private deployment journals with conflict-checked exact undo.
- Make legacy cursor writes atomic with pending hash/mode recovery and conflict refusal.
- Add disposable-home/fault/capability tests and a complete laptop/AI handoff.
- No personal activation, mode/VSync change, OS package installation, clean OS or
  login acceptance is claimed. Physical display mismatch remains unresolved.

## Earlier development checkpoints

Git history and RELEASE-CANDIDATE.md record the earlier functional increments:
ranked Start search, folder cascades, portable preferences, clipboard, theme/cursor
tools, native panel/tray, screenshot editing/delayed capture, native Background and
isolated decoder, guarded Advanced controls and schema-2 diagnostics. The 2026-11-09
core-candidate tag predates these later changes and the portable installer.
