# Wallpaper resource acceptance — 2026-11-10

The optional PCManFM 2.4.0 renderer was tested on authenticated private Xvfb/Openbox with a temporary home and private D-Bus session, with **no compositor**. The supplied local H.264 video was 1920×1080 at 60 fps; its bytes were unchanged. The test used Qt Multimedia 6.12.0 with the FFmpeg backend and system FFmpeg 9.0.2. Stock PCManFM 2.4.1 was the static baseline. This does not establish hardware acceleration, GPU power use, physical input latency or multi-monitor behavior.

Each state settled for two seconds, then ran for six seconds (about 6.01 s measured). CPU is process CPU, summed across threads, expressed as a percentage of one core; kernel-tick resolution limits idle comparisons. RSS includes shared libraries and retained allocator/backend memory, so it is not unique memory or a leak measurement. The states were sampled sequentially in one candidate process, after a separate stock-static process.

| State | CPU ms / sample | One-core CPU | RSS at end (MiB) | Threads | Desktop damage rectangles |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stock static desktop | 0 | 0.00% | 66.7 | 9 | 0 |
| Candidate disabled at startup | 0 | 0.00% | 69.9 | 9 | 0 |
| Video playing, 30 repaint-fps cap | 3830 | 63.78% | 592.4 | 72 | 120 |
| Fullscreen pause | 20 | 0.33% | 576.8 | 72 | 0 |
| Manual pause | 10 | 0.17% | 576.8 | 72 | 0 |
| Off after playback | 0 | 0.00% | 420.6 | 46 | 0 |
| Latched malformed-media error | 0 | 0.00% | 420.7 | 47 | 0 |
| Synthetic 50 fps GIF, video cap set to 15 | 140 | 2.33% | 420.7 | 43 | 293 |

## Defect and correction

Before the fix, disabled startup and Off after playback each produced 12 desktop damage events per six-second sample: the 500 ms status tick unconditionally requested a desktop repaint. The old disabled startup also loaded multimedia resources despite animation being off (about 250 MiB RSS in that run).

The renderer now restores static pixels once when the image is cleared, then leaves unchanged disabled/error states unpainted. Video player, sink and audio output are created only when video is enabled, and destroyed on Off or a switch to GIF. Disabled state skips lock/DPMS queries; the existing 500 ms configuration/status heartbeat remains for control response and liveness, so idle overhead is not literally zero. Error recovery still requires explicit retry/source change.

Frame and paint counters plus player state/position corroborated the XDamage observations. Disabled, fullscreen-paused, manually-paused and error samples had no advancing accepted frames, wallpaper paints or video position. The two paused states showed the actual QMediaPlayer PausedState. Paused decoders remain allocated for resume. Off removed the player/sink/audio objects, but RSS did not return to its initial value during the bounded sample; retained library/allocator resources and idle threads remain until later reclamation or process exit. No claim of complete memory release on Off is made.

## Defaults, rate limits and cleanup

Animation remains optional, disabled and muted by default. The 30 fps setting caps conversion/repaint submissions; it does not reduce source decoding or guarantee 30 displayed frames per second. The tested 60 fps source produced approximately 20 accepted frames/paints per second while consuming substantial CPU. Keep animation off for the lowest resource usage; lower-resolution/frame-rate media reduces the input workload.

The UI says **Maximum video repaint fps**. GIF playback follows its source cadence: the synthetic 20 ms GIF produced about 49 accepted frames/paints per second even with the video cap set to 15. The cap is not advertised as a GIF limit.

After private desktop-off, the renderer exited, its process/thread directory disappeared and its status file was removed. The owned mock-login helper and window manager were terminated and reaped; the private bus/X server were torn down by the harness. No personal process was stopped and no live desktop handoff was performed. The existing private native-icon, fullscreen/mock-lock/manual/screensaver pause, GIF/error and pixel-checked static-restoration regression also passed on the final build.

## Reproduce

```sh
python tests/check_wallpaper_resources_x11.py --run --xvfb /path/to/Xvfb \
  --binary /path/to/pcmanfm/pcmanfm-qt --media /path/to/local/video.mp4 \
  --output /tmp/doro-wallpaper-resources
```

The test requires the existing private-X11 dependencies plus Pillow for a synthetic GIF. It records individual state metrics in `measurements.json` and backend diagnostics in a private log; neither media nor logs are included in the source archive. Do not run other acceptance workloads concurrently when comparing resource measurements.

## Independent rerun on the staged binary

A separate run of the same private-X11 harness confirmed the state, repaint and cleanup assertions. Stock static used 66.5 MiB RSS versus 69.9 MiB disabled startup, both with zero CPU ticks and no desktop damage during their six-second samples. Playing the same 1080p60 input used 62.11% of one CPU core and 588.2 MiB RSS. Fullscreen/manual pause produced no wallpaper damage (0.50%/0.33% CPU), retaining the decoder. Off produced zero CPU ticks and no damage but retained 432.1 MiB RSS. Error state was idle; the synthetic GIF still followed its source cadence. These short samples corroborate, rather than extend, the original limits. For lowest overhead leave animation disabled; this is not an input-latency or long-session guarantee.
