# Wallpaper glass without a compositor

This optional effect gives Start and the glass-capable native taskbar a blurred, tinted wallpaper backdrop with highlights. X11 still sees opaque windows. It **does not show other application windows through the menu/taskbar** and does not introduce a compositor, global rendering/vsync changes, screen-capture polling, a second video decoder or a background Python daemon.

## Enable and restore

Update the menu helpers, and build a new native panel with the current `panel/build.py` in an empty permanent directory. The builder applies both the core panel patch and `0002-wallpaper-glass.patch`. Prepare/select that binary through the existing [native-panel next-startup workflow](../README.md#core-installation-on-cachyos-lxqt). Older panel binaries remain opaque; changing this setting cannot add code to an already-running older binary. No logout, reboot or refresh is automatically performed.

In **DoroShell Settings → Apps & Themes → Wallpaper glass (no compositor)**, choose **Enable wallpaper glass**, then Preview/Apply. Or:

```sh
python setup.py menu wallpaper-glass --packages
python setup.py menu wallpaper-glass            # preview
python setup.py menu wallpaper-glass --apply
python setup.py wallpaper-glass --rollback
```

The package preview includes `python-pillow` for menu image processing. No package is installed by setup. The menu renderer imports Pillow only when glass is enabled; the ordinary opaque menu does not require it. The native panel uses Qt only.

The setting is opt-in and **Keep unchanged** remains the GUI default. It owns only `.config/doroshell/wallpaper-glass.json`; the existing module backup/conflict machinery preserves the previous bytes and mode and refuses conflicting external changes. Restore uses that baseline. Menu helper installation/rollback independently includes `wallpaper_glass.py` and its palette data. Neither operation edits the wallpaper, portrait, application associations, compositor settings or the desktop session. The menu sees a new opt-in on its next open. A running glass-capable panel observes it directly.

## Wallpaper and palette behavior

The effect reads the standard **PCManFM-Qt `lxqt` profile** and its `Desktop/Wallpaper`, `WallpaperMode`, `BgColor` and JPEG `TransformWallpaper` preference. It uses the coordinated Doro palette selected at startup, preserving the existing requirement that coordinated theme changes take effect on normal app/panel startup.

Supported wallpaper modes are **stretch, fit and zoom**. Per-screen custom wallpaper, slideshow, center, tile, missing/invalid/oversized files and unsupported settings fall back to the normal opaque theme. This is a conservative fallback rather than displaying a wrongly aligned backdrop. Physical mixed-DPI/multi-monitor behavior remains unverified.

Animated wallpaper is separate: glass deliberately samples the configured static wallpaper, not the video. GIF input is frozen at its first frame. It does not start another decoder or continuously copy moving frames. This limitation is intentional for the low-overhead first implementation, not a claim of live Aero transparency.

## Implementation and bounds

Source image decode/blur runs asynchronously, with one current request and a coalesced latest request per surface controller. Wallpaper/config notifications and geometry changes invalidate the cache; no recurring repaint/decode timer is used. Small low-resolution atlases are cropped into opaque tinted surfaces. The Start cache is bounded to eight entries and 16 MiB, and its 4K atlas is about 0.39 MiB. Sources are capped at 64 MiB and 40 megapixels; the native crop decoder also bounds expanded dimensions. Transparent input is composited on the configured background, and orientation follows the desktop preference.

Normal async operation and bounded image size do **not** guarantee bounded process-exit time on an unusually slow/blocking filesystem. No physical input-to-photon latency guarantee is made.

## Verification

- Full source suite: **117 tests passed** after integration, including new auto-resolution, opt-in, repeat installation, exact restore, conflict refusal, unsupported-layout fallback, alpha/background, installer and settings-default tests.
- Private installed-menu/native-panel check: actual packaged Start helpers, repeated installation, config enable/repeat, wallpaper atomic replacement, PCManFM source-path changes, one-worker reuse, unsupported-mode fallback/recovery and exact config/menu rollback passed. Personal preferences and session were not used.
- Additional private prototype checks: all four palettes, 100%/150% scale, moved menu, malformed/rotated/transparent images, missing/recreated source, late config creation, rapid changes and parent destruction during decode passed. Independent review issues were fixed before integration.
- Short native idle sample: zero CPU ticks and zero XDamage rectangles over three seconds. Installed Start sample without a blinking cursor: zero backdrop paints and about 0.13 ms process CPU over three seconds.
- Synthetic XTest-to-Qt search/paint medians were around 4 ms, with run-to-run tail variation. These are not physical desktop/input-latency results.

Run the private integration test with an available Xvfb and the newly built panel:

```sh
python tests/check_wallpaper_glass_x11.py --run --xvfb /path/to/Xvfb \
  --binary /path/to/runtime/bin/lxqt-panel --output /path/to/private-evidence
```

A clean CachyOS installation, normal user login, physical multi-monitor/mixed-DPI and longer-running performance acceptance remain open. That initial verification did not activate the personal session. Later deployment evidence is separated in the [current acceptance record](final-acceptance.md).

Setup explicitly rejects custom `XDG_CONFIG_HOME`; standard `~/.config` is required. Oversized source configurations are rejected before parsing. Surface rendering errors restore the opaque theme.

## Start first paint and frame edges

Start keeps its loaded menu and wallpaper atlas after hiding; repeated opens reuse them. The first opening (or a rebuild after preferences change) waits asynchronously for the first glass surface before showing, with a 250 ms readiness deadline after construction/positioning. If decoding fails or misses that deadline, the opening stays on its opaque theme; a late result does not flash into view. The event loop remains responsive. This deadline is not a bound on Python/application startup or process exit.

The raw-wallpaper border overlay has been removed: wallpaper samples are the wrong background when an application or animated video is behind Start, and produced colorful specks along straight edges. The blurred/tinted opaque surface now reaches the frame edge, with the backdrop radius matching the existing 15 px X11 mask. The portrait and input/bounding mask are unchanged. Binary X11 masks still have pixel steps at curved corners; this does not promise fractional transparency without a compositor.

Moving/resizing reuses the blurred atlas instead of decoding again. Screen-size and wallpaper-source changes still invalidate it. Regression coverage includes cold first paint, delayed/failed decode fallback, geometry reuse, alpha, JPEG orientation and frozen GIF input. The private X11 check exercises three fresh processes, straight-edge pixels over a dark window, unchanged masks, supported modes and zero idle backdrop paints at 100%/150%:

```sh
QT_SCALE_FACTOR=1 python tests/check_glass_edges_x11.py --run --xvfb /path/to/Xvfb --output /tmp/start-render-evidence
QT_SCALE_FACTOR=1.5 python tests/check_glass_edges_x11.py --run --xvfb /path/to/Xvfb --output /tmp/start-render-evidence
```

## Repeated-opening performance

The first request starts Start normally; there is no autostart change. Thereafter a lightweight Unix-socket request runs before Qt/GIO imports and toggles one resident menu. Hiding leaves no polling/repaint timer. Reopening resets launch protection, search and category, recomputes screen placement, reloads managed glass configuration, and retries a prior failed/timed-out decode.

Changed favorites, folder/crop preferences, primary action, theme or portrait metadata rebuild the window. Own pin, recent-program and primary-button writes preserve reuse; external edits rebuild. Existing GIO catalog notifications still refresh installed applications. Helper metadata is included in the IPC protocol so a later launch retires an obsolete resident after a code upgrade. Settings modals and active drags are not dismissed by toggle requests. Screenshot mode remains a separate one-shot process.

Private tests measured repeated first paint at 39–47 ms including Python/client startup, versus roughly 508 ms to map the previous fresh-process launcher. Cold opening remains approximately 0.5 seconds. These are private X11 timings, not physical click-to-photon measurements. The hidden resident used approximately 125 MiB RSS (46 MiB anonymous memory); a one-second idle sample recorded zero CPU ticks. This trades retained memory for rapid reopening.

Run the installed private lifecycle/timing check with synthetic settings:

```sh
python tests/check_start_latency_x11.py --run --xvfb /path/to/Xvfb --output /tmp/start-latency.json
```

An optional `--preferences /path/to/config` copies only relevant preferences into the temporary home and references their wallpaper/portrait read-only. It records timings/state, not screenshots or clipboard content. Tests cover first-frame glass, repeated reuse, settings/theme changes and resident retirement on a helper upgrade. Unit tests additionally cover startup cancellation, slow fallback/retry, successful fake launches, modal/drag preservation, portrait changes and the pre-import IPC path.

Rollback to a pre-resident version requires stopping the specific resident as well as restoring helpers. The old client sends no protocol bytes, so restoring its file alone can leave the resident alive. With Start naturally closed, verify the resident PID, UID, executable, exact launcher command and process start time against the deployment receipt; terminate only that verified process, then restore the backed-up files if their deployed hashes still match. Never use a broad process-name kill or restart the desktop session.
