# Optional animated lock-screen decoration: feasibility and implementation gate

Status on 2026-11-14: **design only; no lock-screen animation is implemented**.
No real lock, authentication change, locker replacement or registration was tested.
This is a bounded proposal for the existing X11/XScreenSaver installation, not a
claim that desktop wallpaper animation also works on the lock screen. The user's
accepted wallpaper-derived glass remains unchanged; moving-window Aero is outside
scope. Clean-install, fresh-login and disruptive acceptance remain deferred.

## Evidence and recommended boundary

Read-only inspection found XScreenSaver 6.15 and LXQt Session 2.4.0 installed, with
an XScreenSaver process present. Presence does not establish that locking is enabled,
which authentication method is selected, or that a particular lock path is safe.
The existing Start action dispatches the installed LXQt lockscreen desktop entry
through GIO. Leave that dispatch, session bindings and locker startup unchanged.

The installed upstream `xscreensaver(1)` 6.15 manual describes a host-owned window
per monitor and an external graphics subprocess receiving `XSCREENSAVER_WINDOW`.
That is the candidate integration seam: add a graphics renderer, not a locker.
XScreenSaver continues to own activation, screen coverage, input handling and the
password dialog. The renderer must not implement any of those functions.

**Recommended next implementation:** a small optional renderer adapter plus a
fake-host test, initially disabled and unregistered. The existing desktop decoder
and PCManFM paint layer are not drop-in lock renderers: the desktop lifecycle,
window ownership and IPC consumer differ. Do not start a second desktop renderer,
put a fullscreen player over the desktop, or swap lockers merely to obtain video.

mpv is an installed candidate decoder, not a selected integration yet. Its
[upstream embedding documentation](https://mpv.io/manual/stable/#options-wid)
says that on X11 `--wid` creates a child window under the supplied parent. XScreenSaver's
manual instead requires rendering into its supplied window rather than mapping an
independent toplevel. Establish whether child-window embedding satisfies that
contract before choosing mpv. If it does not, use a renderer that draws into the
provided drawable; do not relax the contract or silently fall back to a fullscreen
window. Avoid committing a general rendering framework before this single question
is answered.

## Proposed renderer contract — not current behavior

- Input: a nonzero, non-root, existing X11 target window and an explicitly selected
  local media file. An environment variable/window ID is a drawing target, not an
  authentication or trust assertion. Refuse missing/invalid targets and never infer
  the personal root window or discover a real locker to attach to.
- Configuration: separate from desktop wallpaper; off by default, muted, one file,
  bounded size/frame rate and a chosen fit policy. Never auto-select personal media
  or scan folders. Accept local regular files only, not URLs, playlists or commands.
- Execution: fixed executable and argument array, no shell interpolation of media
  paths. If evaluating mpv, disable user config/scripts, player controls, terminal
  input, audio, OSD and external IPC; verify those options against the chosen build.
  These constraints reduce unintended behavior; they do not establish a sandbox.
- Drawing: only the supplied host surface or an explicitly validated child of it.
  No independent toplevel, keyboard/pointer grabs, password field, clipboard,
  session-control D-Bus interface or screen capture. No XScreenSaver control command.
- Lifecycle: one renderer/decoder per host target, owned child processes, prompt
  SIGTERM handling and reaping. Parent disappearance, invalid media or decoding
  failure stops rendering without restarting the locker or choosing another surface.
  The design relies on host-owned background coverage; actual crash/coverage behavior
  is an acceptance question, not a security guarantee.
- Optional selection: only after review, add one fixed renderer entry to the existing
  graphics-program mechanism. Do not alter lock enablement, grace time, idle time,
  DPMS, authentication, PAM, systemd sleep hooks or autostart. Preserve original bytes
  and refuse conflicting concurrent edits. Keep existing graphics choices recoverable.

## First isolated acceptance checkpoint

Build only a fake host window on authenticated private Xvfb, a temporary HOME and
private D-Bus, with a visible **renderer preview — not a lock screen** label. Use
procedurally generated test frames, not private artwork/video. Do not start a real
locker, register a saver program, or invoke lock/unlock commands even on the fixture.

1. Pass the fixture's target ID explicitly; verify geometry, hierarchy, rendering
   changes over time and that the player creates no unrelated toplevels. Compare
   client/window and input-focus metadata, without reading clipboard contents.
2. Reject root/zero/stale IDs, missing/unreadable media, URL/playlist-like inputs and
   filenames containing shell characters without executing them. Check disabled,
   unsupported backend and decoder-start-failure paths.
3. Resize/destroy the host, stop/restart the renderer and terminate the decoder.
   Verify bounded teardown, no orphan child, no grabs and no unrelated config writes.
   Exercise two synthetic targets without claiming physical multi-monitor coverage.
4. Measure CPU/memory/frame cadence and request-to-first-frame with an explicit
   method and synthetic limits. Resource caps and failure deadlines must be chosen
   from evidence, not advertised from a decorative demo.
5. If these checks fail twice for the same reason, record the blocker and stop or
   change the approach. Do not integrate into the live locker to debug it.

Passing this checkpoint proves rendering/lifecycle behavior in a fake host only.
It cannot prove authentication, actual lock coverage, unlock safety, suspend/resume,
physical DPMS, other WMs, Wayland or resistance to bypass.

## Approval boundary and next decision

This checkpoint adds documentation only. The next non-disruptive action can be the
small fake-host embedding probe above. No user media or locker configuration is
needed for that probe. A later install/selection patch must present the exact
renderer command, changed settings and conflict-safe rollback for explicit review.
Real lock/unlock or disruptive acceptance remains prohibited until separately
authorized at a chosen safe point; successful mocks do not supply that authorization.

No Gamebox account was inspected or modified. Its Nov 13 staging was reported by
another thread, with backups and isolated checks; actual Gamebox login remains
unverified. Do not treat this development-session design as Gamebox deployment.

## Reference and verification scope

Primary sources inspected: installed `xscreensaver(1)` 6.15 (HOW IT WORKS, programs,
XSCREENSAVER_WINDOW and lifecycle sections), installed `mpv(1)` embedding section,
and the linked upstream mpv manual. The upstream XScreenSaver web manual was not
retrievable in this pass, so its contract was checked against the installed manual.
No source text, media or third-party artwork was copied into implementation files.
The full repository unit suite and source inventory/archive checks validate this
documentation checkpoint's packaging; they do not test lock-screen functionality.
