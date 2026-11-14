# Portable Start preferences

DoroShell Settings → Start Menu → **Portable Start preferences…** exports a
small, versioned JSON file. **Preview and import…** displays the incoming values
and requires Apply; Cancel is the default. **Restore last import** restores the
exact previous file contents only when no subsequent edits conflict.

This first increment covers the primary session button, recent-program recording
and count, optional [recent-app age retention](recent-apps.md), and standard-folder visibility/order. It does not perform any power
or session action. Reopen Start after applying preferences.

## Privacy and compatibility

The export uses a strict allowlist. It contains no app pins, history entries or launch timestamps,
custom folder labels or paths, portrait/crop, wallpaper, clipboard, credentials,
monitor configuration or installer records. These local values are not imported
or replaced. Theme, taskbar and machine-specific configuration remain managed
by their existing modules, not this portable format.

Absent standard links export as hidden. Custom links retain their positions and
content while standard-link slots are reordered. Duplicate standard shortcuts
are refused without edits; resolve duplicates in Start first. A lowered recent
count that would discard existing history is also refused. Imports cannot grow
the folder list past the existing 100-link limit. Unknown formats, duplicate JSON
keys, malformed local data, symlinked paths and oversized files are refused.

A private local rollback record stores the original and imported bytes. Unlike
the portable export, it can contain local paths and history; it is written with
owner-only access and must not be shared. A successful subsequent import replaces
this single rollback point, disclosed in its preview. Files are replaced atomically
one at a time. Portable operations share a lock and check original bytes again
before each write. Failed operations attempt to compensate completed writes;
if disk failure prevents restoration, the recovery record is retained and the
error names affected files. This is not a filesystem-wide atomic transaction or
protection against every external editor racing between the check and replacement.

## Verification

Thirteen focused tests cover privacy exclusions, exact restore, malformed input,
conflicting edits, write-failure compensation in both directions, previous undo
preservation, empty lists, duplicate shortcuts, Unicode expansion and bounds.
Private X11 acceptance uses a temporary installed Settings UI, synthetic paths
and mocked native file/confirmation dialogs. Actual button interaction verifies
export, preview Cancel, Apply, portrait/crop preservation and Restore. No personal
configuration, clipboard, desktop process or power action is used.

The candidate has not been installed into the personal Settings app. Native file
picker interaction and interrupted-process recovery remain manual acceptance
items; rollback will refuse mixed files rather than overwrite later user edits.


The optional `retention_days` field carries only the local expiry setting (0 = no
age limit, 1–365 = days). A legacy import without it preserves the current policy.
Import/preview do not prune history; Start applies expiry on later use, including
removing untimed legacy entries when enabled. Old readers refuse the new field.
Never-configured default exports keep the original field set. Private rollback
continues to preserve exact bytes and can therefore retain pre-expiry history.
