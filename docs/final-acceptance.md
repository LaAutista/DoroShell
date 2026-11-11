# Current acceptance and deployment record — 2026-11-11

Published GitHub main includes the source through `5749fa1`; this consistency
checkpoint follows it. The old optional ZIP and the published 2026-11-09 core
release are historical artifacts, not descriptions of current main. Building or
publishing source is not activation. [Release verification](../RELEASE-CANDIDATE.md).

| Area | Source shipped | Verification recorded | Installation evidence |
| --- | --- | --- | --- |
| Start | Ranked installed-app search, folder cascades, portable Start preferences, configurable primary session action, portrait crop and wallpaper-glass rendering fixes | Unit and private-X11 interaction/rendering checks; session actions mocked | Earlier controlled menu upgrades are recorded. This pass did not re-audit the installed Start revision. Do not infer its revision from GitHub main. |
| Launcher identity and filtered pins | App-ID/class resolution, explicit-pin tie breaking, icon fallback and filter-safe pin activation | Private native checks plus recorded independent controlled live acceptance | The filtered-pin panel runtime was confirmed by read-only process-path inspection. Real Fluorine and Discord reused their pins in earlier live acceptance; windows and panel settings survived. |
| Tray lifecycle and keyboard menus | Attention invalidates stale overflow; popup holds/releases auto-hide; Menu/Shift+F10; no duplicate activation after menu selection | Private-X11 focus, Escape, outside dismissal, disconnect, attention timeout and keyboard/menu regressions | Source-shipped and privately built/staged; not activated by this work. |
| Show Desktop | Window-manager restoration retained; drag-hover stays in showing-desktop mode and ignores early departure/release | Private Openbox checks cover minimized/sticky windows, two workspaces, create/close, repeated toggle, real drags and same-process panel orientation changes | Latest drag fix is staged, not live. |
| Dense taskbar and tray | Bounded scrollable overflow and correctly wrapped long-title tooltips | 60 notifier icons, 12 long-titled tasks, enlarged font, 800×600 Xvfb at Qt 150%/200%; forward/reverse keyboard traversal and four-palette contrast | Latest density fix is staged, not live. This is not physical mixed-DPI evidence. |
| Screenshots | Desktop/window/area, editable annotations, text controls, redaction/blur/pixelate, cancellable delayed recapture and native importer | Private pixel/input checks, including 100%/150% recapture and synthetic clipboard checks | Earlier component evidence is retained; no fresh live capture or exact installed revision claim here. |
| Wallpaper | Paired isolated decoder, native Background controls, mute/volume/pause/Off and static fallback | Private native controls, synthetic media/resource tests and null-sink audio; earlier controlled desktop-only activation | Read-only process-path inspection confirmed the custom native wallpaper-preferences renderer. The user reported animation working. That report is separate from automated tests and does not establish current mute/volume state or physical audio routing. |
| Display controls | Guarded optional native Advanced controls and helper | Private fake-driver Keep/Revert/error/conflict tests | No new hardware/display-setting changes or recovery acceptance in this pass. |
| Setup and recovery | Explicit preview/apply/rollback, original backups and conflict refusal | Temporary-home install/repeat/rollback tests and recorded controlled upgrades | No clean-install or fresh-login acceptance for the current source. |

The later [XEmbed/SNI checkpoint](xembed-tray.md) adds a private synthetic docking,
pixel, input and restart check and a ninth registration-popup patch. It is staged,
not live; no independent rerun is inferred.

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
Aero experiments, compositor changes or further Aero work are scheduled. Neutral
artwork ships; personal artwork and media do not.

## Recovery and genuinely remaining acceptance

Keep versioned native runtimes and existing private recovery data. The documented
[next-startup panel workflow](../panel/README.md) and [wallpaper rollback](../wallpaper/README.md)
remain available; building this source does not invoke them.

- A controlled panel-only activation of the staged fixes, if explicitly chosen,
  followed by real-notifier/app checks and verification that clients/settings survive.
- Broader real-application/notifier diversity, real-client XEmbed variants, long-session use,
  other fonts/layouts and keyboard-only entry to tray overflow.
- Physical multi-monitor/mixed-DPI, Wayland, physical audio/DPMS and display recovery
  remain unverified. Private Xvfb or fake-driver tests do not establish them.
- Fresh-login and clean CachyOS install/upgrade/rollback are user-deferred. Do not
  initiate logout, locking, reboot or a desktop reset to close these items.

The next useful non-disruptive action is a read-only comparison of the staged
runtime's provenance with the installed runtime and a concrete activation/rollback
plan for later review. More speculative feature work is not required to finish
this source checkpoint. Broader product gaps are in the [roadmap](roadmap.md).
