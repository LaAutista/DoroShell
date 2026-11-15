# Start keyboard navigation: search, applications and places

Navigation connects the existing Windows 7-style search, application list and
right-hand places/menu controls. It does not replace Qt's popup-menu behavior,
add another layout or register a global shortcut.

| Focus | Key | Behavior |
| --- | --- | --- |
| Search | Down | Focus the selected result if usable, otherwise the first enabled/selectable result. No action for empty/all-disabled results. |
| Search | Up | Focus the last enabled/selectable result. |
| Search | Home/End, Left/Right, selection/editing modifiers | Normal line-edit behavior. |
| Results | Up/Down | Normal list movement. Bare Up at the first usable row or Down at the last returns to search. |
| Results | Home/End | Select/scroll to the first/last usable row, skipping disabled, nonselectable and hidden rows. |
| Results | Right | Focus the last usable right-hand control used in this window, or the first usable control in displayed order. Scroll folder controls into view. If none is usable, retain normal list handling. |
| Places, folder-browse arrows, Edit folder links, Menu options, primary session button or power arrow | Left | Return to the selected usable result, otherwise the first usable result; if none remain, focus search. Never activate the control. |
| Right-hand controls | Tab / Shift+Tab, Up/Down/Right, activation keys | Existing Qt button/focus/menu behavior. This adapter supplies only cross-column Right from results and Left back; Tab selects other controls. |
| Search/results | Tab / Shift+Tab | Native focus traversal, with Search → Results → All Programs/Back adjacent in the chain. Other controls remain reachable. |
| Search/results | Enter | Existing application launch route; disabled, hidden, nonselectable or stale rows do not dispatch. |
| Start | Escape | Existing stages: clear search, return to Home, then close. A nested menu consumes its own Escape first. |

Only unmodified keys on the application list and registered right-hand buttons get
the bounded handling. Search text editing, modified keys, category controls and
normal Tab traversal remain with Qt. Open folder/context/options menus and modal
dialogs retain ownership; drag operations also block the column adapter. There is
no application-wide key filter. Existing Qt accessible names remain intact and are
checked through its accessibility interface; the results description explains the
new column arrows. This is not a screen-reader acceptance claim.

Column targets exclude hidden, disabled and non-focusable controls; separators
are never targets. The last target is remembered only in memory for this window.
Folder rebuilds preserve a surviving label/path/role and duplicate occurrence,
otherwise use the first available target. Removed widgets are hidden and removed
from the key filter before deferred deletion, so stale controls cannot intercept
arrows. A hidden menu or another popup/modal is not given focus by this restoration.
Resident reopening still starts in search; rebuilding the window resets the target.

A rebuild while results have focus keeps the selected desktop ID when still present,
otherwise selects the nearest remaining row. Empty results return focus to search.
Typing in search keeps search focus and selects the first ranked result as before.
Existing catalog-change restoration is preserved. Resident reopens still reset the
query/category and focus search; cancellation does not launch an app/session action.

## Evidence and limits

The synthetic baseline reproduced missing search-Up entry, no list-edge return,
Tab skipping results and selection resetting on focused refresh. Qt handled simple
disabled endpoints, but a hidden/disabled-row combination needed explicit Home/End
selection. The later bounded column adapter additionally reproduces and fixes
Right staying in results and Left from places failing to return there. It adds no
mnemonics, general directional-layout engine or arbitrary menu-layout adapter.

Offscreen widget-local key tests cover empty/disabled/hidden/nonselectable rows,
Home/End, arrows, text selection, forward/reverse Tab reachability, filtered/catalog
rebuilds, fake Enter dispatch, nested folder-menu navigation, staged Escape and
repeated resident reopen/cancel. Catalogs and folder contents are synthetic; app,
URI and session dispatch are faked. The same tests run against a temporary installed
Start runtime and render its selected-row focus.

These checks are not global key injection, live X11, login, AT-SPI or screen-reader
acceptance. The previously blocked Xvfb test is not retried. No personal application
catalog, history, settings, input or session is used by this acceptance harness.

Column follow-up on published `0c50da5`: **512 full-suite tests pass (28.208s)**.
Ten new cases cover selected/empty/disabled results, absent targets, options/session
controls, dynamic catalog/folder rebuilds, duplicate roles/reordering, scroll reveal,
editing/modifiers/Tab, repeat opens, modal/popup/drag ownership, native folder
Right/Left/Escape and accessible names. The actual temporary-installed runtime
passes these and the ten earlier keyboard cases (**20 tests, 0.563s**). Installed
runtime/toolkit hashes/imports, visible focus, repeat record preservation,
edited-menu rollback refusal and original byte/mode restoration pass. Preferences
remain intact; installer schema, resident protocol and helper packaging are unchanged.
