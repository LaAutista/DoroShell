# DoroShell

DoroShell enhances **LXQt on X11** with a Windows 7-inspired Start menu and taskbar,
Doro themes and loading cursors, screenshots, folder browsing, and optional clipboard,
wallpaper and display controls. It is a customization/setup toolkit, not a replacement
desktop environment. No compositor is required. Development is ongoing.

<img src="assets/doro/start.png" alt="Bundled Doro Start artwork" width="130">

## Install on an Arch-based LXQt computer

From your normal user account in an initialized **LXQt/X11 + Openbox** session:

```sh
bash -c 'set -e; command -v gh >/dev/null || sudo pacman -Syu --needed github-cli; gh auth status --hostname github.com >/dev/null 2>&1 || gh auth login --hostname github.com --git-protocol https --web; f=$(mktemp); trap "rm -f -- \"$f\"" EXIT; gh api repos/LaAutista/DoroShell/contents/bootstrap.sh -H "Accept: application/vnd.github.raw+json" > "$f"; bash "$f" --apply'
```

The repository is currently **private**: sign in with a GitHub account that has
access when prompted. The command installs GitHub CLI if missing, then downloads
the complete installer before executing it. It fetches a specific Git
revision into a permanent user source directory, and verifies its source/asset
inventory. It installs the core modules: Start/settings, native taskbar/tray, themes,
loading cursors, snapping, a single desktop (multiple desktops off; re-enable in
DoroShell Settings), screenshots, and update/removal commands. Missing official
packages are offered through `sudo pacman -Syu --needed`; **review pacman's full-system
update prompt**. There is no AUR helper, unattended package approval, or package removal.

Desktop components are staged for your **next normal login**. The installer never logs
you out, restarts the panel/desktop, changes refresh rate/VSync, or closes applications.
Existing custom module choices and unrelated settings are preserved; conflicts stop
with recovery information. Preview by replacing `--apply` with `--plan`.

**This is a development installer, not a clean-machine-certified stable release.**
Temporary-home install/repeat/upgrade/recovery/removal and build checks are recorded
in [STATUS](docs/STATUS.md). Actual clean Arch/CachyOS/EndeavourOS installation and normal
login remain unverified. Supported configuration capabilities are checked; arbitrary
LXQt layouts, custom XDG roots and Wayland are not claimed to work. The same checks
apply to other Arch derivatives. [Full installation and troubleshooting](docs/INSTALL.md).

## Clone, choose modules, update or remove

```sh
gh repo clone LaAutista/DoroShell
cd DoroShell
python deploy.py                              # inspect platform/packages/modules
python deploy.py --apply                      # same core installer as bootstrap
python deploy.py --modules menu --apply       # scoped Start/settings installation
python deploy.py --with clipboard --apply     # optional session-only history
python deploy.py --with wallpaper --apply     # native Background controls; video stays opt-in
python deploy.py --with display --apply       # optional guarded Advanced controls
```

Keep the source checkout if installing directly from it; maintenance commands refer
to it. Bootstrap stores revisions under `~/.local/share/doroshell/sources/` for you.
Use `doroshell-update` (or rerun the one-command installer) to retrieve current main.
Use `doroshell-remove` for first-install restoration, or the exact `deploy.py --apply
--undo TRANSACTION` command printed by an upgrade to restore its preceding state.
Neither operation deletes your application history, media, saved backups or build trees.
User-edited managed files cause a refusal. [Recovery details](docs/INSTALL.md#recovery).

`main` is the **development** channel. `--channel stable` requires a published `stable`
tag whose `release.json` declares stable; none is advertised yet. `--ref COMMIT` or
`--ref TAG` pins a reviewed source version. Do not use the old core-candidate tag as
though it contains this installer.

## Features and optional modules

- Ranked installed-app search, keyboard navigation, safe GIO launching, pins, folder
  cascades, portrait cropping and path-free preference export/import.
- Opt-in [Mouse & Touchpad preferences](docs/input-preferences.md) in DoroShell
  Settings: supported evdev acceleration profiles, guarded touchpad disabling,
  login persistence and conflict-checked restoration, with a native LXQt settings link.
- Native grouped tasks, drag-to-pin, notification overflow, calendar, Show Desktop,
  density controls and an unbound configurable tray shortcut.
- Editable screenshots, annotations, window/area capture and cancellable delayed recapture.
- Four coordinated themes, existing Doro artwork and animated loading cursors.
- Optional clipboard history in memory, wallpaper-derived glass without a compositor,
  and a separate video decoder with Off/pause/mute/volume controls.
- Optional display controls with a separate guard, visible failures and bounded redacted
  diagnostics. **Physical NVIDIA transition/recovery mismatch remains unresolved.**
  Private fake-driver tests do not establish automatic hardware rollback. See
  [display scope and remaining risk](display/README.md).

Video playback and sound are not automatically enabled. The selected original artwork,
GIF/APNG sources, static wallpaper and optional video are included in `assets/`;
[asset catalog/provenance](docs/assets.md). The source license is **GPL-2.0-or-later**,
with component exceptions and third-party notices preserved. This does not license
third-party character artwork; owner-directed artwork review remains separate.
[Licensing](LICENSING.md). The checkout includes about 80 MB of artwork/video.

## Continue development on another computer

Start with [HANDOFF](docs/HANDOFF.md), then [AGENTS](AGENTS.md),
[ARCHITECTURE](docs/ARCHITECTURE.md), [STATUS](docs/STATUS.md),
[MODULES](docs/MODULES.md), [DEVELOPMENT](docs/DEVELOPMENT.md) and
[ROADMAP](docs/ROADMAP.md). The [detailed feature guide](docs/FEATURE-GUIDE.md)
retains existing behavior and historical evidence. [Changelog](CHANGELOG.md).

```sh
python source_release.py
python -m unittest discover -s tests -v
```

Tests use mocks, offscreen Qt and disposable homes. Opt-in native X11 checks use a
private display. Never run tests by changing a personal monitor, clipboard, session,
locker or power state. There is no claim of universal LXQt/Wayland compatibility,
completed Open-Shell parity, or a finished project.
