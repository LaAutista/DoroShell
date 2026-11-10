# Optional animated desktop wallpaper candidate

This X11/Openbox module adds a video/GIF background to a separately built PCManFM-Qt. It paints in PCManFM's existing background layer, beneath the native icons. It does not cover icons with an overlay, disable them, or modify the system file-manager binary. The first private-desktop proof showed moving video and opened a native desktop folder by double-click.

The design was informed by [Smart Video Wallpaper Reborn](https://github.com/luisbocanegra/plasma-smart-video-wallpaper-reborn), which targets Plasma. This implementation keeps desktop painting in PCManFM and runs Qt Multimedia video decoding in a separate local helper process instead. The patch and renderer are GPL-2.0-or-later, matching the patched upstream code; see COPYING. No media is included.

## Build and prepare

Runtime: PCManFM-Qt/libfm-qt 2.4, Qt 6 Multimedia with its FFmpeg backend, KF6 WindowSystem, X11, Xext, XScreenSaver, Openbox and PySide6 for controls. Build requirements additionally include their development headers, Git, CMake, Ninja, C++ and lxqt-build-tools 2.4. The scripts do not install packages. The existing panel build's `deps` prefix can supply lxqt-build-tools through `CMAKE_PREFIX_PATH`.

```sh
python wallpaper/build.py --work "$HOME/.local/share/doroshell/wallpaper-2.4.0"
python setup.py wallpaper --wallpaper-binary "$HOME/.local/share/doroshell/wallpaper-2.4.0/build/pcmanfm/pcmanfm-qt"
# After reviewing the preview, stage the optional desktop for your next normal login:
python setup.py wallpaper --wallpaper-binary "$HOME/.local/share/doroshell/wallpaper-2.4.0/build/pcmanfm/pcmanfm-qt" --apply
```

Use a permanent empty build directory. Keep `pcmanfm-qt`, `doroshell-video-worker` and `doroshell-wallpaper-build.json` together. The builder records both executable hashes; staging checks both, and the launcher verifies the pair again before startup. Missing, non-executable or changed files select the stock desktop fallback. Legacy single-process build records remain supported for rollback. Staging backs up the user `lxqt-desktop.desktop` autostart override. If the candidate cannot start or exits with an error, its launcher falls back once to the system desktop. The existing running desktop is not stopped. The new desktop starts at a user-chosen normal login. Do not start a second PCManFM desktop in your personal session to test it.

Open **DoroShell animated wallpaper** from Start after staging, or run `python wallpaper/control.py` from source. Choose a local video/GIF, scaling (fit/crop/stretch), monitor, and enable it. Default playback loops and is muted. **Preview** opens a separate muted mpv window; it does not modify the desktop. mpv is optional for that preview only. Changes take effect within about a second when the new desktop is running.

Video repaint caps are 15/30/60 fps. Lower values reduce frame conversion/painting, but do not lower the source decoder's frame rate. Frames larger than the physical screen are downscaled before transport; decoding still uses the source resolution. Prefer a lower-resolution/frame-rate source on a low-power machine. GIF playback uses Qt's movie decoder at the GIF's frame rate. Each selected monitor has its own decoder, which costs more than one decoder across all monitors.

## Pause and recovery

Fullscreen applications pause playback on overlapping monitors when they are on the current workspace. Manual pause, logind LockedHint, the X screen saver and DPMS display-off state are independent reasons. Clearing one reason does not clear others. If logind cannot establish the caller's session lock state, playback stays paused. Polling adds up to roughly a second of delay; this is a resource-saving feature, not a lock or security boundary. Lockers that do not report either logind or X screen-saver state require separate compatibility testing.

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

Physical DPMS power-off, multiple physical monitors, normal login, clean installation and long-session performance remain unverified. No lock-screen animation or changes to locking/authentication are included. A separate XScreenSaver renderer is a possible future integration, not a tested capability of this candidate.

The controls distinguish **staged for next desktop startup** from an **active native renderer**. Active status requires a fresh report from the matching live process and display; closing the native desktop clears its report even if file-manager windows remain open. Staging preserves autostart metadata and the recognized existing Dolphin service startup hook without running it during setup. Animation remains disabled until explicitly enabled.

The private `tests/check_wallpaper_handoff_x11.py` check confirmed that `--desktop-off` preserves an existing file-manager window, but a candidate `--desktop` invocation still forwards to the existing stock PCManFM D-Bus owner, even with another profile. It cannot replace that renderer while preserving its owner process. Use the next normal desktop startup; no live handoff is performed.

## Decoder isolation acceptance (source candidate)

The standard source build now produces both executables. Authenticated private-X11 tests cover actual staged launch, repeat installation, stock fallback for a non-executable helper, exact autostart rollback while preserving media choices, clickable desktop icons, pause reasons, GIF/error/static restoration, stopped-helper timeout, repeated toggles, crash/retry, parent-death cleanup and desktop-off with a surviving file-manager window. Tests: `check_wallpaper_install_x11.py`, `check_wallpaper_lifecycle_x11.py`, `check_wallpaper_controls_x11.py`, `check_wallpaper_isolated_resources_x11.py`.

The earlier in-process optional archive and personal staged renderer are unchanged. This checkout is a newer, unpublished isolation candidate. Short Xvfb/llvmpipe measurements showed Off at about 70 MiB with no decoder process versus roughly 425 MiB retained previously. Playing CPU was similar, not faster; summed process RSS includes shared pages more than once. These are not hardware-acceleration or input-latency measurements. Pause intentionally retains decoder memory for resume; Off releases it. Physical/audio-device, normal-login, clean-system and long-session checks remain separate gates.

Private null-only audio acceptance also passed (`tests/check_wallpaper_audio_x11.py`): default mute, pause, remute and Off produced silent captured samples; unmute/resume produced the synthetic tone; Off removed the helper and audio stream. No physical audio device or user audio session was used. This does not test real-device routing or perceived latency. See [integration evidence](../docs/wallpaper-isolation-verification.md).
