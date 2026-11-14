# Laptop / AI development handoff

This repository contains the complete current published DoroShell source, native
patch chains, build/install scripts, tests, component licenses, and owner-selected
artwork/cursor/wallpaper sources. No prior ChatGPT conversation is required. Personal
pins, histories, monitor settings, credentials and backups are intentionally absent.

## Start here

The repository is private: use an authorized GitHub account (`gh auth login`), then
`gh repo clone LaAutista/DoroShell`. Clone the existing repository, read AGENTS → STATUS → ARCHITECTURE → INSTALL →
MODULES → DEVELOPMENT, and inspect `git status`, remote URL and recent history.
`main` is development, not a finished product. The complete source/art baseline is
`dee97b4`, following `fd1859d` diagnostics and `36929b2` updated provenance/lock-screen
design. Later installer work is documented in CHANGELOG and Git history.

The shared original development checkout was older and dirty; it was preserved.
New work was reconciled in a separate checkout instead of copying it over current
main. Installed Start/search/folder/theme helpers matched published source. A stale
installed toolkit wallpaper controller lacked volume support; current source retains
the newer controller. Do not downgrade it from an old local toolkit or archive.

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
> STATUS/HANDOFF/CHANGELOG current with exact results and remaining limits. Ask for
> my next feature choice if none is specified; do not restart or rewrite the project.

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
