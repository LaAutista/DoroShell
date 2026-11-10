# Decoder-isolation integration acceptance

2026-11-10. Unpublished source candidate; no personal desktop, autostart or existing optional archive replacement.

## Built and verified

The standard `wallpaper/build.py` cloned the pinned upstream tag, applied the integrated patch and built both PCManFM and `doroshell-video-worker`. A format-2 build record hashes both files. Staging and startup reject a missing, changed or non-executable member; startup falls back to stock PCManFM. Legacy format-1 single-process builds remain usable. Both files must stay beside each other in the permanent build directory.

103 automated tests pass. Temporary-home tests cover both-file validation, repeat staging, personal-edit refusal and exact rollback. An actual authenticated private-X11 installation test launched the verified paired build, forced a helper executable-permission failure, observed stock fallback and restored the original autostart byte-for-byte without removing wallpaper choices.

Private native tests pass for moving video beneath clickable native icons; fit/crop/stretch; 15/30/60 maximum repaint caps; fullscreen/mock-lock/manual/screensaver pause composition and resume; GIF; error latch; original static-background restoration. Lifecycle tests cover stopped-helper timeout, repeated On/Off, decoder crash/retry, media changes while paused, desktop-off preserving a file-manager window, and SIGKILL parent cleanup even with a stopped helper.

The transport uses bounded anonymous Linux memfd mappings, not named shared-memory objects. Helpers have parent-death cleanup; Off asynchronously terminates then kills an unresponsive helper after one second. Frame rows are copied without source padding. The desktop never waits on a decoder mutex. Pause intentionally retains memory for resume.

## Scope limits

All runtime checks above use disposable Xvfb/private D-Bus and temporary homes. Xvfb uses llvmpipe for rendering. The initial resource tests did not identify the video decoder; the follow-up below confirms hardware decoding, not physical input latency or an end-to-end GPU rendering benchmark. A source repaint cap is a maximum, not a target frame rate. Each selected monitor still has its own decoder. Physical multi-monitor/mixed-DPI, normal-login, clean-system, real locker/DPMS and long-session acceptance remain open. No compositor, logout, reboot or personal-session handoff was used.

## Audio without disturbing the user

`check_wallpaper_audio_x11.py` passed against the standard build with a generated AAC tone and an isolated null-only PipeWire server. It loads no hardware or session-manager modules and uses explicit private links, so no audible output was played. Captured RMS was exactly zero for default mute, pause, remute and Off; unmute/resume measured about 0.062. Off removed both the audio stream and decoder child. Real-device routing and perceived audio latency remain untested.

## Final standard-build resource sample

Authenticated Xvfb/llvmpipe, 1920×1080 60 fps H.264 source, 30 maximum repaint fps, 2-second settling and 6-second sampling per state:

- Stock static desktop: 66.7 MiB RSS.
- Isolated renderer disabled before playback: 70.1 MiB RSS, zero sampled CPU ticks/repaints.
- Playing: 654.0 MiB summed desktop/helper RSS, 64.9% of one CPU core, about 20 accepted frames/s.
- Off after playback: 70.4 MiB RSS, zero sampled CPU ticks/repaints, no helper.

Earlier in-process samples retained roughly 425 MiB after Off, with about 62% of one core while playing. This fixes retained Off memory, not playback CPU or physical input latency. Summed RSS double-counts shared pages; short samples and software rendering do not establish hardware performance. Final resource test passed with synchronized XDamage teardown; an earlier harness-only teardown race was corrected.

## Independent source review

A separate read-only review found no additional material Linux/X11 blocker after checking lifecycle, bounded frame transport, padded row copying and startup integrity fallback. Six wallpaper unit tests passed in that review. The requested padded-RGB32 regression now lives at `tests/check_video_transport.cpp` and passed:

```sh
c++ -std=c++17 tests/check_video_transport.cpp $(pkg-config --cflags --libs Qt6Gui) -o /tmp/doro-transport-test
/tmp/doro-transport-test
```

This review did not independently repeat physical-display or long-session acceptance.

## Physical decoder diagnosis without personal desktop activation

A bounded private-Xvfb test on the installed RTX 5090 / 620.70.06 driver verified that Qt's **default decoder path selects CUDA/NVDEC**, despite software-rendered Xvfb graphics. With diagnostics routed to a private stderr log, Qt reported `Selected format cuda for hw cuda`; FFmpeg reported `Format cuda requires hwaccel h264_nvdec initialisation`, supported NVDEC capabilities and `pix_fmt: cuda`. Moving frames were observed and Off reclaimed the helper. This distinguishes GPU video decoding from frame transfer, color conversion and desktop painting. It does not establish an entirely GPU-resident rendering path.

`nvidia-smi pmon` associated the helper with a CUDA context, but returned `-` for per-process decoder utilization. Therefore no NVDEC utilization percentage is reported. The logged sample used roughly 63.6% of one CPU core; diagnostic logging and short samples limit comparisons. No renderer/backend/vsync settings were changed. Physical display latency and end-to-end hardware rendering remain unmeasured.

`tests/check_wallpaper_decode_x11.py` preserves the opt-in probe. It requires NVIDIA tooling and the existing private-X11 prerequisites. Keep its raw logs private because they can include the media path. The supplied research's useful recommendation to distinguish decoding from rendering was applied; unsupported assumptions about an mpv backend, multiple FFmpeg decoders and global vsync changes were not adopted.

A separate temporary software-decode control (`QT_FFMPEG_DECODING_HW_DEVICE_TYPES=,`, not saved to any configuration) reported `Selected format with no conversion yuv420p`, with no helper CUDA process. With the same source/settings and logging, default NVDEC measured 63.6% of one CPU core and 648.5 MiB summed RSS; the software control measured 105.6% and 547.8 MiB. Off returned both to about 70 MiB. These bounded samples support retaining the default hardware decoder rather than disabling it; they do not prove live-session latency or optimal behavior for other media. No production default was changed.
