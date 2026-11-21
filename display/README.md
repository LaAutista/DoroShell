# Private display-controls candidate

Adds a native **Display (current session)** group inside PCManFM Desktop Preferences → Advanced. The Advanced page scrolls when the window or available screen is small. This is a private source/build candidate, not an installed feature. The standard wallpaper builder/installer has narrow optional integration; shared module/settings and panel sources are not edited.

## Behavior and scope

- Select an active output and one of its advertised refresh modes **at its current resolution**. Exact RandR mode IDs select the timing; rounded Hz values are labels only. This path is vendor-independent X11 RandR and can work on NVIDIA, Intel or AMD.
- **VSync — NVIDIA OpenGL (X screen 0)** queries and changes `[screen:0]/SyncToVBlank`. It affects OpenGL clients started afterward; apps can override it. This is not a universal Vulkan/game VSync toggle. Intel/AMD have no implemented global toggle; the checkbox is disabled when NV-CONTROL cannot report a Boolean value.
- **Test display changes** starts an independent helper. **Keep** confirms only after the actual state is rechecked. Revert, closing Preferences, application exit/EOF, SIGTERM, invalid confirmation input or timeout request restoration. Duplicate transactions are locked out.
- The confirmation window is 15 seconds after initial application/verification. Verification subprocess timeouts are capped to its remaining time. Rollback starts at expiry, but driver commands may delay completion. The UI does not promise completed restoration at precisely 15 seconds.
- Ordinary **Apply** starts the same guarded test when the display selection differs from the last query, while saving the other desktop preferences normally. **OK** opens a visible Keep/Revert confirmation and waits: a successful Keep saves ordinary preferences and closes; Revert, timeout or error keeps Preferences open. With no pending display edits, Apply/OK behave as before. The separate Test button remains available.
- After each completed or failed transaction, an open Preferences window automatically reads actual state and repopulates its controls. The transaction result remains visible; a successful read does not imply successful rollback. OK→Keep closes normally without starting an unnecessary query. Reload remains available if reading fails. Closing Preferences explicitly requests rollback even if another PCManFM window keeps the process alive. Closing the confirmation requests Revert; application exit still supplies EOF to the independent guard.
- No compositor, force-composition-pipeline, environment override, config file, login persistence, package installation or system service is introduced. Originals stay in the guard's memory until Keep or rollback. No settings are applied merely by opening the tab.

Unsupported: Wayland/Xwayland; inactive outputs; shared-CRTC clones; interlaced/doublescan current modes; zero-Hz/non-timing modes. Other active outputs, geometry, transform, panning, gamma and output properties participate in the state fingerprint. Detected concurrent edits cause refusal rather than overwriting another tool's work. RandR/NV-CONTROL changes are not an atomic transaction across other display tools; avoid concurrent external changes during confirmation.

A disconnected output, changed layout, unavailable X server, failed driver, SIGKILL of the guard, machine crash or power loss can prevent rollback. The helper does not force reconnection or overwrite conflicting edits. It reports incomplete recovery while the UI remains available. There is no recovery service or persistent crash journal. Physical multi-monitor/scaled/rotated display acceptance is still pending.

## Files and integration

- `backend.py`: validated RandR/NV-CONTROL queries, transaction and separate rollback guard.
- `dorodisplaycontrols.h`: asynchronous native Qt controls; unparented guard process survives dialog/application destruction and receives EOF.
- `pcmanfm-advanced.patch`: narrow integration hunks for `pcmanfm/desktoppreferencesdialog.cpp`; adds the group and an Advanced-page scroll area.
- `build_candidate.py`: copies a supplied PCManFM source tree to an empty private directory, checks/applies the patch, copies the header/helper, sets the helper's absolute path in that private build and compiles. It never installs or modifies the input tree. The helper is colocated with the executable and its digest is compiled into the native controls.

Use a reviewed PCManFM 2.4.0 source candidate, including any existing DoroShell wallpaper changes you intend to retain:

```sh
python display/build_candidate.py --source /path/to/pcmanfm-source \
  --work /tmp/doroshell-display-candidate --prefix /path/to/lxqt-build-deps
```

The `--prefix` is optional if CMake already finds the dependencies. Requires the existing native PCManFM Qt6/libfm-qt/LXQt build dependencies, Python 3 and xrandr; NVIDIA VSync additionally requires nvidia-settings/NV-CONTROL. No packages are added automatically. Move the executable and its matching helpers together. The native controls verify the display helper before every query/apply. The integrated path below also verifies the complete build before desktop startup.

## Verification

```sh
python -m unittest discover -s tests -v
python tests/check_display_x11.py --run --xvfb /path/to/Xvfb \
  --screenshot /tmp/display-controls.png
python tests/check_display_pcmanfm_x11.py --run --xvfb /path/to/Xvfb \
  --binary /path/to/candidate/build/pcmanfm/pcmanfm-qt \
  --screenshot /tmp/display-native.png
QT_SCALE_FACTOR=1.5 python tests/check_display_pcmanfm_x11.py --run \
  --xvfb /path/to/Xvfb --binary /path/to/candidate/build/pcmanfm/pcmanfm-qt \
  --screenshot /tmp/display-native-150.png
```

The unit tests use synthetic drivers. The native Qt UI test runs under authenticated private Xvfb, a temporary home/runtime and private D-Bus, with the production guard/CLI but fake driver operations. It covers Keep/Revert, 15-second expiry, errors, repeated apply, unsupported VSync/shared CRTCs, disconnects, dialog close and application exit. Unit coverage additionally exercises invalid IDs, stale requests, partial application failures, concurrent edits/locks, SIGTERM and slow/stalled calls. The PCManFM test opens the actual built candidate on private Xvfb, navigates Advanced with keyboard input and captures its top/scrolled state without applying settings.

Read-only local hardware checks confirmed the installed driver supports the query and the parser lists the physical display's advertised rates. **No physical display refresh/VSync mutation, login or fresh-install test has been performed.** UI/fake-driver testing does not establish hardware rollback reliability.

## Sources checked

- Installed `nvidia-settings --describe=SyncToVBlank`: applies to OpenGL clients started after the setting changes.
- [NVIDIA 620.70.06 OpenGL environment documentation](https://download.nvidia.com/XFree86/Linux-x86_64/620.70.06/README/openglenvvariables.html): OpenGL vblank scope and separately scoped Vulkan display synchronization.
- Installed xrandr manual: exact mode XIDs versus approximate `--rate` selection; output and current-mode reporting.
- [Mesa environment documentation](https://docs.mesa3d.org/envvars.html): application/driver controls do not provide a portable universal desktop VSync checkbox.

No reference screenshot or personal display configuration is included in the source candidate.

### Verified checkpoint

The integrated private build passed 18 display unit/process tests, 4 display installer tests and the repository-wide run of 151 tests (the latter includes concurrent workers' tests). The real Qt control suite passed on private Xvfb with fake drivers and the production guard/CLI, including compiled-helper integrity checks before launch. The actual PCManFM Advanced tab was opened and visually inspected at 100% and 150% scaling; scrolling exposes the complete scope text, status and buttons without overlap. These are private UI and mock-driver results, not physical mode-switch acceptance.


## Standard optional build and installer integration

```sh
CMAKE_PREFIX_PATH=/path/to/lxqt-build-deps python wallpaper/build.py \
  --display-controls --work /path/to/new-permanent-candidate
```

The work directory must be empty. This clones the PCManFM release matching the installed `pcmanfm-qt` (reviewed revisions are verified), applies the existing isolated-video patch, then adds the display controls. It produces `build/pcmanfm/pcmanfm-qt`, `doroshell-video-worker`, `doroshell-display-backend.py` and `doroshell-wallpaper-build.json` together. A format-3 build record pins all three payload digests. Omitting `--display-controls` preserves the legacy format-2 paired build. Format-1/2 installations remain supported.

For a future explicitly authorized next-login staging, the existing command is:

```sh
python setup.py wallpaper --wallpaper-binary /path/to/candidate/build/pcmanfm/pcmanfm-qt
python setup.py wallpaper --wallpaper-binary /path/to/candidate/build/pcmanfm/pcmanfm-qt --apply
```

The first command previews. The second changes only the existing module's managed launcher/autostart/control entries, with original contents/modes backed up and conflicts refused. It does not restart the desktop or set refresh/VSync. All payloads must match the build record at staging and startup. Missing/altered payloads trigger the established stock-PCManFM fallback. An already running candidate independently checks its compiled display-helper digest before launching that helper.

`python setup.py wallpaper --rollback` restores the module's original **first-install** baseline, not necessarily the preceding upgrade. To return to an older verified isolated renderer while retaining the module baseline, stage its original build path again. Existing renderer binaries, helper, source and build records are never modified or deleted by this integration. Existing wallpaper choices are preserved. The permanent candidate remains on disk after rollback.

Additional private checks:

```sh
python -m unittest discover -s tests -p test_display_install.py -v
python tests/check_display_install_x11.py --run --xvfb /path/to/Xvfb \
  --binary /path/to/candidate/build/pcmanfm/pcmanfm-qt
```

These cover format compatibility, helper-integrity refusal before writes, startup fallback, repeat staging, first-baseline preservation across upgrades, personal-edit conflicts, exact rollback and real staged launch on private X11. Only disposable copies/homes are staged. The original permanent build stays unchanged.


The permanent integrated candidate also passed the existing private isolated-wallpaper lifecycle/resource suite with synthetic video: playback through the separate decoder, fullscreen/manual pause with no repainting, Off releasing the helper, invalid-media error latching, GIF behavior and process/status cleanup. The existing isolated renderer/source remained unchanged across 272 recorded file hashes; the new decoder executable is byte-identical to the existing one. These private measurements do not establish physical GPU power or input latency.


### Source-release audit

The release audit corrected two native integration issues: the helper is now executed from the exact bytes whose compiled digest was verified, closing the check/reopen race; and a guard that exits without a terminal protocol message now reports recovery as unverified rather than retaining a stale confirmation prompt. Private native tests cover the changed launch path, missing/altered helpers and an unexpected nonzero guard exit. The original candidate remains preserved; the audited candidate has a separate build directory and digest.

The patch is a source candidate, not a claim of hardware acceptance. The previously verified renderer lifecycle and installer tests remain applicable because those paths did not change in the audit. A separate extracted baseline verifies patch applicability and file hashes without modifying Git refs or any publisher checkout.

## Licensing

The original display helper, build script, native controls and PCManFM patch are GPL-2.0-or-later. The native integration retains PCManFM's upstream notices; see [source licensing](../LICENSING.md) and [GPL text](../LICENSE).

## Native dialog button regression gate

```sh
python tests/check_native_display_buttons.py --run --xvfb /path/to/Xvfb \
  --binary /path/to/private/build/pcmanfm/pcmanfm-qt
```

This runs the actual candidate executable with a test-only Qt preload driver on authenticated private X11, private home and D-Bus. Production helper bytes/integrity checks and the production 15-second guard remain in use; synthetic xrandr/nvidia-settings executables only change a temporary JSON fixture. It covers the reported 2560×1440 479.99→59.95 Hz selection through bottom Apply/OK, Keep/Revert, timeout, apply failure, unchanged selection, ordinary preference saving, and closing Preferences while the process stays alive. The preload library is not part of the candidate. No physical mode/VSync mutation or live activation is established.

## Post-transition verification diagnostics

The parser canonicalizes whitespace left by the RandR `*current` annotation on a preferred mode. Strict layout and external-edit comparisons are retained. Failed verification/recovery reports bounded structured field labels (mode, connection, geometry/rotation, CRTC, gamma, brightness, transforms and other protected properties). Raw property values, EDID, serials and fingerprint hashes are not emitted. Both the initial verification failure and any recovery failure are retained; the UI retains one bounded, redacted last-failure record as described below. There is no automatic write retry.

Private regressions cover a successful preferred 59.95 Hz switch, refused recovery after a synthetic external property change with the new mode still active, and read-only repopulation with the error preserved. The original user-reported false-layout cause remains unknown without the post-switch snapshot. The user reported successfully switching and manually restoring the original rate; this does not establish automatic hardware rollback reliability.

## Visible failures and local diagnostic record

A guard error, missing terminal result or abnormal exit leaves a window-modal **Display change failed** dialog visible until Close/dismissal. It never offers Keep for an unverified state. The dialog explains that recovery is unverified and actual settings may need manual restoration. Preferences remains open, rereads actual state, and retains its error. Successful Keep/Revert behavior and external-edit/disconnection checks are unchanged. This improves failure visibility and evidence; it does not resolve the unknown physical NVIDIA state mismatch or establish hardware rollback reliability.

While the UI is alive, a terminal failure best-effort replaces `$XDG_STATE_HOME/doroshell-display-errors/last-failure.json` (default `~/.local/state/doroshell-display-errors/last-failure.json`). The new directory is owner-only (0700), the atomic record is owner-only (0600), and symlink/non-private destinations are refused. One record, at most 2 KiB, contains a schema number, fixed reason (`guard_error`, `abnormal_exit`, `guard_start_failed`), `recovery: unverified`, and at most 16 unique allowlisted field labels. No raw error/driver output, EDID, serials, monitor/output identifiers, timestamps or arbitrary helper properties are recorded. The last failure remains after subsequent success; it is historical evidence, not current status. Unwritable storage does not block the dialog, actual-state query or guard recovery. No retention history, telemetry or background logging service is introduced. App exit or abrupt process loss can prevent this UI-owned record; it is not a crash-recovery journal.

Privacy/storage tests compile the real native writer:

```sh
python -m unittest discover -s tests -p test_display_failure_record.py -v
```

The native test command above additionally covers Apply with early verification/recovery failure, abnormal guard exit, Close-only failure presentation and dismissal, failed diagnostic storage, and preserved actual-state refresh without retrying writes. Tests use fake drivers and disposable state homes only.

### Diagnostic phases (schema 2)

The bounded failure record additionally keeps at most three ordered diagnostic events, each with a fixed `phase`, fixed `reason`, and up to six unique allowlisted field labels. Phases distinguish preflight, applying commands, apply verification, periodic verification, Keep verification and recovery. Reasons distinguish state mismatch, external-change refusal, command timeout, command failure, unavailable command and deadline. An initial verification failure and a later recovery failure retain separate events; unknown phases/reasons/fields from helper messages are discarded by the native writer. The existing overall failure reason and up to 16 summary fields remain; the entire record still has the 2 KiB limit and owner-only atomic replacement.

Exact labels now identify BorderDimensions, link-status, Colorspace, recognized dithering fields, Broadcast RGB, max bpc and non-desktop, without logging their values. Other properties remain grouped and redacted. Finer fingerprints live only in in-memory diagnostic metadata outside the state dictionary: layout fingerprints, equality checks, state tokens, driver calls, deadlines and external-edit refusal remain unchanged. This diagnoses a future independently authorized failure; it does not resolve the unknown hardware mismatch or establish automatic hardware rollback.

Targeted checks:

```sh
python -m unittest discover -s tests -p test_display_diagnostics.py -v
python -m unittest discover -s tests -p test_display_failure_record.py -v
```
