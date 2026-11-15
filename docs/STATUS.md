# Current development status — 2026-11-14

This is a portable development baseline, not a finished desktop or a certified
stable installer. [Detailed historical acceptance](final-acceptance.md) remains
separate from this pass. Source publication does not imply live activation.

| Area | Implemented | Evidence / remaining boundary |
| --- | --- | --- |
| Source/art baseline | Complete current published source plus owner-requested artwork, original GIF, transparent APNG and wallpapers | Baseline `dee97b4`; incorporates upstream `36929b2`. Shared older dirty checkout retained without overwriting it. Installed Start helper bytes match the published source. |
| Artwork reproduction | Portable relative source paths and exact catalog hashes | Bundled Start image matches installed pixels. APNG regenerates installed wait/progress cursor bytes exactly. Native binaries/caches/private configs excluded. |
| Start/search/folders/portable preferences | Implemented | Existing unit/private UI coverage; installed file comparison in this pass. No new live interaction or login test. |
| Mouse & Touchpad | DoroShell Settings page, installed opt-in X11 helper, login intent, restoration and guarded removal/undo; read-only capability/configuration-intent status | 35 input unit/lifecycle/diagnostic tests and private rendered installed-toolkit acceptance; evdev profile support only when exposed. Current initialization remains unverified; stale logs cannot establish it. Native LXQt is linked, not patched. No physical input or login acceptance. |
| Panel/tray | Ten-patch native panel, profile-preserving updates, Quick Launch apps merged into taskbar pins (opt-in command for existing installs) | Read-only running path confirms ten-patch runtime. New upgrade tests preserve config and baseline and cover interrupted writes. No panel refresh performed. |
| Wallpaper/display | Native Background controls, isolated decoder, guarded Advanced UI and schema-2 diagnostics | Read-only running path confirms schema-2 desktop. Physical mode-transition mismatch remains unknown; user previously restored rate manually. No hardware test in this pass. |
| Optional Alt+F1 | Explicit deploy/bootstrap/setup selection, custom replacement choice, next-startup disk binding | Disposable-home apply/repeat/recovery/remove/undo and installed-toolkit CLI; Qt reads private binding fixtures. Whole-file ownership refuses later shortcut edits. No live daemon reload or login acceptance. |
| Installer | Bootstrap, approved automatic prerequisite stages, capability/package checks, scoped modules, versioned builds, next-login staging, update/removal, journal and exact completed-upgrade undo | Disposable-home and fake-command missing-capability/cancellation/fault tests; see release evidence for final counts. Actual package/authentication and clean-machine acceptance remain separate. Existing adapters remain the persistence engines. |
| Compatibility | Arch lineage/pacman, LXQt/X11, Openbox; single panel1 or bounded explicit multi-panel selection through setup/deploy/bootstrap; native CMake check | CachyOS development host. Arch/EndeavourOS detection is fixture-tested, not clean-OS installation-tested. Wayland and broad XDG relocation refused; bounded explicit single-desktop/snapping config-root support only. Explicit panelN selection preserves other standard panels; shared widgets/ambiguous layouts remain unsupported. |
| Lock-screen animation | Design only | [Separate design](animated-lock-screen-design.md); no authentication/locker changes or claim of implementation. |

The inherited 262-test suite passed before installer edits; the portable installer
checkpoint passed 285 tests and the recovery follow-up passed 302. Input integration
passed 326; read-only diagnostics passed 337 tests. The public-bootstrap follow-up passes **346 tests**. New targeted tests cover
real temporary-home menu/toolkit installation, combined panel/theme/snapping/capture/
clipboard staging, repeats, first-baseline restoration, exact prior-upgrade undo,
injected partial failure/recovery, invalid records, byte/mode/symlink conflicts and
native launcher upgrades, cursor interrupted-write recovery and bootstrap transport refusal. Build/bootstrap/final suite results are recorded in
[release evidence](../RELEASE-CANDIDATE.md).

The completed-panel recovery follow-up passes **350 tests**, including four new
disposable-home regressions. A completed native-panel step no longer blocks recovery
of later work when the separate stock LXQt layout gains another panel. Recorded
managed outputs remain verified and unchanged; exact undo preserves the new stock
layout and restores the prior managed bytes/modes. Content, chmod and symlink conflicts,
unfinished unsupported layouts and custom XDG roots still refuse. That checkpoint
alone did not enable first-time multi-panel installation or broaden hardware/login acceptance.

The subsequent explicit-selection adapter passes **360 tests**, including ten new
panel-selection tests. Temporary homes cover selecting either panel, untouched INI
sections and geometry, wrong/missing/shared selection, repeat and interrupted staging,
conflict refusal, exact upgrade undo, sizing/clipboard placement and later Quick Launch
merging. The installed toolkit's real CLI passes preview/apply/repeat/rollback with a
fake package query; installed Settings renders offscreen and routes the prepared plan
without executing a command. A suite-detected eager Qt import regression was fixed;
legacy missing-prerequisite diagnostics remain covered. No native panel was launched.

The deploy/bootstrap integration on `df1d976` passes **373 tests**, including eleven
new CLI selection/recovery tests and two bootstrap tests. Plan/apply/repeat/scoped
update/recovery/remove retain the chosen panel and preserve unrelated sections.
Wrong/missing/shared selection and changed completed outputs refuse before package
offers/builds. Interrupted first staging resumes its saved plan, with exact undo and
legacy single-panel behavior covered. Tests use disposable homes, actual profile and
journal adapters, mocked package/build boundaries and inert binary paths; bootstrap
argument forwarding is synthetic. Explicit choice records use pointer 2/journal 3;
old installers refuse them. Source/archive hashes are checked separately. No new
native UI, package, real-session or clean-OS acceptance is claimed.

The automatic-prerequisite follow-up on `a7cbccb` passes **387 tests**. Fourteen added
cases cover the exact README download command, missing curl/Git/Python, safe argv,
normal approval-command construction, cancellation/failure, success without an
available dependency, strict post-package panel validation, no-package/plan refusal,
scoped guidance without user-state reads and expected versus unexpected import errors.
Package/authentication/download commands are fake or mocked; real temporary-home
profile adapters run. No actual package installation, sudo authentication, clean OS
or login test occurred. Pre-validation packages may update the system before a layout
is rejected; DoroShell configuration still requires successful validation. This
supersedes the prior checkpoint's manual-only prerequisite boundary.

The argument-order review correction passes **391 tests**. Bootstrap and the README
downloader reject invalid actions/syntax before prerequisite authentication; fake
commands prove zero calls for the reproduced guidance/apply conflict, unknown options
and invalid panel IDs. The downloader intentionally accepts only its small install
interface; advanced options remain in local bootstrap/deploy. Valid automatic flows,
catalog forwarding, cancellation and post-package validation remain fixture-tested.
Actual administrative authentication/package and clean-install gates are unchanged.

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

Public-access follow-up: anonymous raw download and candidate bootstrap plan/repeat
passed against published `870bdac4` in a disposable HOME with Git global config,
credential helpers and interactive prompts disabled, no tokens, and no display/session
bus. Source inventory passed; no configuration or deployment state was created.
The exact README command also passed a synthetic partial-download refusal check.
This is download/plan acceptance, not a package install or clean-machine test.
Single-desktop fixture coverage includes plan/no write, repeat, count/firstdesk scope,
conflict refusal and byte/mode restoration, without launching live commands.

Historically, the authenticated private-GitHub bootstrap was tested against published `5c0baba`: real
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


The optional Alt+F1 follow-up on `4e608ed` passes **413 tests**, including 21 new
shortcut tests and one bootstrap-forwarding test. Fake command checks also cover
invalid replacement arguments before acquisition/authentication. Tests install real
menu/toolkit files in disposable homes, exercise existing Print/Alt+F1 ordering,
interrupted writes/restoration, stale review, exact bytes/modes, malformed records,
symlinks and launcher-removal guards. Private Qt parsing verifies supported stored
bindings; installed CLI preview/apply/rollback works without Qt/PATH commands.
The older independent-module test excludes this dependent adapter, whose combined
lifecycle now has separate coverage. No native process/build, live shortcut/input,
package authentication, fresh OS or login test occurred.


The explicit-config-root follow-up on `72833d0` passes **429 tests**: 15 added
config-root tests plus one bootstrap forwarding test, retaining all 413 prior cases.
Only single-desktop is supported with an alternate home-contained config root.
Disposable fixtures cover spaces, missing/changed/overlapping roots, configured
cache/runtime overlap, symlinks, invalid/missing ownership metadata, unrelated file/XML
preservation, legacy default ownership, installed CLI packaging, repeat, interruption,
completed finalization, removal and exact upgrade undo. Existing module code from
`72833d0` separately refuses the new edit kinds for apply/rollback without changing
fixture bytes/modes. No native UI/build, actual custom-root Openbox startup, clean OS,
packages/authentication or live session acceptance occurred. See [path inventory](config-roots.md).


The independent-review symlink correction passes **431 tests twice**: with XDG
config/data/state/cache unset and with normal inherited paths under a disposable
home. The prior 429-test run did not exercise the reproduced in-home ancestor alias.
Two new matrix/recovery tests prove module/setup/installed CLI refusal without target
or ownership changes; inherited-config fixture errors are fixed by binding the three
fixtures to their own temporary config paths. Real environment mismatch refusal is
unchanged. No live, login, package or native hardware acceptance is added.


Custom-root snapping follow-up on `6311413`: snapping alone and combined with
single-desktop now stage XML/autostart at the explicit root, keeping helper/launcher
and state paths fixed. Disposable-home tests cover shared XML ownership, exact
repeat/removal/undo, partial multi-file writes, between-step recovery, conflicting
roots/paths/edits and installed-toolkit CLI. Ambiguous interrupted shared XML changes
still refuse. Actual custom-root Openbox/autostart startup remains unverified.
The separate optional Alt+F1 runtime attempt stopped when private Xvfb could not bind
its sockets; no shortcut daemon or input test ran and no host changes were made.

Final custom-root snapping validation: **444 tests pass** with inherited normal
XDG paths under a disposable HOME, offscreen Qt and a private nonexistent session
bus (24.703s). The 29 focused config-root tests and 16 bootstrap tests also pass.
Two existing snapping fixtures now bind their own config directory; production
mismatch refusal is unchanged. The prior reader at `6311413` separately refuses
new module apply/rollback and combined journal requests before fixture writes.


Recent-app retention follow-up on `09a013a`: optional age policy in Start Menu
options, no age limit/timestamp collection by default. Timed successful launches
record local integer timestamps; menu presentation/history changes expire entries,
with count/recording/clear controls retained. Untimed or future-dated entries expire
when enabled; malformed data refuses writes. Failed saves hide expired entries and
show a warning. Portable export contains policy only; import leaves history alone
until Start applies it. Older backups and private portable undo remain outside expiry.
See recent-apps.md. No personal history/session access or live activation is needed.

Retention verification: **457 tests pass** (25.284s), including 13 new clock,
legacy/corruption, save-failure, portable privacy and offscreen resident/UI cases.
Disposable installed Start/portable helpers pass rendered age-choice, exact expiry,
visible failure/retry and timestamp-exclusion checks. This is offscreen fixture
acceptance, not live login, real input or long-running-session validation.


Start keyboard follow-up on `baa0a23` addresses confirmed search/results gaps:
widget-scoped Up/Down entry, list-edge return to search, selectable-row Home/End,
Search → Results → All Programs/Back Tab order and focused selection retention.
Native text editing/modifiers, remaining Tab traversal, nested folder menus and
staged Escape are preserved. Disabled/hidden/nonselectable/stale rows do not launch.
Source and temporary installed-runtime tests use offscreen local key events, a
synthetic catalog and fake dispatch. No Xvfb retry, global shortcut change or live
input/session action; AT-SPI/screen-reader/live X11 acceptance remains unverified.
See start-keyboard.md for precise scope and remaining broader parity work.

Keyboard verification: **467 full-suite tests pass** (25.515s); all 10 new widget
cases also pass against the actual temporary installed Start (0.239s). Its source
hash matches, and synthetic offscreen result-focus rendering was inspected. Tests
block real app/session/URI dispatch and use no personal catalog/history or display.
This source candidate awaits independent review; it is not deployed or pushed.


Folder-link separators follow up on published `474cf6c`: opt-in add/move/remove in
the existing editor, non-focusable rendered lines, stored edge/repeated items
preserved and visually collapsed. Local version 2 is used only with separators;
old readers refuse it. New portable version 2 carries standard IDs/visibility and
separator markers, excludes private labels/paths, and retains exact conflict-safe
restore. Legacy portable imports leave local separators unchanged. Existing custom
rows and fixed system groups remain; no general command/menu-tree format. See
start-separators.md for migration, local 100-item bounds and portability limits.

Separator validation: **481 full-suite tests pass** (25.767s), including 14 new
fixture cases. The actual temporary installed Start/toolkit passes 24 combined
separator/keyboard cases (0.414s), path-free UI export, preview Cancel/Apply and
exact Restore with mocked dialogs. Synthetic editor/menu rendering at 100% and
150% scale was inspected. Exact old readers reject the new formats. This is
offscreen acceptance, not live X11, screen-reader, physical DPI, login or clean-OS
verification. Source-only candidate awaits independent review before publication.


Power availability follow-up on published `1533623`: only four read-only logind
Can-methods, with auto-start and interactive authorization disabled. Asynchronous
bounded snapshots update Start power controls/primary choices; unknown, denied,
unsupported and inhibited actions disable, while challenge explicitly reports
authorization needed. Saved primary selection is retained. Existing Cancel-default
confirmation, GIO LXQt dispatch, All session options, logout and locker behavior
remain; no automatic action/retry, polling or new mandatory service. Installer
copies the helper with Start/toolkit and the resident signature includes it.
See power-capabilities.md for timing and live/hardware acceptance limits.

Power validation: **500 full-suite tests pass** (26.618s), including 19 focused
capability/UI/lifecycle cases (0.299s separately). Actual temporary installed
Start/helper passes the same 19 cases (0.301s), toolkit imports/hashes and rendered
state inspection. Transport responses and dispatch are fake; private nonexistent
system/session bus addresses additionally isolate subprocesses. No personal bus
probe, actual power/lock call, authentication or live/session change. Source-only
candidate awaits independent review; no live service/hardware/polkit acceptance.
