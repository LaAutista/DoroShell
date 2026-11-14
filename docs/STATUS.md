# Current development status — 2026-11-14

This is a portable development baseline, not a finished desktop or a certified
stable installer. [Detailed historical acceptance](final-acceptance.md) remains
separate from this pass. Source publication does not imply live activation.

| Area | Implemented | Evidence / remaining boundary |
| --- | --- | --- |
| Source/art baseline | Complete current published source plus owner-requested artwork, original GIF, transparent APNG and wallpapers | Baseline `dee97b4`; incorporates upstream `36929b2`. Shared older dirty checkout retained without overwriting it. Installed Start helper bytes match the published source. |
| Artwork reproduction | Portable relative source paths and exact catalog hashes | Bundled Start image matches installed pixels. APNG regenerates installed wait/progress cursor bytes exactly. Native binaries/caches/private configs excluded. |
| Start/search/folders/portable preferences | Implemented | Existing unit/private UI coverage; installed file comparison in this pass. No new live interaction or login test. |
| Panel/tray | Ten-patch native panel and profile-preserving updates | Read-only running path confirms ten-patch runtime. New upgrade tests preserve config and baseline and cover interrupted writes. No panel refresh performed. |
| Wallpaper/display | Native Background controls, isolated decoder, guarded Advanced UI and schema-2 diagnostics | Read-only running path confirms schema-2 desktop. Physical mode-transition mismatch remains unknown; user previously restored rate manually. No hardware test in this pass. |
| Installer | Bootstrap, capability/package checks, scoped modules, versioned builds, next-login staging, update/removal, journal and exact completed-upgrade undo | Disposable-home and missing-capability/fault tests; see release evidence for final counts. Existing adapters remain the persistence engines. |
| Compatibility | Arch lineage/pacman, LXQt/X11, single panel1/Openbox capability gates; native CMake check | CachyOS development host. Arch/EndeavourOS detection is fixture-tested, not clean-OS installation-tested. Custom XDG roots/multi-panel/Wayland refused. |
| Lock-screen animation | Design only | [Separate design](animated-lock-screen-design.md); no authentication/locker changes or claim of implementation. |

The inherited 262-test suite passed before installer edits; the portable installer
checkpoint passed 285 tests. After the recovery follow-up, the full suite passes
**302 tests**. New targeted tests cover
real temporary-home menu/toolkit installation, combined panel/theme/snapping/capture/
clipboard staging, repeats, first-baseline restoration, exact prior-upgrade undo,
injected partial failure/recovery, invalid records, byte/mode/symlink conflicts and
native launcher upgrades, cursor interrupted-write recovery and bootstrap transport refusal. Build/bootstrap/final suite results are recorded in
[release evidence](../RELEASE-CANDIDATE.md).

The recovery follow-up to `fa8808c` adds 17 tests: completed-output content/mode
edits cannot be adopted during recovery; unsupported/malformed journals are refused
before request consumption or writes. Format-2 journals preserve successful-step
evidence. Existing active-step retries, repeat/removal and exact upgrade undo pass;
valid completed format-1 undo remains supported. Legacy pending journals and
ambiguous interrupted overlapping writes require manual inspection. These are
disposable-home fault-injection checks, not real power-loss or clean-OS acceptance.

Unverified: clean Arch/CachyOS/EndeavourOS machine install, normal login/autostart on
that machine, physical multi-monitor/mixed-DPI and NVIDIA rollback, physical audio/
DPMS, long-session resource behavior, arbitrary future LXQt releases and Wayland.
No package installation, personal deployment, session refresh or hardware mode
write was performed during this work. Artwork authorship/redistribution terms remain
the owner's review responsibility; no new third-party license is asserted.

The authenticated private-GitHub bootstrap was tested against published `5c0baba`: real
download/plan, scoped menu apply with `--no-packages`, repeat and removal all passed
in a disposable home. It used development-host dependencies, not a clean OS. The
new full source archive also passed inventory/hash round-trip checks.

## Additional independent QA received at handoff

On baseline `dee97b4`, independent private-X11 screenshot QA passed menu-open
Print, rendered editing, annotated PNG/image clipboard export, native ScreenGrab
import/Copy and exact Writer/Draw paste after the editor exited. Instrumented global
Print passed three Escape/reopen cycles and exact 1024×768 full-frame clipboard
pixels. The initial failure was a harness command-serialization error: LXQt treated
`python SCRIPT` as one executable; the production single-launcher path worked.
These are independent results, not reruns by the installer task, and do not prove
Wayland, physical mixed-DPI, fresh login or full Spectacle parity.

The separate unmerged `probe/animated-lock-surface` experiment at
`f81d5d58dadcc140ce383316f965cf6a5616ccdf` failed its final stacking assertion:
mpv's child covered an existing synthetic sibling overlay on launch and restart.
Independent QA confirmed 69 preceding assertions and the same final failure.
It is **unimplemented/unready as locker integration**, excluded from this release,
and must not be installed or registered. This is not evidence of a real XScreenSaver
vulnerability; real host hierarchy/authentication and lock testing were not reviewed
or authorized. Unit passes do not override the rendering failure.
