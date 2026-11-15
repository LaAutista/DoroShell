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
design. The current coordinator-verified published checkpoint is `f980512`, including automatic
prerequisites, optional Alt+F1, bounded custom-root snapping/single-desktop,
retention, separators, keyboard navigation and power capability states. The
[release integration pass](release-integration.md) checks their combined installed
lifecycle without changing runtime source or the personal installation. Later
historical sections retain the tests/limits of their individual checkpoints.

The shared original development checkout was older and dirty; it was preserved.
New work was reconciled in a separate checkout instead of copying it over current
main. Historical installed Start/search/folder/theme helpers matched their
then-published source; this is not a current live comparison. A stale
installed toolkit wallpaper controller lacked volume support; current source retains
the newer controller. Do not downgrade it from an old local toolkit or archive.

Public-access follow-up replaces the obsolete GitHub CLI sign-in bootstrap with
anonymous HTTPS download/fetch. Disposable-home plan/repeat and partial-download
refusal pass; no new installation or login acceptance is claimed. Single-desktop
next-login and restoration boundaries are documented in INSTALL.

## Decisions and constraints

- LXQt/X11/Openbox is the working target. No required compositor. The user accepted
  wallpaper-derived glass; true moving-window Aero work was dropped.
- Windows 7 is the current menu layout scope. Other menu styles are deferred until
  explicitly requested; retain the broader function inventory without expanding layouts.
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

The [calendar bounds candidate](panel-calendar.md) adds an eleventh ordered panel
patch on published `f980512`: reserve scrollbar space and respect the available
work area in the compact horizontal clock popup. Old-source regressions and 768
native Qt snippet cases pass after the fix. Full panel configuration is blocked by
installed liblxqt 2.5.0 versus the available build-tools 2.4.0; no dependency bypass,
complete plugin build or live update. Preserve the prior ten-patch runtime.

Documentation now explicitly inventories the already-shipped
[automatic fullscreen wallpaper pause](../wallpaper/README.md#pause-and-recovery):
default-on/opt-out, monitor/workspace scope, independent pause reasons and polling
delay. Isolated-decoder publication is confirmed by local ancestry; its earlier
private acceptance and controlled deployment remain historical. Runtime source,
tests and installed files are unchanged; no new live/hardware acceptance.

The application-properties candidate on published `012aa93` adds a read-only
modal to the existing context menu, native keyboard-context invocation, bounded selectable
GIO metadata and explicit missing/stale status. No source-file probe, Exec handling,
editing, clipboard operation or preference mutation. Installed-byte/rollback and
offscreen focus/render checks are recorded in [application properties](app-properties.md).
Roadmap wording now distinguishes local setup requirements from the explicitly
approved bootstrap/deploy package flow. No live activation or new dependency.

The next source candidate adds [optional Recent Documents](recent-documents.md)
on published `5cc96a4`: default-off, explicit read of shared desktop XBEL in a
bounded cancellable worker, no target probes or shared-store writes. Supported
local URI entries remain availability-unverified; selection uses GIO. Paths/history
never enter preferences/backups/portable export. Native submenu keyboard ownership
and installed helper lifecycle pass 531 full-suite/eight installed UI tests; real
documents are not opened.

The catalog follow-up on published `da49537` adds real GIO/offscreen fixture
acceptance only: no production catalog/search/installer defect was reproduced.
Disposable roots cover precedence/visibility, duplicates, localized/Unicode search,
registered Flatpak-shaped exports and live file notifications with pin/selection/
column-focus retention. Installed helpers, repeat ownership and preference-preserving
removal pass. The full suite passes **515 tests**. See [exact cases and boundaries](app-search.md#real-catalog-fixture-acceptance--2026-11-15).
Real packages, application dispatch, personal catalog, login and clean OS are untested.

The cross-column keyboard follow-up to published `0c50da5` adds only Right from
results to remembered/first usable places/menu controls and Left back to usable
results or search. It skips unavailable/separator rows, reveals scrolled targets
and retains surviving folder identity on rebuild. Text editing, native Tab/menu
keys, modal ownership and drag behavior remain. Existing accessible names pass
Qt interface checks; no new layout or setting. **512 tests** and **20 actual
temporary-installed keyboard tests** pass, with repeat/conflict-aware exact rollback.
See [focus paths and limits](start-keyboard.md); no live input/AT-SPI/X11 claim.

The mapped-position Start follow-up to published `27cfea1` is a three-line glass
handler correction: refresh after Qt's show helper rather than waiting for the
queued geometry timer. A failing first-backdrop-paint test establishes the old/new
origin discrepancy. Two new tests and synthetic four-scale source/installed render
matrices cover it; see [precise observations and limits](wallpaper-glass.md#mapped-position-first-frame-follow-up).
Existing `983ac44` readiness and fringe fixes already remain. No mask/opacity/layout
redesign, live deployment or confirmation of the personal color/edge symptom.

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
`--panel panelN`. Validate before module package offers/build/managed writes; bootstrap
needs Git/Python first, and selection validation needs PySide6/GIO importable.
Pointer format 2/journal format 3 retain the choice through repeat, scoped update and
recovery; old installers refuse these schemas. Legacy single-panel schemas remain
supported. Recover unfinished first staging using its saved plan rather than upgrading
an incomplete manifest. Do not infer a choice, replace unrelated sections, or migrate
old pending journals. The 373-test suite covers invalid selection, source/output edits,
interruption, exact undo/removal and safe bootstrap forwarding in disposable homes.
No real native process, package or session change was performed. See INSTALL for limits.

The prerequisite follow-up on `a7cbccb` supplies automatic user-initiated missing-tool
stages: curl in the README download command, Git/Python in bootstrap, PySide6/GIO
in explicit panel validation. Print the plan, keep normal sudo/pacman approval,
stop on cancellation/failure, then recheck before module/configuration work. Do not
weaken panel validation: a prerequisite full-system update may finish even when the
layout is subsequently refused. Plan and `--no-packages` never offer authentication.
`deploy.py --prerequisites` prints scoped guidance without reading user state; it
is not an install/readiness check. Missing sudo/pacman requires manual administration,
not a new helper or policy. Fake-command/disposable-home evidence is separate from
actual pacman, authentication, clean OS and login acceptance; see RELEASE-CANDIDATE.

The review correction on `060a904` rejects invalid arguments before missing-tool
acquisition can invoke sudo/pacman. Bootstrap has a bounded exact-option/value and
action-conflict gate; its module list is checked against deploy by tests. The README
downloader supports only apply/plan/no-packages/panel and refuses advanced options;
use local bootstrap/deploy for those. Do not remove this early gate or infer that
Python's later parser can protect an earlier package call. The existing valid
automatic flow and post-prerequisite panel validation remain unchanged.

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


Optional Alt+F1 follow-up on `4e608ed`: `start-shortcut` is an explicit deploy/bootstrap/
setup selection, with separate custom-binding replacement consent. Reuses integrate
values and shared INI/transaction code; no new daemon or GUI. Journal 4 retains review
fingerprint and consent; per-module phases distinguish interrupted writes/restoration
from later user edits. Conservative whole-file ownership refuses unrelated later
shortcut edits and blocks other module writers until restored; Print+Start combined
ordering/removal is tested. Old schema support and baseline versus upgrade undo stay
separate. Installed toolkit CLI is tested in disposable homes without Qt/PATH tools.
No live shortcut reload, login acceptance or package authentication occurred. See
INSTALL for supported syntax and recovery limits; preserve the independent disabled
experimental input-helper work and its real authentication blocker.


Config-root follow-up on `72833d0`: read docs/config-roots.md before extending paths.
The inventory shows mixed fixed installer paths and environment/Qt runtime resolution;
do not remove compatibility refusal globally. The new CLI-only subset is single-desktop
with an initialized home-contained root, spaces supported, no overlapping/symlink roots.
State/data/cache/runtime paths remain unchanged. Root choice is stored in phased module
ownership and journal 5, reused for repeat/recovery/removal; changed roots, metadata,
pre-ownership config and managed values/modes refuse. Old schemas remain supported.
Use scoped source/installed CLI, not Settings GUI or core presets, for this adapter.
Actual Openbox startup with the custom root is unverified. No live/package changes.


Independent review correction on unpublished `0b32202`: install.safe checks the
leaf and resolved home containment, so in-home symlink ancestors bypassed lexical
root overlap checks through direct modules/setup. config_root now walks components
through the selected home for roots, XML targets and ownership records, and rechecks
before a custom target write. New tests reproduce the original bug and cover aliases
to reserved/ordinary paths, descendant links, installed CLI and pending recovery.
Three legacy temporary-home fixtures set their own XDG_CONFIG_HOME. The production
mismatch refusal stays strict. Both unset-XDG and inherited-disposable-XDG full runs
pass 431 tests; no live action or publication occurred. Prior 0b32202 artifacts remain
immutable; use the correction for independent verification, not the superseded bundle.


Follow-up on `6311413` extends the explicit config-root adapter to snapping alone or
with single-desktop. See config-roots.md: only config XML/autostart move; helper,
launcher and state paths remain fixed. Root/path validation covers every target;
both adapters use shared locks and distinct XML ownership. Keep ambiguous-overlap
recovery refusal and retain journals. No runtime/config environment is relocated.
Alt+F1 private runtime acceptance remains blocked by Xvfb listener creation in the
available sandbox; no host display fallback, package installation or security change.
The experimental input helper remains disabled/unpublished and untouched.

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
This checkpoint was independently reviewed and published as `474cf6c`; no live
deployment was performed by that increment.


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
verification. This checkpoint was independently reviewed and published as `1533623`;
publication does not establish live activation.


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
checkpoint was independently reviewed and published as `660de77`; no live
service/hardware/polkit acceptance.
