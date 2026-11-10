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

A clean CachyOS installation, normal user login, physical multi-monitor/mixed-DPI and longer-running performance acceptance remain open. The implementation was not activated in the personal session during this work.

Setup explicitly rejects custom `XDG_CONFIG_HOME`; standard `~/.config` is required. Oversized source configurations are rejected before parsing. Surface rendering errors restore the opaque theme.

## Rounded-edge smoothing without a compositor

The optional Start backdrop now blends a two-physical-pixel **inner** border against cached static-wallpaper samples, with an antialiased glass contour inset by one physical pixel. Its X11 bounding/input mask is unchanged. This addresses the clipped staircase on the outer frame corners; it does not alter the portrait crop or its frame.

The extra decode runs in the existing asynchronous worker. Only eight corner/edge tiles remain afterward, capped at 256 KiB (20,784 bytes at 100% and 31,376 bytes for the screen-fitted 150% test). There is no periodic capture, decoder or repaint timer. The temporary raw source/screen are capped at 9 megapixels; null Qt decodes, unsupported geometry, and fit/crop modes keep the previous edge rendering. Qt orientation and alpha/background composition are handled for supported stretch input.

Regression tests cover bounds, alpha, JPEG rotation and tile retention. Private X11 checks at 100% and screen-fitted 150% verify actual smoothing, movement refresh, exactly unchanged masks, disabled fallback and zero idle edge paints. Like wallpaper glass itself, this cannot provide correct fractional transparency over another application or animated wallpaper. It is a static-wallpaper visual approximation, not a compositor.
