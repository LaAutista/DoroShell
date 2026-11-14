# Current acceptance and deployment record — 2026-11-14

This checkpoint follows published `fd1859d`, including the newer Start, screenshot
and display-diagnostic changes. Read-only inspection confirms the startup wrapper
and running executable select the tested ten-patch shortcut runtime; binary hash and
all ten runtime patch notices match retained evidence/current source. This supersedes
older four-/nine-patch selection notes, without claiming a new live UI acceptance.
Installed Start/search and capture payloads match current source bytes; resident
reload was not established. No refresh or Gamebox-account change occurred here.
[Release verification](../RELEASE-CANDIDATE.md).

| Area | Source shipped | Verification recorded | Installation evidence |
| --- | --- | --- | --- |
| Start | Ranked installed-app search, folder cascades, portable Start preferences, configurable primary session action, portrait crop and wallpaper-glass rendering fixes | Unit and private-X11 interaction/rendering checks; session actions mocked | Installed Start/search payload bytes match current source in this read-only pass; resident reload and new UI acceptance were not established. |
| Launcher identity and filtered pins | App-ID/class resolution, explicit-pin tie breaking, icon fallback and filter-safe pin activation | Private native checks plus recorded independent controlled live acceptance | The ten-patch panel is now confirmed by read-only process-path/hash inspection; earlier filtered-pin evidence remains historical. Real Fluorine and Discord reused their pins in earlier live acceptance; windows and panel settings survived. |
| Tray lifecycle and keyboard menus | Attention invalidates stale overflow; popup holds/releases auto-hide; Menu/Shift+F10; no duplicate activation after menu selection | Private-X11 focus, Escape, outside dismissal, disconnect, attention timeout and keyboard/menu regressions | Included in the now-observed ten-patch runtime; no activation or new live interaction check in this pass. |
| Show Desktop | Window-manager restoration retained; drag-hover stays in showing-desktop mode and ignores early departure/release | Private Openbox checks cover minimized/sticky windows, two workspaces, create/close, repeated toggle, real drags and same-process panel orientation changes | Included in the observed ten-patch runtime; no new live interaction check. |
| Dense taskbar and tray | Bounded scrollable overflow and correctly wrapped long-title tooltips | 60 notifier icons, 12 long-titled tasks, enlarged font, 800×600 Xvfb at Qt 150%/200%; forward/reverse keyboard traversal and four-palette contrast | Included in the observed ten-patch runtime; no new live interaction check. This is not physical mixed-DPI evidence. |
| Screenshots | Desktop/window/area, editable annotations, text controls, redaction/blur/pixelate, cancellable delayed recapture and native importer | Private pixel/input checks, including 100%/150% recapture and synthetic clipboard checks | Installed capture payload bytes match current source; earlier component evidence is retained, with no fresh live capture or resident-reload claim. |
| Wallpaper | Paired isolated decoder, native Background controls, mute/volume/pause/Off and static fallback | Private native controls, synthetic media/resource tests and null-sink audio; earlier controlled desktop-only activation | An earlier read-only process-path inspection confirmed the custom native wallpaper-preferences renderer; that renderer was not re-audited in this pass. The user reported animation working. That report is separate from automated tests and does not establish current mute/volume state or physical audio routing. |
| Display controls | Guarded optional native Advanced controls and helper | Private fake-driver Keep/Revert/error/conflict tests | No new hardware/display-setting changes or recovery acceptance in this pass. |
| Setup and recovery | Explicit preview/apply/rollback, original backups and conflict refusal | Temporary-home install/repeat/rollback tests and recorded controlled upgrades | No clean-install or fresh-login acceptance for the current source. |

The XEmbed and native-shortcut changes are included in the observed running binary.
Their recorded private/independent acceptance remains distinct from today's read-only
provenance check. No current shortcut assignment or screen-reader compatibility was
inferred. Optional lock-screen animation remains **unimplemented**; see the
[design-only checkpoint](animated-lock-screen-design.md). Gamebox setup was reported
by another thread as staged with backups/isolated checks; actual login remains
unverified, and this pass did not inspect that account.

## What independent evidence establishes

Independent controlled native/live acceptance is recorded for launcher identity
and filtered pins. Later tray, Show Desktop and density commits have their own
passing private tests and independent remote-commit confirmations. Independent
reruns were requested for later increments; a remote confirmation or a running
rerun is not itself an independent UI pass. No additional independent completion
is inferred here.

The installation observations above are read-only snapshots, not new activation
or proofs of every enabled option. Personal executable paths, media, configuration
and recovery checkpoints are intentionally excluded from public source.

## Appearance decision

The user chose lightweight wallpaper-derived glass and dropped true moving-window
Aero/compositor work. Wallpaper glass samples the configured static backdrop; it
is not transparency through moving application windows or video frames. No live
Aero experiments, compositor changes or further Aero work are scheduled. The owner-requested artwork and wallpaper source bundle now ships separately from
private desktop settings; see assets.md.

## Recovery and genuinely remaining acceptance

Keep versioned native runtimes and existing private recovery data. The documented
[next-startup panel workflow](../panel/README.md) and [wallpaper rollback](../wallpaper/README.md)
remain available; building this source does not invoke them.

- Broader real-notifier/app acceptance for the already selected ten-patch panel,
  only at a chosen safe point; no redundant refresh is needed for this docs checkpoint.
- Broader real-application/notifier diversity, real-client XEmbed variants, long-session use,
  other fonts/layouts and broader [configured native shortcut](tray-shortcut.md) coverage. Pointer-free synthetic entry passes; popup AT-SPI labels remain an inherited limitation.
- Physical multi-monitor/mixed-DPI, Wayland, physical audio/DPMS and display recovery
  remain unverified. Private Xvfb or fake-driver tests do not establish them.
- Fresh-login and clean CachyOS install/upgrade/rollback are user-deferred. Do not
  initiate logout, locking, reboot or a desktop reset to close these items.

The next useful non-disruptive action for the requested animation gap is the
[fake-host rendering probe](animated-lock-screen-design.md#first-isolated-acceptance-checkpoint).
It must not register with or control the real locker. Broader product gaps remain
in the [roadmap](roadmap.md).
