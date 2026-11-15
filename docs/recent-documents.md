# Optional Recent Documents

In Start, open **Menu options → Recent documents (shared history) → Enable Recent
documents view**. This is off by default. It adds a right-column submenu using
the desktop's shared `$XDG_DATA_HOME/recently-used.xbel` store (default
`~/.local/share/recently-used.xbel`). Only opening that submenu reads the store;
opening Start, searching applications and enabling the option do not read it.
Uncheck the option to hide the view. No background monitoring or polling is added.

The list contains at most 20 supported local file URIs, ordered by their recorded
visited/modified/added time with deterministic URI ties. Invalid times sort last.
Duplicate canonical URIs collapse; an application-private marker suppresses all
duplicates of that URI. Names come from URI basenames, not untrusted titles or
application command strings. A tooltip shows the URI to distinguish same-named
documents. DoroShell never indexes documents or reads their contents, icons,
thumbnails, existence or mount availability. The list may contain deleted/offline
targets; availability is explicitly unverified.

An explicit selection dispatches the validated URI through GIO's default application
handler. Failure to dispatch is shown without changing history. Accepted dispatch
is not proof that the receiving application opened the document; it may report a
missing file or access a mounted filesystem itself. This initial implementation
does not support remote URI authorities/schemes, relative paths, query/fragment
URIs, control characters, dot path components, trailing directory slashes or
non-UTF-8 filenames. A local file URI does not prove a regular file or local disk.
No shell/Exec parsing or recorded application command is used.

## Privacy and limits

The shared store is read-only. DoroShell does not delete, clear, rewrite or copy
its history, and disabling the view does not clear shared desktop history. Manage
that history through the applications that record it. No secure-erasure claim or
misleading Clear button is provided. Applications that do not contribute to this
XBEL store will not appear; this is not a universal recent-document index.

Only `{ "version": 1, "enabled": true/false }` is saved in DoroShell's separate
`recent-documents.json` preference. Existing preferences/schemas remain unchanged.
Malformed, future, symlinked or externally edited preferences refuse replacement.
No document paths, timestamps or entries are saved in DoroShell preferences,
backups or portable exports. This separate opt-in is also excluded from portable
export/import, so importing settings cannot turn it on. Menu removal preserves
the preference and shared store. In-memory rows are discarded after submenu close.

A separate on-demand worker reads at most 1 MiB from one regular, non-symlink
store file, parses at most 2,048 bookmarks with depth/attribute bounds, and returns
at most 20 entries. DTDs and entity declarations are rejected, including encoded
XML declarations; no external resource or XInclude resolver is installed. The GUI
limits worker output to 128 KiB and cancels after 1.5 seconds or menu close/disable.
An OS-blocked filesystem read may take longer to terminate, but its late result is
discarded. The known shared store may itself reside on a mounted data directory;
the worker does not probe any referenced document target. No new dependency,
privileged path, daemon or authentication is introduced.

Native QMenu arrows, Enter and Escape own the open submenu. Existing Start
Left/Right column navigation includes its button only while visible/enabled.
The Windows 7 layout and default controls remain unchanged while disabled.

## Verification boundary

Synthetic XBEL tests cover URI rejection/normalization, malformed/oversized XML,
DTD/entities/UTF-16 attacks, count/depth bounds, duplicates/private markers, invalid
times, unavailable targets without filesystem probes, FIFO/symlink refusal and
future/invalid preferences. Offscreen tests exercise default-off/no worker, actual
worker reads of disposable stores, native-menu Enter/Escape, cancellation/timeout,
late results, close/reopen, disable, fake GIO dispatch failure/success and save
conflicts. Installer tests cover helper runtime/toolkit closure, repeat ownership,
edited-helper refusal, exact prior bytes/mode rollback and untouched fixture history.

The complete suite is run with disposable HOME/XDG, offscreen Qt and nonexistent
private bus addresses. Eight document UI cases also pass from the actual temporary
installed menu, with installed runtime/toolkit imports and rendered synthetic menu
inspection. No personal recent store/document, actual application launch, live
X11/global input, AT-SPI, package, fresh-login or clean-OS acceptance is claimed.

References: [GTK shared recent-file semantics](https://docs.gtk.org/gtk3/class.RecentManager.html),
[GLib desktop bookmark format/private visibility](https://docs.gtk.org/glib/struct.BookmarkFile.html),
[Python XML security guidance](https://docs.python.org/3/library/xml.html#xml-security).
Only the stored metadata is used; GTK's target-querying convenience APIs are not.
