# Compact calendar bounds candidate — 2026-11-15

Documentation follow-up to frozen source candidate
`eec9ad84d7ba03c70dd43ebe00d3877db56227a1`, based on coordinator-verified published
`f980512bf30dd05d99987a8022b3f33c620691ab`. The inherited native patch fixes two
source-reproduced compact-calendar cases: scrollbars stealing the other axis despite
spare room, and positioning beyond the reported available work area. Existing
native calendar interaction, themes, preferences and the rotated-clock path remain.
[Exact source fixture and limits](docs/panel-calendar.md).

The old source fails both regressions independently. Compiled native Qt source
snippets pass 192 cases at each of four scales (768 total), with enlarged fonts,
narrow/short work areas, week numbers, both edges, repeated opens, mouse month
navigation, date keys, month/year headers, final-week visibility and Escape.
All eleven patches apply to pinned upstream; the shared build/notice inventory
includes the new patch. No new helper or installation schema.
The full disposable/offscreen unit suite passes **540 tests (35.883s)**,
including existing build-notice and reversible installer coverage.

The original configuration failed on installed liblxqt 2.5.0 versus saved
build-tools 2.4.0. A later **complete native build passed all 1,367 steps** in a new
private tree using already-cached liblxqt 2.4.0-1.2 headers/library/CMake files with
the matching saved tools. The actual clock code is linked into the full executable.
The cache was extracted privately, not system-installed. No package scripts,
source-pin or version-check changes, downloads, install/staging or panel execution.
The default host liblxqt 2.5 dependency mismatch still requires compatible tools or
an explicitly prepared compatible prefix; no clean-OS/default-bootstrap claim.

The runtime patch, builder and tests are unchanged in this documentation-only
follow-up. Earlier test counts and frozen `eec9ad8` evidence are retained, not rerun
or replaced. Documentation links, unchanged code bytes/modes, inventory/checksums
and source round trips are checked. The coordinator subsequently confirmed a
separate fresh full build: exit 0, all 1,367 steps, with the calendar positioning
symbol in the final executable; the 540 unit and 768 native-widget cases also passed
independently. Neither build was installed or executed. No Xvfb retry, personal
configuration/media or session access, live deployment, input, display, power or
locker changes. Publication remains pending; no push.

## Historical fullscreen wallpaper pause documentation — 2026-11-15

Documentation-only candidate on coordinator-verified published
`28bfcd83d741c0000f2db69b38f221bcf251c97d`. The roadmap and source-shipped summary now
explicitly include existing automatic fullscreen pause, default-on/opt-out,
monitor/workspace applicability, independent pause reasons and the 500 ms polling
cadence without a hard deadline. [Behavior and evidence](wallpaper/README.md#pause-and-recovery).

The isolated renderer/worker already occur in `fad281f`; native Background controls
occur in `a0f82f9`. Local ancestry confirms both precede this published base. Stale
unpublished-candidate wording is replaced with historical context; the original
private-test counts and controlled-deployment observations are retained.

Verification covers documentation links, exact unchanged non-documentation bytes
and modes, source inventory/checksums and bundle/archive/patch round trips. The
**540 full-suite/nine installed tests** below belong to the unchanged base and were
not rerun for this documentation-only increment. No personal-media access/playback, X11 retry,
runtime build/deployment or live session/hardware check. Physical multi-monitor,
DPMS, normal-login and clean-OS limits remain. Independent review before publication.

## Historical read-only application properties checkpoint — 2026-11-15

Source candidate on published `012aa9318841eca4aae2aa5d511043c4309b4ba1` adds
Properties to the existing app context menu and native keyboard-context invocation. A native
modal exposes selectable plain-text name, desktop ID, description and source
location from the current GIO object. Missing/stale catalog fields are explicit;
locations are snapshots, not file-existence claims. No Exec, filesystem scan/file
read, editor, deletion, automatic clipboard operation or preference write.

**540 full-suite tests pass (35.204s)**; **nine installed-copy tests pass (0.156s)**.
Nine new fixture tests cover actual temporary GIO entries/keyfiles, duplicate
names, deleted source, missing/non-file metadata, display bounds/escapes, native
popup/dialog keyboard paths, accessibility names, stale catalog and corrupt-pin
independence, empty/disabled/drag guards, repeated close and lifetime/focus recovery.
The installed program passes the same nine cases, runtime/toolkit byte/import
checks, rendering inspection, repeat ownership, edited-menu refusal and exact
original byte/mode rollback. A clipped status notice found during visual inspection
was corrected with dialog layout sizing. Native context events route keyboard
requests to the selected row without a duplicate key-press handler; platform
shortcut generation itself remains unverified. No new helper or installer schema.

The roadmap now distinguishes local setup's package guidance from bootstrap/deploy's
explicitly requested automatic prerequisite/module package flow and normal approval.
No package operation was run. No personal catalog, real app/clipboard/session/input/
display/locker action, Xvfb retry, login or clean-OS claim. Existing source/assets,
original dirty workspace, prior evidence and disabled helper are preserved.
See [scope and limits](docs/app-properties.md). Local candidate awaits independent
review; no publication or deployment.

## Historical optional Recent Documents checkpoint — 2026-11-15

Source candidate on published `5cc96a4982aa2547d58079adc3722d70c1248549` adds a
default-off native submenu and separate boolean-only preference. The worker reads
shared desktop XBEL only on explicit submenu open, with bounded bytes/records/output
and cancellation/timeout. Private markers and unsupported URIs are omitted; no
target stat, content, icon, thumbnail or mount probing. Actual availability remains
unknown. Explicit selection dispatches through GIO; it does not prove app success.

No shared-history deletion/copying, personal document indexing, default enablement
or portable-history export. The installer includes the new helper in both runtime
and toolkit; runtime signatures detect upgrades. Existing baseline ownership and
rollback semantics remain. Document preference survives menu removal; no history
is included in the managed-file manifest. See [limits and reproduction scope](docs/recent-documents.md).

**531 full-suite tests pass (34.827s)**, including 16 new cases. Eight installed
UI tests pass (0.453s). Synthetic reader/UI tests include hostile XML/URI input, private duplicates, missing
targets without probing, no-read default, cancellation/late results, native keys,
fake GIO errors, invalid/future settings, exact installer rollback and history
privacy. Eight UI tests also pass using actual temporary-installed code and helper
imports, with synthetic screenshots inspected outside the source archive. No actual
document opening, personal history read, live deployment, package/authentication,
session/device action, Xvfb retry, login or clean-OS claim. Original source, prior
evidence and disabled helper remain preserved. Independent review precedes publication.

## Historical real GIO catalog acceptance checkpoint — 2026-11-15

Tests/documentation-only follow-up to published
`da49537f618b14d88676cfd7202e9f6f5cc9bd39`; no catalog runtime defect reproduced.
Existing GIO discovery, search, monitor/debounce, installer and launch code remain
byte-identical. Three fresh-process scenarios use actual GIO/Qt with disposable
HOME/XDG roots, blocked personal buses and fake executable desktop entries.

The complete **515-test suite passes in 33.612s**, including the three new cases.
They cover user/system precedence, Hidden/NoDisplay/desktop/TryExec rules, duplicate
names/IDs, localized French/German/Japanese/accent search, registered versus omitted
Flatpak-shaped exports, real create/remove/override/metadata notifications, and
selection/right-column focus/pin retention. A 32-file burst caused one rescan in
the recorded run; the test allows up to three and verifies the existing 150 ms
single-shot timer. Typing and the observed settled window cause no catalog queries;
dragging defers them. No application/URI/session dispatch is allowed by the harness.

All three scenarios also pass against the actual temporary-installed menu, with
runtime/toolkit helper byte/import closure, unchanged repeat ownership records and
preference-preserving removal. The fixtures do not establish real Flatpak package
installation/launch, live X11, AT-SPI, physical input, login or clean-OS behavior.
Source inventory, archive/bundle and exact-base patch round-trips are recorded in
the private handoff evidence. No runtime installer migration or new dependency.

Original dirty source, previous evidence and disabled helper remain intact. No
packages, authentication, personal catalog/history, display/input/session/locker
action, live activation or blocked-Xvfb retry. Existing source/art/license notices
are preserved, with no new artwork or private fixture assets in the source archive.
Candidate awaits independent review; no push or deployment.
See [reproduction and limits](docs/app-search.md#real-catalog-fixture-acceptance--2026-11-15).

## Historical Start cross-column keyboard checkpoint — 2026-11-15

Source follow-up to published `0c50da54f9a09499c780796eab8bbfce277e91f8`.
Existing search/results navigation was inspected first; it had no column adapter.
Right from results now enters the remembered or first usable right-side control;
Left from places/options/session controls returns to the selected usable result,
first usable result, or search when none remain. Tab chooses other controls; other
keys retain native widget behavior. No new layout, global shortcut or setting.

The widget-local filter skips hidden/disabled/non-focusable targets, scrolls folder
controls into view and remembers only in-memory identity/role/duplicate occurrence.
Folder rebuilds hide/unregister old controls and restore surviving focus or a usable
fallback. Hidden windows, active drags and popup/modal ownership block navigation.
Search cursor/selection modifiers, category controls, native folder submenu arrows,
Tab and staged Escape remain. Existing Qt accessible names pass interface checks;
results now describe the cross-column keys. No redundant labels replace native names.

**512 full-suite tests pass (28.208s)** with disposable HOME/XDG, offscreen Qt,
synthetic catalogs and private nonexistent bus addresses. Ten added tests cover
column paths, unusable/empty results, dynamic folder/catalog rebuilds, duplicates,
scroll reveal, editing/Tab/reopens, hidden/modal/popup/drag ownership, native submenu
keys and names. Exact baseline export reproduces missing traversal. The actual
temporary-installed menu passes these and ten prior keyboard tests (**20, 0.563s**),
source/toolkit byte/import identity and synthetic visible-focus inspection.
Repeat preserves first-install records; external menu edits refuse rollback; exact
previous menu bytes/mode return, without changing fixture preferences. No installer
schema or new helper dependency. Source checksums, complete archive/bundle and
exact-base patch round-trips are verified; private fixtures/screenshots stay outside.

No app/URI/session/power/input/display/locker dispatch, package/authentication,
personal configuration/history, live activation or blocked-Xvfb retry occurred.
This is not live X11/global shortcut, AT-SPI/screen-reader, login or clean-OS
acceptance. The prior rendering fix remains, with its real color/cut-edge symptoms
still unverified. Original dirty source, prior evidence and disabled input helper
remain intact. Source candidate awaits independent review; no push/deployment.

See [precise focus paths and limits](docs/start-keyboard.md).

## Historical Start first-frame sampling checkpoint — 2026-11-15

Source follow-up to published `27cfea1927a5dea44466a220162e7fcc2b905039`.
The earlier `983ac44` readiness/fringe fix is already present. This increment fixes
one separately reproduced discrepancy: the first glass paint sampled pre-map
coordinates, before Qt adjusted the popup origin. A three-line event-filter addition
resamples on ShowToParent, reusing the cached atlas before queued paints. Ordinary
Show was too early in the failing regression. No theme, layout, opacity, mask,
installer schema or decoding/fallback behavior is redesigned.

**502 full-suite tests pass (27.221s)** in disposable HOME/XDG with offscreen Qt
and private nonexistent bus addresses. Two new tests cover actual first backdrop
paint across three openings, plus fractional alpha and texture scale at DPR
1/1.25/1.5/2. The coordinate test fails on baseline with `(2,224)` versus `(4,226)`.
An independent synthetic matrix exercises two themes and four modes across all four
scales and three cycles: 96 source openings have identical first-callback/settled
captures after the fix. Baseline differences affected eight cold-glass cases, up
to 12/255 per channel; no full palette flash was reproduced.

The actual temporary-installed runtime/toolkit additionally passes 72 openings,
including simulated compositor detection/translucent-theme selection. Helper
bytes/imports, repeat/first-record preservation, edited-helper rollback refusal
and exact baseline restoration pass at each scale. Preferences remain untouched
by removal. Existing artwork, license notices, old builds/evidence, original dirty
checkout and disabled input-helper branch remain preserved.

Curve alpha is unchanged from baseline in the inspected opaque/glass fixtures;
no new white outline was reproduced outside the intentionally overlapping portrait.
X11 binary curved-mask steps remain a limitation. Offscreen captures may trigger
another paint and are not scanout or real compositor/X11 evidence. The reported
personal color/edge symptom is not established as fixed. No live session/display,
input, power, package, authentication or blocked-Xvfb action occurred.

See [rendering observations and Qt implementation reference](docs/wallpaper-glass.md#mapped-position-first-frame-follow-up).
Source inventory/checksums and archive/bundle/exact-base patch round-trips are
verified. This local source candidate awaits independent review; no push/deployment.

## Historical combined release integration checkpoint — 2026-11-15

Documentation-only follow-up to published
`660de7737cc5df522f781c1ff377a4ee99b6895d`. Runtime, tests, artwork and licenses
are unchanged. New disposable-home evidence passes 27 cross-revision subprocess
steps plus seven installed-toolkit boundary checks; no product regression reproduced.
See [the exact integration scope and remaining gates](docs/release-integration.md).
The prior independently verified 500-test suite was not repeated for unchanged code.

Actual old-revision adapters exercise update, interrupted recovery, completed-output
conflict refusal, old/future schema refusal, repeat, first-baseline restoration and
exact upgrade undo. New preferences and unrelated files survive. Installed CLI/import
closure and offscreen combined menu checks pass with fake packages/catalog/service
and no real dispatch. Old-program undo retains preference data but cannot supply
newer retention behavior; full maintenance still needs the complete source checkout.

Windows 7 remains the requested layout scope; other layouts require an explicit
request. Existing full functionality/reference comparisons are retained. The stale
folder-cascade inventory and historical publication/live wording are corrected.
Source inventories/checksums, archive/bundle and exact-base patch are checked for
round-trip bytes/modes. No private fixture/evidence/screenshot enters the source.
This candidate awaits independent review before publication; no personal installation,
package/authentication, power/input/display/session action or blocked-Xvfb retry.

## Historical read-only power capability checkpoint — 2026-11-15

Source follow-up to published `1533623d43c49a8c98bd5ec017a88f473e27d3dc` in a new
isolated checkout. Existing Start actions only checked installed LXQt entries.
The new optional helper queries exactly four logind Can-methods, asynchronously,
with service auto-start and interactive authorization disabled. It never calls a
modifying method, starts a service/agent or performs authentication.

Primary choices, the saved primary button and power menu now distinguish yes,
authorization-required, denied, unsupported, inhibited and unknown states. Unknown,
pending and negative replies disable direct power actions. Saved preferences are
not silently changed; new unavailable primary selections refuse. Native LXQt
options/logout/locker behavior and Cancel-default GIO dispatch remain. Cached
availability is checked before and after confirmation; no completion or late reply
queues an action. Refresh occurs on Start show or explicit Refresh, without polling.
See docs/power-capabilities.md for timeout, advisory-snapshot and backend boundaries.

**500 tests passed in 26.618s**, with disposable HOME/XDG, offscreen Qt, memory
GSettings and private nonexistent system/session bus addresses. Nineteen new tests
cover fixed read-only methods/flags, yes/no/na/challenge/inhibitors, missing service
or Qt, errors/malformed replies/timeouts, coalescing/cancellation/owner destruction,
late results, changed capabilities, disabled primary consistency, actual offscreen
Cancel/Yes confirmation with fake launch, and helper install/repeat/conflict/restore.
Actual temporary installed Start/helper passed all 19 cases (0.301s), exact hashes,
toolkit imports and synthetic rendered state inspection. No personal bus probing,
real session/power/lock call, credentials, packages, daemon or security changes.

The helper is copied with both runtime and toolkit and included in the resident
signature. Existing installer transactions/first backups remain. Complete source
inventory/checksums, bundle, archive and exact-base patch round-trip are verified.
Only relevant source/tests/docs/metadata change; original dirty workspace, prior
artifacts, artwork/licenses and disabled input-helper branch remain untouched.
No push, live installation/activation, blocked Xvfb retry, logout or desktop refresh.

Mocked service and offscreen results do not establish live logind/LXQt/polkit,
physical power/sleep/resume/inhibitors, AT-SPI/screen-reader, login or clean-OS
acceptance. Replies are advisory; actual outcomes remain with LXQt and the system.
This checkpoint was subsequently independently verified and published as `660de77`.

# Start folder-link separators checkpoint — 2026-11-14

Source follow-up to published `474cf6c67aae58050d9427b0f742c55667058846`.
Baseline source and synthetic rendering confirmed only fixed system-group dividers;
the existing folder editor had no separator item. A new opt-in **Add separator**
row reuses Move up/down, Remove, Save/Cancel and the existing conflict/backup path.
Rendered leading/trailing/repeated lines collapse without changing stored rows.
Lines are non-focusable/noninteractive; nested folder browsing and Start keys remain.
Fixed system groups and the default folder list are preserved.

Local lists with separators save version 2; folder-only saves retain version 1.
Exact baseline readers reject version 2. Portable version 2 projects separator
markers among standard IDs/visibility without private labels/paths. New imports
replace standard/separator slots, preserving custom data/order and exact local undo;
legacy version-1 imports leave local separators alone. Resulting local lists remain
bounded to 100 items. See docs/start-separators.md and docs/portable-settings.md for
migration, projection and refusal boundaries. No arbitrary commands or menu tree.

**481 tests passed** in 25.767s with disposable HOME/XDG, offscreen Qt, memory
GSettings and no personal display/session bus, including 14 new separator cases.
Actual temporary installed Start/toolkit passed 24 separator/keyboard cases
(0.414s), exact source identity, portable UI export/preview Cancel/Apply/Restore
with mocked file/confirmation dialogs, and rendered controls at 100%/150% scale.
All screenshots contain synthetic/disposable data and are excluded from source.
No actual app/session/URI dispatch, personal catalog/history or settings were used.
These are not live X11, AT-SPI/screen-reader, physical DPI, login or clean-OS tests.
The blocked Xvfb capability was not retried; no packages or global inputs changed.

Source inventory/checksums, complete Git bundle/archive and scoped patch round-trip
are verified for this increment. Only Start, portable preferences, tests, docs and
metadata change. Existing artwork/licenses, installers and disabled helper remain
untouched, as do the original dirty workspace and previous evidence. This local
candidate awaits independent review before publication; no push or deployment.

# Start keyboard navigation checkpoint — 2026-11-14

Source follow-up to published `baa0a23b7c1c1c506bdac46f934136c5f94f1076`,
from a new isolated checkout. Confirmed baseline gaps: search Up did not enter the
last result, Up at the first result did not return to search, Tab from search did
not enter results, and a focused list rebuild lost its selected desktop entry.
Native Home/End handled simple disabled rows, but left selection unchanged with
mixed hidden/disabled endpoints in the added fixture.

Only the Start runtime changes: widget-local Up/Down and list-edge focus, usable-row
Home/End, Search → Results → All Programs/Back Tab order, focused selection retention,
accessible key descriptions and refusal to activate disabled/hidden/stale rows.
Native text editing/modifiers, the remaining Tab chain, safe GIO launch, nested
folder menus and staged Escape remain intact. See docs/start-keyboard.md.

**467 full-suite tests passed** in 25.515s with a disposable HOME/XDG, offscreen Qt,
memory GSettings and no personal display/session bus. Ten targeted cases cover
empty/disabled/hidden rows, endpoint/boundary keys, focused filtered/catalog rebuild,
text editing, Tab/backtab/reachability, fake Enter activation, nested folder keys,
staged Escape and three resident reopen/cancel cycles. The actual temporary-home
installed Start passed those same ten cases (0.239s), source identity and rendered
result-focus inspection. App/session/URI dispatch is mocked or blocked.

Source inventory/checksums, complete Git archive and scoped patch round-trip are
verified for this increment. Source/test/docs/metadata only; existing artwork and
licenses are unchanged. No personal fixtures, screenshots, configs, history,
credentials, binaries, caches or evidence bundles are part of the source archive.
The original dirty workspace and disabled input-helper candidate remain untouched.
No package, live/session/input change, global key injection or Xvfb retry occurred.
Offscreen tests do not establish AT-SPI/screen-reader, live X11, login or clean-OS
acceptance. Broader cross-column arrows/mnemonics remain deferred. This local
candidate awaits independent review before publication; no push is performed.

# Optional recent-app retention checkpoint — 2026-11-14

Source follow-up to published `09a013acad71c68943aba2b698082bd609153302`.
Start Menu options now offer optional day-based recent-app expiry. Default remains
no age limit and no timestamp collection. Bounded local records, legacy migration,
future-clock handling, visible atomic-save failures and portable policy-only export
reuse existing stores. No polling, document indexing, telemetry or transmission.
Older history backups/private portable undo remain outside active-history expiry.

All **457 unit tests passed** in a disposable HOME/offscreen environment (25.284s).
The temporary installed Start and portable helpers also passed rendered option,
expiry, failure/retry and privacy checks with synthetic records. No personal history
was read, no live configuration changed, and login/long-session acceptance remains
unverified. See docs/recent-apps.md for exact semantics and compatibility limits.

# Custom-root snapping checkpoint — 2026-11-14

Source-only follow-up based on published `63114132943c24cdd54be1b9a97de695f7a0aba3`.
The explicit CLI config-root adapter now supports snapping alone or with
single-desktop. XML/autostart config use the chosen root; program/data/state paths
stay fixed. Both writers share locks, retain exact first backups and refuse root,
symlink, managed-content/mode and ambiguous shared-file recovery conflicts.
See docs/config-roots.md for the precise supported grammar and recovery boundary.

Validation: 12 new disposable-home tests plus one bootstrap forwarding test, with
existing recovery/ownership regressions retained. Installed toolkit CLI executes
against private fixture homes. Package commands/build/platform discovery are mocked;
there is no actual package authentication, runtime startup, login or clean-OS test.
An earlier optional Alt+F1 runtime attempt stopped at failed private Xvfb listener
creation; its runtime acceptance gap remains open. No live setting/session change.

# Config-root symlink review correction — 2026-11-14

Independent review of unpublished `0b32202f752af49f227478ba0e3dc71a26fe4bcd` found
that `HOME/alias -> HOME/.local` with root `HOME/alias/alias-config` passed the
lexical overlap check and direct module apply changed the real reserved-path XML.
This was reproduced in a disposable home before fixing it. Deployment's stronger
ancestor check did not protect direct module/setup paths.

A small shared component check now rejects in-home symlink aliases on root, fixed
XML target and ownership paths through the selected home, before module/setup/CLI
writes. Custom target writes recheck the components. Existing home containment,
reserved-path overlap, root ownership, environment mismatch, rollback and journal
checks remain intact. No shared install.safe behavior or live session is changed.

**431 full-suite tests pass in each of two disposable environments**: XDG variables
unset, and normal XDG config/data/state/cache inherited under the disposable home.
Seventeen root tests pass, including two new matrix/pending-recovery tests. The new
regressions failed on the reviewed source. They cover reserved and ordinary ancestor
aliases, symlinked Openbox directories/XML files, module preview/apply/restore,
setup with zero subprocess calls, installed CLI, and pending deployment recovery.
Targets and ownership/journal evidence remain unchanged on refusal. Three existing
module/settings fixtures now set their own XDG_CONFIG_HOME; no production mismatch
check was weakened. Code was tested before documentation/metadata refresh.

The previous candidate source and artifacts are preserved. This correction is local,
unpublished and awaiting independent review. Source/archive integrity and preservation
checks are recorded in the new durable evidence directory. Actual Openbox startup,
login, clean OS and adversarial concurrent filesystem replacement remain unverified;
this remains bounded path validation, not a dirfd-based atomic filesystem transaction.

# Explicit config-root checkpoint — 2026-11-14

Based on published `72833d01815ea8b544f11414d8b15003ec208fb8`. The source inventory
in docs/config-roots.md identifies mixed fixed config/data/state paths and separate
runtime environment/Qt resolution. This candidate supports a coherent config-only
subset: `single-desktop` with an explicitly selected initialized Openbox config root
inside the user's home, including spaces. Broad core/mixed-module, custom data/state,
GUI and outside-home relocation remain unsupported.

Reuse existing XML ownership/editing, backup, transaction, snapshot and undo code.
Record the relative root and phased module ownership; journal 5 binds the root and
pre-ownership file snapshot. Reject changed roots, missing/corrupt metadata, symlink
paths, overlap with default or configured cache/runtime paths, stale pre-write review,
managed desktop edits and chmod conflicts. Preserve unrelated XML/files and original
bytes/modes. Repeat/recovery/remove reuse the recorded root. No file is moved and no
environment or live process changes. Unsupported/legacy default ownership is never
silently migrated. Old module code refuses the new root-specific edit kinds; old
deployment code refuses journal 5. Same-source recovery remains required.

**429 full-suite tests pass** in disposable HOME/runtime with offscreen Qt and no
personal display/session bus. Fifteen new config-root tests and one bootstrap test
exercise real fixture files, installed toolkit CLI without Qt/PATH tools, safe argv,
root and metadata conflicts, failed/interrupted apply/restore/finalization and exact
undo. Package/build commands are mocked; old-engine refusal is separately verified
with the actual baseline source. Inventory, archive round-trip, patch reproduction
and standalone bundle checks are recorded in the durable private handoff.

The adapter stages the selected XML only: actual Openbox startup must separately
resolve to that config root. No startup environment, login, live workspace, package,
input/display or native UI/build test is claimed. Original dirty checkout, prior
source/evidence, disabled unpublished input helper, artwork and licenses stay intact.
This source candidate awaits independent review; no push or live deployment.

# Optional Alt+F1 ownership checkpoint — 2026-11-14

Based on published `4e608edb6c8cc69aa5fd66eceaa75e0a1839ba43`. Add optional
`start-shortcut` selection to deploy/bootstrap/setup. Reuse integrate's Start values,
shared INI editing and existing transactional backup/undo. Core defaults are
unchanged. Show the current/proposed binding; custom replacement needs an explicit
flag. Never reload the shortcut daemon. The saved file targets its next normal
startup, not a verified active shortcut.

The adapter preserves unrelated bytes on first apply, then conservatively owns the
whole shortcut file. Later edits/renumbering/chmod refuse repeat/removal; other
DoroShell shortcut writes refuse until this ownership is restored. Combined
screenshots/Start deployment orders install/removal safely. Pending/complete/
restoring records retain first-install originals. Journal 4 binds the reviewed
Alt+F1 fingerprint and replacement choice for recovery; old schemas remain supported
for their existing modules. Changed review during build or before interrupted
ownership refuses rather than adopting an edit. Launcher removal cannot strand an
owned binding. Exact upgrade undo remains separate from baseline removal.

**413 tests pass** in disposable HOME/runtime with offscreen Qt and no personal
session bus/display. Added 21 shortcut tests and one bootstrap forwarding test;
invalid replacement syntax also joins zero-command prerequisite checks. Actual
menu/toolkit files and CLI run in fixtures, including installed CLI without Qt or
PATH tools; Qt reads private encoded action fixtures. Package/build/daemon transport
is mocked or unused. Source inventory, archive round-trip, patch applicability and
bundle checks are recorded separately in durable private evidence.

Known limits: CLI only; one standard Alt+F1 action, default XDG layout, conservative
ASCII launcher-path syntax, full-file ownership. Legacy combined integration must
be restored first. Interrupted overlapping writes may require manual inspection
under the existing completed-step guard. Actual shortcut-daemon startup/login and
clean-machine/package acceptance are unverified. No session/input/display/package
change or publication was performed for this candidate. Original dirty source,
previous evidence, disabled experimental input-helper work, artwork and licenses
remain unchanged.

# Prerequisite argument-order correction — 2026-11-14

Based on unpublished `060a904ff8ffd7bb671b62549e179c2b1a60d9af`. Independent review
found missing-tool acquisition could invoke sudo/pacman before Python rejected
`--apply --prerequisites`, unknown options or malformed panel IDs. The failure was
reproduced with fake command markers; no real package or authentication operation.

Bootstrap now validates its documented exact options, separate values, bounded
module choices and action conflicts in pure Bash before checking acquisition tools.
The README downloader accepts only apply/plan, no-packages and optional panelN;
advanced options use local bootstrap/deploy. Both entry points reject malformed
requests before package/authentication/download operations. Saved-state, topology
and ownership checks stay in Python. Valid automatic prerequisite staging is retained.

The **391-test full suite passes**, including four added tests with invalid-argument
matrices, missing/present curl, zero-command assertions, tool-free help/guidance and
catalog compatibility. Thirteen bootstrap and seven prerequisite tests also passed
as focused checks. The exact README command's successful panel forwarding and prior
cancellation/revalidation/rollback regressions remain included. Tests used disposable
homes, offscreen Qt and fake package/authentication/download boundaries. No real
package, authentication, native UI, login, input/display or personal-session change.
Source/archive inventory and incremental/cumulative patch checks accompany the new
private bundle. Prior `060a904` evidence remains unchanged; no publication is included.

# Automatic prerequisite flow checkpoint — 2026-11-14

Based on `a7cbccbc10ae8e3dc8964b013831e1ced9f24cff`, preserving recorded panel choice,
strict layout validation and installer recovery. The README copy-paste command can
offer missing curl; bootstrap can offer Git/Python; deploy can offer PySide6/GIO
needed for explicit panel validation. Each stage prints its command/effect, uses
ordinary sudo/pacman approval and stops on cancellation/failure or an unavailable
dependency after the command succeeds. No unattended flags or authorization grants.
Plan and `--no-packages` do not authenticate or install. `--prerequisites` prints
scoped guidance without reading user state; it is not an installation/readiness check.

This deliberately supersedes manual-only prerequisites in the previous checkpoint:
these prerequisite full-system updates can precede layout validation and are not
rolled back if the layout is refused. The same panel validation is rerun afterward;
module package/build and DoroShell configuration writes still require success.
Known platform errors refuse before this stage. Missing/broken dependency imports
have actionable Arch commands; unexpected programming errors are not converted into
an automatic package request.

The **387-test full suite passes** in disposable HOME/runtime with offscreen Qt and
no personal display/session bus. Fourteen added tests cover exact README command
execution with fake download/package tools, missing-tool identity, cancellation,
failure/no-effect success, no-package/plan guidance, post-package wrong/shared-panel
refusal, successful revalidation, scoped no-state package guidance and import errors.
Actual temporary-home profile/journal adapters run; package/authentication/build
boundaries are mocked. Source/archive checks accompany the private review bundle.
No real authentication/package install, native UI/build, clean OS, login, physical
input/display or session change occurred. Disabled input-helper work is untouched.
Publication awaits independent review and a fresh remote-head check; local GitHub
DNS resolution failed. No push was attempted.

# Deploy/bootstrap explicit-panel checkpoint — 2026-11-14

Based on `df1d976666924ae4c8c3f09a581b4475f0786204`, preserving the prior
panel-selection adapter, public bootstrap and recovery fixes. Bootstrap/deploy now
accept `--panel panelN` and validate it before package offers, builds or managed-file
writes. Source download/cache creation still precedes that check in bootstrap.
No panel is guessed; unrelated source sections and selected geometry are retained.
Pointer format 2/journal format 3 preserve explicit choices across repeat, scoped
updates and recovery; older installers refuse those versions. Legacy single-panel
records remain supported. Interrupted first staging resumes its saved preparation.

The **373-test full suite passes** with disposable HOME/runtime, offscreen Qt and
no personal display/session bus. Eleven new deploy CLI tests and two bootstrap tests
cover plan/apply/repeat/recover/remove, exact upgrade undo, unchanged unrelated sections,
wrong/missing/shared choices, input/source/output conflicts, malformed records,
missing validation bindings and safe argument forwarding. Real temporary-home profile
and journal adapters run; package inventory/build execution are mocked and binary
paths are inert. The initial baseline reproduction confirms both missing CLI selection
and interrupted first staging wrongly taking the upgrade path.

Git/Python must be available before bootstrap, and PySide6/GIO before explicit panel
validation. Missing acquisition/validation tools stop without package changes.
Source/archive round-trip hashes and an applicable patch are included in the durable
private review bundle. No native build/launch, package install, hardware, login,
personal deployment or new authentication test occurred. Custom XDG roots, arbitrary
layout grammars and real multi-monitor/session behavior remain unsupported/unverified.
No unpublished input-helper code is included. Publication requires independent review
and a fresh remote-head check; the attempted read-only GitHub check could not resolve
the host in this environment. No push was attempted.

# Explicit native-panel selection checkpoint — 2026-11-14

Based on published `010af6a77040169eac7133d38d7573e9c602ec23`, preserving completed-step
recovery and public bootstrap. `profile.py prepare --panel panelN` adds bounded
first-time multi-panel preparation through the existing setup/Settings plan workflow.
No selection is guessed. Unrelated sections remain byte-identical, selected geometry
is retained, and shared widget IDs/ambiguous syntax are refused. The installed layout
helper also routes sizing, clipboard and Quick Launch changes to the unique owned panel.

The **360-test full suite passes**, including ten new selection/lifecycle tests.
The suite used offscreen Qt, disposable HOME/runtime and no personal display/session
bus. Real installed-toolkit CLI preview/apply/repeat/rollback passed with a synthetic
package-query command; an installed Settings page was rendered offscreen and its
prepared-plan command inspected without executing it. Exact mode/byte restoration,
interrupted staging/retry, upgrade undo and conflict refusals are covered. The first
full run found an eager Qt import breaking missing-dependency diagnostics; the final
run includes the corrected lazy dependency boundary and all prior regressions.

Source/hash and archive round-trip checks accompany the private review bundle. No
binary build, native process launch, physical multi-monitor, login, package mutation,
device/session change or new authentication test occurred. Full bootstrap/deploy
multi-panel support and custom XDG roots remain unsupported; use the documented
prepared-plan workflow. Source publication/deployment is separate from this evidence.

# Completed native-panel recovery checkpoint — 2026-11-14

Based on `c87ff151f7ca658b665d79bbc4a323461f086068`, preserving public bootstrap and
the continuation wording. No unpublished system-input helper is included. In a
disposable home, interrupt before maintenance after menu/native-panel complete,
then add a second panel to the separate stock LXQt file. The baseline CLI wrongly
refuses recovery on its single-panel capability gate. Recovery now omits that
irrelevant check only after validating the journal and completed output bytes/modes.
The requested modules, remaining capability checks and conflict safeguards are unchanged.

Four focused regression tests and the **350-test full suite pass**, using offscreen
Qt and disposable homes without a personal display/session bus. Tests cover the
reproduced failure, unchanged completed evidence, exact undo preserving the new stock
layout, content/mode/symlink conflicts, unfinished native-panel refusal and retained
custom-XDG refusal. Package inventory/native building are mocked in the new CLI
tests; the real temporary-home native-profile and journal adapters run. Existing
repeat/removal/upgrade and recovery regressions remain included. No package, native
binary, live UI, login, physical input/display or clean-OS acceptance is added.

Source inventory, catalogued artwork and exported-archive hashes are verified for
the review bundle. First/unfinished native-profile recovery remains broader work;
same-source recovery still refuses older pending journals rather than migrating them.
The previous disabled input-helper/authentication investigation remains separate.

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

After `f26f439`, the [entry probe](docs/tray-lifecycle.md#keyboard-only-entry-historical-native-limitation)
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

## Portable development installer — 2026-11-14

Baseline `dee97b4` is remotely published and preserves the complete source/art
bundle plus upstream `36929b2`. The next increment adds bootstrap acquisition,
capability/package detection, native build reuse, scoped module orchestration,
legacy-manifest recognition, update/removal launchers and a private deployment
journal. Completed-upgrade undo restores preceding bytes/modes/manifests; module
removal retains first-install baseline semantics. Pending module recovery refuses
normal retries, reuses the same source and preserves conflict checks. Cursor
writes now use atomic records and pending hashes/modes; native panel upgrades
retain personal panel settings and original backups.

Verification boundaries:

- Inherited full suite: 262 tests before changes. An intermediate complete suite
  passed 277 tests. Final suite: **285 tests passed** (`python -m unittest discover -s tests -v`).
- Targeted bootstrap: five tests with fake Git/GitHub-CLI transport, including the exact
  README shell command, failed-download non-execution, source reuse/dirty refusal,
  stable-label refusal, and symlink refusal. No remote write by these tests.
- Targeted deployment: 15 temporary-home tests, including actual menu installation,
  combined core/clipboard adapters, package-offer mocks, interrupted persistence,
  malformed undo, bytes/modes/symlinks, finalization recovery and native upgrades.
- Cursor suite: seven tests including legacy record and partial-write recovery.
- Fresh actual standard ten-patch panel build and standard paired native Background
  + display build passed. Wallpaper build used the private panel build-tools prefix;
  no OS package was installed. This is not clean-host dependency acceptance.
- Complete disposable-home acceptance used those actual compiled payloads for
  staging, with all core modules plus clipboard/wallpaper/glass/display. Install,
  repeat, exact previous-upgrade undo, installed toolkit imports and first-baseline
  removal passed. No native executable was launched by that staging test.
- The bundled Start art matches installed image pixels; APNG-generated wait and
  progress cursor bytes match the installed cursor files exactly. Media frames and
  metadata were reviewed; personal configs/identifiers and binaries are excluded.

A local Docker daemon was unavailable. No clean Arch/CachyOS/EndeavourOS VM, normal
login, live desktop interaction or physical display recovery is claimed. Read-only
process inspection still found the ten-patch panel, schema-2 desktop and clipboard
helper; no session process was refreshed. The hardware NVIDIA mismatch remains
unknown. `release.json` declares development; no stable portable release is invented.
See README and docs/INSTALL.md, STATUS.md and HANDOFF.md for installation and limits.

### Private-repository bootstrap correction

The real unauthenticated raw-GitHub download returned HTTP 404 after publication.
Read-only repository metadata confirms PRIVATE visibility. README now uses GitHub
CLI authentication and the authorized contents endpoint, with download completion
checked before execution. Bootstrap fetch uses a per-command CLI credential helper
and does not change repository visibility or persistent Git configuration. Five
bootstrap tests cover the corrected command and failed-download non-execution.

The corrected published revision `5c0baba43e2161ea56e03b5a8011290e2590bd2a`
was fetched through the exact authenticated README command with the action changed
to plan-only in a disposable home. It passed inventory verification and retained a
clean source checkout without credential-helper config entries. The same command
then passed a real scoped menu install with `--no-packages`, followed by repeat
installation and removal through the downloaded source. Original module backup
bytes survived the repeat, and managed menu/manifest files were removed as expected.
No authentication prompt was opened by testing; existing authorization was read-only.
No user configuration or live display/bus was accessed by the installation fixture.
The full suite after the authentication correction passed **285 tests**.

The committed source export was round-trip extracted and passed both
`python source_release.py` and `sha256sum -c SHA256SUMS`. No `.git` directory,
compiled runtime, cache, private config, journal or credential is part of the export.

### Independent QA context retained

The separately recorded screenshot acceptance on `dee97b4` passed rendered capture,
native import, exact application paste and global Print after a test-harness command
serialization correction. This task did not repeat those UI suites. The unmerged
lock-surface probe at `f81d5d5` has a reproduced final overlay-stacking failure and
is excluded/unready; unit assertions do not establish working locker integration.
STATUS and HANDOFF preserve the exact boundaries without copying private logs.

### Deployment recovery correction — 2026-11-14

Based on published `fa8808c75f4d6d1d639432d95f093d20a1497459` in a separate
checkout; the original dirty workspace and personal installation remain unchanged.
Independent fixture reproductions confirmed two defects in that baseline: recovery
adopted a user edit to a completed menu output, making undo overwrite it, and
recovery performed writes through journal format 999 that undo subsequently refused.

`deploy.py` now writes format-2 journals with cumulative completed-step bytes/modes
and the active target inventory. Recovery verifies completed outputs before doing
work; finalization retains the saved evidence instead of sampling arbitrary current
files as owned. Shared validation covers schema/status, request, progress, snapshot
paths/bytes/modes and embedded deployment pointers before consuming recovery requests
or writing. Original pre-transaction snapshots and first-install module records
remain distinct and unchanged by successful retries.

Verification:

- `python -m unittest discover -s tests -v`: **302 tests passed** with display/session
  buses unset and Qt offscreen. No live UI, clipboard or display was exercised.
- 17 new recovery tests cover the two reproductions, content/mode/symlink conflicts,
  malformed/unsupported records without target/pointer/journal changes, CLI refusal
  before prerequisite/build work, saved evidence and finalization, overlapping
  successful writes and ambiguous interruption, and legacy/current interrupted undo.
- Existing temporary-home tests still cover active-module partial-write recovery,
  real menu/toolkit repeat/upgrade, exact previous-upgrade undo, combined optional
  module staging and first-baseline removal. No package manager mutation occurred.
- Source inventory/checksums and the extracted Git archive are checked for this
  increment; only code/tests/documentation/metadata change. Existing catalogued
  artwork and all component licenses remain unchanged. No private fixture homes,
  journals, configuration, screenshots, credentials, caches or compiled runtimes
  are included.

Compatibility limits: format-1 pending journals lack completed-step evidence and
are refused, not migrated from current bytes. Valid completed format-1 journals
retain exact undo, but earlier adoption cannot be detected retrospectively.
Interrupted overlapping writes or changed active target inventories require manual
inspection. Preserve journals and originals instead of deleting them to bypass
conflicts. The same-source recovery rule remains. These tests simulate exceptions,
not actual power loss, clean-machine install, login or physical hardware acceptance.

### Installed input-preferences integration — 2026-11-14

Integrates feature `0cf6019a0e4d5e32d1e81df4f2f495075b1f4694` with main
`e18026e166c96382f24843cdb3467ffe989c5568`, retaining the recovery fixes above.
The feature's helper, DoroShell Settings page and original tests are retained.
Installer integration adds the helper to toolkit payloads, declares Xlib/udev
dependencies, pins autostart to the installed location, records ownership before
creation/removal, and refuses program removal/changed-helper undo while restoration
is pending. Stop managing and restore includes absent saved choices without
discarding their unresolved receipts. Ended-session evidence is archived privately
before retirement; no old-session property is forced onto a new session.

Validation for this increment:

- **326 tests passed**: `python -m unittest discover -s tests -v`, display/session
  buses unset and Qt offscreen. This retains all 17 recovery regressions and includes
  24 input tests (12 feature + 12 installer/lifecycle tests).
- Disposable homes cover actual install/repeat/older-toolkit upgrade/removal/exact
  undo, unchanged-helper undo with active choices, preflight refusal before any
  module removal, input/helper byte/mode conflicts, retained lock inode, missing
  helpers, malformed records, absent/unsupported restoration, archive failure,
  interrupted autostart creation/removal and explicit safe retry.
- `python tests/check_installed_input_x11.py --xvfb /path/to/private/Xvfb --output
  /path/to/private/evidence` passed on authenticated private X11. It imports the
  installed toolkit, renders actual Settings, uses keyboard/pointer events against
  mocked devices, verifies saved opt-in/restoration and last-mouse refusal, checks
  narrow/large-font scrolling, and removes the fixture installation safely. Both
  private screenshots were visually inspected; neither is published.
- Exported source inventory/checksums are verified; program/test/docs/metadata only.
  Existing artwork, licenses, display/panel implementations and the dirty original
  workspace are preserved. No live activation, device assignment or packages.

Read-only host evidence: a matching evdev system rule and Xorg initialization log
select scheme `none/0`, while the pointer exposes no `Device Accel Profile`.
This is configured/initialization evidence, not a motion-response test. A future
system-scheme rule change requires separately approved device reinitialization or
a new Xorg session to reread the configuration; refreshing Settings/panel/desktop
is not that operation. No restart is performed or required merely to publish this
source. Physical evdev/touchpad changes, normal login ordering, hotplug, clean OS
installation and Wayland remain unverified/unsupported as documented. The reference
UI was native LXQt; this implementation is a DoroShell page plus native link.

Compatibility: unintegrated feature autostart entries without recorded ownership
are not guessed/adopted. Active or unresolved input state must be resolved before
helper replacement by undo/removal; inactive choices, archived evidence and locks
are retained. No installer automatically changes input to make removal succeed.

### Read-only input capability diagnostics — 2026-11-14

Based on integrated `d84b39272b7a45efd51751a7a6b5b97da767f95c`. Current main and
worker activity were checked before editing the clean integration checkout; the
original dirty workspace and personal installation remain untouched.

The installed Mouse & Touchpad page now separates user preference/observed profile,
runtime profile control, and matching standard-system-rule intent. The read-only
scan is limited to 64 files, 64 KiB per file, 256 KiB total, with explicit malformed,
unreadable, unsupported, changed, bounded and conflicting evidence. No files are
written by Refresh. Current Xorg initialization remains **unverified** because the
available XInput data cannot bind a historical log to the current server/device
initialization. Logs and privileged sources are deliberately not read or promoted
to proof. No physical motion-response or effective-system-scheme claim is made.

- `python -m unittest discover -s tests -v`: **337 passed**, with display/session
  buses unset and Qt offscreen. Includes 11 new diagnostic tests, all 24 previous
  input/lifecycle tests, and all 17 deployment recovery regressions.
- Fixtures cover absent/malformed/truncated/conflicting/unsupported rules,
  unreadable/changing evidence, byte/file-count limits, symlink/nonregular refusal,
  stale or matching logs not read/promoted, and Refresh without device, preference
  or session-marker writes. Product/path/type match behavior is fixture-tested.
- The installed-toolkit private-X11 check passed with mocked devices and rules:
  available/unavailable runtime controls, separate `none` intent/unverified status,
  existing opt-in/restoration/last-mouse behavior, narrow/large-font scrolling,
  helper packaging and removal. Private screenshots were visually inspected and
  excluded from the source archive.
- A read-only current-device check found evdev properties, no exposed acceleration
  profile and a matching system `none` request. It made no property/session-marker
  writes; the new UI correctly leaves initialization unverified. Raw device
  identity, logs and system configuration are not copied into published fixtures.
- Source inventory/checksums and archive round-trip are verified for this increment.
  Existing artwork, component licensing, apply/restore behavior and program rollback
  remain intact. This is source/private-test evidence, not personal deployment,
  physical input testing, login, hotplug or clean-OS acceptance.

The scope is a DoroShell status page with a native LXQt link. It cannot change the
system acceleration scheme and adds no daemon, privileged reader or diagnostic log.
Custom Xorg config sources/overrides and reliable current-initialization provenance
remain outside this conservative diagnostic. Publication is held for independent
review of the prepared commit; no session action or deployment is part of this pass.

Final custom-root snapping validation: **444 tests pass** with inherited normal
XDG paths under a disposable HOME, offscreen Qt and a private nonexistent session
bus (24.703s). The 29 focused config-root tests and 16 bootstrap tests also pass.
Two existing snapping fixtures now bind their own config directory; production
mismatch refusal is unchanged. The prior reader at `6311413` separately refuses
new module apply/rollback and combined journal requests before fixture writes.
