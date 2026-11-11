# Combined screenshot and native Background source candidate

Prepared locally on 2026-11-10; publication is pending parent verification. This
is a complete source candidate based on published main
`1f687d2ab01a09774baf8baf6bf1ec538221e745`, incorporating committed screenshot
release `9a6c5d1ab01ee47c1ca2307eeeab0e9ba76ce0f9` and the approved native
wallpaper preferences implementation. Neither component requires an external
unpublished patch. The screenshot commit was imported without modification to
its originating checkout. There were no implementation conflicts.

## Changes

- Screenshot annotations gain selection/editing, text font/color controls,
  snapped lines, numbered stamps, Blur/Pixelate, and cancellable delayed full
  desktop or monitor recapture with optional pointer inclusion.
- PCManFM-Qt Background retains its static wallpaper groups and adds the approved
  Animated Wallpaper group: type, local file Browse, fullscreen pause, mute,
  repaint FPS, volume slider, and silent Preview/Stop. Existing fit and monitor
  selections are preserved. Apply/OK saves atomically with backup and conflict
  refusal; Cancel retains only previously applied changes.
- The existing Advanced display implementation and helper are unchanged.
  The standard wallpaper builder includes Background controls and retains
  Advanced when invoked with `--display-controls`.

## Verification for this combined source

`python -m unittest discover -s tests -v`: **230 passed** (11.799 seconds).
These are local/offscreen/mocked and temporary-home tests, not clean OS tests.
The standard native builder completed against the pinned PCManFM-Qt revision,
producing the desktop executable, decoder helper, display helper and format-3
integrity record in an isolated build directory.

Private X11 integration checks rerun from this combined checkout:

- `check_overlay_editing_x11.py`: real input, crop/annotation edits,
  text formatting, undo/redo, save cancellation, exact PNG/clipboard pixels.
- `check_recapture_x11.py`: cancellation, delayed fresh captures, pointer hotspot,
  exact PNG/clipboard output at scale factors 1 and 1.5.
- `check_native_wallpaper_buttons.py`: ten native scenarios covering unchanged
  Apply, Static, preview failure, Cancel, Apply, OK, invalid file, conflict,
  preview Stop and preview cancellation.
- `check_native_display_buttons.py`: ten existing Advanced Apply/OK, Keep/Revert,
  timeout, error, external-change and close scenarios using fake display drivers.

All use temporary homes, authenticated private displays and synthetic content.
No personal desktop, clipboard, audio or settings are changed by this packaging
verification. No second live activation was performed.

## Earlier component evidence and limits

Before this integration, the identical wallpaper implementation passed null-only
synthetic audio tests: 25% volume produced approximately one quarter of the
full-volume waveform; 0%, mute, pause and Off were silent. It was also built with
the standard builder, staged with exact pre-upgrade managed-file backups, and
activated through a guarded desktop-only refresh. Current animation and native
preference bytes were preserved; the live Background dialog was inspected and
cancelled without applying or previewing. Those are earlier component checks,
not new deployment or login tests for this combined commit.

The screenshot release has additional component-level checks described in
[its verification notes](docs/screenshot-verification.md). Other inherited areas,
including Start search, folder cascades, portable preferences, panel grouping and
installer recovery, retain their prior evidence; this integration does not claim
new live or hardware acceptance for them.

Normal-login acceptance of this exact combined build, clean installation,
physical mixed-DPI/multi-monitor behavior, real audio-device routing, display
hardware recovery, Wayland and long-session performance remain unverified.
Blur and Pixelate obscure appearance; use solid Redact to cover sensitive output.
The editor retains the frozen original until it closes.

## Build, packaging and rollback

Read README.md and component READMEs. Native builds require the documented
existing development dependencies and fetch pinned upstream sources. Build the
paired desktop with `python wallpaper/build.py --work /permanent/empty/directory
--display-controls`; keep both executables, display helper and build record
together. Preview selected installer modules before applying. Building source
never enables wallpaper, audio, display changes or desktop integration.

Ordinary installer rollback restores the first-install baseline. The earlier
controlled upgrade also used a private exact pre-upgrade backup/undo, which is
not distributed with source and does not replace the ordinary installer policy.
Content/mode conflicts are refused. General race-free or power-loss guarantees
are not claimed.

Original DoroShell source is GPL-2.0-or-later; all component notices are retained.
See LICENSING.md. No binaries, media, personal paths/configuration, real desktop
screenshots, private backups, toolchains or caches are included. SOURCE-MANIFEST.json
records source provenance and payload hashes. SHA256SUMS covers all source files
and the manifest, excluding itself. Verify with `sha256sum -c SHA256SUMS`.
