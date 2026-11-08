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
python integrate.py --apply --live      # make it the Start button
```

`--live` briefly stops and restarts only the panel and global shortcut service so they cannot overwrite the saved changes. It does not restart your session or close applications. Give the components a moment to become ready. When neither component is running, omit `--live`. The current implementation assumes standard `/usr/bin` component paths and default home-directory XDG layout.

The legacy `lxqt-comfort` filenames are retained for compatibility with the prototype. DoroShell installs `start_menu.py`, `start.svg`, a launcher, and an application desktop entry under `~/.local`. Favorites live in `~/.config/lxqt-comfort/favorites.json`.

## Backups and rollback

Installation records original managed contents and modes in `~/.local/state/lxqt-comfort/menu-install.json`. Panel/shortcut integration records full original configuration text and per-key before/after values in `menu-integration.json` in the same directory. Keep these manifests private: they can contain personal configuration. Repeated installs are supported; conflicting edits to managed files or keys are refused.

Rollback integration **before** removing its launcher:

```sh
python integrate.py --rollback --live
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
- Implement the persistent single-desktop module; see [scope](docs/roadmap.md).
- Screenshots and clipboard workflow.
- Taskbar behavior and window icons.
- Edge-drag tiling with the actual window manager.
- Dolphin defaults and application file associations.
- Broader desktop compatibility and complete installer orchestration.

Only the Start menu and panel integration are implemented here. No blanket desktop replacement, workspace reset, or future module is run by these commands.

Source licensing has not yet been selected; private access does not itself grant redistribution rights. Choose a source license before a public release.
