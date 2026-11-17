# Rebuilding after system updates

DoroShell's desktop (patched PCManFM) and taskbar (patched lxqt-panel) are native
programs linked against the system's LXQt libraries. When a system update replaces
one of those libraries with an incompatible version, the old build can no longer
start. On 2026-11-14, for example, libfm-qt 2.4 (`libfm-qt6.so.17`) was replaced by
2.5 (`.so.18`) and menu-cache was removed. The desktop then silently fell back to
stock PCManFM, losing the video wallpaper and the display controls.

## What happens now

Each native build keeps a copy of the DoroShell sources that made it, in `recipe/`
inside its build directory (about 1.6 MB, without artwork or tests). At every login,
its launcher runs `recipe/native_rebuild.py login`, which checks with `ldd` that every
library the build needs still resolves.

- **All libraries present:** the DoroShell build starts as before.
- **A library is missing:** the stock program starts for this session. The stock
  taskbar uses its own LXQt profile, so DoroShell's `panel.conf` is never touched.
  A background rebuild starts at low priority, and you get a desktop notification:
  - *Rebuilding…* when it starts,
  - *…is ready* when the new build is staged; it is used from the next login,
  - *…rebuild failed* with the log path if a step fails. A failed version is retried
    after 24 hours, or immediately with `rebuild <kind> --current <exe> --force`.

The desktop rebuild follows the system: it builds the PCManFM release matching the
installed `pcmanfm-qt --version`, together with the lxqt-build-tools release that
PCManFM states it needs, built privately (no packages are installed). Releases with a
reviewed upstream revision (PCManFM 2.4.0 and 2.5.0) are verified against it. A newer
release still builds, and is recorded as `"reviewed": false` in
`doroshell-wallpaper-build.json`. The new launcher is staged through the normal
wallpaper module, so its backup and conflict checks apply.

The taskbar rebuild uses the same pinned lxqt-panel source and patches as before,
built against the system's current liblxqt, and staged with the usual panel upgrade.
An LXQt release family the panel build does not know yet fails with a notification.

Logs are in `~/.local/state/doroshell/native-rebuild-{desktop,panel}.log`, and the
last result is in `native-rebuild.json` in the same folder.

## Limits

- Only missing libraries are detected. An incompatible library that keeps the same
  version number is not detected; the desktop launcher still falls back to stock if
  the program exits with an error.
- When an upstream change makes a DoroShell patch stop applying, the rebuild fails
  and tells you. Fixing that needs a DoroShell update.
- Builds made before this change have no `recipe/` and keep the old behaviour until
  they are rebuilt once.
- The taskbar rebuild path is covered by unit tests only. A real automatic rebuild
  after an actual library break has not been observed yet.
