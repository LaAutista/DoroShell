# Laptop / AI development handoff

This repository contains the complete current published DoroShell source, native
patch chains, build/install scripts, tests, component licenses, and owner-selected
artwork/cursor/wallpaper sources. No prior ChatGPT conversation is required. Personal
pins, histories, monitor settings, credentials and backups are intentionally absent.

## Start here

The repository is public: no GitHub authentication is required. Use
`git clone https://github.com/LaAutista/DoroShell.git`. Clone the existing repository, read AGENTS → STATUS → ARCHITECTURE → INSTALL →
MODULES → DEVELOPMENT, and inspect `git status`, remote URL and recent history.
`main` is development, not a finished product. The complete source/art baseline is
`dee97b4`, following `fd1859d` diagnostics and `36929b2` updated provenance/lock-screen
design. Later installer work is documented in CHANGELOG and Git history.

The shared original development checkout was older and dirty; it was preserved.
New work was reconciled in a separate checkout instead of copying it over current
main. Installed Start/search/folder/theme helpers matched published source. A stale
installed toolkit wallpaper controller lacked volume support; current source retains
the newer controller. Do not downgrade it from an old local toolkit or archive.

Public-access follow-up replaces the obsolete GitHub CLI sign-in bootstrap with
anonymous HTTPS download/fetch. Disposable-home plan/repeat and partial-download
refusal pass; no new installation or login acceptance is claimed. Single-desktop
next-login and restoration boundaries are documented in INSTALL.

## Decisions and constraints

- LXQt/X11/Openbox is the working target. No required compositor. The user accepted
  wallpaper-derived glass; true moving-window Aero work was dropped.
- App launches use GIO, never shell-parsed desktop Exec strings. Search indexes only
  the installed-app catalog; folder browsing is lazy and bounded. No telemetry.
- Native panel/PCManFM remain private builds, with system packages retained and
  next-login selection. Never refresh a personal panel just to test an installer:
  app output pipes may be inherited. Display mode tests need separate explicit intent.
- Baseline rollback and previous-upgrade undo are different. Preserve first-install
  manifests, current user choices and lock inodes. Conflicts must remain visible.
- Legacy `lxqt-comfort` paths remain supported. Unknown schemas/layouts are refused,
  not silently migrated. Installer starts from an initialized LXQt session.
- Owner explicitly requested the existing fan art and animation bundle. Preserve
  assets/catalog.json and separate provenance; GPL covers original code, not newly
  asserted artwork rights. Keep third-party/component notices unchanged.

## Known issues and recent evidence

Laptop follow-up (2026-11-14): stock LXQt panel files without `panels=` were wrongly
refused; Quick Launch apps were duplicated beside taskbar pins; upgrades from the
older installer kept the plain Start icon. All three are fixed with unit/temporary-home
tests. A live laptop update and next-login check are separate and recorded only once done.

The physical NVIDIA refresh change can take effect and then fail verification before
Keep/Revert. The user restored the rate manually. The root cause and physical rollback
reliability remain unverified. Preferred-marker whitespace handling, Apply/OK routing,
safe actual-state reload, persistent Close-only errors, and bounded schema-2 phase/
property diagnostics are implemented. Differential fixture checks preserved accepted
state equality; do not weaken external-change checks to hide the problem.

Source includes ranked search, folder cascades, portable preferences, native Background
controls, isolated video decoding, ten panel patches, and screenshot editing/recapture.
Private tests and read-only runtime provenance are documented; none proves clean OS,
new login, physical mixed-DPI/audio/DPMS or long-session acceptance. Lock-screen
animation is design only. See STATUS for remaining gaps and ROADMAP for priorities.

New installer tests exercise capability refusal, missing prerequisites, actual
temporary-home adapters, repeat/update/removal, journal recovery and exact undo.
Cursor recovery now preserves legacy schemas while recording pending hashes/modes,
refusing chmod conflicts and supporting interrupted restoration. Keep records and
inspect errors rather than forcing retries. There is no stable portable installer tag until clean-machine acceptance.

The follow-up to `fa8808c` fixes two independently reproduced deployment recovery
defects: adopting edits to completed modules, and writing through unknown journal
schemas. Format-2 journals preserve completed output bytes/modes immediately;
shared validation gates CLI request reading, recovery/finalization and undo.
Legacy pending journals and ambiguous interrupted shared-file writes require
inspection, not guessed migration. Completed legacy undo remains supported.
See INSTALL's recovery limits and RELEASE-CANDIDATE's targeted regression evidence.

The bounded multi-panel recovery follow-up on `c87ff151` skips the stock-layout
capability check only when the validated recovery journal says native-panel already
completed. A later second panel in the stock file is preserved during recovery and
exact undo. Completed output content/mode/symlink edits still refuse before prerequisites
or writes. That checkpoint alone did not support first/unfinished multi-panel work;
custom XDG roots remain unsupported. Recovery still requires its creating source
revision; do not edit an old pending journal's source hash to force migration.

The next bounded adapter, based on `010af6a`, adds `panel/profile.py prepare --panel
panelN`. Only explicit selection allows multiple source panels. It preserves
unrelated INI sections byte-for-byte and selected geometry, refusing shared widgets,
foreign reserved IDs and ambiguous syntax. Settings already accepts the prepared
plan; no second selector was added. Toolkit packaging includes `panel/layout.py`,
and sizing/clipboard/Quick Launch lookup use the unique owned taskbar panel. Private
setup repeat/restoration, interrupted staging/retry,
upgrade undo and installed offscreen UI checks pass; no native/login/hardware claim.

The follow-up on `df1d976` integrates that adapter into deploy/bootstrap with explicit
`--panel panelN`. Validate before package offers/build/managed writes; bootstrap needs
Git/Python first, and selection validation needs PySide6/GIO already importable.
Pointer format 2/journal format 3 retain the choice through repeat, scoped update and
recovery; old installers refuse these schemas. Legacy single-panel schemas remain
supported. Recover unfinished first staging using its saved plan rather than upgrading
an incomplete manifest. Do not infer a choice, replace unrelated sections, or migrate
old pending journals. The 373-test suite covers invalid selection, source/output edits,
interruption, exact undo/removal and safe bootstrap forwarding in disposable homes.
No real native process, package or session change was performed. See INSTALL for limits.

Input preferences from `0cf6019` are integrated on top of `e18026e`. The helper now
ships in the menu toolkit with declared Xlib/udev prerequisites. DoroShell Settings
has its own Mouse & Touchpad page and a native LXQt link; this is not an LXQt UI
patch. Program removal/changed-helper undo must refuse enabled choices, unresolved
receipts or remaining autostart. Use the page's Stop managing and restore action;
keep absent/unsupported-device receipts until resolved. Ended-session evidence is
archived privately before retirement, and inactive choices/locks survive removal.
See input-preferences.md for ownership/migration and system-scheme limitations.

The diagnostic follow-up on `d84b392` adds a read-only bounded standard-config scan
to the installed page. Keep system-rule intent separate from runtime profile and
user preference state. Current Xorg initialization is deliberately unverified:
XInput lacks a trustworthy current-device/session provenance binding, and this
implementation does not read or promote historical logs. Unknown selectors,
conflicting requests and unreadable/malformed/oversized files remain explicit.
No hardware changes, system-rule edits, session refresh or reinitialization are
needed to test this code; use fixtures and the installed private-X11 check.

## Ready-to-paste agent prompt

> Work on DoroShell at https://github.com/LaAutista/DoroShell.git. Clone it into a new
> directory if needed, verify origin/main, and read AGENTS.md plus docs/HANDOFF.md,
> STATUS.md, ARCHITECTURE.md, INSTALL.md, MODULES.md and DEVELOPMENT.md. Inspect the
> actual implementation before choosing a focused next task from ROADMAP.md. Preserve
> the working LXQt/X11/Openbox design, optional modules, owner-selected assets, current
> source licensing and existing user settings. Run the source inventory check and
> unit suite, and test installer changes only in disposable homes/private displays.
> Do not change my session, monitor/VSync settings, clipboard, locker or packages as
> a test; no logout/reboot or desktop refresh. Do not overwrite dirty work or force-push.
> Distinguish mocks/private checks from clean-machine and hardware acceptance. Keep
> STATUS/HANDOFF/CHANGELOG current with exact results and remaining limits. Continue
> with the next well-defined unfinished roadmap item within authorized scope. Ask
> only for genuine ambiguity or a blocker requiring my decision; do not restart or
> rewrite the project.

Future agents should fetch before publishing, reconcile newer upstream changes,
refresh source hashes after staging intended files, review privacy/assets/notices,
commit focused changes and verify the remote SHA after an authorized normal push.
Keep native source/build dependencies documented so another machine can rebuild
without private paths or copies of the original developer's configuration.

Additional handoff evidence is recorded in STATUS: independent private screenshot
QA passed rendered/capture/native-import/paste paths and desktop-wide Print after
a harness serialization fix. No production fix was indicated. The unmerged
animated-lock-surface probe at `f81d5d5` instead has a reproduced final overlay-stacking
failure; do not present or register it as working locker support. Its source is not
in main or this release manifest. Keep future locker tests isolated and separately
authorized; the synthetic failure makes no real-locker vulnerability claim.
