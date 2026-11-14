# Fake-host animated renderer probe

**Experimental graphics test only. Not a locker, saver registration, installation
module or security boundary.**

**Current acceptance result: BLOCKED.** The final overlay-before-launch check
reproduces a stacking incompatibility and intentionally exits nonzero with
`result: FAIL`. Earlier passing checkpoints below are historical; the expanded
probe is not an all-green integration test.

Implements the first isolated checkpoint from
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

## Initial checkpoint — 2026-11-14

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

## CPU follow-up — 2026-11-14

The high CPU cost reproduced after a two-second warm-up: 5.62 CPU seconds over
8.164 seconds, so startup alone did not explain it. A diagnostic run's mpv log
repeated `Assuming -nan FPS for display sync` in the X11 output. Its thread counters
put the work in the main/output/logging threads; the GIF demux thread accumulated
no measurable CPU ticks. Verbose logging itself adds cost, so that diagnostic run
is excluded from the performance comparison.

The smallest effective change is `--display-fps-override=60` **only for this private
Xvfb fixture**. The installed mpv manual documents this as an override when detected
refresh is wrong. It is not a physical refresh measurement, display-setting change,
GIF frame-rate change, or recommendation to override a real monitor's refresh.
Default `--comparison fixture60` enables it; pass `--comparison baseline` to rerun
the original command. No decoder, media, scaling or synchronization-mode change
is retained. Both cases still use the exact generated eight-frame GIF.

Controlled alternatives, each with the full lifecycle/rejection checks passing:

| Variant | CPU seconds / sampled seconds | Transitions / distinct hashes | RSS kB | First pixels ms | SIGTERM / target-destroy ms |
| --- | --- | --- | --- | --- | --- |
| Original, longer sample | 5.62 / 8.164 | 80 / 8 | 84,916 | 94.7 | 7.2 / 25.3 |
| Single decoder thread | 5.54 / 8.173 | 80 / 8 | 85,172 | 92.9 | 7.3 / 25.2 |
| `video-sync=desync` | 5.03 / 8.385 | 81 / 8 | 84,968 | 94.3 | 7.3 / 25.4 |
| Disable zimg scaling | 5.53 / 8.195 | 81 / 8 | 84,944 | 93.1 | 7.3 / 76.0 |
| Fixture refresh override | 0.07 / 8.195 | 81 / 8 | 84,880 | 93.2 | 15.4 / 25.4 |
| Final baseline repeat | 5.52 / 8.170 | 80 / 8 | 84,756 | 94.9 | 7.2 / 75.7 |
| Final fixed repeat | 0.08 / 8.178 | 81 / 8 | 84,616 | 98.1 | 15.3 / 75.9 |

Final repeat: decoder usage fell from approximately 67.6% to 1.0% of one CPU
(about 98.6% less), with effectively unchanged memory and observed animation
cadence. These are short synthetic measurements, not hardware power/latency claims.
The two-second warm-up occurs before 160 pixel samples at 50 ms intervals; CPU
counters cover that sample only, not startup. First-frame and teardown retain the
original measurement method. No verbose log was enabled in comparison runs.

The final baseline and fixed runs each passed **34 assertions**, including a new
8–12 observed-transitions/second check around the intended 10 fps. All original
rejection, hierarchy, focus/grab, resize, restart and cleanup checks remain intact.
All 263 repository tests and four probe unit tests passed. The latter checks that
the reproducible baseline and default command differ only by the fixture override.
There is no hard CPU assertion that could conflate host contention with correctness.

The evidence supports a fixture/mpv invalid-refresh interaction; it does not prove
an upstream root cause in source code or generalize to real X servers. GIF looping
and decoding are unchanged and inexpensive in the fixed run. This resolves the
observed fixture cost without broadening the experiment into a renderer framework.

## Host lifecycle and synthetic overlay checkpoint

The extended fixture unmaps/remaps the supplied rendering parent while the outer
fake host stays mapped. It checks descendant visibility, exact background pixels,
continued process life, new animated frames on remap and unchanged focus. It then
creates and raises a fixture-owned sibling above the render child, visibly labelled
**SYNTHETIC GRAPHICS OVERLAY / NOT AUTHENTICATION**. Ten 50 ms pixel samples check
stable overlay coverage, alongside hierarchy/stacking, focus and grab checks.

With that overlay still present, the fixture terminates its decoder. It requires
only the decoder child to disappear, the supplied parent to remain viewable and
the overlay pixels to remain unchanged. Removing the overlay must reveal exact
black pixels across the entire 360×200 parent, without clearing it in the test.
The existing restart, invalid backend/media and final process-reaping assertions
then run unchanged. Assertion-phase exceptions now record `result: FAIL` and the failure message
in the evidence JSON before propagating a nonzero exit.

The first extended run passed 59 assertions (including ten individual overlay
stability samples), with no forced cleanup. The measured remap-to-colored-pixels
interval was 94.0 ms; first frame 93.8 ms; SIGTERM exit 7.3 ms; target-destroy exit
25.2 ms. The unchanged two-second warm-up/eight-second sample measured 0.06 CPU
seconds over 8.175 seconds, 81 frame transitions/eight distinct hashes and
85,192 kB RSS. Private screenshot inspection confirmed the synthetic labels,
overlay coverage and black parent after decoder exit.

A second run also passed all 59 assertions with no forced cleanup: first frame
94.2 ms, remap 124.9 ms, SIGTERM 7.2 ms and target destruction 25.3 ms. It measured
0.08 CPU seconds over 8.174 seconds, 81 transitions/eight hashes and 84,536 kB RSS.
All four probe unit tests and 263 repository tests passed. No failed assertion
occurred in either extended run; snapshots and polling cannot exclude every
transient between observations.

This proves host graphics observations only. The overlay is created and raised
**after** the renderer; overlay ordering across a new renderer launch, real
password dialogs, focus routing under an actual host grab, asynchronous crash
races and real XScreenSaver coverage remain untested. The overlay is destroyed
before the existing restart test. The supplied parent is deliberately black and
owned by the fixture; this result does not prove how a real locker maintains its
covering windows. No locker process, authentication, registration, personal
session or clipboard is involved. The refresh override remains private-fixture
behavior, not a production default.

## Final stacking checkpoint — integration blocked

The fixture now creates and maps a clearly labelled host-owned overlay **before**
launching mpv, retains that same window through termination/restart, and never
raises or redraws it afterward. No mpv embedding options changed. Pixel snapshots
and child stacking both show the newly mapped renderer above the existing overlay
on **both launch and restart**. The final compatibility assertion fails visibly;
it has not been changed to accept the unwanted stacking.

| Complete run observation | Launch | Restart |
| --- | --- | --- |
| Overlay pixels preserved while renderer runs | No | No |
| Overlay remains highest child | No | No |
| Request to rendered pixels | 94.0 ms | 93.0 ms |
| SIGTERM to reaped exit | 15.3 ms | 7.2 ms |
| Focus preserved; no input grabs | Yes | Yes |
| Only decoder child removed; host and overlay remain mapped | Yes | Yes |
| Original overlay pixels restored after decoder exit | No | No |

The first run stopped at the post-exit pixel assertion. Its evidence is retained.
The diagnostic revision separates surviving windows from restored content so it
can finish the requested restart observation: **no repaint or restacking was
added**. The fixture does not service Expose events for that label, so lost text
on re-exposure is a fixture limitation, not proof that mpv destroyed the overlay.
The independent stacking order and covered-pixel observations establish the
launch/restart incompatibility regardless of that repaint limitation.

The complete run passed 69 preceding assertions, including all 59 prior checks
and ten new rendering/focus/grab/window-survival checks, then failed the final
stacking requirement. All seven owned decoders exited; no forced cleanup occurred.
The unchanged performance sample measured 0.06 CPU seconds over 8.173 seconds,
81 transitions/eight hashes and 84,680 kB RSS. Initial first pixels were 92.8 ms,
remap 94.4 ms and original target-destroy exit 75.9 ms. Measurement methods and
polling limits remain as described above. The four probe unit tests and all 263
repository tests passed; that does **not** override the native acceptance failure.

Synthetic screenshots before launch, during each launch, and after each exit,
plus `overlay_before_launch` observations in `results.json`, preserve the result.
No repeated attempt to force this scenario to pass was made; no host re-raise
comparison or compensating framework was implemented.

**Decision:** conclude this fake-host exploration without an installable adapter.
Unmodified mpv child embedding does not preserve an existing sibling overlay's
stacking in this fixture. Whether real XScreenSaver uses a conflicting hierarchy
or explicitly manages stacking is still unknown. Do not register this renderer or
infer an authentication vulnerability from the synthetic result. A future
integration decision needs authoritative review of the actual host hierarchy,
stacking and repaint ownership; any real-lock acceptance requires separate
explicit authorization at a safe point. Further incremental mocks are not a
substitute for that contract evidence.

## Limits and integration decision

The final overlay-before-launch assertion fails as documented above. Untested: actual XScreenSaver host
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
contract and whether its resource cost on the intended host is acceptable, before designing an adapter.
No install or registration is proposed by this checkpoint. Any later selection
requires an exact command/settings diff and rollback review. Real lock/unlock
remains separately authorized at a safe point; this result supplies no such
permission. No desktop refresh, live setting or security change was performed.
