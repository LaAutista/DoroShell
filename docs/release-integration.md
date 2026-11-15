# Combined release integration — 2026-11-15

Runtime source is unchanged from published
`660de7737cc5df522f781c1ff377a4ee99b6895d`. This pass found no reproduced product
regression requiring a code change. Publication of that base and its 500-test suite
were independently verified by the coordinator; those unchanged tests were not
rerun here. New checks exercise cross-feature boundaries rather than count as new
unit tests. This documentation candidate still requires independent review.

## New evidence

All writes used disposable HOME/config/data/state/cache/runtime directories.
Qt used offscreen rendering; system/session bus addresses pointed to nonexistent
private paths. Catalogs, launch dispatch, package availability and platform
compatibility were synthetic. The real menu/module/deployment adapters wrote and
restored fixture files; package/build/process mutation boundaries were forbidden.
Installed setup's package queries used a fake pacman accepting only `-Q`.

| Boundary | Result |
| --- | --- |
| Pre-feature `a7cbccbc10ae8e3dc8964b013831e1ced9f24cff` → current | 13 subprocess steps: actual menu/config/maintenance install, update, repeat, exact prior-upgrade undo, re-upgrade, Alt+F1 explicit replacement/refusal, exact shortcut undo and full removal. First-install originals/modes and new preferences survive; optional shortcut stays absent until requested. Unrelated shortcut/XML bytes survive. |
| Custom-root `63114132943c24cdd54be1b9a97de695f7a0aba3` → current | Eight steps: add shared-root snapping beside existing single-desktop in a path with spaces; old/future journal refusal before writes; exact upgrade undo; re-add; separate removals restore original XML/mode. Default-root and unrelated files remain untouched. |
| Interrupted old → current update | Six steps: actual menu completes before injected interruption at maintenance; old-source recovery refuses; current recovery refuses an edited completed helper; exact conflict resolution permits recovery and prior-upgrade undo. Original snapshots/preferences survive. |
| Installed dependency/CLI closure | Actual installed imports resolve Start/search/folder/power helpers and Settings/portable/setup/modules from the toolkit. Setup/module help and custom-root plan/apply/repeat/reverse-order rollback work. No package/authentication command runs. |
| Combined installed Start | Offscreen synthetic catalog: age-boundary pruning, noninteractive separator, search/results arrows and Home/End, empty results, retained unavailable primary choice. No app/URI/session dispatch; four fake read-only capability replies. Synthetic rendering inspected. |
| Preference/version/removal | Combined export retains retention policy and separators without history/timestamps/private paths. Current future local versions refuse writes. Menu removal preserves preference bytes and removes owned helper. |

Totals: **27 cross-revision subprocess steps across three scenarios**, plus
**seven installed-toolkit boundary checks**. The normal-root scenario completed
before a later fixture incorrectly bound XDG_CONFIG_HOME for its custom-root case;
the product correctly refused that mismatch before writes. The fixture environment
was corrected and only custom-root/recovery scenarios rerun. An earlier harness
incorrectly imported full-source deploy from the reduced installed toolkit and was
corrected. These were test-harness issues, not product defects or ignored failures.

## Completion and remaining acceptance

| Item | Published/source-tested | Isolated/installed evidence | Live or remaining boundary |
| --- | --- | --- | --- |
| Automatic prerequisites | Explicit staged plans, normal approval, cancellation and early argument validation | Prior fake-command coverage; unchanged in this pass | Actual package/authentication and clean Arch derivative install not established |
| Optional Alt+F1 | Explicit ownership, replacement, recovery and undo | New actual disposable-file combined lifecycle; prior parsing/CLI tests | Real isolated shortcut-daemon test blocked by unavailable safe X11 harness; no retry or live reload |
| Bounded XDG adapters | Only snapping, single-desktop or both; config root recorded | New old/current upgrade, exact undo and installed CLI | No full-shell relocation or actual Openbox startup acceptance |
| Retention/separators/keyboard/capabilities | Published opt-ins/controls with prior independent unit/offscreen coverage | New actual installed composition and export/refusal checks | No new live interaction, screen-reader, hardware power or authorization test |
| Search/folders/portable | Published; existing bounded implementations retained | Installed helper closure and preference lifecycle | Historical private/live evidence applies only to its recorded revisions; no current live equality claim |
| Display/input/locker | Unchanged by this pass | No new acceptance | Physical NVIDIA verification/rollback remains unresolved; disabled administrative input experiment stays separate/unpublished; animated locker remains unready |

Old-program undo preserves preference bytes rather than translating them to old
semantics. Pre-retention Start does not enforce the newer age policy; older
folder/portable readers refuse unsupported versions. Full deployment/maintenance
requires the retained complete source, not the reduced Settings toolkit.

No personal settings/history/bus were read, no source helper gate changed, and no
packages, live installation, daemon reload, display/input/power action, login,
desktop refresh or blocked-Xvfb retry occurred. No fresh-OS, hardware, full parity
or stable-release claim follows from these checks. Existing artwork and component
license notices remain unchanged. Windows 7 is the current layout scope; other
styles require an explicit request, while the broad functionality inventory remains.
