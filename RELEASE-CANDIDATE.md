# DoroShell complete source candidate v5 (licensed) — 2026-11-10

Complete combined source; no prior unpublished commit or temporary patch is required. Includes all v3 features and transaction hardening, plus mode-only edit refusal for menu and shared optional installation/recovery. Source provenance and exact hashes are in SOURCE-MANIFEST.json. V4 is preserved unchanged. The owner approved GPL-2.0-or-later for original DoroShell source, preserving component licenses; see LICENSING.md. This successor changes notices/documentation only, plus non-executable SPDX comments in display source/patch.

Verification: **210 tests passed in 11.624 seconds** on this licensed source candidate. Display patch syntax was parsed successfully. No fresh native build or private UI checks were rerun for these notice-only changes. Parent independent results are not claimed.

## Release-readiness matrix (inherited v4 packaging-time snapshot)

The matrix below preserves v4 evidence and is not a current live-deployment inspection. The parent separately reported a subsequent five-file toolkit upgrade; no live deployment was performed in this licensing task.

| Area | Implemented | Private verification | Live installed evidence | Staged status | Still unverified |
|---|---|---|---|---|---|
| Ranked local app search | Name/executable/keyword ranking, keyboard results, empty states | Unit and prior isolated keyboard/catalog tests | Runtime/toolkit search upgrade previously installed; inspected toolkit hashes match candidate | Complete v4 source packaged; no activation this task | Fresh OS/login, broader app catalogs; no new on-screen live check |
| Folder cascades | Bounded lazy folder menus | Prior private folder/keyboard/integration tests | Existing toolkit helper matches candidate; retained by search upgrade | Complete v4 source packaged | Broader filesystem/desktop environments and clean login |
| Portable Start preferences | Path-free export, preview/import and conflict-checked restore | Prior portable and combined toolkit tests | Existing installed portable helper matches candidate; no personal import performed | Complete v4 source packaged | Broader cross-machine acceptance |
| Display controls | Guarded session RandR test and NVIDIA future-client OpenGL control | Prior fake-driver/native private UI and paired integrity tests | No display-control live activation performed by this work | Private native candidate previously built; live display-enabled staging is not established here | Physical changes/recovery, Intel/AMD hardware, multi-monitor/rotation/scaling, normal login |
| Installer hardening | Actionable expected errors, read-only previews, transaction preflight and mode-conflict refusal | 210-test worker suite; malformed/interrupted writes, chmod, symlinks and legacy schema checks | Live installed installer/setup/module helpers remain older; five program payloads need a future narrow upgrade | V4 source/evidence only; deployment plan is read-only and unexecuted | Persistent I/O/power-loss durability, hostile manifests, editor races; actual deployment not performed |

Ordinary rollback restores the first-install baseline. Optional failure compensation restores the immediately preceding installed version. Menu interrupted writes retain a recovery manifest. Content/mode conflicts refuse instead of adopting user edits. Legacy modes use conservative known payload/baseline states; an edit indistinguishable from an allowed recovery state cannot be detected. General race-free or power-loss guarantees are not claimed. Special permission bits are outside the ordinary-file chmod tests.

Build/setup: read README.md, docs/clean-environment-simulation.md and component READMEs. Preview selected modules first; never treat menu installation as permission to apply desktop modules. Native builders require documented development dependencies and fetch pinned upstream sources. Display builds use wallpaper/build.py --display-controls with a new permanent work directory; keep executable, video helper, display helper and format-3 record together. No binaries/toolchain/media/configuration are included.

The original-source licensing decision is resolved. Publication still requires the intended destination/authorization and preservation of component notices. Clean OS/login and physical hardware acceptance are required before making stable hardware claims. A separately approved future toolkit-only deployment may use the private outer-directory plan; it was not executed while the user slept. No live changes, session/power actions, package operations, network, Git configuration or push occurred in packaging.

Verify extracted source: `sha256sum -c SHA256SUMS`. Outer files provide archive hash, test log, scoped patch and private read-only deployment plan. The deployment inventory is deliberately outside the source archive.
