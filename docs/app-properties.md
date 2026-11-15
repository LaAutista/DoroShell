# Read-only application properties

Right-click an application in Start and choose **Properties…**. With an application
selected, the platform's keyboard context-menu request (normally **Menu** or
**Shift+F10**) opens the same native menu. The modal
dialog shows display name, desktop ID, description and source desktop-entry location
when GIO supplies them. Distinct IDs/locations distinguish same-named applications.

Fields are selectable, read-only plain text. Close or Escape returns to the existing
menu query/category, selection, scroll and list focus (search if no usable result
remains). The list handles the native context event once, without a second key-press
handler. This also handles keyboard events with no pointer position. Native menus/modals own their keys; drag, hidden and disabled rows do not
open another context menu. Pin errors do not block this read-only operation. There
is no automatic copy, editing, file-opening, deletion or settings mutation.

Only four metadata getters on the current catalog object are used. The dialog does
not read, interpret or display Exec/command lines, scan directories, resolve a
desktop entry again, or stat/read the source file. A source location is a GIO
snapshot, **not proof that the file still exists**. If a catalog notification removed
the selected ID before Properties opens, the dialog says so and retains only that
selected ID. A missing ID/description/location is explicitly “Not provided by GIO.”
Objects created without a source filename remain useful without invented paths.

Rendered fields are capped at 256 characters for name, 1,024 for ID, and 4,096 each
for description and location, plus a truncation marker. Control/bidi characters are
shown as escapes. Unicode text and ampersands/markup remain literal in the fields.
These are display bounds; the GIO getter API itself returns the complete cached
string before truncation. The dialog is a snapshot, not a live filesystem monitor.

## Verification

Synthetic metadata and actual disposable GIO desktop-entry/keyfile fixtures cover
duplicate labels, deleted source files, no filename/ID, unavailable getter data,
Unicode/control characters, markup/mnemonics, bounds and no Python filesystem probes.
Offscreen Qt tests send native keyboard/mouse context events and exercise
Properties navigation, accessible
field names and selection, Close/Escape/reopen, catalog removal during the popup,
empty/disabled/drag ownership, preference preservation, lifetime/focus restoration
and the readable status layout. Clipboard contents are never read or changed.

The installed-copy test imports the actual temporary-installed Start program,
repeats the nine property cases, inspects its rendered dialog and return focus,
checks runtime/toolkit bytes, repeat ownership, edited-menu rollback refusal and
exact original menu bytes/mode restoration. No new helper/package/schema is needed.

This is synthetic/offscreen and temporary-home acceptance. No personal application
catalog, real application launch, live X11/AT-SPI, fresh-login or clean-OS acceptance
is claimed. Editable properties, rename/delete/sort and broader item operations
remain separate work.

References: [GIO application ID may be absent](https://docs.gtk.org/gio/method.AppInfo.get_id.html),
[GIO source filename may be absent](https://docs.gtk.org/gio-unix/method.DesktopAppInfo.get_filename.html),
[Qt context-menu event delivery](https://doc.qt.io/qt-6/qcontextmenuevent.html).
Actual platform shortcut generation remains part of live X11 acceptance.
