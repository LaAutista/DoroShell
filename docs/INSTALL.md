# Installation, update and recovery

## Supported starting point

Use a normal user account that has already started an LXQt/X11 session on Arch,
CachyOS or EndeavourOS. Other Arch derivatives pass the same capability checks.
Core setup currently needs a single `panel1` and Openbox configuration. Missing or
custom layouts produce a specific refusal. DoroShell does not install a display
manager, switch desktop environments, or claim Wayland support. Custom XDG roots
remain unsupported by the older installation adapters and are refused explicitly.

The exact bootstrap command is in [README](../README.md). It downloads to a temporary
file before execution, fetches the complete Git revision, checks its inventory and
keeps the source at `~/.local/share/doroshell/sources/COMMIT`. About 80 MB of bundled
artwork/video is included. No runtime binaries are downloaded. A direct clone works
too; keep that checkout because maintenance launchers reference it.

## Preview, installation and package boundaries

`python deploy.py` reports the distribution/session, selected modules and installed
package versions without changing files. `--apply` performs the plan. `--modules`
selects a scope; without it, an existing deployment reuses its recorded module set,
and a first installation uses `core`. `--with clipboard`, `--with wallpaper`,
`--with wallpaper-glass` and `--with display` add optional components. Display is
part of the wallpaper native build; clipboard needs the native panel and Start.
`--theme windows|polar|heretic|spring` selects the initial theme. Existing theme,
cursor and glass selections are retained on update; change them explicitly in
Settings or with the existing `setup.py` interface.

Missing official packages trigger `sudo pacman -Syu --needed ...` and pacman's
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

## Recovery

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

Recovery uses the recorded module set/theme/action and existing module conflict
checks; it does not discard user edits. Cursor writes now retain pending hashes/modes for retry and use atomic records. A corrupt
manifest still requires manual inspection; keep the journal and originals.
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
