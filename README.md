# DoroShell

**DoroShell is an LXQt customization/setup toolkit with Plasma-like features**, inspired by familiar Windows and Plasma workflows. It configures and extends an existing LXQt installation; it is not a standalone desktop environment or a replacement shell.

The first module is a two-column Qt Start menu: application search, categories, pinning, personal-folder links, LXQt settings, and a session/power dialog. A dedicated LXQt Quick Launch button and Alt+F1 open it. Alt+F1 again or Escape closes it. The original Fancy Menu preferences are retained for rollback.

## Status and support

Early working prototype. Developed on CachyOS LXQt 2.4 / X11 with Openbox and Python 3.14. The repository version has been tested with automated offscreen tests and temporary installation homes. Its predecessor was exercised on a live LXQt session, including panel activation and keyboard toggling. **No fresh-install VM, logout/login, Wayland, or other-distribution validation has been completed.**

Integration currently expects `panel1`, the Fancy Menu plugin, and the standard `Alt+F1.1` Fancy Menu shortcut. It rejects custom shortcut mappings and unsupported layouts rather than replacing them silently. Other LXQt layouts need inspection and adaptation. Multi-monitor/panel-edge positioning and long-session behavior need more testing. Folder links respect the existing default file manager; this module does not install or select Dolphin.

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

The working-tree menu now includes the pink theme, Home / All programs navigation, ordered pins, optional recent programs, and the folder editor. Its compact right-column controls leave all six default folders visible at the default 680×570 size; smaller windows retain scrolling. Automated geometry checks cover three window sizes. Offscreen rendering was visually inspected. The updated menu and DoroShell Settings launcher are installed locally; the personal Start icon, cursor, favorites, panel configuration and default-app choices were preserved.

`setup.py` selects menu, panel, snapping, screenshots, Kate/Dolphin associations and per-app dark themes, single-desktop, taskbar and optional cursor modules. The default selection is only the menu; all desktop/default-app changes require explicit selection. With no action flag it previews changes. `--packages` only prints an Arch/CachyOS package command; it does not execute it. Do not apply the all-module preset as a substitute for reviewing each component. Existing desktop settings and artwork must be preserved when upgrading a personal installation.

The additional modules remain experimental. Geometry/helper tests and temporary-home apply/repeat/rollback checks are not fresh-install, post-login, multi-monitor, or real screenshot-paste validation. No desktop session is restarted by tests. The original roadmap and Windows 7 comparison document retain the design and acceptance requirements; some implementation has moved ahead of those planning snapshots.

Latest validation: **42 automated tests pass** using offscreen Qt and temporary homes. Real X11 checks also exercised the menu search, the Qt folder picker, settings apply/restore, left/right mouse-drag snapping and geometry restoration on a test window, and click-to-restore on an isolated native LXQt icon taskbar. ScreenGrab capture → cancel → capture produced the expected 120×90 image; isolated LibreOffice Writer and Draw instances both pasted it with matching dimensions and pixels. The early sandbox-only X11 startup failure was resolved by running the authorized desktop tests outside the sandbox, without changing display permissions. [Detailed test scope and remaining gaps](docs/verification.md).

Kate/Dolphin opt-in defaults resolved correctly through both xdg-mime and GIO in a temporary home; separate test instances visibly used dark colors. Personal defaults were not changed. Fresh-login, clean-install, Wayland and multi-monitor validation remain outstanding. No desktop session was restarted.

## DoroShell settings

Run `python setup.py --gui` from the checkout, or **DoroShell Settings** after installing/updating the menu. It is also available under Start → Menu options. Every option begins at **Keep unchanged**. Choose the components you want, preview, then apply. Existing rollback manifests enable **Restore previous settings**. Modules apply sequentially; if one fails, the log identifies it and earlier successful modules can be restored individually.

- **Taskbar:** grouped application icons or LXQt icons with labels. This uses LXQt's native taskbar: click an open app's icon to activate/restore it; grouped windows use LXQt's group UI. Launch closed apps from Start or existing Quick Launch icons. Existing Quick Launch entries remain; this is not Plasma's unified pinned-launcher/task-manager plugin. The explicit option can detach a known DockBarX entry while retaining its configuration for rollback.
- **Snapping:** Openbox/X11 mouse-drag left/right halves, plus Super+Left/Right and Super+Down to restore. Existing conflicting bindings are refused. Enable the refresh checkbox to start the helper now; otherwise it starts at the next login.
- **Screenshots:** Print uses ScreenGrab region selection. Drag, then Enter to confirm; Escape cancels. The helper owns the completed clipboard image until replaced, so pasting works after ScreenGrab exits. Other capture modes are not exposed yet.
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

`cursor.py` creates an inherited Breeze theme that replaces only wait/watch and progress/left_ptr_watch. The progress cursor retains the original Breeze arrow and hotspot. All other shapes come from Breeze. It accepts a local animated GIF, preserves frame timing, and builds 24/30/32/48/64-pixel Xcursors with Pillow (distribution package `python-pillow`); no compiler or xcursorgen is required. No artwork is included or uploaded.

```sh
python cursor.py --gif /path/to/personal-animation.gif          # preview planned files
python cursor.py --gif /path/to/personal-animation.gif --apply
python cursor.py --rollback
```

The module updates the LXQt cursor theme, the user default cursor theme, and the Xresources theme entry. It preserves cursor size and the rest of each configuration file. Original bytes/modes are backed up in `~/.local/state/lxqt-comfort/cursor-install.json`. Repeat application is supported. Rollback refuses any managed file changed since installation rather than overwriting personal edits. Keep that private backup. There is no automatic package installation or session restart. Restart applications that cache cursors; log out and back in when convenient for consistent session-wide pickup. The installer does not force-refresh running applications or the X server resource database. Automated tests use temporary homes and synthetic artwork; live X11 validation is separate. Wayland is untested.

## Edit the Start menu's folder links

Choose **Edit folder links…** beneath the folder list. Add folders with the folder picker; double-click a Name cell (or press F2) to rename it; use Move up/Move down to reorder; uncheck Show to hide a link; or Remove to remove the shortcut only. No folder or file is deleted. Restore defaults prepares the original six standard links. **Save** applies changes; Cancel or Escape discards them.

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

Drag a pinned app before or after another pin in **Home** or **Pinned**. Escape cancels the drag. Search results and recent-only entries cannot be dragged. The right-click **Move pin up/down** commands remain available with keyboard menu navigation. Saved order survives reopening Start; existing favorites are backed up and concurrent edits are refused.

The opt-in `dbus-run-session -- python tests/check_start_drag_x11.py --run` check uses synthetic desktop entries and a temporary favorites file. It moves the real pointer, then restores it. It verifies reorder, Escape cancellation, keyboard movement, persistence, and that dragging never launches an app.


### Capture an open Start menu

With DoroShell Start open, press **Print Screen**. DoroShell snapshots the screen before releasing the menu, then opens a region selector over that snapshot. Drag a region and press **Enter** or **Copy** to confirm. **Escape** or **Cancel** leaves the clipboard unchanged; selecting a region alone does not copy it. The captured pixels retain the open menu.

This does not change the global Print binding used when Start is closed. It is validated on a single-screen X11 session; Wayland and mixed-DPI/multi-monitor capture remain unverified. The capture process stays alive only to serve its clipboard image until another owner replaces it. The file-output test path never writes the real clipboard.

### Readability and reference behavior

Body text inherits the system font size. Pink surfaces use dark plum text, the darker places pane uses light text, and dropdown selected/disabled states have explicit colors. Contrast regression checks cover menu/settings text and the native panel gradient; rendered light/dark palettes and 16-point body text were inspected. Long app names elide instead of creating horizontal scrolling. Custom third-party widget/theme combinations still need broader testing.

Behavior follows the [original Windows 7 taskbar guidance](https://learn.microsoft.com/en-us/windows/win32/uxguide/winenv-taskbar) and [Classic/Open-Shell customization reference](https://www.classicshell.net/faq/), while the supplied concept sets the pink/Doro appearance. Native Windows-only integrations remain listed separately in the parity plan.

Current increment: 55 automated tests passed. Separate native pin-editor input checks passed offscreen and on X11. A real Print/region/Enter/Escape check verified open-menu pixels and no selected-app launch, using temporary PNG output and confirming the existing clipboard was unchanged. No login or clean-install test is implied.
