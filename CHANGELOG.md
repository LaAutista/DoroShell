# Changelog

## 0.2.0-dev — 2026-11-14

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
