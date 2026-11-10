# Clean-environment simulation and setup boundaries

These are disposable-home tests on the development host, **not a clean OS installation or normal-login acceptance**. Python `-S` hides site packages for dependency-negative checks. A restricted PATH hides external tools, and child environments omit DISPLAY, WAYLAND_DISPLAY and D-Bus addresses. Positive GUI imports still use the host's installed PySide6/GIO libraries with Qt offscreen; package availability in the setup-dispatch test is a stub, not evidence of package completeness.

## Review before installation

Use an existing supported Arch/CachyOS LXQt X11/Openbox installation and a normal desktop user. Review `python setup.py menu --packages` and `python setup.py menu` first. The former only prints a package command. Apply requires a working pacman query and the listed packages; it never installs them. Missing pacman or required Python bindings refuses before menu writes. Other distributions require their own dependency validation; the dispatcher does not bypass Arch package checks.

Menu/search/folder cascades use PySide6 (including its Qt platform plugins) and GIO via python-gobject. Search adds no Python dependency. Portable preferences use those same bindings for validation/UI. Snapping and screenshots additionally require their listed X11/application packages; cursor and enabled wallpaper glass need Pillow. A package-name check is not proof that a Qt platform plugin can load or a graphical session works.

Optional native panel, ScreenGrab and wallpaper builds require the development toolchains listed in their component READMEs. Builders fetch pinned upstream sources; this source archive is not an offline toolchain. Use an empty permanent work directory. Display-enabled wallpaper also needs xrandr at runtime; nvidia-settings/NV-CONTROL is optional for the NVIDIA OpenGL checkbox. `setup.py wallpaper --packages` does not infer these extra display capabilities from a binary. Missing RandR produces a query error; missing NV-CONTROL disables the VSync option. No universal Intel/AMD/Vulkan VSync switch is supplied.

## Scoped install and restoration

After reviewing a module's preview, apply only that module, for example `python setup.py menu --apply`. `install.py menu --apply` performs Python binding checks but does not perform setup's package-manager checks. Menu installation also copies the settings toolkit; it does not apply its optional modules. `--home /path/to/disposable-home` redirects managed targets for tests, but is not a container and does not isolate every host dependency. Never use `--live` in a disposable-home simulation.

`python setup.py menu --rollback` restores managed files to their **first-install** contents/modes, removes originally absent managed files, and refuses conflicting edits. Restore any menu/panel integration first. It retains personal preferences and reference backups; empty directories may remain. It is not a previous-version upgrade undo. Keep any separately recorded upgrade undo if that is what you need. Optional modules use their own rollback commands and manifests; do not delete manifests to bypass conflicts.

Example of an independently scoped optional association: preview `python setup.py kate`, then apply only after Kate is installed; restore with `python setup.py kate --rollback`. This is an opt-in MIME association change. Native panel/wallpaper staging is a separate next-login operation, not part of the menu install. See the component docs for paired helper integrity, permanent build locations and restoration.

## Reproduce the boundary checks

Run `python -m unittest discover -s tests -p test_clean_environment.py -v` from this source. It covers:

- stdlib-only setup/install/module/build help, menu preview and package-list output without writes;
- missing pacman, missing site packages and simulated missing packages refusing before managed writes;
- optional previews leaving no lock/state files, including failed missing-prerequisite previews;
- setup menu dispatch with simulated package availability, installed toolkit imports from outside the source directory, repeat install and exact managed bytes/modes rollback;
- missing Kate refusal, then scoped association install/repeat/rollback with a discoverable stub that is never launched;
- structured display-query failure without external capabilities;
- native builders preserving a nonempty work directory before invoking external tools.

The broader suite contains mock driver, integrity and rollback tests. These checks do not validate distro dependency closure, upstream downloads/builds on a fresh OS, Qt XCB plugin loading, real application launches, normal login, physical display changes or hardware recovery. The original-source license was subsequently selected as GPL-2.0-or-later; existing component terms remain intact. See ../LICENSING.md. This test audit does not grant additional rights.
