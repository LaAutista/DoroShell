# Acceptance matrix — 2026-11-10

DoroShell is an LXQt toolkit. The published core candidate and this local optional source candidate are separate artifacts; the optional archive is not published. The earlier optional archive passes 102 tests. The newer decoder-isolation/source candidate passes 111 tests, including configurable primary session controls.

| Component | Implemented / development deployment | Evidence and limits |
| --- | --- | --- |
| Start | Active: labeled pins, separate recent view, bottom programs/search, portrait/folders/settings, centered shutdown arrow, application drag export | Automated tests and private real-X11 navigation/reorder/export checks; power actions mocked |
| Taskbar | Active: grouped tasks and pins, Start drop-to-pin, hidden-icon chevron, dark popup, clock/date/calendar, Show Desktop | Real private taskbar/drop/context checks; all four palette contrast checks; guarded live panel refresh preserved clients/settings |
| Desktop shortcuts | Start drops copy application launchers through PCManFM | Real pinned/searched drops, special filenames, Copy here confirmation, cancellation and one-shot launcher exit; native trust settings unchanged |
| Snapping | Core implementation and installed helper | Existing private Openbox checks; physical multi-monitor/long-session acceptance pending |
| Screenshots | Desktop/window/area capture, clipboard safety, annotation and optional native importer | Existing private pixel checks at 100%/150%, cancellation and import checks; no new live capture claim |
| Setup / restore | Explicit modules, retained original backups, conflict refusal, repeat installation | Temporary-home automated install/repeat/rollback checks; guarded development upgrades; no clean CachyOS or normal-login acceptance |
| Appearance | Four optional palettes, direct portrait choice | Existing private rendering/readability tests; no compositor installed or activated; neutral SVG ships by default |
| Wallpaper | Optional, disabled/muted; corrected renderer staged, older renderer currently active but off | Private native-icon/pause/error/static-restore and resource checks; real login, physical DPMS, broader lockers, physical mixed-DPI and long sessions unverified |

## Installation and recovery

Follow [optional installation and restore](optional-installation.md) for the menu and panel, and the [wallpaper build instructions](../wallpaper/README.md) for its separate native renderer. Keep versioned native runtime directories: their resources are tied to those prefixes. Installing helpers alone does not select a palette or enable animation.

The current development panel is in `$HOME/.local/share/doroshell/panel-drag-contrast-2.4.1/runtime`; its prepared profile is `$HOME/.local/state/doroshell/core-panel-profile`. The staged decoder-isolation wallpaper executable is in `$HOME/.local/share/doroshell/wallpaper-isolated-2.4.0/build/pcmanfm`, beside its integrity-checked helper. The previous idle renderer remains available for rollback. The previous native runtimes remain available. Private `optional-install-before-*`, `before-drag-contrast-activation-*` and `before-wallpaper-idle-fix-*` checkpoints retain upgrade recovery data and must not be published.

`python setup.py native-panel --rollback --keep-panel-edits` restores the original panel selection for its next normal startup. `python setup.py wallpaper --rollback` restores the original desktop selection; Wallpaper controls → Off independently disables animation. Restore panel/legacy integration before `python setup.py menu --rollback`. Original baseline manifests remain under `.local/state/doroshell` and `.local/state/lxqt-comfort`; they are not replaced with upgrade checkpoints.

## Remaining acceptance

A normal user-chosen login and clean CachyOS install/upgrade/rollback remain pending. No disposable clean system was available. No logout, power action, compositor or live desktop renderer handoff was used to claim those checks. The [clean-system checklist](../README.md#clean-cachyos-lxqt-acceptance-checklist) remains the release gate for broader deployment.

Wallpaper's video setting caps repaint submissions, not decoding or GIF cadence. Playing the tested 1080p60 video uses substantial CPU. The earlier in-process renderer retained memory after Off; the staged isolated renderer releases the helper and returns to roughly 70 MiB. Default NVDEC decoding was verified separately from Xvfb software rendering. See [measured resource limits](wallpaper-resource-verification.md).

## Independent final review and symbolic-icon correction

A second private-X11 pass verified real Print with Start open (frozen menu pixels, confirmation, Escape and unchanged clipboard), exact Writer/Draw clipboard paste, and overlapping/clipped window capture at 100% and 150%. Native ScreenGrab imported and copied every annotated pixel. These checks used temporary homes and synthetic content, not the personal clipboard.

All four current menu/panel palettes rendered without a compositor and remained opaque when the desktop pixels changed. Visual inspection found light-theme symbolic icons disappearing on dark controls. Start now colors only its search, navigation and session symbols using each control's foreground; application icons and artwork are unchanged. A regression checks every palette, including Back and the session submenu. The full suite passes 102 tests. This does not measure physical input latency.

The local End Result concept was compared with actual renders. Its two-column proportions, Pinned header, elevated portrait, bottom navigation/search, split shutdown, separators and coordinated pink taskbar are represented. The concept's transparent Aero glass is intentionally not reproduced: the user requires compositor-free LXQt. Personal artwork is configurable; the distribution keeps neutral artwork. The illustrated advanced-search and portable export/import panels remain deferred as recorded in the roadmap; the current module backup/rollback is not portable backup parity. No exact visual or full Spectacle/Open-Shell parity is claimed.

The independent screenshot editing check also passed actual crop resize/move, redaction, Undo/Redo, real Qt save-dialog Cancel/Save, exact PNG pixels and full-desktop Enter. A repeated wallpaper resource check corroborated zero repainting when disabled/paused and substantial CPU/memory use during video playback. Current four-palette tests recorded about 3.5–4.8 ms menu process CPU per 5.25-second idle sample, zero panel CPU ticks, and roughly 4.2–4.3 ms median synthetic key-to-paint completion. These are bounded private-X11 observations, not physical input latency, a comparison against an older build, or long-session acceptance; paired variants used identical current styles.

## Next implemented interaction: primary session button

The newer source candidate adds Menu options → Primary session button: Shut down, Restart, Log out, Sleep, Hibernate or Lock screen. Shut down remains the default. The other five actions remain available in the split submenu. Choosing a preference never executes it; existing confirmation remains Cancel-default for every action except the established immediate Lock screen behavior. Missing LXQt actions are disabled. The choice persists independently of pins/recent history, with atomic replacement, backups and refusal of detected prior external edits, symlinks or corrupt preferences. As with the existing preference writer, this is optimistic conflict detection, not a cross-process concurrent-writer lock.

Three new automated regressions and a private-X11 UI test passed. The latter selected Restart by keyboard, reopened the menu, opened the actual confirmation and canceled with Escape; all session dispatch was mocked and zero actions launched. This feature is source-only pending deployment, not a claim that the personal menu changed. Advanced search, cascades and portable export/import remain unimplemented.

## Portrait crop preview

Clicking the Start portrait or choosing one in the folder editor now opens a non-destructive crop preview. Drag or arrow keys reposition; a slider or mouse wheel zooms from 100% to 400%; Reset restores centered framing. Apply saves normalized crop metadata with the original file path, never rewrites the picture. The existing portrait and preferences remain unchanged on Escape/Cancel, including canceling the outer folder editor. Cropping uses a square preview matching the portrait content area. Large images are decoded at a bounded preview size; EXIF auto-orientation is enabled. Missing/unreadable images retain the existing fallback behavior.

111 automated tests pass, including malformed/extreme metadata, framing/clamping, original preservation, stored crop pixels, retained folder settings and canceled nested edits. Private X11 verified actual dialog drag, keyboard zoom, Apply, reopened pixel result and Escape cancellation on a synthetic image. Independent review found and corrected a huge-number validation edge. Both installer copies include the new sibling module. No personal portrait or live menu was changed during this acceptance.

## Compositor-free wallpaper-glass source candidate

The newer glass source candidate passes 116 automated tests and the installed Start/native-panel private enable/change/repeat/rollback check. It adds a Settings opt-in with exact backup/restore and automatic standard PCManFM wallpaper resolution. No personal-session activation occurred. This is frozen wallpaper sampling, not transparency through application windows; unsupported wallpaper layouts fall back to opaque. See [wallpaper-glass verification and limits](wallpaper-glass.md).
