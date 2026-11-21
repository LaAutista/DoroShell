# DoroShell Panel prototype

A native LXQt Panel 2.4.1 build with DoroShell unified pinned tasks and a hidden-tray popup. Current source includes the ordered patch series described below. Building it does not replace the installed panel. Do not replace a running panel or DockBarX applet: applications may inherit their output pipes.

## Built behavior

- Opt-in pink gradient styling (`panel1/doroshellTheme=true`), with pale task highlights and a pink hidden-tray popup.
- Bottom-oriented, 40-pixel candidate profile with the existing panel icon size (28 pixels by default) and compact native task buttons.
- Narrow Show Desktop target at the far right, after the clock. Preparation reuses an existing Show Desktop widget and preserves its other settings. The optional `doroshellEdge` style keeps the native action, tooltip and accessible name; `doroshellEdgeWidth` defaults to 12 pixels and is bounded to 8–32 pixels. Vertical panels use that extent as the target height.
- Unified pinned/running application buttons: a closed pin launches its desktop entry through GIO; the matching window reuses that button. Running apps have an underline. Click to activate/restore and drag to reorder.
- DockBarX pinned launchers migrate in order into the native taskbar, using desktop entries. Existing widgets, clock settings and tray hide/auto-hide preferences are retained. The old panel file is never overwritten.
- A small upward arrow opens a separate grid of hidden notification icons. The popup uses LXQt's native StatusNotifierItem buttons, supports mouse activation, Enter/Space and Escape, and closes if a represented service disconnects.
- The generated profile places a two-line local clock just before Show Desktop. Click it to open the calendar. With a stock tray configuration, new notification icons go behind the up arrow. Choose Always show in the notification area settings to keep an icon on the bar. Existing Hide/Auto-hide lists retain their selection. The arrow appears only when there are hidden icons. Right-click the notification area and use its Configure dialog to choose icons; `profile.py prepare --hide TITLE` can explicitly supply hidden titles instead.

**Pinned order persists across panel restarts.** Matching prefers explicit application/desktop-file IDs, then `StartupWMClass` (class or instance), then desktop-basename/class matches. A unique explicit pin breaks equal-strength ties; multiple matching pins remain ambiguous. Unmatched windows retain normal task buttons. Ambiguous identities are refused during preparation. Unpinned running-task order, thumbnail/peek polish and further glass-like visual polish remain development work. This does not claim all Open-Shell functionality or an exact Windows 7 reproduction.

## Build separately

The builder clones pinned upstream revisions, validates and applies the complete ordered patch series, and stages installation into a private directory. It never runs pacman, sudo or a system installation. Existing installed build dependencies are required: C/C++ toolchain, Git, CMake/Ninja, Qt 6 development tools, GIO Unix development headers (`gio-unix-2.0`) and the LXQt panel development dependencies. Missing dependencies stop the build. The compatible pinned LXQt build-tools helper is built locally as well: 2.4.0 for liblxqt 2.4, or 2.5.0 for liblxqt 2.5. Standard development metadata is checked before acquisition; unknown combinations fail with guidance. See [dependency selection and limits](../docs/panel-build-dependencies.md). One `PATCHES` list drives both application and runtime notice copying; missing, unlisted or duplicate entries fail before building. Run `python source_release.py` first to verify the source inventory.

```sh
python panel/build.py --check-dependencies
python panel/build.py --work /absolute/empty/build-directory
```

The executable is `build-directory/runtime/bin/lxqt-panel`. Keep the whole build directory: compiled backend/plugin paths refer to that runtime prefix. The supplied script rejects a nonempty build directory and changed upstream tags. It is not a redistributable package builder yet.

## Prepare and review

From the existing LXQt user's session:

```sh
python panel/profile.py prepare \
  --binary /absolute/build-directory/runtime/bin/lxqt-panel \
  --prepared /absolute/new/private-profile-directory
```

This reads the current configuration and, if DockBarX is present on the selected panel, its pinned launchers, then creates a private candidate and validation record. Nothing starts, stops or changes in the current session. Missing launchers and conflicting widget identifiers are refused. Review the candidate before enabling. These files contain personal paths and must not be committed.

### Explicit selection in a multi-panel profile

For a standard profile with more than one panel, select the panel by its existing
INI ID; no panel is chosen automatically:

```sh
python panel/profile.py prepare --panel panel2 \
  --binary /absolute/build-directory/runtime/bin/lxqt-panel \
  --prepared /absolute/new/private-profile-directory
python setup.py native-panel --prepared /absolute/new/private-profile-directory
python setup.py native-panel --prepared /absolute/new/private-profile-directory --apply
```

Alternatively choose that `plan.json` in **Settings → Taskbar & Windows → Prepared
taskbar plan**, then preview before applying. The CLI preview reports the selected
panel. Selection is made during preparation, not changed while enabling a plan.
The selected panel receives the DoroShell taskbar/Start/tray/clock widgets; explicit
selection retains its position, size, icon size and line count. Unselected panel
and plugin sections, global settings and unrelated sections are copied byte-for-byte.
The original stock file is never written. Later taskbar sizing, clipboard placement
and Quick Launch merging locate the selected DoroShell panel rather than assuming panel1.

This bounded adapter requires an explicit `panels=` list for multiple `panelN`
sections, distinct plugin identifiers and explicit plugin types on unselected panels.
Shared widgets, duplicate/encoded/ambiguous section names, missing panel/plugin lists,
or DoroShell identifiers owned elsewhere are refused. It does not infer which physical
monitor a panel occupies. Omit `--panel` only for the existing single-panel1 workflow;
that legacy workflow retains its existing default geometry changes.

`deploy.py` and bootstrap also accept `--panel panelN`, validate it before module
package offers/builds and record it for repeat/recovery. See the [installer workflow](../docs/INSTALL.md#explicit-panel-selection).
Apply can offer missing PySide6/GIO validation prerequisites with pacman approval,
then reruns validation before any DoroShell configuration write. Neither workflow chooses
among panels or migrates installed layouts. Restore before selecting a different plan.
Custom XDG roots, arbitrary INI grammars, actual multi-monitor/login behavior and
native runtime acceptance remain unverified or unsupported. Toolkit imports and the
new panel-selection helper are installed together; multi-panel sizing requires PySide6.

## Reversible next-login switch

After the prototype is suitable for your desktop:

```sh
python panel/profile.py enable-next-login --prepared /absolute/private-profile-directory
```

This backs up the previous user autostart override and any managed target files, writes a separate DoroShell panel config, and overrides only the LXQt panel autostart entry for the **next normal login**. Current applications and the current panel continue running. The launcher redirects output to a private file, avoiding inherited pipes from a temporary supervising process. Repeating the same unmodified plan preserves the initial backups. Restore before staging a different plan.

Undo with:

```sh
python panel/profile.py restore-next-login
```

Rollback refuses changed managed files. LXQt itself can update the candidate profile during ordinary use. Pass `--keep-panel-edits` to save a private copy of that profile before restoring. Changes to the launcher or autostart entry still cause rollback to refuse. It restores the prior autostart entry and target files, leaving the original LXQt panel configuration intact. If a new panel is already running, restoration takes effect at the next user-chosen login; it never kills that process. Keep the runtime directory until the switch has been restored and the custom panel is no longer in use.

This next-login path is tested with temporary homes, not an actual logout/login. Earlier controlled live upgrades are recorded separately in the [acceptance matrix](../docs/final-acceptance.md); they do not establish fresh-login acceptance.

## Verification

```sh
python -m unittest discover -s tests -v
python tests/check_tray_lifecycle_x11.py --run --xvfb /path/to/Xvfb --binary /path/to/lxqt-panel --evidence /private/output --case popup
python tests/check_show_desktop_x11.py --run --xvfb /path/to/Xvfb --binary /path/to/lxqt-panel
python tests/check_panel_density_x11.py --run --xvfb /path/to/Xvfb --binary /path/to/lxqt-panel --evidence /private/output --scale 2
```

These opt-in checks require Xvfb, xauth, Openbox and their Python dependencies.
They start authenticated disposable displays and private session buses, use
synthetic fixtures and leave personal windows/settings/clipboard alone. The legacy
`panel/check_x11.py` also requires a separate private X11 display: a private
`dbus-run-session` alone does not isolate pointer input or windows.

Current recorded native scope includes identity and filtered pins, tray attention,
focus/auto-hide and keyboard menus, Show Desktop state preservation and live panel
orientation changes in a private session, and 60-icon overflow with long task
labels at 150%/200%. Four palette contrast checks pass. See the linked feature
notes below and [current release verification](../RELEASE-CANDIDATE.md) for exact
scope; old 58-test/core checkpoints are historical. This does not establish every
real application, fresh login, physical monitor/DPI behavior or Wayland.

Pins are configured by `doroshellPinned` under the taskbar group as a list of absolute desktop-entry paths. The candidate profile writes this list; dragging changes its order. Right-click the taskbar, open its configuration, then choose **Pinned applications…** to add desktop entries, remove pins or move them up/down. Save applies the list; Cancel leaves it unchanged. Missing entries, ambiguous identities and edits made while the dialog was open are refused. The containing LXQt configuration dialog’s Reset remains available; saving pins does not replace its saved reset state. Grouping must remain enabled for unified pins. Existing LXQt Meta+number task shortcuts dispatch pinned launches too, with private X11 activation coverage documented in the filtered-pin checks below; broader shortcut environments remain separate acceptance.

Remaining: broader real-application/DBusMenu and real-client XEmbed variant coverage,
keyboard-only entry to overflow, physical multi-monitor/mixed-DPI, Wayland and
sustained use. Fresh-login and clean-install checks are user-deferred. Patches
0005–0008 remain staged rather than live on the recorded installation. Building
or publishing this source does not activate it.

## Upstream attribution

Based on [LXQt Panel](https://github.com/lxqt/lxqt-panel), tag 2.4.1, commit `cffb0cd29c6ce0360356006ce727a9b01347e062`; local build helpers use [lxqt-build-tools](https://github.com/lxqt/lxqt-build-tools) 2.4.0, commit `0f56cd400d2afcb6f16d4ca88538ed716439c2c2`, or 2.5.0, commit `ca90f9b0c5eedc3ab89d4031811dff833392bf3b`, selected from the installed liblxqt dependency contract.

The panel changes and scripts in this directory are LGPL-2.1-or-later. Upstream copyright headers are retained in the patched source. See [license](licenses/LGPL-2.1.txt) and [upstream authors](licenses/LXQt-AUTHORS). The patch and pinned sources make the modifications reviewable/rebuildable. This declaration does not relicense unrelated DoroShell files or third-party artwork. No Doro artwork, personal panel configurations, screenshots or compiled binaries are bundled here.

### Pin and unpin from the task button

The source panel provides **Unpin from taskbar** to closed-launcher, single-window and grouped-window context menus. Unpin changes only the saved launcher list; open windows retain their task buttons until they close naturally. **Pin to taskbar** appears for running apps with one unambiguous visible desktop entry matching their resolved launcher identity. With grouping disabled, existing pins can be removed but adding a unified pin is disabled. Use taskbar settings to enable grouping. Ambiguous app identities omit the Pin action rather than selecting an arbitrary launcher.

`python tests/check_taskbar_pin_menu_x11.py --run --xvfb /path/to/Xvfb --binary /path/to/lxqt-panel` checks real private-X11 menus, pin order and persistence, surviving disposable windows, unchanged desktop entries and grouped/ungrouped paths. It never removes an app or signals a personal window. A staged build takes effect only at the next normal panel/session startup.

### Optional wallpaper glass

The current builder also applies `patches/0002-wallpaper-glass.patch`. It adds an opt-in, asynchronous cached wallpaper backdrop to the native panel, not a compositor. Existing binaries are unchanged until rebuilt and selected through the normal next-startup workflow. Default/fallback remains the existing opaque theme. [Configuration, limits and private verification](../docs/wallpaper-glass.md).

### Launcher identity and icon fallback

The builder applies `0003-launcher-identity.patch` after the existing panel/glass patches.
It joins application-ID and class-based windows to their resolved launcher and
uses launcher/native icons before the generic fallback. See [matching rules and
private regression tests](../docs/taskbar-identity.md).

### Pinned launchers under task filters

`0004-filtered-pins.patch` keeps launcher pins visible when all their windows are
filtered out, with existing-window activation instead of duplicate launches.
See [behavior and private regression checks](../docs/taskbar-filters.md).

### Tray popup attention lifecycle

`0005-tray-attention-popup.patch` closes stale overflow snapshots when an item's
attention timer moves it into or out of the panel, and holds an auto-hiding panel
visible while overflow is open. See [focus, status transitions
and private checks](../docs/tray-lifecycle.md).

`0006-tray-keyboard-context.patch` supports Menu/Shift+F10 on overflow icons and
prevents a menu-selection key release from also activating the application.

Show Desktop's expanded [private X11 acceptance](../docs/show-desktop.md) covers
mixed minimized/sticky/workspace state, window creation/closure, repeated toggle
and orientation changes in the same running panel.
`0007-show-desktop-drag.patch` keeps the desktop exposed during repeated drag
hovers; clicks retain their normal toggle behavior.

`0008-panel-density.patch` bounds large hidden-icon popups with keyboard-accessible
scrolling and preserves wrapped long task-label tooltips. See [density and scaling
checks](../docs/panel-density.md) for the synthetic scope and remaining limits.

## Legacy tray registration

`0009-tray-registration-popup.patch` invalidates an open overflow snapshot when
a new item registers. The synthetic XEmbed/SNI docking, pixel, input and restart
check and precise plugin/profile limits are in [legacy tray acceptance](../docs/xembed-tray.md).
This patch remains staged; no live panel refresh was performed.

`0010-tray-shortcut.patch` adds the unbound LXQt action **Show/hide hidden notification icons**. Configure an unused chord in LXQt Shortcut Keys after safe deployment. [Behavior, latency evidence, conflict policy and accessibility limits](../docs/tray-shortcut.md). No user binding is assigned by default.


## Compact calendar bounds follow-up

`0011-calendar-bounds.patch` preserves the compact calendar's native behavior while
accounting for scrollbar space and the reported available work area. The actual
source methods pass a compiled Qt offscreen fixture, followed by a successful full
native build using cached liblxqt 2.4 files in a private prefix with build-tools 2.4.
No package was system-installed or version check bypassed. The later
[dependency-selection candidate](../docs/panel-build-dependencies.md) also builds
against liblxqt 2.5 using pinned tools 2.5. No panel run or live upgrade is claimed. A separate coordinator build also completed
all 1,367 steps and confirmed the linked calendar symbol, without execution.
See [reproduction and limits](../docs/panel-calendar.md).

`0012-calendar-holidays-dst.patch` bolds US federal holidays (US locale only) and the
local daylight-saving transition days in the calendar, with tooltips. See
[holiday and DST marks](../docs/panel-calendar.md#holidays-and-daylight-saving-days--2026-11-15).

`0013-layout-request-loop.patch` stops two plugins from re-posting `LayoutRequest` on
every layout pass. The clock's `fitClock()` reset and re-shrank its font each pass, and
the show-desktop edge button cleared and re-set its size limits each pass; either one kept
the panel at most of a CPU core (11,000-23,000 wakeups per second) and loaded the X server
through the taskbar's icon-geometry refresh. Measured on the owner machine after the fix:
under 1% CPU and about one wakeup per second.
