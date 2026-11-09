# Screenshot verification

## Current evidence

The 34-test suite runs offscreen with temporary installation homes. Screenshot lifecycle tests use a synthetic child through real QProcess signals. See the [current verification report](verification.md) for exact scope.

A real local X11 check now passed: ScreenGrab drag + Enter capture → Escape cancellation → another capture. Both captures were 120×90 with the expected synthetic pixels. Isolated LibreOffice Writer and Draw test instances pasted the image after ScreenGrab exited, and their graphic dimensions and pixels matched. Cancellation retained the preceding image. No personal settings changed or screenshot artifacts were committed.

ScreenGrab initially aborted inside the restricted task sandbox. Authorized tests outside that sandbox connected to X11 without changing display settings. Its selection UI required Enter after the drag. Source inspection of [ScreenGrab core](https://github.com/lxqt/screengrab/blob/master/src/core/core.cpp) and [configuration loading](https://github.com/lxqt/screengrab/blob/master/src/core/config.cpp) supported the command/config choices; the actual tests above are separate evidence.

## Live acceptance still required

Perform these checks from a working X11 session at a user-chosen time. Use non-sensitive sample content and scratch documents; do not add desktop screenshots or private configuration to the repository. A successful capture intentionally replaces the clipboard, so first preserve anything needed from it.

1. Review the screenshot module's preview and existing Print binding before any installation. Test the checkout helper directly with `python runtime/screenshot.py` before changing shortcuts. It stays running to own the clipboard; subsequent invocations request another capture from that owner. Ensure the owner is running the intended checkout version. An older installed owner can receive requests instead.
2. Select a small sample region. After ScreenGrab exits, paste into two independent image-capable applications. Verify actual content and dimensions, then repeat after switching applications and waiting several seconds. Keep the helper running during paste checks.
3. Capture A, cancel B with Escape, then capture C. Check that A remains after B and C replaces it only after success. Repeat cancellation before selection, mid-drag and with a zero-size selection. Begin a separate cancellation check with plain text and rich text already copied.
4. Press Print rapidly during selection: there should be one overlay. Repeat successful captures and confirm no stuck input grab. Check each monitor and a crossing selection, including differing scales and negative screen origins.
5. Verify clipboard persistence with and without the usual clipboard manager in a disposable test session. Record tool versions, monitor layout and results. Window/full-screen capture acceptance remains outstanding: the current helper requests region capture only.
6. End only the helper started for this test when finished (Ctrl+C in its terminal). Clipboard persistence after the owner exits is not guaranteed. No logout, panel restart or application closure is needed for these checks.

Installation and rollback must be reviewed separately. `python modules.py screenshots` previews changes; apply/repeat/rollback tests currently use temporary homes. Do not infer live shortcut activation, fresh-login persistence or clean-install support from those tests. Plan any login or VM test separately; never force a session restart to complete this checklist.
