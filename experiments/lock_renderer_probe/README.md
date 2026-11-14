# Fake-host animated renderer probe

**Experimental graphics test only. Not a locker, saver registration, installation
module or security boundary.** Implements the first isolated checkpoint from
[the design](../../docs/animated-lock-screen-design.md), without changing that
proposal's real-lock approval boundary.

The runner creates an authenticated private Xvfb, temporary HOME/private D-Bus and
a visibly labelled fake host. It generates eight GIF frames and supplies each
marked child target explicitly to mpv's X11 output. No real locker is started or
controlled. There is no enabled setting, autostart entry or installed adapter.
Running without the explicit `--run`/`--xvfb` arguments refuses operation.

Requirements already available on the test machine: Python, Pillow, python-Xlib,
Xvfb, xauth, dbus-run-session and mpv with X11 output. This experiment does not
install dependencies. From the repository root:

```sh
python -m unittest discover -s experiments/lock_renderer_probe -p 'test_*.py' -v
python experiments/lock_renderer_probe/probe.py --run \
  --xvfb /absolute/path/to/Xvfb --mpv /absolute/path/to/mpv \
  --evidence /absolute/path/outside/the/checkout
```

The internal worker guard rejects ordinary display environments. This guard and
the marker are accident prevention, not authentication: callers could forge their
own environment or X11 properties. Do not invoke the worker manually or supply a
personal display. Only synthetic local GIFs up to 1 MiB are accepted. Header and
path validation are not a decoder sandbox or protection against hostile media.
The fixture reads pixels only from its private server and never reads clipboard
contents. The 24-bit Xvfb image conversion is fixture-specific.

## Verified checkpoint — 2026-11-14

Two isolated runs passed; the second strengthened restart verification to require
a new child and fresh pixels, and checked that unsupported output leaves no mapped
fallback window. The final run passed 33 assertions:

- Reject zero/root/stale/unmarked targets, missing/unreadable/relative media,
  URL/file URI, a disguised playlist, an escaping symlink and absent decoder.
- Render changing pixels below the supplied child, resize, render on two synthetic
  targets, stop, destroy a target and restart. A shell-like filename remains one
  argument and executes no command.
- Preserve input focus, hold no keyboard/pointer grab, create no unrelated mapped
  output window, reject corrupt media/unsupported output, retain the fake host and
  fixture settings, and reap all owned decoders. One extra unmapped or input-only
  root child was observed; this is not a claim of zero auxiliary X11 windows.

The final run used mpv 0.41.0-dirty, software X11 output, an 800×600×24 Xvfb,
160×90 generated frames at a nominal 10 fps and an initial 320×180 target:

| Measurement | Observation |
| --- | --- |
| Spawn request to first colored pixels | 96.8 ms |
| Sampling interval / duration | 50 ms / 1.532 s |
| Changed adjacent samples / distinct pixel hashes | 14 / 8 |
| Decoder CPU during sample | 0.99 CPU seconds |
| Decoder resident memory at end of sample | 84,528 kB |
| SIGTERM to reaped exit | 7.2 ms |
| Target destruction to observed natural exit | 25.4 ms |

First-frame/destruction checks poll every 25 ms; timings include scheduling and
pixel inspection, not physical display latency. CPU is the decoder's `/proc`
user+system tick difference; RSS is a single `/proc` sample. This short synthetic
run is not a performance budget: roughly 65% of one CPU during sampling is too
expensive to assume suitable for idle decoration without further investigation.
No hardware acceleration or power measurements were made. SIGTERM exits were
signal -15, target destruction exited 0, and decoder failures exited 2.

The three probe unit tests and all 263 existing repository unit tests passed.
Synthetic screenshot inspection confirmed both children beneath the explicit
“NOT A LOCK SCREEN” label. Logs, screenshot and generated media are private test
artifacts and are not source files.

## Limits and integration decision

No failed assertion remains in the final run. Untested: actual XScreenSaver host
contract/coverage, authentication, unlock, suspend, DPMS, real monitors, Wayland,
other mpv builds, hostile media, long-running resource use and actual lock safety.
The test only checks selected fixture settings; it is not a syscall audit proving
absence of every possible write. It does not establish a production resource cap.
A transient output window between observations is not ruled out by snapshot tests.

This is a separate topic-branch experiment, limited to this directory. Shared
source inventories and installer/module files deliberately remain unchanged for
the concurrent release owner. Integration must refresh and validate source
inventories/archive metadata; this topic is not a release-ready source archive.

Next decision: review whether mpv child embedding satisfies the real host's
contract and whether its resource cost is acceptable, before designing an adapter.
No install or registration is proposed by this checkpoint. Any later selection
requires an exact command/settings diff and rollback review. Real lock/unlock
remains separately authorized at a safe point; this result supplies no such
permission. No desktop refresh, live setting or security change was performed.
