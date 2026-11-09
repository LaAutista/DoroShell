# DoroShell

**DoroShell is an LXQt customization/setup toolkit with Plasma-like features**, inspired by familiar Windows and Plasma workflows. It configures and extends an existing LXQt installation; it is not a standalone desktop environment or a replacement shell.

The first module is a two-column Qt Start menu: application search, categories, pinning, personal-folder links, LXQt settings, and confirmed split session/power controls. A dedicated LXQt Quick Launch button and Alt+F1 open it. Alt+F1 again closes it. Escape clears a search, returns from a category to Home, then closes the menu. The All Programs button changes to Back while browsing or searching. The original Fancy Menu preferences are retained for rollback.

## Status and support

The core release candidate targets CachyOS LXQt 2.4 on X11 with Openbox and Python 3.14. The supported core consists of Start, the native taskbar with notification overflow, snapping, desktop and region screenshots with annotation, and reversible setup. The repository version has been tested with automated offscreen tests and temporary installation homes. The earlier native panel was observed running on the development desktop. The corrected clock/tray build passed private LXQt session startup and is staged there for the next normal login. Clean-machine dependency and login validation for this corrected build remain open.

Integration currently expects `panel1`, the Fancy Menu plugin, and the standard `Alt+F1.1` Fancy Menu shortcut. It rejects custom shortcut mappings and unsupported layouts rather than replacing them silently. Other LXQt layouts need inspection and adaptation. Multi-monitor/panel-edge positioning and long-session behavior need more testing. Folder links respect the existing default file manager; this module does not install or select Dolphin.

## Core installation on CachyOS LXQt

From an existing single-panel LXQt/Openbox session, preview and install the three independent modules. The menu adopts existing personal artwork and pins. The screenshot module can update an existing enabled Print command through LXQt’s running shortcut daemon. It checks that the live command agrees with the saved configuration. More complex live bindings require offline configuration.

```sh
python setup.py menu snapping screenshots
python setup.py menu snapping screenshots --apply
python setup.py snapping --apply --live  # optional: start snapping in this session
```

Check runtime package requirements for the selected modules with `python setup.py menu snapping screenshots native-panel cursor --packages`. This prints the package-manager command for review. Setup checks the installed packages on apply.

To build from source, provide Git, CMake, Ninja, a C/C++ toolchain and pkg-config. The native panel needs Qt 6 Widgets, DBus, XML, Linguist and private headers, LXQt, lxqt-globalkeys-ui, lxqt-menu-data, KDE WindowSystem, LayerShellQt, GIO Unix headers, X11/XCB and xkbcommon-x11. The default plugin build also uses KF6 Solid, libdbusmenu-lxqt and libsysstat. CMake reports missing build dependencies. The panel builder fetches its pinned lxqt-build-tools revision into the private work directory. The native ScreenGrab build can reuse that prefix.

Build the native panel once in a permanent, initially empty user directory. Prepare its profile **after** installing Start. Preparation reads DockBarX pins when that applet is present. Stock LXQt layouts need no DockBarX installation. The prepared panel reuses an existing Start launcher or adds one alongside the original widgets.

```sh
python panel/build.py --work "$HOME/.local/share/doroshell/panel-core-2.4.1"
python panel/profile.py prepare \
  --binary "$HOME/.local/share/doroshell/panel-core-2.4.1/runtime/bin/lxqt-panel" \
  --prepared "$HOME/.local/state/doroshell/core-panel-profile"
python setup.py native-panel           # inspect the next-login changes
python setup.py native-panel --apply
```

LXQt loads the staged taskbar on its next normal startup. A private X11 session verified that LXQt selected the user autostart entry over the stock panel. Start opens on pins. The right-hand clock shows time above the date and opens a calendar when clicked. On stock tray settings, notification apps appear in a popup behind the up chevron. Choose Always show in the notification area settings to put an icon on the bar. The far-right strip toggles Show Desktop. In **DoroShell Settings → Taskbar & Windows**, the DoroShell taskbar option previews, stages or restores the prepared panel. A nondefault profile can be selected using its `plan.json`. **Taskbar icon and button size** offers Small (20 px icons, 36 px buttons), Medium (28/48) and Large (36/56). Keep unchanged preserves the existing size. Restore previous settings recovers the values from before the first size change. The selection takes effect on the panel’s next startup.

To switch back, run `python setup.py native-panel --rollback --keep-panel-edits`. This restores the previous autostart entry and preserves any changed candidate settings in a private recovery file. The previous panel returns at the following normal login. To remove snapping while it is active, run `python setup.py snapping --rollback --live`. Restore screenshots with `python setup.py screenshots --rollback`. Restore legacy Start-button integration, if installed, before removing the menu with `python setup.py menu --rollback`. Original personal artwork and pins remain governed by their existing settings and backups.

## Dependencies

Use your distribution's package manager. On CachyOS/Arch, runtime packages are `python`, `pyside6`, `python-gobject`, `lxqt-panel`, `lxqt-session`, `lxqt-globalkeys`, `lxqt-config`, `xdg-user-dirs`, and `procps-ng`. Qt's image and platform plugins must be usable in the desktop session. Python packages installed through pip alone do not supply the complete LXQt/GIO environment.

The scripts **never install, remove, or upgrade packages**. Review missing dependencies and use your normal full-system-update workflow. Avoid partial Arch upgrades. Install and run as your normal desktop user, not root.

## Install

Clone/download this repository using your existing GitHub access. Start an LXQt session once so user settings exist, then from the project directory:

```sh
python install.py menu                  # inspect planned file changes
python install.py menu --apply          # install optional launcher
~/.local/bin/lxqt-comfort-menu           # try it before integration
python integrate.py                    # inspect panel/shortcut changes
python integrate.py --apply             # only while LXQt components are stopped
```

Live panel/shortcut restarts are disabled because launched applications can inherit their output pipes. Do not stop a running desktop to integrate this prototype. Use the [separate native panel next-login workflow](panel/README.md) when ready, or apply legacy integration while those LXQt components are not running. Configuration currently assumes default home-directory XDG layout.

The legacy `lxqt-comfort` filenames are retained for compatibility with the prototype. DoroShell installs `start_menu.py`, `start.svg`, a launcher, and an application desktop entry under `~/.local`. Favorites live in `~/.config/lxqt-comfort/favorites.json`.

## Backups and rollback

Installation records original managed contents and modes in `~/.local/state/lxqt-comfort/menu-install.json`. Panel/shortcut integration records full original configuration text and per-key before/after values in `menu-integration.json` in the same directory. Keep these manifests private: they can contain personal configuration. Repeated installs are supported; conflicting edits to managed files or keys are refused.

Rollback integration **before** removing its launcher:

```sh
python integrate.py --rollback           # only while LXQt components are stopped
python install.py menu --rollback
```

Only owned integration keys are restored, preserving unrelated changes. Favorites and reference desktop backups remain. Inspect errors before retrying; these scripts are not a crash-proof package manager. In particular, restoring the desktop-era reference snapshots wholesale could undo unrelated settings and is not part of normal rollback.

## Icon and asset policy

The repository includes only an original neutral menu SVG. **No Doro/NIKKE artwork or generated character artwork is distributed.** See [custom icons and rights](docs/assets.md). Changing the brand in the README does not grant rights to third-party characters or trademarks. This project is not affiliated with LXQt, KDE, or NIKKE's publishers.

## Tests

```sh
python -m unittest discover -s tests -v
```

Tests use Qt's offscreen platform, mocks for external actions, and temporary installation homes. They cover search/category filtering, missing folders, URI dispatch, session-dialog dispatch, file backups/rollback, integration repeat application, unrelated-setting preservation, and symlink rejection. They do not execute logout, power actions, or change the real panel. Current scripts read the available application catalog for the menu UI tests.

## Roadmap

- Verify this menu/setup on a clean CachyOS LXQt VM and after login.
- Validate the persistent single-desktop module after login; see [scope](docs/roadmap.md).
- Broaden screenshot validation across monitors and clipboard managers.
- Validate taskbar behavior on more LXQt layouts.
- Extend edge-drag tiling beyond the tested Openbox/X11 layout.
- Broaden optional Kate/Dolphin associations beyond plain text and folders.
- Broader desktop compatibility and complete installer orchestration.

The menu-specific commands above change only the Start menu and its panel integration. The working tree also contains experimental optional modules and a `setup.py` dispatcher, described below; they are not yet a clean-install-tested release.

Source licensing has not yet been selected; private access does not itself grant redistribution rights. Choose a source license before a public release.

## Current development checkpoint

Start opens on labeled, editable pins. On a fresh configuration it looks for a terminal, Firefox, Dolphin, Kate, VLC and LXQt Configuration Center. GIO resolves installed alternatives for missing handlers. Existing pin order, removed pins and intentionally empty lists survive upgrades. Recent programs has its own view. All Programs and search stay at the bottom. The right column groups folders, Games and Computer, and available desktop settings. The default menu measures 508 × 634 logical pixels and scrolls on smaller displays.

`setup.py` selects menu, panel, snapping, screenshots, Kate/Dolphin associations and per-app dark themes, single-desktop, taskbar and optional cursor modules. The default selection is only the menu; all desktop/default-app changes require explicit selection. With no action flag it previews changes. `--packages` only prints an Arch/CachyOS package command; it does not execute it. Do not apply the all-module preset as a substitute for reviewing each component. Existing desktop settings and artwork must be preserved when upgrading a personal installation.

The additional modules remain experimental. Geometry/helper tests and temporary-home apply/repeat/rollback checks are not fresh-install, post-login, multi-monitor, or real screenshot-paste validation. No desktop session is restarted by tests. The [roadmap](docs/roadmap.md) separates implemented features from remaining design and acceptance work.

Current validation: **83 automated tests pass** using offscreen Qt and temporary homes. Real X11 checks also exercised the menu search, the Qt folder picker, settings apply/restore, left/right mouse-drag snapping and geometry restoration on a test window, and click-to-restore on an isolated native LXQt icon taskbar. ScreenGrab capture → cancel → capture produced the expected 120×90 image; isolated LibreOffice Writer and Draw instances both pasted it with matching dimensions and pixels. The early sandbox-only X11 startup failure was resolved by running the authorized desktop tests outside the sandbox, without changing display permissions. [Detailed test scope and remaining gaps](docs/verification.md).

Kate/Dolphin opt-in defaults resolved correctly through both xdg-mime and GIO in a temporary home; separate test instances visibly used dark colors. Personal defaults were not changed. Fresh-login, clean-install, Wayland and multi-monitor validation remain outstanding. No desktop session was restarted.

## DoroShell settings

Run `python setup.py --gui` from the checkout, or **DoroShell Settings** after installing/updating the menu. It is also available under Start → Menu options. Settings uses five category pages: **Start Menu**, **Taskbar & Windows**, **Screenshots**, **Apps & Themes**, and **Cursor**. Start Menu links to the installed launcher for pins, recent programs and folder links. Taskbar & Windows groups DoroShell controls separately from optional LXQt and DockBarX settings. Preview and apply results appear when there is output. Selections stay selected when changing pages, and a summary shows the total pending changes across all pages. Every option begins at **Keep unchanged**. Choose the components you want, preview, then apply. Existing rollback manifests enable **Restore previous settings**. Modules apply sequentially; if one fails, the log identifies it and earlier successful modules can be restored individually.

- **Legacy taskbar module:** grouped application icons or LXQt icons with labels. This configures the installed LXQt taskbar: click an open app's icon to activate/restore it; grouped windows use LXQt's group UI. Launch closed apps from Start or existing Quick Launch icons. Existing Quick Launch entries remain; this is not Plasma's unified pinned-launcher/task-manager plugin. The explicit option can detach a known DockBarX entry while retaining its configuration for rollback. For unified pinned/running buttons and the hidden-tray popup, use the separate [native panel candidate](panel/README.md); it is not activated by this legacy option.
- **Snapping:** Openbox/X11 mouse-drag left/right halves, plus Super+Left/Right and Super+Down to restore. Existing conflicting bindings are refused. Enable the refresh checkbox to start the helper now; otherwise it starts at the next login.
- **Screenshots:** Print freezes the desktop, including an open Start menu. Enter copies the full desktop, or drag a region and move or resize it before copying. Draw, highlight, add text, or redact in the overlay. Save writes a PNG and copies the finished image. Escape cancels. **Open in ScreenGrab** passes the finished image to the optional native importer.
- **One desktop:** saves Openbox's desktop count and initial desktop as 1. It does not migrate live windows or restart the session. Application rules targeting other desktops are refused. Verify at a user-chosen next login.
- **Kate/Dolphin:** separate opt-ins for `text/plain`, `inode/directory`, and each app's Breeze Dark color scheme. Other MIME choices and global themes are retained. Apps must already be installed. Save work and close the affected app yourself before applying or restoring its theme so it cannot overwrite the file. DoroShell never closes it.
- **Personal artwork:** choose a Start image and select menu Enable/update. A local managed PNG is backed up; future menu upgrades preserve it. The cursor uses your animated GIF frames and their timing, with one character per frame. The normal pointer remains inherited by default; pink is an explicit option. No Doro reference or animation is bundled.

Examples (preview first; append `--apply` only for selected changes):

```sh
python setup.py taskbar --taskbar-style icons
python setup.py taskbar --taskbar-style standard
python setup.py kate dolphin kate-dark dolphin-dark
python setup.py screenshots snapping single-desktop
python setup.py cursor --gif /path/to/spinning-doro.gif
python setup.py menu --icon /path/to/personal-doro.png
python setup.py kate dolphin --rollback
```

The settings checkbox starts only the edge-snapping helper. Live panel and shortcut restarts are refused; the native panel supports a reversible next-login switch. One-desktop and app-theme changes are not forced into running applications. Installer configuration paths currently follow the default home-directory XDG layout; custom XDG layouts require adaptation. Menu preferences themselves respect `XDG_CONFIG_HOME`.


## Personal animated loading cursor

`cursor.py` creates an inherited Breeze theme that replaces only wait/watch and progress/left_ptr_watch. The progress cursor retains the original Breeze arrow and hotspot. All other shapes come from Breeze. It accepts an animated GIF, WebP or APNG and preserves frame timing. APNG keeps its authored canvas and skips an optional still poster. It builds 24/30/32/48/64-pixel Xcursors with Pillow (distribution package `python-pillow`); no compiler or xcursorgen is required. No artwork is included or uploaded.

```sh
python cursor.py --gif /path/to/personal-animation.gif          # preview planned files
python cursor.py --gif /path/to/personal-animation.gif --apply
python cursor.py --rollback
```

The module updates the LXQt cursor theme, the user default cursor theme, and the Xresources theme entry. It preserves cursor size and the rest of each configuration file. Original bytes/modes are backed up in `~/.local/state/lxqt-comfort/cursor-install.json`. Repeat application is supported. Rollback refuses any managed file changed since installation rather than overwriting personal edits. Keep that private backup. There is no automatic package installation or session restart. Restart applications that cache cursors; log out and back in when convenient for consistent session-wide pickup. The installer does not force-refresh running applications or the X server resource database. The transparent personal cursor is installed locally on the development machine. The source distribution includes only the neutral Start SVG. Automated cursor tests use temporary homes and synthetic artwork. A separate private X11 check sampled the installed personal animation and ordinary/pink/restored pointer pixels at 30 px. Wayland is untested.

## Edit the Start menu's folder links

Choose **Edit folder links…** beneath the folder list. Use **Change folder…** to redirect a selected link. Choose which system links to show and use **Choose portrait…** for a menu picture independent of the panel Start icon. Add folders with the folder picker; double-click a Name cell (or press F2) to rename it; use Move up/Move down to reorder; uncheck Show to hide a link; or Remove to remove the shortcut only. No folder or file is deleted. Restore defaults prepares the original six standard links. **Save** applies changes; Cancel or Escape discards them.

Settings are stored separately from favorites in `~/.config/lxqt-comfort/folders.json` (or under XDG_CONFIG_HOME). Standard links resolve the user's actual system folder locations. Custom paths are private machine-specific data and must not be committed or uploaded. Existing settings are backed up as `folders.json.backup-<timestamp>` before changed saves. Invalid or concurrently modified settings are preserved, with an error instead of overwrite. Restoring defaults changes links only; it does not reset app pins, LXQt settings, or the filesystem.

Folder-editor validation: five additional automated tests cover mouse add/reorder, keyboard rename/hide, persistence, cancellation, defaults/backups, invalid/concurrent/failed-save protection, empty lists and modal return to the menu. At that earlier checkpoint the suite passed 14 tests (including separate cursor tests); see the current validation above. `python tests/check_folders_x11.py` checks the editor on X11 with temporary configuration; directory-picker selection is mocked. An installed Documents link was dispatched successfully to the actual Dolphin handler. Native file-picker interaction, visual confirmation of the resulting Dolphin window, clean-install and post-login behavior have not been verified for this change. No logout or power action was executed.

## Optional QuickStart for Gaming

DoroShell targets **CachyOS and Arch-based systems**. Other distributions can adapt the package names and commands. These are optional commands for you to choose and run yourself; DoroShell does not install gaming applications. Package names and upstream instructions were checked on 2026-11-08; availability can change.

`sudo pacman -Syu --needed PACKAGE` refreshes repository databases, **updates the whole system**, and installs the selected package. `--needed` skips reinstalling packages already up to date; it does not suppress system upgrades. Avoid `pacman -Sy PACKAGE` partial upgrades. Review the transaction before accepting it.

| Application | Install command | Source |
| --- | --- | --- |
| OBS Studio | `sudo pacman -Syu --needed obs-studio` | [Arch Extra](https://archlinux.org/packages/extra/x86_64/obs-studio/); CachyOS may supply an optimized build. |
| Discord | `sudo pacman -Syu --needed discord` | [Arch Extra](https://archlinux.org/packages/extra/x86_64/discord/), official Discord client. |
| Signal | `sudo pacman -Syu --needed signal-desktop` | [Arch Extra](https://archlinux.org/packages/extra/x86_64/signal-desktop/), Arch-maintained package. |
| Blender | `sudo pacman -Syu --needed blender` | [Arch Extra](https://archlinux.org/packages/extra/x86_64/blender/). |
| Flatpak | `sudo pacman -Syu --needed flatpak` | [Flathub's Arch setup](https://flathub.org/en/setup/Arch). |
| Steam | `sudo pacman -Syu --needed steam` | [Arch Multilib](https://archlinux.org/packages/multilib/x86_64/steam/). Enable `[multilib]` and its `Include` line in `/etc/pacman.conf` first if disabled. Review the appropriate GPU and 32-bit driver choices; see [Arch's Steam guide](https://wiki.archlinux.org/title/Steam). |
| Kate | `sudo pacman -Syu --needed kate` | [Arch Extra](https://archlinux.org/packages/extra/x86_64/kate/). Installing it does not opt into DoroShell's default-editor setting. |
| Dolphin | `sudo pacman -Syu --needed dolphin` | [Arch Extra](https://archlinux.org/packages/extra/x86_64/dolphin/). Installing it does not change DoroShell's file-manager setting. |
| Breeze Dark (optional for Kate/Dolphin) | `sudo pacman -Syu --needed breeze` | Provides the color scheme used by the opt-in dark-theme modules. |

### Discord, Vesktop and Vencord

**Discord** is the official app. **Vesktop** is a separate third-party Discord desktop client with **Vencord included**. **Vencord** adds plugins and themes to Discord; it is not another messaging service. Vesktop does not require separately patching the official Discord app. Enable the plugins you want in Vencord's settings. No existing Discord installation or plugin configuration was inspected for this guide. See [Vesktop's project](https://github.com/Vencord/Vesktop) and [installation instructions](https://vesktop.dev/install/linux/).

On CachyOS, [`vesktop-bin`](https://dashboard.cachyos.org/package/cachyos/x86_64/vesktop-bin) is available in the `cachyos` repository (also confirmed in the local repository database):

```sh
sudo pacman -Syu --needed vesktop-bin
```

On plain Arch, upstream recommends the **AUR** package `vesktop-bin`. With an already installed AUR helper, review the PKGBUILD and sources before building:

```sh
sudo pacman -Syu
paru -S --needed vesktop-bin
```

The AUR is community-maintained build recipes, not an official Arch binary repository. Do not add CachyOS repositories to another distribution merely to run this command.

To add Vencord to the **official Discord app** instead, [Vencord's official Linux instructions](https://vencord.dev/download/) provide this upstream installer command:

```sh
sh -c "$(curl -sS https://vencord.dev/install.sh)"
```

This downloads and executes a third-party installer. Review the script first if you choose this route, run it as your normal user, and select the intended Discord installation in its prompts. DoroShell never runs it. Discord does not endorse these modifications; consult [Vencord's FAQ](https://vencord.dev/support/) for support and client-modification caveats.

### Bottles, Stremio and Heroic through Flathub

After installing Flatpak, add Flathub for your user once, then choose any applications below:

```sh
flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub com.usebottles.bottles
flatpak install --user flathub com.stremio.Stremio
flatpak install --user flathub com.heroicgameslauncher.hgl
```

[Bottles supports and recommends its Flatpak](https://docs.usebottles.com/getting-started/installation). [Stremio links to its Flathub release](https://www.stremio.com/downloads). [Heroic recommends Flatpak](https://heroicgameslauncher.com/downloads). Flatpak manages these separately from pacman; use `flatpak update --user` for updates. Adding Flathub is an explicit additional software source.

CachyOS also offers a native [Heroic package](https://dashboard.cachyos.org/package/cachyos/x86_64/heroic-games-launcher-bin):

```sh
sudo pacman -Syu --needed heroic-games-launcher-bin
```

That pacman command is **CachyOS-specific**. On other Arch-based systems, use the upstream Flatpak route above or independently review the AUR package. Choose one packaging route per app to avoid duplicate installations.

### Fluorine Manager

[Fluorine Manager](https://github.com/SulfurNitride/Fluorine-Manager) is a Linux port of Mod Organizer 2 with FUSE-based virtual filesystem support. It is an **upstream third-party download**, not a verified pacman package in this guide. Download the current archive matching your system from its [releases](https://github.com/SulfurNitride/Fluorine-Manager/releases), extract it into a user-owned directory, open a terminal there, and run:

```sh
./fluorine-manager
```

Follow upstream's runtime requirements and Settings → Compatibility instructions to select Proton and prepare Windows-tool support. Do not substitute an invented `pacman` package name. DoroShell neither downloads Fluorine nor configures Wine/Proton or games for you.

## Drag taskbar icons

With an existing DockBarX LXQt plugin, enable **DockBarX icon dragging** in DoroShell settings, or run:

```sh
python modules.py taskbar-drag --apply
```

Hold the left mouse button on an application icon and drag it before or after another icon. Escape cancels. Pinned launcher order survives applet restarts; unpinned running applications retain their order only for the current session. This option keeps your current icons and panel layout.

The optional compatibility hook recovers internal drops lost at the Qt/GTK embedding boundary. It installs two managed files in your Python user-site directory and activates only for `/usr/share/dockbarx/lxqt-panel-applet.py`. System package files are untouched. Reapply after a Python minor-version upgrade. Existing files are backed up; conflicting edits are refused. Activation waits until your next normal login. Live applet refresh is disabled because applications can inherit its output pipes and fail with EPIPE when the applet exits.

Undo with `python modules.py taskbar-drag --rollback`. This removes the hook; it does not undo icon arrangements you deliberately saved while using it.

The opt-in X11 check is `dbus-run-session -- python tests/check_taskbar_drag_x11.py --run` (requires python-xlib). It uses synthetic launchers and a temporary home, moves the mouse, and opens/closes only its own test panel.


## Open-Shell parity

The goal now covers all Open-Shell feature families, with Windows 7 kept as the primary menu style. [The parity inventory and delivery plan](docs/open-shell-parity.md) distinguishes implemented behavior, missing features and Windows-only integrations. Full parity is not complete; Explorer and Internet Explorer extensions cannot run directly in LXQt.

Start now exposes application-provided tasks in the application right-click menu, such as New Window when the app declares it. Tasks use GIO desktop actions without shell command parsing. This does not yet provide recent-document jump lists, and successful dispatch cannot prove that the target application completed its action.


## DoroShell Panel development

A separately built native LXQt Panel prototype now provides a hidden-tray arrow and popup, native grouped tasks and a reversible next-login profile migration from DockBarX. The current desktop is not switched automatically. Its unified pinned/running icons launch through GIO, reuse matching application buttons and save dragged pin order across panel restarts. The pink glass-like styling follows the supplied concept. See [build, verification, limitations and rollback](panel/README.md). Broader application matching and final Windows 7 visual polish remain unfinished.


### Reorder Start pins

Start opens on **Pinned** in saved order. **Recent programs** opens a separate list when history has available apps. **All Programs** and search stay at the bottom.

Drag a pinned app before or after another pin in **Home** or **Pinned**. Escape cancels the drag. Search results and recent-only entries cannot be dragged. The right-click **Move pin up/down** commands remain available with keyboard menu navigation. Saved order survives reopening Start; existing favorites are backed up and concurrent edits are refused.

The opt-in `dbus-run-session -- python tests/check_start_drag_x11.py --run` check uses synthetic desktop entries and a temporary favorites file. It moves the real pointer, then restores it. It verifies reorder, Escape cancellation, keyboard movement, persistence, All Programs/Back navigation, search focus, click-away dismissal, and no accidental app launch.


### Capture an open Start menu

Press **Print Screen** with Start open or closed. Drag to select, drag inside the selection to move it, or pull its handles to resize. The toolbar reports the selected size in pixels. Choose an annotation tool above the selection. **Color** sets the ink or highlighter color, and the width control sets the stroke in pixels. Each mark retains the settings it was drawn with. Ctrl+Z undoes an annotation and Ctrl+Shift+Z redoes it.

**Enter**, **Copy**, or **Ctrl+C** copies the selection, or the full desktop when there is no selection. **Save** or **Ctrl+S** saves the final pixels as a PNG and copies them. Cancelling the save dialog returns to editing. **Escape** or **Cancel** closes the overlay and preserves the clipboard. On X11 a separate owner supplies the image after the editor exits and releases it when replaced.

**Open in ScreenGrab** imports the exact cropped and annotated pixels into the native LXQt window. Its Copy and Save actions work on that image. To enable the importer on another installation, build the pinned ScreenGrab source in an empty user directory and apply the screenshots module with the resulting executable:

```sh
python screengrab/build.py --work "$HOME/.local/share/doroshell/screengrab-import-build"
python setup.py screenshots --apply --native-preview "$HOME/.local/share/doroshell/screengrab-import-build/build/screengrab"
```

This build requires the ScreenGrab 3.2.0 development dependencies, including CMake, Ninja, Qt 6, lxqt-build-tools, libqtxdg, LayerShellQt, KWindowSystem and XCB development files. If using the build-tools prefix from the panel build, set `CMAKE_PREFIX_PATH` to its `deps` directory for the build command. The installer manages a private executable and keeps the system ScreenGrab package. The overlay’s Copy and Save work independently of the importer. [Screenshot verification and limits](docs/screenshot-verification.md).

### Readability and reference behavior

Body text inherits the system font size. Pink surfaces use dark plum text, the darker places pane uses light text, and dropdown selected/disabled states have explicit colors. Contrast regression checks cover menu/settings text and the native panel gradient; rendered light/dark palettes and 16-point body text were inspected. Long app names elide instead of creating horizontal scrolling. Custom third-party widget/theme combinations still need broader testing.

Behavior follows the [original Windows 7 taskbar guidance](https://learn.microsoft.com/en-us/windows/win32/uxguide/winenv-taskbar) and [Classic/Open-Shell customization reference](https://www.classicshell.net/faq/), while the supplied concept sets the pink/Doro appearance. Native Windows-only integrations remain listed separately in the parity plan.

At the pin-editor and capture checkpoint, 61 automated tests passed. Separate native pin-editor input checks passed offscreen and on X11. A real Print/region/Enter/Escape check verified open-menu pixels and no selected-app launch, using temporary PNG output and confirming the existing clipboard was unchanged. A separate private-X11 test then exercised the production clipboard path: successful capture, mid-drag cancellation retaining the image, actual Writer/Draw Paste with matching pixels, and clipboard-owner exit after replacement. No login or clean-install test is implied.


### Isolated clipboard-paste acceptance

```sh
python tests/check_menu_clipboard_x11.py --run --xvfb /path/to/Xvfb
```

Requires Xvfb, xauth, Python Xlib/PySide6, and LibreOffice with Python UNO. The test creates an authenticated private X11 display with TCP disabled, a private D-Bus session, temporary homes and separate LibreOffice profiles. It never connects to the personal display or clipboard. It runs the production menu-capture helper without the file-output test sink, checks cancellation before selection and during a later drag, then pastes the completed 120×90 image into Writer and Draw and checks every exported pixel. Finally it replaces the private clipboard and verifies the helper releases ownership and exits.

The test display is an isolated acceptance environment, not a clean CachyOS installation. No system package installation is performed by the test.


### Categorized Settings acceptance

```sh
python tests/check_settings_pages_x11.py --run --xvfb /path/to/Xvfb
```

On the same private-display harness, real pointer and keyboard events exercised category navigation and retained selections. Preview left the temporary MIME configuration unchanged; Apply created the selected module's backup and association; Restore returned the original configuration exactly. The personal home and defaults were not changed. Category normal/selected/hover colors pass contrast checks, and all five pages were visually inspected with 16-point system text and a dark palette.


### Split session and power controls

The main **Shut down…** button asks for confirmation, with **Cancel** selected by default. Its adjacent arrow offers Lock screen, Log out, Sleep, Hibernate, Restart, and the full native LXQt session dialog. Shutdown, restart, logout, sleep and hibernate always use DoroShell's confirmation; Escape returns to Start. Actions use installed LXQt desktop entries through GIO and never enter recent-program history. Missing desktop entries are disabled; hardware and session support remain delegated to LXQt.

This confirmation does not change LXQt preferences: [LXQt's manual](https://github.com/lxqt/lxqt-session/blob/master/lxqt-leave/resources/lxqt-leave.1) explains that argument-based actions may otherwise run directly depending on its confirmation setting.

```sh
python tests/check_power_controls_x11.py --run --xvfb /path/to/Xvfb
```

The private-display test exercises the split menu, keyboard selection, Cancel-default prompts, Escape, and a confirmed fake dispatch. Every GIO session lookup is replaced by a test dispatcher. **No real lock, sleep, logout, restart or shutdown action is executed by these tests.** Automated tests also cover missing/unknown actions, duplicate-dispatch prevention and exclusion from recent-app history.

### Recent programs

Under **Start → Menu options → Recent program count**, choose 5, 10, 15, 20, 30 or 50 programs. Existing preferences default to 20. Lowering the count immediately trims the oldest entries. Turning off **Remember recent programs** clears the active list and stops recording launches. Earlier preference backups can still contain history.

The private X11 check uses pointer input to change the count and verifies the selection after reopening Start. Run it with `python tests/check_recent_controls_x11.py --run --xvfb /path/to/Xvfb`.
