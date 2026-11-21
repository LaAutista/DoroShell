# Optional animated desktop wallpaper candidate

This X11/Openbox module adds a video/GIF background to a separately built PCManFM-Qt. It paints in PCManFM's existing background layer, beneath the native icons. It does not cover icons with an overlay, disable them, or modify the system file-manager binary. The first private-desktop proof showed moving video and opened a native desktop folder by double-click.

The design was informed by [Smart Video Wallpaper Reborn](https://github.com/luisbocanegra/plasma-smart-video-wallpaper-reborn), which targets Plasma. This implementation keeps desktop painting in PCManFM and runs Qt Multimedia video decoding in a separate local helper process instead. The patch and renderer are GPL-2.0-or-later, matching the patched upstream code; see COPYING. No media is included.

## Build and prepare

Runtime: the installed PCManFM-Qt/libfm-qt (2.4 or newer), Qt 6 Multimedia with its FFmpeg backend, KF6 WindowSystem, X11, Xext, XScreenSaver, Openbox and PySide6 for controls. Build requirements additionally include their development headers, Git, CMake, Ninja and C++. The builder clones the PCManFM release matching `pcmanfm-qt --version` (or `--tag`) and builds the lxqt-build-tools release it needs into the build's private `deps`. The scripts do not install packages. Each build keeps a `recipe/` copy of these sources so it can [rebuild itself after a breaking system update](../docs/native-rebuild.md).

```sh
python wallpaper/build.py --work "$HOME/.local/share/doroshell/wallpaper-2.5.0"
python setup.py wallpaper --wallpaper-binary "$HOME/.local/share/doroshell/wallpaper-2.5.0/build/pcmanfm/pcmanfm-qt"
# After reviewing the preview, stage the optional desktop for your next normal login:
python setup.py wallpaper --wallpaper-binary "$HOME/.local/share/doroshell/wallpaper-2.5.0/build/pcmanfm/pcmanfm-qt" --apply
```

Use a permanent empty build directory. Keep `pcmanfm-qt`, `doroshell-video-worker` and `doroshell-wallpaper-build.json` together. The builder records both executable hashes; staging checks both, and the launcher verifies the pair again before startup. Missing, non-executable or changed files select the stock desktop fallback. Legacy single-process build records remain supported for rollback. Staging backs up the user `lxqt-desktop.desktop` autostart override. If the candidate cannot start or exits with an error, its launcher falls back once to the system desktop. The existing running desktop is not stopped. The new desktop starts at a user-chosen normal login. Do not start a second PCManFM desktop in your personal session to test it.

Open **DoroShell animated wallpaper** from Start after staging, or run `python wallpaper/control.py` from source. Choose a local video/GIF, scaling (fit/crop/stretch), monitor, and enable it. Default playback loops and is muted. **Preview** opens a separate muted mpv window; it does not modify the desktop. mpv is optional for that preview only. Changes take effect within about a second when the new desktop is running.

Video repaint caps are 15/30/60 fps. Lower values reduce frame conversion/painting, but do not lower the source decoder's frame rate. Frames larger than the physical screen are downscaled before transport; decoding still uses the source resolution. Prefer a lower-resolution/frame-rate source on a low-power machine. GIF playback uses Qt's movie decoder at the GIF's frame rate. Each selected monitor has its own decoder, which costs more than one decoder across all monitors.

## Pause and recovery

**Automatic fullscreen pause is enabled by default** (`pause_fullscreen=true`);
animation itself remains opt-in. Uncheck **Pause when fullscreen** in Desktop
Preferences → Background, or **Pause for fullscreen apps on this monitor** in the
standalone controller, then Apply to opt out. Both edit the same setting.

The renderer checks the window manager's reported fullscreen state on the current
workspace, including windows on all workspaces, and tests overlap with each selected
monitor. A fullscreen window on another workspace or a non-overlapping monitor does
not add that monitor's fullscreen pause reason. This is window-state/geometry
detection, not application-specific game detection; physical multi-monitor behavior
remains unverified.

Manual pause, logind LockedHint, the X screen saver and DPMS display-off state are
independent reasons. Exiting fullscreen or opting out removes only the fullscreen
reason; playback resumes only when no other reason remains. If logind cannot
establish the caller's session lock state, playback stays paused. The renderer
checks every 500 ms; response is normally within about a second, but event-loop or
helper delays can make it longer. This is not a hard deadline, a lock or security
boundary. Lockers that do not report either logind or X screen-saver state require
separate compatibility testing. Pause retains decoder resources for resume;
**Off** releases them.

Source: [renderer](dorowallpaper.cpp), [controller defaults/checkbox](control.py)
and [native checkbox](dorowallpapercontrols.h). The existing
[private-X11 harness](../tests/check_wallpaper_x11.py) exercises fullscreen,
mock-lock/manual pause composition and resume. Its recorded
[isolation acceptance](../docs/wallpaper-isolation-verification.md) and earlier
[resource sample](../docs/wallpaper-resource-verification.md) are historical
private tests, not a new live-session or hardware check.

**Off — restore static wallpaper now** terminates the video helper and releases its decoder/backend resources (a stopped helper is killed after one second), then restores PCManFM's existing static background; its wallpaper preferences were never changed. The equivalent is:

```sh
python wallpaper/control.py off
python wallpaper/control.py pause
python wallpaper/control.py resume
python wallpaper/control.py status
```

Decoder errors stop animation and restore the static background, without an automatic retry loop. Correct the media selection and explicitly choose Apply / retry. To restore the original desktop selection, turn animation off first, then run `python setup.py wallpaper --rollback`. The original desktop starts at the next normal login. Rollback refuses edited managed launcher/autostart files; personal media and wallpaper choices remain intact.

## Validation and limits

`tests/test_wallpaper.py` covers defaults/options and temporary-home staging, repeat installation, binary-integrity refusal, conflicting edits and exact autostart rollback. The native acceptance check runs entirely on an authenticated private X11 server and temporary home:

```sh
python tests/check_wallpaper_x11.py --run --xvfb /path/to/Xvfb \
  --binary /path/to/build/pcmanfm/pcmanfm-qt --media /path/to/local/video.mp4
```

It requires Python Xlib, PySide6, PyGObject and Pillow, Openbox, Xvfb and xauth. It tests moving video beneath a clickable native folder, real fullscreen state, a mock login lock service, overlapping pause reasons, private X screen-saver state, synthetic GIF frames, error handling and original-background restoration. It never locks a real session or uses the personal clipboard. The supplied test video is read unchanged and is not packaged.

Physical DPMS power-off, multiple physical monitors, normal login, clean installation and long-session performance remain unverified. No lock-screen animation or changes to locking/authentication are included. A separate XScreenSaver renderer is a possible future integration, not a tested capability of this candidate. See the [design and isolated acceptance gate](../docs/animated-lock-screen-design.md); desktop animation does not establish lock-screen support.

The controls distinguish **staged for next desktop startup** from an **active native renderer**. Active status requires a fresh report from the matching live process and display; closing the native desktop clears its report even if file-manager windows remain open. Staging preserves autostart metadata and the recognized existing Dolphin service startup hook without running it during setup. Animation remains disabled until explicitly enabled.

The private `tests/check_wallpaper_handoff_x11.py` check confirmed that `--desktop-off` preserves an existing file-manager window, but a candidate `--desktop` invocation still forwards to the existing stock PCManFM D-Bus owner, even with another profile. It cannot replace that renderer while preserving its owner process. Use the next normal desktop startup; no live handoff is performed.

## Decoder isolation acceptance (published source)

The standard source build now produces both executables. Authenticated private-X11 tests cover actual staged launch, repeat installation, stock fallback for a non-executable helper, exact autostart rollback while preserving media choices, clickable desktop icons, pause reasons, GIF/error/static restoration, stopped-helper timeout, repeated toggles, crash/retry, parent-death cleanup and desktop-off with a surviving file-manager window. Tests: `check_wallpaper_install_x11.py`, `check_wallpaper_lifecycle_x11.py`, `check_wallpaper_controls_x11.py`, `check_wallpaper_isolated_resources_x11.py`.

The November 10 isolation acceptance was recorded before publication, without
replacing the then-existing optional archive or personal staged renderer. The
isolated renderer and worker are now in published source history (`fad281f`), with
native Background controls added in `a0f82f9`; both precede the coordinator-verified
published checkpoint `28bfcd8`. Source publication does not establish which build
is currently running. The controlled deployment below is a separate historical
observation, not a fresh runtime check.

Short Xvfb/llvmpipe measurements showed Off at about 70 MiB with no decoder process versus roughly 425 MiB retained previously. Playing CPU was similar, not faster; summed process RSS includes shared pages more than once. These are not hardware-acceleration or input-latency measurements. Pause intentionally retains decoder memory for resume; Off releases it. Physical/audio-device, normal-login, clean-system and long-session checks remain separate gates.

Private null-only audio acceptance also passed (`tests/check_wallpaper_audio_x11.py`): default mute, pause, remute and Off produced silent captured samples; unmute/resume produced the synthetic tone; Off removed the helper and audio stream. No physical audio device or user audio session was used. This does not test real-device routing or perceived latency. See [integration evidence](../docs/wallpaper-isolation-verification.md).

## Native Background preferences candidate

New builds include Type (Static/Animated), local media Browse, fullscreen
pause, mute, repaint FPS limit and volume directly in **Desktop Preferences →
Background**. The widgets inherit the desktop's Qt palette and style. The approved layout keeps
static color/image/EXIF/per-monitor controls above the Animated Wallpaper group; the
page scrolls on smaller displays. Advanced display controls are unchanged.
Build with `--display-controls` to retain the verified Advanced integration.

**Preview** requires optional mpv, opens only on a deliberate
click, disables audio, and never writes settings or changes desktop playback.
Stop preview, Cancel, Apply and OK terminate that preview. Invalid media or a
failed player leaves the prior desktop settings intact. Preview displays the
media only; it does not simulate monitor layout or desktop fit.

Apply saves animation settings and leaves Preferences open. OK saves and closes.
Cancel discards only unapplied edits, retaining any earlier Apply. Selecting Static
and applying disables animation, revealing the native static background again.
Manual pause, fit and monitor selection from the existing controller are preserved.
The approved mockup omits a separate fit row. Volume uses a horizontal slider,
disabled while muted; Stop is enabled only while a preview process exists.
Example media names and settings from the mockup are never installed.
Volume is 0–100%; existing configurations default to 100% volume **with mute still
on by default**. Repaint limits do not change decoder frame rate.

The first edit backs up existing `wallpaper.json` bytes beside it as
`wallpaper.json.before-native-prefs` (owner-only). Writes are atomic; a changed,
unreadable or symlinked current file is refused. Reopen Preferences after an
external edit. The installer still uses its existing verified build records and
rollback. No personal deployment or autostart change is performed by building.

Private candidate validation: 216 unit tests; actual native Apply, OK, Cancel,
Cancel-after-Apply, unchanged Apply, Static, invalid file and conflicting-edit
checks; real silent mpv preview, Stop, Cancel and failure; all ten existing native
Advanced button scenarios with fake drivers. Null-only audio captured 25% volume
at approximately one quarter of the full-volume waveform, zero volume as silence,
and restored volume, mute, pause and Off correctly. Run:

```sh
python -m unittest discover -s tests -v
python tests/check_native_wallpaper_buttons.py --run --xvfb /path/to/Xvfb --binary /path/to/private/pcmanfm-qt
python tests/check_native_display_buttons.py --run --xvfb /path/to/Xvfb --binary /path/to/private/pcmanfm-qt
python tests/check_wallpaper_audio_x11.py --run --xvfb /path/to/Xvfb --binary /path/to/private/pcmanfm-qt
```

These use temporary homes, authenticated private X11 and generated media. Native
Preferences testing does not imply personal-session, normal-login, physical audio,
hardware-decoder, multiple-monitor or clean-install acceptance. Earlier
login verification applies to the prior renderer, not this new preferences build.


### Controlled deployment follow-up

The approved layout was subsequently built through the standard builder with
`--display-controls` into a new permanent directory. The display helper and native
display controls matched the published version. A temporary-home check verified
exact pre-upgrade staging undo and refusal of conflicting edits; this is separate
from the installer's first-install rollback.

An idle-session, desktop-only graceful refresh then activated the paired build.
The existing animation resumed muted, and wallpaper/native preference bytes were
unchanged. The live Background dialog was inspected without Apply, OK or Preview
and dismissed through its Cancel/reject path. Previous binaries were retained.
This confirms that controlled refresh, not a new login or clean installation.
