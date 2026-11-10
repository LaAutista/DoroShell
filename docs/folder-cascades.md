# Lazy folder cascades

Click the arrow beside a Start-menu folder link to browse its contents. Clicking
its label still opens that folder in the default file manager. Subfolders expand
on demand; files open through their existing GIO handler. Keyboard navigation and
Escape follow standard Qt menu behavior. No preference migration is required.

This is not an indexer: no file contents, thumbnails, or descendants are read in
advance. Each expansion uses a short-lived helper, with a 1.5-second deadline,
a 2,000-entry scan limit and 200 displayed entries. Folders appear first. A
notice explains truncation; **Open this folder** is always available. Browsing is
limited to five nested levels. Hidden entries, symbolic links and special files
are omitted. Network or unavailable paths can time out without blocking the UI.
The list refreshes on reopening. Names with non-UTF-8 bytes retain their exact
path through encoded helper arguments and URI metadata.

Closing a menu cancels its own helper; Linux parent-death protection also ends
helpers if the menu process crashes. There is no background watcher or timer
while idle. No executable is launched merely by listing a directory.

## Verification

The original isolated snapshot suite passed 159 tests. After integration onto
published `7ad3929`, its full suite passed 137 tests (unpublished display tests
are intentionally not included). Eight feature tests cover
one-level listing, bounds, malformed responses, Unicode and non-UTF-8 paths,
async navigation, cancellation, timeout responsiveness, depth and refresh.
An independent 50-cycle lifecycle review left no QProcess children.

`tests/check_folder_cascade_x11.py` uses an authenticated private Xvfb, temporary
configuration/files, an actual temporary menu installation and rollback, and
mocked GIO dispatch. It verifies the actual browse arrow,
nested Right/Return selection, exact file URI, Escape without launch, and unchanged
folder-label behavior. It never opens a user document or alters the personal
session. Actual handler applications, slow network mounts and a clean installed
session remain manual acceptance items. This candidate is not activated live.
