# DoroShell Panel prototype

A native LXQt Panel 2.4.1 build with a DoroShell hidden-tray popup. This is a working development increment, not the finished Windows 7 panel design. It runs separately from the installed panel. Do not replace a running panel or DockBarX applet: applications may inherit their output pipes.

## Built behavior

- Bottom-oriented, 40-pixel candidate profile with 28-pixel icons and compact native task buttons.
- Native grouped tasks for open applications; click to activate/restore and drag to reorder.
- DockBarX pinned launchers migrate in order to native Quick Launch, using desktop entries. Existing widgets, clock settings and tray hide/auto-hide preferences are retained. The old panel file is never overwritten.
- A small upward arrow opens a separate grid of hidden notification icons. The popup uses LXQt's native StatusNotifierItem buttons, supports mouse activation, Enter/Space and Escape, and closes if a represented service disconnects.
- User-configured Hide/Auto-hide lists determine which icons appear in overflow. The arrow appears only when there are hidden icons. Right-click the notification area and use its Configure dialog to choose icons; `profile.py prepare --hide TITLE` can explicitly supply hidden titles instead.

**Pins and running tasks are currently separate widgets.** A fully unified pinned/running model, persistent running-task order, thumbnail/peek polish and the final glass-like appearance remain development work. This does not claim all Open-Shell functionality or an exact Windows 7 reproduction.

## Build separately

The builder clones pinned upstream revisions, applies the small patch, and stages installation into a private directory. It never runs pacman, sudo or a system installation. Existing installed build dependencies are required: C/C++ toolchain, Git, CMake/Ninja, Qt 6 development tools and the LXQt panel development dependencies. Missing dependencies stop the build. The pinned LXQt build-tools helper is built locally as well.

```sh
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

This reads the current single-panel configuration and DockBarX pinned launchers, then creates a private candidate and validation record. Nothing starts, stops or changes in the current session. Missing launchers, multiple panels and conflicting widget identifiers are refused. Review the candidate before enabling. These files contain personal paths and must not be committed.

## Reversible next-login switch

After the prototype is suitable for your desktop:

```sh
python panel/profile.py enable-next-login --prepared /absolute/private-profile-directory
```

This backs up the previous user autostart override and any managed target files, writes a separate DoroShell panel config, and overrides only the LXQt panel autostart entry for the **next normal login**. Current applications and the current panel continue running. The launcher redirects output to a private file, avoiding inherited pipes from a temporary supervising process. An existing staged switch must be restored before another is enabled.

Undo with:

```sh
python panel/profile.py restore-next-login
```

Rollback refuses changed managed files. It restores the prior autostart entry and target files, leaving the original LXQt panel configuration intact. If a new panel is already running, restoration takes effect at the next user-chosen login; it never kills that process. Keep the runtime directory until the switch has been restored and the custom panel is no longer in use.

This next-login path is tested with temporary homes, not an actual logout/login. No switch has been enabled on the personal desktop during development.

## Verification

```sh
python -m unittest discover -s tests -v
dbus-run-session -- python panel/check_x11.py --run --binary /absolute/path/to/lxqt-panel
```

The X11 check refuses an already-owned notifier bus, uses private settings and synthetic tray/window fixtures, briefly moves the mouse, and restores its position. It does not instantiate the legacy XEmbed tray, reserve screen space, rearrange personal tasks, or close personal applications. A separate private D-Bus session isolates notification services; it is not a virtual display.

Verified development build: compiled against the installed Qt 6.12 / LXQt libraries; 46 automated tests passed. Real X11 checks exercised arrow opening, mouse/keyboard activation, imported DBusMenu selection and fallback context dispatch, Escape, service-disconnect cleanup, native task restore and drag ordering between disposable windows. The tiny popup and arrow were visually inspected. This verifies synthetic applications, not every real tray app.

Still required: real-application DBusMenu breadth, attention/passive/auto-hide transitions, large icon counts, keyboard focus restoration, multi-monitor/DPI and panel edges, legacy XEmbed behavior, Wayland, sustained use, fresh login and clean installation. No production switch is implied by these checks.

## Upstream attribution

Based on [LXQt Panel](https://github.com/lxqt/lxqt-panel), tag 2.4.1, commit `cffb0cd29c6ce0360356006ce727a9b01347e062`; local build helpers use [lxqt-build-tools](https://github.com/lxqt/lxqt-build-tools) 2.4.0, commit `0f56cd400d2afcb6f16d4ca88538ed716439c2c2`.

The panel changes and scripts in this directory are LGPL-2.1-or-later. Upstream copyright headers are retained in the patched source. See [license](licenses/LGPL-2.1.txt) and [upstream authors](licenses/LXQt-AUTHORS). The patch and pinned sources make the modifications reviewable/rebuildable. This declaration does not relicense unrelated DoroShell files or third-party artwork. No Doro artwork, personal panel configurations, screenshots or compiled binaries are bundled here.
