# Start folder-link separators

In **Edit folder links…**, choose **Add separator**, then use **Move up / Move down**
to place it between folders. **Remove** deletes the selected item. Changes take
effect only after **Save**; Cancel/Escape leaves the file unchanged. Separators
have no name, destination, visibility checkbox or launch action. Folder links,
including their browse arrows and nested menus, keep their existing behavior.

The separator is a non-focusable horizontal line. Leading/trailing separators,
consecutive separators and separators separated only by hidden links collapse in
the rendered menu. Their exact order remains in the editor and saved data. Empty
or separator-only compositions show no folder rows/lines. Fixed system-link groups
keep their existing grouping; separators cannot be moved into those groups or into
the application catalog. This adds no commands or general menu-tree format.

## Local compatibility and failure handling

The default folder list is unchanged. Existing version-1 records are read without
a write or migration on open. Saving a list with separators uses local version 2;
a separator is exactly `{"type": "separator"}`. Extra fields, unknown item types,
unsupported versions and more than 100 total folder/separator rows are refused.
Removing the last separator saves the folder-only version-1 format again.

Old readers reject version 2, preserving the file instead of silently losing its
separators. Malformed existing data disables Save. The existing conflict check,
previous-byte backup and atomic replacement remain: external edits refuse Save,
and a failed replacement leaves the old file and editable selection intact for
retry. Opening/cancelling does not write. An explicit Save can reorder JSON keys
through Qt's existing table mapping; existing folder values and exact backup bytes
are preserved. These checks are not an atomic lock against every external editor.

## Path-free portability

New portable exports use version 2 and include separator rows interleaved with
standard-folder IDs/visibility. Custom labels, paths, icons, portrait/crop and
history remain excluded. Custom folders disappear from the exported projection;
therefore a separator can become a leading/trailing/repeated row, which is handled
by the same rendering rule on the destination. All six standard-folder IDs remain
present exactly once; missing local standard folders export as hidden.

A version-2 import replaces the destination's separator/standard-folder slots in
order. Existing custom rows retain their data and order relative to each other, with
any extra imported rows appended. Their numeric indices or neighboring groups can
change when other slots are removed/replaced; private destinations/names are never imported.
This is not a transfer of the source's complete custom composition. A version-1
import reorders standard slots only and **leaves local separators unchanged**.
The preview names separators and explains replacement; Apply is explicit and
Cancel remains the default. Exact local restore and conflict refusal are unchanged.

The portable list is bounded at six standard IDs plus at most 100 separator rows;
the resulting local composition must still fit 100 total rows. An import exceeding
that limit refuses before writes (including if preserved local custom/standard
rows use the remaining slots). Duplicate keys/standard IDs, separator payloads,
unknown fields/formats and malformed local records are refused. Old portable
readers reject the new version; update both Start and the installed toolkit.

## Verification boundary

Offscreen tests use disposable preferences, synthetic apps and fake/blocked launch,
URI and session dispatch. They cover editor persistence/cancellation/failure,
normalization without saved-data loss, empty/hidden layouts, Tab skipping and nested
folder menus, legacy records, portable projection/import/undo, bounds and conflicts.
The actual temporary-home installed Start/toolkit is also tested and rendered at
100% and 150% scale. This is not live X11, AT-SPI/screen-reader, physical DPI, login
or clean-OS acceptance. No personal settings, session or global keys are changed.
