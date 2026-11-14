# Provenance and optional lock-screen design checkpoint — 2026-11-14

Based on published `fd1859d`, preserving all later Start, screenshot and display work.
Read-only hashes identify the running/selected ten-patch panel and installed Start/search
and capture payloads; this is not new activation or full live acceptance. The
[optional animation design](docs/animated-lock-screen-design.md) is unimplemented:
no locker command, authentication/config change or prototype was executed. Gamebox
staging is reported separately, not reproduced; login remains unverified.
This documentation-only increment checks the full unit suite and exported source
inventory/checksums. Earlier build/UI evidence below belongs to its named checkpoint.

## Historical source release evidence — 2026-11-11

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

## Subsequent native shortcut checkpoint

The [tenth patch](docs/tray-shortcut.md) adds an unbound LXQt tray action. Pointer-free
entry, focus, navigation, menus, toggle, disconnect/empty state and daemon reconnect
are privately tested. Queued entry measured 44–46 ms in five synthetic samples, not
physical latency. The strict AT-SPI popup-label probe still fails on both old and
new runtimes; that limitation is retained explicitly. Native task/tray regressions,
237 unit tests, clean patch-chain and source-export checks cover this increment.
The parent reported nine-patch activation; the tenth patch remains staged pending
an explicit safe point. No live queries or binding changes were performed here.

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
  entry now has an unbound configurable action; popup AT-SPI labels and real-client XEmbed variants remain open.
- Physical mixed-DPI/multi-monitor, Wayland, real audio/DPMS and display recovery
  remain outside private Xvfb/fake-driver evidence.
- Fresh-login and clean-system acceptance remain explicitly user-deferred.

This is a source/build/package checkpoint, not full desktop parity or a claim that
the current installation runs every source improvement. No CI service was added.

## Persistent display failure visibility

This increment follows main `abc9dac`. Terminal display guard failures now remain visible in a Close-only dialog; they never offer Keep for an unverified state. Actual-state refresh continues. One owner-only, bounded last-failure record stores fixed reason/field labels rather than raw driver output or monitor identifiers; [scope and privacy](display/README.md#visible-failures-and-local-diagnostic-record). The earlier statement that no diagnostic log exists has been corrected.

The reconciled full suite passed **251 tests**. Thirteen private native-X11 scenarios passed on the Background-enabled paired build, including successful Keep/Revert, early verification/recovery refusal, abnormal guard exit, failed diagnostic storage, and dismissal. The synthetic failure dialog was visually checked at 150% scale. These tests use fake drivers and disposable state homes. A separate parent rerun passed the earlier 236-test base suite and five relevant native cases before reconciliation with newer main.

The paired executable was staged with exact previous-upgrade backup/undo and unchanged first-install baseline. The existing volume-aware wallpaper controller was explicitly retained because the installed toolkit carried older controller data. All checked wallpaper/preferences remained unchanged. Desktop activation was deferred due to recent input; the previously active Background-enabled build remains running. No physical mode/VSync test or assignment was performed. The underlying hardware mismatch remains unknown, and the user's manual restoration is not evidence of automatic rollback. No new live/login/clean-install acceptance is claimed. Private runtime backups, diagnostic records and local paths are excluded from this source snapshot.

## Structured display failure phases — private source candidate

This candidate follows published main `958248b6e1f158e95cabf0cba21cbda6e95134bd`, retaining the screenshot window-capture work (`0e66e29179051a5eb7459afe003e5a2e9ca19958`) unchanged. Diagnostic schema 2 preserves separate apply/verification/recovery events and exact allowlisted property labels, without changing accepted-state equality, tokens, layout hashes or guard decisions. The record remains private, atomically replaced and capped at 2 KiB; [scope](display/README.md#diagnostic-phases-schema-2).

The reconciled full suite passed **262 tests**. The standard Background+display build and **13 private native-X11 scenarios** passed. Native tests read the actual UI-written schema-2 record and assert separate apply-verification/state-mismatch and recovery/external-change events, brightness/Colorspace labels, command-failure classification, and exclusion of raw property values. Independent writer tests are supplemented by this full helper-to-UI-to-record check. A strict native Qt cast-policy compilation issue found by the standard build was corrected with explicit QStringLiteral values and a regression compile using the same restrictions.

The new paired executable and source patch remain private and uninstalled. No live staging, activation, display/VSync mutation or physical retest occurred for this diagnostic increment. Prior warning-only activation is separate evidence. The original hardware mismatch remains unknown and automatic hardware rollback unverified. The earlier differential comparison against `e284054` matched 26 parse/token snapshots, 676 equality comparisons and 26 transaction outcomes/driver-query traces; finer diagnostic metadata is excluded from accepted-state mappings. Existing screenshot tests are included in the combined suite; no additional unchanged screenshot UI acceptance is claimed.

## Reproduction baseline — 2026-11-14

This baseline starts from published `fd1859d` and retains all its source. The
installed Start/search/folder/theme helpers match that revision. The shared older
checkout has uncommitted work and was left untouched; it was not overlaid onto
newer main. The installed toolkit wallpaper controller predates the volume-aware
source and was not copied over it. Actual personal configs/backups are excluded.

Owner-requested Doro artwork, original and transparent loading animations, static
Heretic wallpaper and the selected optional video are now catalogued in `assets/`.
They are included without inventing an artwork license. Generated themes and cursor
files remain reproducible from source; no native executables/caches are included.
The inventory checker permits only artwork with exact catalog hashes and sizes.
The inherited 262-test full suite and four source-inventory tests pass. This checkpoint precedes installer orchestration.
No personal install, session restart, display write or clean-OS test was performed.
