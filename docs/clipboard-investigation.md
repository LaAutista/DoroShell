# Intermittent clipboard investigation — 2026-11-10

Status: **not reproduced; not fixed**. The report describes copied text disappearing when switching from an open document to Firefox or Discord. It was working again during observation. Do not treat passing checks as disproving an intermittent failure.

Read-only session inspection found no running/installed clipboard manager and no owner of the X11 CLIPBOARD_MANAGER selection. Kate continued owning CLIPBOARD and answered a TARGETS request with normal text formats. The diagnostic inspected process ownership and format names only, never personal clipboard text. No conflicting Copy/Paste shortcut was found in the inspected LXQt/Openbox configuration. Absence of a clipboard manager does not establish the cause of loss while the source application remains open.

Further checks used an authenticated private Xvfb display, private home/configuration/session bus, synthetic text, a new anonymous Kate process and a separate Firefox profile. The working desktop, applications and clipboard were not used:

- Twelve real Kate-to-Firefox address-field and textarea copy/paste round trips passed, including multiline Unicode text.
- Changing focus and PRIMARY selection preserved CLIPBOARD. Six normal Start open/Escape-close cycles also preserved it.
- The existing screenshot regression passed image handoff, cancellation, pixel-exact Writer/Draw paste, and helper exit after another owner replaced the image. Installed clipboard helpers matched the tested source.
- All 117 automated tests passed. This is the current checkout's result, not a re-verification of older release archives.

Reproduce the focused test with installed Kate, Firefox, Openbox, Python Xlib and PySide6:

```sh
python tests/check_clipboard_switch_x11.py --run --xvfb /path/to/Xvfb
```

No clipboard manager, persistent clipboard history, autostart entry or runtime fix was installed. Discord's logged-in input path, personal Firefox extensions/profile and a long-duration intermittent failure remain unverified. The next useful evidence is ownership plus a TARGETS response during an actual failure, before copying again; clipboard contents need not be logged.
