# Installation, update and recovery

## Supported starting point

Use a normal user account that has already started an LXQt/X11 session on Arch,
CachyOS or EndeavourOS. Other Arch derivatives pass the same capability checks.
Core setup needs Openbox configuration and either a single `panel1` or an explicitly
selected panel in a supported standard layout. LXQt's default layout without a
`panels=` line counts as a single `panel1`. Missing or ambiguous layouts produce a
specific refusal. DoroShell does not install a display
manager, switch desktop environments, or claim Wayland support. Custom XDG roots
remain unsupported by the older installation adapters and are refused explicitly.

The repository is public. The bootstrap command in [README](../README.md) uses
`curl`, Git and Python and requires no GitHub account, token or GitHub CLI. The apply
flow offers missing prerequisites with normal pacman approval. Git fetch uses anonymous
HTTPS with credential helpers disabled for that command; persistent Git configuration
is unchanged. Prerequisite installation is a separate stage before layout validation;
it never authorizes writing an unvalidated DoroShell profile. Plan mode and
`--no-packages` report missing tools without authentication or package execution.
The command downloads to a temporary
file before execution, fetches the complete Git revision, checks its inventory and
keeps the source at `~/.local/share/doroshell/sources/COMMIT`. About 80 MB of bundled
artwork/video is included. No runtime binaries are downloaded. A direct clone works
too; keep that checkout because maintenance launchers reference it.

## Preview, installation and package boundaries

`python deploy.py` reports the distribution/session, selected modules/panel and installed
package versions without changing files. `--apply` performs the plan. `--modules`
selects a scope; without it, an existing deployment reuses its recorded module set,
and a first installation uses `core`. `--with clipboard`, `--with wallpaper`,
`--with wallpaper-glass` and `--with display` add optional components. Display is
part of the wallpaper native build; clipboard needs the native panel and Start.
`--theme windows|polar|heretic|spring` selects the initial theme. Existing theme,
cursor and glass selections are retained on update; change them explicitly in
Settings or with the existing `setup.py` interface.

After layout validation, missing selected module packages trigger `sudo pacman -Syu --needed ...` and pacman's
normal confirmation. `--no-packages` refuses instead. This updates the whole system
when necessary; it is not an isolated Python dependency installation. No AUR
helper or repository is added. Packages are never removed during DoroShell rollback.
[Arch's partial-upgrade guidance](https://wiki.archlinux.org/title/System_maintenance#Partial_upgrades_are_unsupported)
explains why `pacman -Sy PACKAGE` is not used.

The package list derives from `setup.PACKAGES`, plus native build dependencies in
`deploy.py`. Core uses Python/PySide6/GIO, Pillow/Breeze cursors, LXQt/Openbox and
Xlib. Native builds use C/C++, Git, CMake/Ninja, pkgconf, Qt6 development tools,
LXQt libraries, KWindowSystem, LayerShellQt and the panel's plugin dependencies.
Wallpaper additionally uses libfm-qt and Qt Multimedia/FFmpeg. Packages were checked
against [Arch panel metadata](https://archlinux.org/packages/extra/x86_64/lxqt-panel/)
and [PCManFM metadata](https://archlinux.org/packages/extra/x86_64/pcmanfm-qt/).
Repository availability and ABI compatibility are checked again on the target.

Builders use private versioned directories under `~/.local/share/doroshell/builds/`.
An incomplete build is retained with its error; move that failed build aside before
retrying. Never remove a runtime used by a running/staged panel. Source changes or
package-version changes produce a different build directory. Reused payloads are
hash-checked. System LXQt binaries remain installed.

Configuration adapters retain unrelated keys and first-install originals. The
native panel adds Start and tray integration to a separate profile. Existing custom
Alt+F1 mappings are not silently replaced: the new orchestration provides the Start
button; use the existing reviewed shortcut-integration workflow separately if needed.
Screenshots configure Print on disk; running shortcut daemons may require the next
normal login to pick up changes. No process is restarted by `deploy.py`.

## Prerequisite stages

The README block is one copy-paste command. It assumes Arch's base Bash/coreutils
(`mktemp`, `rm`, `mkdir`, `mv`) and an initialized LXQt/X11 desktop. Run it as the
normal desktop user with working `sudo` and Arch `pacman`; it does not configure administrative access. It
prints each missing-prerequisite plan before invoking sudo/pacman. Authentication
and pacman's ordinary confirmation remain interactive; there is no `--noconfirm`,
credential handling, AUR helper or fallback privileged shell.

| Stage | Official Arch packages | When needed |
| --- | --- | --- |
| Web download | `curl` | README command only; a local bootstrap script uses Git directly |
| Source acquisition | `git python` | Bootstrap before source download/verification |
| Explicit panel validation | `pyside6 python-gobject` | Missing/broken QtCore or GIO imports for a selected `--panel`; checked before DoroShell configuration writes |
| Selected modules/build | Derived from `setup.PACKAGES` and native builder requirements | After platform and panel validation; optional modules only when selected |

Each command has the form `sudo pacman -Syu --needed PACKAGE...`, for example
`sudo pacman -Syu --needed curl git python` or
`sudo pacman -Syu --needed pyside6 python-gobject`. These are full-system updates,
not isolated Python installs. Arch's [pyside6](https://archlinux.org/packages/extra/x86_64/pyside6/)
provides Qt bindings; [python-gobject](https://archlinux.org/packages/extra/x86_64/python-gobject/)
provides GIO and depends on GLib/introspection runtime packages.

**Prerequisites may be installed before the panel can be validated.** If validation
then refuses the layout, no DoroShell configuration is written, but successfully
installed packages/system updates are not rolled back. Declining authentication or
pacman, any command failure, or dependencies still unavailable afterward stops the
flow without a silent retry. An interrupted package operation needs normal package
manager inspection; DoroShell does not repair it automatically. A Python upgrade or
custom/virtual-environment interpreter can require rerunning with the system Python.
Known platform/layout errors still refuse before package offers when detectable.

Use the README block's final `doroshell --plan`, or `bash bootstrap.sh --plan`, for
preview. `--no-packages` also forbids prerequisite offers. When tools are missing,
these modes return nonzero with package guidance; they do not report install success.
Bootstrap plan may download/cache source once acquisition tools are present.

From an existing checkout, `python -B deploy.py --prerequisites --modules menu` prints
the separated package groups without importing GUI bindings, reading installed-user
state, checking packages or downloading anything. Omit `--modules` for core, or add
`--with` options explicitly. Its default is core, not the installed module selection;
it is guidance only and cannot combine with apply/remove/recover/undo. Ordinary
`deploy.py` plans still report platform issues and now explicitly label a blocked plan.

## Explicit panel selection

First-time native-panel setup can select a standard `panelN` by its existing INI ID:

```sh
python deploy.py --modules native-panel --panel panel2         # plan only
python deploy.py --modules native-panel --panel panel2 --apply
bash bootstrap.sh --panel panel2 --plan                       # core plan
bash bootstrap.sh --panel panel2 --apply
```

This reuses the [prepared-profile adapter](../panel/README.md#explicit-selection-in-a-multi-panel-profile).
The stock LXQt file is never written. Unselected panel/plugin sections and unrelated
settings remain byte-identical in the staged profile; selected geometry is retained.
The adapter requires a `panels=` list for multiple panels and unique widget ownership.
Wrong/missing panels, shared widgets and ambiguous syntax refuse before selected
module package offers, builds or managed-file writes. Validation prerequisites may
need the separately described earlier package stage. No panel is chosen automatically. Bootstrap
still downloads and caches the source before that validation.

PySide6 and GIO must be importable for explicit-selection validation. Apply can offer
their packages, then reruns the same validation; plan/`--no-packages` reports the
exact prerequisite command instead. The default single-panel1
workflow retains its existing behavior and geometry defaults.

Repeat and recovery reuse the saved panel choice; omit `--panel`. Scoped updates
retain that choice while native-panel remains installed. A different choice is
refused; restore the previous native-panel staging before choosing another panel.
Personal edits to the staged profile survive runtime upgrades but can block removal.
No new monitor mapping, custom-XDG adapter or actual multi-monitor/login acceptance
is claimed.

## One desktop and restoring multiple desktops

Fresh `core` installs include `single-desktop`; existing deployments keep their
recorded module selection. A scoped install such as `--modules menu` does not add it.
To opt in separately, use `python deploy.py --modules single-desktop --apply`.
Restore with `python deploy.py --modules single-desktop --remove --apply`, or
Settings → Taskbar & Windows → One desktop → Restore previous settings.
These commands save Openbox's desktop count and first desktop for the next normal
login. They do not migrate live windows or change the running desktop count;
`modules.py single-desktop --live` is explicitly refused. Conflicting personal edits
stop restoration. Disposable-file tests cover repeat, scoped XML edits and exact
restoration, not login or live keyboard/scroll-wheel behavior.

## Optional media and display controls

Artwork is included in the source tree. A fresh menu uses the bundled Start image;
cursor installation uses the transparent APNG. Existing custom Start art is retained.
The static wallpaper and video are available under `assets/wallpapers/`; choose them
through native preferences. Video and audio are not automatically enabled. Four
palette generators remain available, and custom portraits can be chosen in Start.

`--with wallpaper` stages native Background controls. `--with display` also builds
the guarded Advanced display UI. It does not set a mode or VSync during installation.
**Physical NVIDIA transition/recovery mismatch remains unresolved.** Do not infer
hardware rollback reliability from fake-driver tests. See [display diagnostics](../display/README.md).

### Duplicate app icons after an earlier install

Installs made before Quick Launch merging kept LXQt's Quick Launch bar next to the
DoroShell taskbar, so each pinned app also appeared as a separate running button.
From the source checkout:

```sh
python panel/profile.py preview-merge-quicklaunch   # list what would be pinned
python panel/profile.py merge-quicklaunch           # back up, then pin; next login
```

Folder links and custom commands stay in Quick Launch. The previous panel profile is
saved as `~/.local/state/doroshell/panel-before-merge-*.conf`. Because the profile now
differs from the installed one, restoring the stock panel later needs
`--keep-panel-edits`.

## Recovery

Mouse & Touchpad preferences are opt-in after installing the menu/toolkit. The
installer does not change input devices or enable login reapplication. Before
menu/toolkit removal or an undo replacing its input helper, use **Stop managing
and restore** on that DoroShell Settings page. Enabled choices, unresolved
restoration receipts or remaining owned autostart block removal. Missing devices,
unsupported restoration or external edits require inspection; the helper and
evidence stay available. Inactive saved choices, archived previous-session receipts
and the retained input lock survive removal. [Input lifecycle and limits](input-preferences.md).

Each deployment prints a transaction ID. Its private journal lives under
`~/.local/state/doroshell/deployments/ID/`. Backups can contain private configuration;
do not upload them. Exact undo for a completed upgrade:

```sh
python deploy.py --apply --undo ID
```

This checks every target's bytes and mode before restoring any file. An edit or
symlink causes refusal. Undo itself is resumable if interrupted. It restores the
prior manifests as well as program/config files. It does not remove packages,
source downloads, native builds or unrelated data, and does not refresh the session.

On a failed module operation, subsequent normal applies refuse the pending deployment.
After correcting the reported prerequisite, use the **same source revision**:

```sh
python deploy.py --apply --recover
```

Recovery uses the recorded module set/theme/action/panel and existing module conflict
checks. Journal formats 2 and 3 save each completed module's output bytes and modes;
recovery and finalization verify that evidence instead of adopting current edits.
Unknown versions, invalid progress/request/snapshot records, and changed completed
files are refused before recovery writes. Cursor writes retain pending hashes/modes
for retry and use atomic records.

If native-panel already completed, recovery does not require its separate stock LXQt
configuration to remain a single-panel layout: that completed step is skipped, so
recovery will not read or rewrite the stock profile. Its recorded managed files must
still match exactly. A second panel subsequently added to the stock file survives
recovery and exact undo. An interrupted first-time native-panel stage resumes its
saved preparation rather than treating a partly written manifest as a finished
installation. Its source, selected panel, prepared bytes and managed files must
still validate. Custom XDG roots remain refused. The same-source
requirement still applies; this change does not migrate pending journals from older
revisions or justify changing their recorded source hashes.

Explicit choices use deployment pointer format 2 and journal format 3. Older
installers refuse these versions; use this source or a compatible newer release.
Legacy single-panel transactions keep pointer format 1 and journal format 2.
No old pending transaction is silently migrated or assigned a guessed panel.

Legacy format-1 **pending** journals have no completed-step evidence and require
manual inspection; no safe history can be reconstructed from current files alone.
Valid completed format-1 journals retain their recorded exact-undo support, but
the new checks cannot retrospectively detect edits already adopted by an older
installer. New active-step retries retain their original snapshots and module
conflict checks. If an interrupted step changed a file also owned by a completed
step, or its declared target inventory changed, recovery conservatively refuses
the ambiguous state. A corrupt manifest also requires manual inspection; keep
the journal and originals.
Do not delete records to bypass refusal. Exact undo is available after a transaction
has completed/recovered; incomplete writes are never blindly assumed to be owned.

First-install restoration is different:

```sh
doroshell-remove
python deploy.py --modules clipboard --remove --apply   # only clipboard
```

Modules restore in dependency order, preserving user histories/media. Changed native
panel settings can block removal; the existing `panel/profile.py restore-next-login
--keep-panel-edits` workflow saves a private recovery copy. Legacy menu integration
must be restored before deleting its launcher. Optional component locks retain their
existing inodes. Empty directories, reference snapshots and journals may remain.

## Updates and channels

`doroshell-update` fetches the latest development revision in a new source directory.
It checks inventory and invokes the same installer. Scoped updates are supported
with `--modules menu` or another module. Native panel upgrades retain the configured
panel and change only the staged runtime reference. Unknown deployment schemas are
refused; no speculative migration or downgrade is attempted. Portable preferences
have their own validated format and import/restore lifecycle.

`release.json` labels this work development. The bootstrap accepts `--ref COMMIT|TAG`
for a reviewed version. `--channel stable` requires an actual `stable` tag and a
stable declaration; no current stable portable installer is claimed. Do not force
update a dirty source checkout. Baseline publication and normal Git history remain
recoverable independently of installed-user manifests.

## Verification boundary

Temporary homes, fake missing packages, mocked native executables, actual native
source builds and isolated checks are distinct from a clean OS. See [STATUS](STATUS.md).
This task did not install packages on the development host, change its settings,
restart applications, or run login/logout/reboot. Test the clean-system checklist in
[DEVELOPMENT](DEVELOPMENT.md) on a disposable Arch installation before promoting stable.
