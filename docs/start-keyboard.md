# Start keyboard navigation: search and applications

This increment connects the existing search and application list; it does not
replace Qt's menu behavior or register a global shortcut.

| Focus | Key | Behavior |
| --- | --- | --- |
| Search | Down | Focus the selected result if usable, otherwise the first enabled/selectable result. No action for empty/all-disabled results. |
| Search | Up | Focus the last enabled/selectable result. |
| Search | Home/End, Left/Right, selection/editing modifiers | Normal line-edit behavior. |
| Results | Up/Down | Normal list movement. Bare Up at the first usable row or Down at the last returns to search. |
| Results | Home/End | Select/scroll to the first/last usable row, skipping disabled, nonselectable and hidden rows. |
| Search/results | Tab / Shift+Tab | Native focus traversal, with Search → Results → All Programs/Back adjacent in the chain. Other controls remain reachable. |
| Search/results | Enter | Existing application launch route; disabled, hidden, nonselectable or stale rows do not dispatch. |
| Start | Escape | Existing stages: clear search, return to Home, then close. A nested menu consumes its own Escape first. |

Only unmodified list arrows/Home/End get the bounded list handling. Modified keys,
search text editing, category controls, nested folder/context menus, Left/Right and
normal Tab traversal remain with Qt. There is no application-wide key filter.
Accessible names remain intact; search/results descriptions explain their keys.

A rebuild while results have focus keeps the selected desktop ID when still present,
otherwise selects the nearest remaining row. Empty results return focus to search.
Typing in search keeps search focus and selects the first ranked result as before.
Existing catalog-change restoration is preserved. Resident reopens still reset the
query/category and focus search; cancellation does not launch an app/session action.

## Evidence and limits

The synthetic baseline reproduced missing search-Up entry, no list-edge return,
Tab skipping results and selection resetting on focused refresh. Qt handled simple
disabled endpoints, but a hidden/disabled-row combination needed explicit Home/End
selection. This scope adds no general cross-column arrow model, mnemonics or arbitrary
menu-layout adapters.

Offscreen widget-local key tests cover empty/disabled/hidden/nonselectable rows,
Home/End, arrows, text selection, forward/reverse Tab reachability, filtered/catalog
rebuilds, fake Enter dispatch, nested folder-menu navigation, staged Escape and
repeated resident reopen/cancel. Catalogs and folder contents are synthetic; app,
URI and session dispatch are faked. The same tests run against a temporary installed
Start runtime and render its selected-row focus.

These checks are not global key injection, live X11, login, AT-SPI or screen-reader
acceptance. The previously blocked Xvfb test is not retried. No personal application
catalog, history, settings, input or session is used by this acceptance harness.
