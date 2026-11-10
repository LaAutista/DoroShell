# DoroClipboard

An optional X11 clipboard-history service and a **fixed visible clipboard button immediately before the hidden-icons arrow** on the DoroShell native panel. This is a Quick Launch button, not a notification icon that can collapse into the overflow popup.

```sh
python setup.py clipboard             # preview native-panel/file changes
python setup.py clipboard --apply     # install + autostart at next normal login
python setup.py clipboard --rollback  # restore prior files/settings
```

A staged native DoroShell panel with a notification-area widget is required. Setup refuses unknown layouts and conflicting edits. Repeated installation and exact rollback are tested. It does not restart the panel or kill another clipboard manager. When launching, it refuses known competing managers (CopyQ, Qlipper, Klipper, ClipIt, Parcellite, xfce4-clipman); disable the other manager yourself before starting DoroClipboard. This detection is best-effort, not an exhaustive inventory.

The clipboard button opens a searchable list. Double-click or **Copy selected** restores an item to Ctrl+C/Ctrl+V clipboard; it never injects a paste into another app. Delete removes one history item. Clear history clears the list but leaves the current clipboard untouched. Closing/Escape hides the window and collection continues. Quit and forget history stops collection and discards history; the button can start it again. Rollback also requests the current-display service to stop. Pause collection excludes subsequent copies until resumed. Selection-only PRIMARY/middle-click clipboard is untouched.

## Privacy and limits

- **Memory-only, session-scoped. No clipboard contents are saved or logged; core dumps are disabled for the service and acquisition helper.** Restart/logout loses history.
- Does not import the clipboard that existed before startup.
- Up to 50 entries, 16 MiB total; individual supported text/image entries are limited to 4 MiB, text to 262,144 characters. Oversized/unsupported entries are left on the clipboard without retention.
- Recognized password-manager exclusion MIME markers are skipped. **Ordinary copied passwords are indistinguishable from ordinary text. Pause before copying secrets.** There is no claim of universal secret detection or secure memory erasure.
- Supported copies are detached from the source app and owned by the service, preserving supported rich formats and allowing paste after that app exits. Acquisition runs in a disposable helper, not the UI process. Nonresponding owners are timed out after 1.5 seconds (with a helper-side 2-second backstop), stale results are discarded, and additional helper address-space growth is capped. A timed-out copy stays with its source and is not added to history.
- Images are copied in memory. No file URLs are opened or executed. Original files are never modified. Replaying a stored file-list converts known Cut markers to Copy, avoiding an unexpected historical move; the original live cut operation remains intact.

## Verification

Unit checks cover bounds, deduplication, markers, rich text, images, fixed placement, repeated install and rollback/conflict refusal. `tests/check_doroclipboard_x11.py --xvfb /path/to/Xvfb` uses an authenticated private X server and external producers to test source-exit persistence, PRIMARY separation, rich formats/images, pause, search/reuse/delete/clear, singleton activation and a deliberately nonresponding X11 owner with an event-loop heartbeat. Personal clipboard is not read by tests.

The fixed-button mouse click was verified on an actual private native panel. Physical-session/mixed-DPI layout, real-app/manager compatibility and normal-login startup still require acceptance. No Wayland support is claimed.
