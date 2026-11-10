# Opaque theme verification — 2026-11-10

An experimental styling change added static gradient stops and top/bottom bevel colors to the existing Start/taskbar styles. It added no runtime service, timer, compositor, animation, blur or background capture. The experiment was **omitted from the final source candidate**, which retains the baseline styles. This is an opaque Aero-inspired finish, not Windows 7 rendering parity. The four actual menu/panel renders were inspected alongside the concept reference for palette and layout; the fixture uses the neutral portrait and no personal artwork.

## Measurement method and limits

`tests/check_opaque_themes_x11.py` runs an authenticated Xvfb/Openbox desktop with temporary HOME/config/runtime and a private session bus. It asserts that the X11 compositor selection is unowned before and after the test. It renders the real Start menu and existing native theme-capable panel. Changing the root background from red to blue leaves sampled menu-frame and panel-background pixels identical, establishing opacity at those sample locations.

Baseline and experimental styles use identical code, applications and native panel binary. One run interleaves baseline/final for each palette; the repeated run reverses that order. Each condition measures approximately five seconds of idle time (actual elapsed time is recorded), process CPU and Qt paint events. Native panel XDamage rectangles are also counted in the reverse run; these are rendering damage notifications, not a one-to-one count of Qt paint events. The clock fixture contains no personal notification apps. Panel CPU is quantized to kernel clock ticks; zero recorded ticks does not mean zero cost.

Each condition sends 50 XTest search-key events and records completion after Qt handles the changed search text and a paint event. Combined distributions contain 100 samples per palette/condition. This includes X server/Qt scheduling and the harness's 1 ms polling interval. It is **not physical input-to-photon latency**, a game benchmark, or a measurement of the full personal desktop. Background system load is uncontrolled; small timing differences are not evidence of an effect or its absence. Existing search behavior and caret blinking remain present.

## Reproduction

Before changing the styles, save their generated source data from the trusted baseline checkout:

```sh
python - <<'PY'
import json
from pathlib import Path
from themes import PALETTES, theme_files
Path('/tmp/doro-theme-baseline.json').write_text(json.dumps({name: theme_files(p) for name, p in PALETTES.items()}))
PY
```

For a future style experiment, from the changed checkout run the following twice, using separate output directories and adding `--reverse` for the second run. Do not run other acceptance workloads concurrently with the measurement:

```sh
python tests/check_opaque_themes_x11.py --run --xvfb /path/to/Xvfb \
  --binary /path/to/theme-capable/lxqt-panel \
  --baseline-styles /tmp/doro-theme-baseline.json --output /tmp/doro-opaque-run
```

Dependencies are the existing private-X11 test dependencies: Xvfb, xauth, Openbox, Python Xlib/PySide6 and the native panel build. No compositor or package installation is part of this check. `measurements.json` retains individual search timings, CPU, paint/damage counts and opacity samples; PNGs are private test artifacts and are not distributed.

## Recorded results

Two completed paired runs (baseline/final, then final/baseline) produced the results below. An intermediate exploratory repeat overlapped the unit suite and is excluded from this timing summary. Each table cell shows baseline → experiment (the harness labels the latter `final`). These are historical experiment results, not a claim that the experimental styles shipped.

| Palette | Search median (ms) | Search p95 (ms) | Idle menu CPU (ms, two windows total) | Menu paint events (two windows) | Panel damage rectangles (reverse run) |
| --- | --- | --- | --- | --- | --- |
| Windows | 4.22 → 4.17 | 5.02 → 4.50 | 10.95 → 10.95 | 80 → 76 | 0 → 0 |
| Polar | 4.20 → 4.21 | 4.42 → 4.41 | 14.58 → 11.22 | 80 → 80 | 1 → 0 |
| Heretic | 4.22 → 4.31 | 4.49 → 5.52 | 10.77 → 13.71 | 80 → 80 | 0 → 0 |
| Spring | 4.25 → 4.20 | 4.61 → 4.53 | 13.01 → 12.12 | 80 → 80 | 0 → 0 |

Individual idle windows lasted 4.75–5.25 seconds. Panel CPU recorded 0–0 ms per window at kernel-tick resolution. The menu retains its existing caret repainting; the experiment added no timer. No additional repaint activity was observed in these paired fixtures. These results do not guarantee zero overhead or unchanged physical input latency on every machine.

All 99 automated tests passed with the experimental styles, including existing palette contrast and temporary-home theme switch/repeat/conflict/rollback checks. No personal theme, compositor configuration, installed application or session was changed.

## Decision

Heretic's measured p95 rose from 4.49 to 5.52 ms, while the other presets were slightly lower. These short synthetic measurements do not establish causation or physical input latency. Given the priority on responsiveness and the limited visual difference, the additional highlights were omitted rather than presented as a latency-neutral improvement. The final source retains the exact baseline `themes.py`; no live theme or session change was made. The measurement harness remains available for future comparisons.
