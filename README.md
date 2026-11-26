# DoroShell

DoroShell gives an LXQt/X11 desktop a Windows 7-style Start menu and taskbar. The default Doro theme is pink. The hidden-icons arrow opens applications near the calendar clock. **Wi-Fi & Network** shows nearby networks and phone hotspots, asks for a password when needed, and offers Connect, Disconnect and Forget from a connection’s right-click menu.

<img src="assets/doro/start.png" alt="Doro Start artwork" width="130">

You can choose a personal portrait in DoroShell Settings. Bundled fan artwork and wallpaper media retain their recorded provenance and separate licensing status. [Artwork catalog](docs/assets.md)

## Install or update

Run this from your normal user account on an Arch-based LXQt/X11 desktop using Openbox. The installer checks the packages needed for the native build. Pacman shows any proposed system upgrade before installing missing prerequisites. Allow time for the first build of the patched LXQt components.

```sh
bash -c 'f=$(mktemp) || exit 1; trap '\''rm -f -- "$f"'\'' EXIT; curl -fsSL https://raw.githubusercontent.com/LaAutista/DoroShell/main/bootstrap.sh -o "$f" && bash "$f" --apply'
```

On a computer with an existing native installation, run:

```sh
~/.local/bin/doroshell-update
```

The installation command also recognises an RC2 installation and migrates the launcher files it owns. Saved pins, recent programs and personal settings stay in the account. If migration reports an edited launcher or an unfinished RC2 transaction, it names the conflict. [RC2 migration and undo](native/migration/README.md)

To preview prerequisites before applying, use `--plan` in place of `--apply`. With several LXQt panels, add `--panel panel2` to choose your panel on first installation. Log in again when ready to start the new panel, desktop and background helpers.

For a smaller installation, add `--modules menu` to install Start by itself. To add clipboard history to the full setup, use `--with clipboard`. Optional settings keep their own rollback records. [Module reference](native/modules/README.md)

## Using the desktop

- **Start** opens to Pinned. Recent programs, All Programs and search have separate places in the menu. Drag an application to the taskbar to pin it or to the desktop to create a shortcut.
- **Wi-Fi & Network** opens from Start or the taskbar. To join a phone hotspot, turn the hotspot on, choose its name under Available Wi-Fi, then click Connect.
- **Mouse and Touchpad** combines pointer settings and the acceleration switch. On a fresh installation, supported mice use a flat acceleration profile by default.
- **Display preferences** offers refresh-rate selection with a confirmation countdown. **Print** freezes the screen for selection, annotation, redaction, saving or copying.
- **Dolphin** uses Ark’s archive actions. **DoroShell Settings** provides theme, cursor, Start preferences and links to the native desktop tools.

## Recovery and removal

If an installation is interrupted, rerun the installation command with `--recover` in place of `--apply`. To return a native upgrade to the previous runtime, run:

```sh
~/.local/share/doroshell/native/current/bin/doroshell-maintenance rollback
```

To remove the native configuration, run `~/.local/bin/doroshell-remove`. On a migrated account this restores RC2 first. Running the restored removal command then removes RC2. Recovery checks the recorded files and reports conflicting personal edits.

## Building and testing

The native applications use C++20, Qt 6, GIO, libnm and X11. The bundle includes privately built LXQt panel, PCManFM desktop, pointer settings and ScreenGrab components. See the [native build and verification notes](docs/native-rewrite.md) for CMake commands and test coverage. The development channel tracks `main`.
