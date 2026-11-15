# Compact clock calendar bounds

The earlier `0001-hidden-tray-popup.patch` already wraps the compact horizontal
clock's calendar in a scroll area and caps its popup. The later tray-density patch
changes the hidden-icons popup, not the calendar. This follow-up addresses two
remaining source-reproduced cases; it does not establish the cause of a reported
personal-session clipping symptom.

`0011-calendar-bounds.patch` changes only the compact clock's popup sizing:

- Reserve the horizontal scrollbar's height when width is constrained, and the
  vertical scrollbar's width when height is constrained. Previously the added bar
  consumed calendar space on the other axis, hiding the last week or columns and
  producing an unnecessary second scrollbar despite spare room.
- Use the screen's reported available work area, intersected with the relevant
  panel edge. The old full-screen bounds could place the popup over another
  reserved area; setting the panel edge must not expand a smaller available area.

For example, an 18 pt calendar in a 320×400 logical-pixel work area needed a
horizontal scrollbar. Before the fix the popup remained 259 pixels tall; that bar
removed 14 pixels from its viewport, clipping the final week. The new calculation
allows 273 pixels, keeping the complete calendar height visible. These numbers
come from the synthetic Fusion/DejaVu Sans fixture, not a physical monitor.

A genuinely too-small work area still requires scrolling. The fix does not shrink
fonts, force every column/header into view at once, or replace Qt's calendar. Month
buttons, date selection, year display and Escape retain native handling. The
noncompact/rotated-clock branch, time formats/zones, themes and settings are unchanged.

## Native Qt source fixture

`tests/check_calendar_offscreen.py` compiles the **actual patched calendar
construction and position method** into `tests/calendar_popup.cpp`. Only the panel,
screen work area and anchor are synthetic. Widgets, layout, scrollbars, date model,
mouse/key event handling and pixel capture use native Qt. The wrapper uses a
disposable HOME/XDG tree, offscreen QPA and nonexistent private D-Bus addresses;
it never launches the panel, queries personal configuration or injects global input.

```sh
python tests/check_calendar_offscreen.py \
  --source /path/to/patched/lxqt-panel/plugin-worldclock/lxqtworldclock.cpp \
  --evidence /path/to/new/private-evidence-directory
```

This needs existing C++17, pkg-config, Qt6 Widgets/Test development files and the
Qt offscreen plugin. The source must have the declared panel patches applied.
Optional `--bounds-case screen` or `workarea` isolates the two regressions. The
harness refuses an existing evidence directory, uses bounded compile/run timeouts
and writes only synthetic captures. It is separate from the ordinary unit suite.

The old source fails independently on scrollbar clipping and reserved-work-area
containment. The fixed source passes **192 cases at each of 100%, 125%, 150% and
200% Qt scaling (768 cases)**: 10/18/28 pt fonts, four logical work areas, top/bottom
panels, week-number on/off, repeated opens and both screen/work-area scenarios.
Checks cover the complete last week when height permits, reachable oversize content,
month/year button sizing, mouse previous/next month, native date arrow navigation,
a later month/year, and Escape dismissal. Synthetic rendered captures were inspected.
No existing Xvfb test was retried.

The full disposable/offscreen unit suite passes **540 tests in 35.883s**,
including the existing ordered-patch/notice copying and installer regressions.

## Full native build evidence and remaining limits

All eleven ordered patches apply to pinned upstream
`cffb0cd29c6ce0360356006ce727a9b01347e062`. The builder's shared patch list also copies
this patch into runtime notices; existing versioned builds and rollback are retained.
Deployment's existing source digest includes the new patch, so it selects a new build
rather than overwriting a previous runtime. No installer/schema migration is added.

The initial configuration attempt failed: installed liblxqt 2.5.0 requires
lxqt2-build-tools 2.5.0, while the saved pinned build prefix provides 2.4.0. That
failure remains part of the frozen `eec9ad8` review evidence.

A subsequent **complete native panel build passed all 1,367 steps** in a new private
tree, with the same eleven patches and no source edits. An already-cached
liblxqt 2.4.0-1.2 package supplied matching headers, library and CMake files, extracted
only into a private prefix alongside the existing build-tools 2.4.0. The package was
not system-installed; no package scripts, system helpers or policies were used.
No downloads, source-pin changes or version-check bypass. The actual clock object
and static plugin archive were built and linked into the final panel executable;
its symbols include the calendar positioning method. This closes the compilation
gap for that prepared dependency set, beyond the extracted-method fixture.

The earlier 540 unit and 768 native-widget cases belong to the unchanged runtime
source; this documentation-only follow-up does not rerun them. The coordinator
independently passed those 540 unit and 768 native-widget cases, then completed a
separate fresh full build: exit 0, all 1,367 steps, with the calendar positioning
symbol confirmed in the final executable. Neither build was installed or executed.

The default host configuration with liblxqt 2.5 still needs compatible build-tools
or an explicitly prepared compatible dependency prefix. The private cached 2.4
build does not establish default bootstrap/clean-OS readiness or a redistributable
binary. No install, staging, panel execution or live update was performed. Original
builds, source/evidence bundles and personal settings remain unchanged. Actual WM
work-area reporting, personal/live clipping, physical mixed-DPI/multi-monitor,
other styles/locales, live font changes, normal login and clean OS remain unverified.
