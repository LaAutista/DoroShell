# DoroShell

DoroShell enhances **LXQt on X11** with a Windows 7-inspired Start menu and taskbar,
Doro themes and loading cursors, screenshots, folder browsing, and optional clipboard,
wallpaper and display controls. It is a customization/setup toolkit, not a replacement
desktop environment. No compositor is required. Development is ongoing.

<img src="assets/doro/start.png" alt="Bundled Doro Start artwork" width="130">

## Install on an Arch-based LXQt computer

From your normal user account in an initialized **LXQt/X11 + Openbox** session:

```sh
bash -c '
set -e
[[ $EUID != 0 ]] || { echo "Run as your normal desktop user, not root." >&2; exit 1; }
apply=false; plan=false; allow_packages=true
forwarded=("$@")
invalid() { echo "Download arguments: $1. No prerequisites requested." >&2; exit 2; }
while (($#)); do
    case "$1" in
        --apply) apply=true; shift ;;
        --plan) plan=true; shift ;;
        --no-packages) allow_packages=false; shift ;;
        --panel)
            (($# >= 2)) && [[ "$2" =~ ^panel[1-9][0-9]*$ ]] || invalid "Use --panel panelN"
            shift 2 ;;
        *) invalid "Use only --apply or --plan, --no-packages and --panel panelN; advanced options require local bootstrap/deploy" ;;
    esac
done
"$apply" && "$plan" && invalid "--apply cannot combine with --plan"
if ! command -v curl >/dev/null; then
    echo "Prerequisite plan: sudo pacman -Syu --needed curl" >&2
    echo "This may update the whole system before DoroShell validation. Review pacman approval; decline to cancel." >&2
    "$apply" && "$allow_packages" || { echo "Plan only or --no-packages; no packages changed. Use --apply or install curl separately." >&2; exit 1; }
    command -v sudo >/dev/null && command -v pacman >/dev/null || {
        echo "Automatic prerequisites require sudo and Arch pacman; no download performed." >&2; exit 1;
    }
    sudo pacman -Syu --needed curl
    command -v curl >/dev/null || { echo "curl is still unavailable; stopping before download." >&2; exit 1; }
fi
f=$(mktemp)
trap "rm -f -- \"$f\"" EXIT
curl --fail --location --silent --show-error https://raw.githubusercontent.com/LaAutista/DoroShell/main/bootstrap.sh --output "$f"
bash "$f" "${forwarded[@]}"
' doroshell --apply
```

This downloader accepts only `--apply` or `--plan`, optional `--no-packages`, and
`--panel panelN` with a separate value. Invalid/conflicting arguments stop before
any download or prerequisite prompt. Use local `bootstrap.sh` or `deploy.py` for
advanced module, channel, guidance or maintenance options; see below.

The repository is **public**: no GitHub account, token or GitHub CLI is needed.
The command downloads the complete installer before executing it,
and fetches a specific Git revision into a permanent user source directory, then
verifies its source/asset inventory. It installs the core modules: Start/settings,
native taskbar/tray, themes,
loading cursors, snapping, a single desktop (multiple desktops off; re-enable in
DoroShell Settings), screenshots, and update/removal commands. Missing prerequisites
are offered in stages: curl for the download, Git/Python for
source acquisition, then PySide6/GIO if needed to validate an explicit panel choice.
Each stage prints its package command before invoking `sudo pacman -Syu --needed`;
**review pacman's full-system update prompt, or decline to cancel**. Prerequisite
installation may update the system before a layout can be checked; no DoroShell
configuration is written until that check passes. Selected module/runtime/build
packages follow validation. There is no AUR helper, unattended approval or package removal.

Desktop components are staged for your **next normal login**. The installer never logs
you out, restarts the panel/desktop, changes refresh rate/VSync, or closes applications.
Existing custom module choices and unrelated settings are preserved; conflicts stop
with recovery information. Preview by changing the final `doroshell --apply` to
`doroshell --plan`; missing prerequisites are reported without authentication or
installation. Bootstrap plan can download/cache source when its tools are present.

**This is a development installer, not a clean-machine-certified stable release.**
Temporary-home install/repeat/upgrade/recovery/removal and build checks are recorded
in [STATUS](docs/STATUS.md). Actual clean Arch/CachyOS/EndeavourOS installation and normal
login remain unverified. Supported configuration capabilities are checked; arbitrary
LXQt layouts, custom XDG roots and Wayland are not claimed to work. The same checks
apply to other Arch derivatives. [Full installation and troubleshooting](docs/INSTALL.md).

## Clone, choose modules, update or remove

```sh
git clone https://github.com/LaAutista/DoroShell.git
cd DoroShell
python deploy.py                              # inspect platform/packages/modules
python deploy.py --apply                      # same core installer as bootstrap
python deploy.py --modules menu --apply       # scoped Start/settings installation
python deploy.py --with clipboard --apply     # optional session-only history
python deploy.py --with wallpaper --apply     # native Background controls; video stays opt-in
python deploy.py --with display --apply       # optional guarded Advanced controls
python deploy.py --modules start-shortcut     # optional Alt+F1 plan; includes menu
```

Alt+F1 is **opt-in**. The shortcut plan shows the current binding; an existing custom
action requires the explicit `--replace-start-shortcut` choice as well as `--apply`.
It saves for normal shortcut-daemon startup without reloading it. Read the
[ownership and restoration limits](docs/INSTALL.md#optional-altf1-start-shortcut) before applying.

For a standard multi-panel layout, explicitly choose the existing panel ID with
`--panel panel2` (also accepted by bootstrap). Preview first; apply retains other
panel/plugin sections and the chosen panel's geometry. Selection validation requires
PySide6 and GIO; apply can offer their packages, then recheck the panel.
Repeat/recovery uses the recorded choice; no panel
is guessed or silently changed. [Selection and limits](docs/INSTALL.md#explicit-panel-selection).

For package guidance from an existing checkout, without downloads, platform probes
or user-state reads, run `python -B deploy.py --prerequisites --modules menu` (omit
`--modules` for core). It prints separate acquisition, panel-validation and selected
module packages. This is guidance, not an installation or readiness check. The
normal-user flow requires working Arch `pacman` and `sudo`; it never configures
administrative access. See [prerequisite stages](docs/INSTALL.md#prerequisite-stages).

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
