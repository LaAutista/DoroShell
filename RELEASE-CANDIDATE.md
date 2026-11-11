# Current source release evidence — 2026-11-11

This source consistency checkpoint follows published main `5749fa1`. GitHub main
already contains the screenshot/native Background integration, Start glass fixes,
launcher identity and filtered-pin fixes, tray lifecycle/keyboard menus, Show
Desktop drag behavior, and density/long-tooltip improvements. They are not an
unpublished optional source candidate. The existing 2026-11-09 core release ZIP is
a separate historical artifact; no new GitHub release or binary deployment is
created by this pass.

## Subsequent XEmbed checkpoint

The [synthetic legacy tray acceptance](docs/xembed-tray.md) follows `1e029cc`.
It adds patch 0009 for newly registered items leaving stale overflow snapshots.
The nine-patch standard build, full 237-test unit suite, private coexistence and
related tray/density regressions are checked for this increment. Earlier eight-patch
build/archive evidence below remains historical. No live activation was retried.

## Subsequent keyboard-entry acceptance

After `f26f439`, the [entry probe](docs/tray-lifecycle.md#keyboard-only-entry-known-limitation)
confirms the no-focus dock has no normal keyboard-only route to overflow under
Openbox. No notifier shortcut action exists in the inspected source. This increment
changes tests/docs only, preserves all nine patches, and reruns the full 237-test
suite plus popup/imported-menu/fallback keyboard checks on the same tested runtime.
It makes no new build or live activation claim.

## Source, tests and live installation are different claims

The [acceptance matrix](docs/final-acceptance.md) records the distinction. Read-only
process paths confirmed the filtered-pin panel and custom native wallpaper-
preferences renderer. Recorded independent live acceptance covers identity and
filtered pins. The user reported animation working; that feedback is not a new
hardware/audio test. Exact installed Start/screenshot revisions were not re-audited.
Tray patches 0005/0006, Show Desktop patch 0007 and density patch 0008 are
source-shipped, privately tested and staged, not activated on the personal session
by this work. Later independent remote checks do not imply independent UI passes.

Lightweight wallpaper-derived glass is the accepted visual scope. The user dropped
true moving-window Aero work and deferred disruptive acceptance. No compositor,
logout, locker, reboot, desktop reset or personal clipboard operation was performed.

## Verification in this consistency pass

All 237 unit tests and the documented native panel builder passed for this
checkpoint. The builder fetches and checks the pinned LXQt Panel and build-tools
revisions, applies all eight patches in order, stages installation through DESTDIR,
and copies the same patches and component licenses into runtime notices. The
resulting source is compared with the previously tested density candidate.

A single ordered patch list now serves application and notice copying. Missing,
unlisted or duplicate patch entries fail before cloning/building. Regression tests
cover inventory refusal and byte-for-byte inclusion of applied patches/licenses.
The prior metadata had nine failing file hashes and omitted newer panel patches;
`source_release.py` now refreshes/checks the complete tracked inventory, payload
hashes, modes and checksum file, and refuses an omitted untracked panel patch.

The exported source archive is checked independently of Git metadata, including
`sha256sum -c SHA256SUMS`, and its unit suite is run. No new runtime/UI or hardware
claim is inferred from these build/package checks. The preceding source checkpoint
passed 231 tests plus density at 150%/200%, tray focus/auto-hide/menu/native taskbar
checks and all four palette contrast checks; see [density evidence](docs/panel-density.md).
Earlier screenshot, native Background and fake-driver display checks remain
component evidence rather than tests rerun in this documentation pass.

## Reproduce build and source packaging

From a complete checkout, first run `python source_release.py`. Build the panel
with `python panel/build.py --work /permanent/empty/build-directory`. Keep that
whole directory: runtime/plugin paths refer to its prefix. The builder does not
install system packages or activate the panel. Component build requirements and
next-startup choices are in [panel/README.md](panel/README.md); paired wallpaper
build requirements remain in [wallpaper/README.md](wallpaper/README.md).

After intentional source edits, stage every intended source file, update release
provenance/evidence as appropriate, then run:

```sh
python source_release.py --refresh
python source_release.py
python -m unittest discover -s tests -v
git add SOURCE-MANIFEST.json SOURCE-SCAN.json SHA256SUMS
# Commit the reviewed source and metadata before exporting that revision.
git archive --format=zip --prefix=DoroShell/ -o /private/output/DoroShell-source.zip HEAD
```

Extract to a new private directory. There, run `python source_release.py`,
`sha256sum -c SHA256SUMS` and the unit command again. Hash the ZIP externally if
sharing it. `git archive` includes tracked files only; the inventory checker detects
missing/extra archive files and changed payloads. Generated Python caches are
ignored during archive checking. Do not package a working directory wholesale.
No binary package or new release service is introduced.

Original source is GPL-2.0-or-later with component exceptions preserved; see
[LICENSING.md](LICENSING.md). Native patch headers, panel LGPL text/authors and
ScreenGrab/PCManFM notices remain intact. The reviewed source excludes personal
paths/configuration, artwork/media, real desktop screenshots, logs, binaries,
private backups, caches and toolchains. Neutral project SVGs remain included.

## Remaining checklist

- Review staged-versus-installed provenance and prepare a later activation/rollback
  plan without changing the session; activation itself needs the user's chosen time.
- Broaden real notifier/app and long-session acceptance; keyboard-only overflow
  entry is a confirmed native limitation; real-client XEmbed variants remain unverified.
- Physical mixed-DPI/multi-monitor, Wayland, real audio/DPMS and display recovery
  remain outside private Xvfb/fake-driver evidence.
- Fresh-login and clean-system acceptance remain explicitly user-deferred.

This is a source/build/package checkpoint, not full desktop parity or a claim that
the current installation runs every source improvement. No CI service was added.
