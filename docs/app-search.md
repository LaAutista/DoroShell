# Ranked local Start search

This bounded source candidate searches installed, visible applications only. It does not search files/content, query a network service, store search text or add telemetry. The existing recent-program behavior still records successful application launches when enabled.

Ranking favors exact display names, exact executable basenames, full-name prefixes, then name-token prefixes. Remaining matches rank by name, executable, keywords and description in that order, with exact tokens ahead of prefixes and substrings. Every query term must match somewhere; terms may appear in different fields or a different order. Case folding and Unicode decomposition support case-insensitive and accent-insensitive matches, including composed/decomposed accents and Straße/STRASSE. This is not typo correction, transliteration or fuzzy edit-distance search.

The index is built once from the existing GIO catalog and rebuilt on the existing catalog-change notification. Query matching reads only cached strings; it does not rescan desktop directories or call metadata getters per keystroke. GIO visibility rules remain in effect, with an explicit Hidden check. Exact desktop IDs remain the result identity. App launch still uses the existing GIO `launch_item` path; executable text is only search metadata and is never parsed or executed through a shell.

Search shows at most 100 ranked results with a refinement notice for broader matches. Blank/whitespace-only text returns to the existing pins/category view. Clear messages explain an empty pin/category/recent view or a search with no matches. Down moves from search to the first selected result; Up/Down then use normal list navigation. Enter in search or the list activates the selected result through the existing dispatcher. Empty results cannot launch anything; Escape retains its existing back/clear/close behavior. Ctrl+F retains its existing focus shortcut.

## Real catalog fixture acceptance — 2026-11-15

The follow-up on published `da49537` found no catalog runtime defect in the bounded
cases below; production catalog/search/installer code is unchanged. Three fresh-process
tests use actual GIO discovery and notifications with disposable HOME/XDG directories,
fake executable entries, offscreen Qt and nonexistent private bus addresses. They
do not enumerate personal applications or launch anything. Current keyboard paths
are documented in [Start keyboard navigation](start-keyboard.md).

- User entries override lower-priority system entries by desktop ID. Hidden and
  NoDisplay overrides suppress the lower entry; deleting the override reveals it.
  OnlyShowIn/NotShowIn for LXQt and missing TryExec are respected.
- Same-named applications retain distinct IDs and deterministic search order.
  Actual localized French names, German case folding, composed/decomposed accents,
  Japanese text and desktop-entry keywords remain searchable.
- A 32-entry creation burst triggered one catalog query in the recorded run.
  The test permits up to three notifications-driven queries, checks the existing
  150 ms single-shot debounce, and preserves category/query, selected desktop ID
  and right-column focus. Metadata changes, override changes and removal rebuild
  the cached index. Typing makes no catalog query; drag deferral does not query until
  the drag ends, and a settled catalog makes no polling queries in the observed window.
- User and system Flatpak-shaped export roots are discovered when included in
  XDG_DATA_DIRS. Identical files outside those registered roots are absent. This
  tests desktop-entry exports, not Flatpak installation, activation or sandboxing.
- Pins, including an unavailable ID, and disabled recent-recording preferences
  remain byte-identical. Actual temporary installation verifies runtime/toolkit
  helper bytes and runtime imports; repeat installation preserves its ownership
  record and removal preserves fixture preferences.

Reproduce without X11 or a session bus:

```sh
python -B tests/check_app_catalog_offscreen.py --run
python -B tests/check_app_catalog_offscreen.py --run --installed
```

Each launcher creates and removes its own fixture home. GIO notifications reach
the Qt GLib dispatcher directly; the test does not manually pump a second GLib loop.
This is development-host GIO/offscreen acceptance, not live desktop, real package,
fresh-login, clean-OS, AT-SPI or general cross-distribution acceptance. The observed
query counts are not a latency guarantee.

GIO uses the process's data-directory environment, so a running resident cannot
discover a newly added export root merely because another process changed its
environment. A later normal menu process must inherit that root. DoroShell adds
no fallback directory scanner or polling. See the [desktop-entry precedence and
visibility specification](https://specifications.freedesktop.org/desktop-entry/latest-single/),
[GIO monitor rearming contract](https://docs.gtk.org/gio/class.AppInfoMonitor.html)
and [Flatpak export conventions](https://docs.flatpak.org/en/latest/conventions.html).

## Historical initial search verification

- `python -m unittest discover -s tests -v`: 136 passed on base `7ad3929991249341631ecf7f59a60c1733ee6095` plus this change.
- Seven new tests cover ranking, multi-field/reordered tokens, substring fallback, Unicode/case/accents, blank query, deterministic ties, visibility rules, metadata caching and temporary-home install/repeat/rollback with an independently imported installed menu.
- `python tests/check_app_search_x11.py --run --xvfb /path/to/Xvfb`: real private-X11 keyboard input with synthetic desktop entries and mocked app launches; ranking, hidden entries, Down/Up, search/list Enter, no-results no-op, Escape and catalog-index replacement passed.
- Existing `check_app_catalog_x11.py` passed with real GIO install/remove/reinstall notifications; search/category/selection and missing pins survive refresh.
- Cached ranking of 5,000 synthetic entries over 20 queries measured 10.24 ms median and 22.98 ms maximum on the development host. This is ranking time, not end-to-end rendering or a universal latency guarantee. Rendering is bounded to 100 search rows; extremely large catalogs still use a synchronous linear scan of cached metadata.

No personal-file indexing, personal preference changes, real app launches during the new private test, live activation, normal-login test or clean installation is claimed.

## Folder-cascade coordination

This change was developed in its own checkout from the published base. It does not merge, overwrite or modify the folder-cascade checkout. The shared integration files are `menu/start_menu.py` and `install.py`; `themes.py` and folder-cascade code are untouched.

When combining branches, preserve both helper imports and both installer helper entries/toolkit entries. The search-specific Start hunks add an index beside catalog assignment, a status label beside the result list, widget-scoped Down navigation, and the ranked-query branch in `refresh`. Folder opening and cascade behavior are not changed. Resolve overlapping import/installer list hunks by retaining both additions; this integration candidate retains both features plus portable settings, and passed the combined gate described below.


## Combined integration checkpoint

Integrated against committed portable-settings base `1b69898ddc191ea28abf23b34a50269282a4fb73`, which includes folder cascades. Only the expected Start import and installer helper-list overlaps required resolution. Folder and portable source implementations are unchanged. All 157 combined unit tests passed, including portable tests. Private X11 search, real GIO catalog refresh, installed search/cascade interaction and installed portable-settings checks passed. The combined installed test verifies helper payloads, ranked-query/selection preservation across nested cascades, search Enter afterward and removal of all helper payloads on rollback. All settings mutations are confined to disposable homes; launches are mocked. No live activation or push was performed.
