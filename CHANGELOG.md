# Changelog

## 0.2.0-dev — 2026-11-14

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
