# Development and safe testing

Read [AGENTS](../AGENTS.md), [STATUS](STATUS.md), [ARCHITECTURE](ARCHITECTURE.md) and
[INSTALL](INSTALL.md) before edits. Use a separate branch/checkout. Never overwrite
a dirty workspace with a newer source snapshot or force-push a shared branch.

```sh
gh repo clone LaAutista/DoroShell
cd DoroShell
git switch -c work/describe-change
python source_release.py
python -m unittest discover -s tests -v
python deploy.py --modules menu              # read-only capability/package plan
```

Dependencies are distribution packages, not just pip packages. Tests need
PySide6, GIO/PyGObject, Pillow and Python Xlib; the existing cursor tests also read
Breeze cursors. Qt UI tests use offscreen rendering. Use `QT_QPA_PLATFORM=offscreen`
when needed. Build dependencies and command lines are in [INSTALL](INSTALL.md),
[panel](../panel/README.md), [wallpaper](../wallpaper/README.md) and
[ScreenGrab](../screengrab/README.md). Builders fetch pinned upstream tags and refuse
unexpected hashes or nonempty work directories. A native prefix is not relocatable.

Installer regression tests use temporary homes and fake dependencies/native
executables where stated; they are not clean OS tests. Private native tests under
`tests/check_*_x11.py` require an authenticated Xvfb display, private D-Bus and
disposable home. Read each test's options first. Never point synthetic drivers,
pointer tests, clipboard tests or mode tests at the personal display. Session/power
dispatch remains mocked. Do not invoke a real locker, login, logout or reboot.

For a clean-machine acceptance run, record the distribution/package versions and
source SHA, baseline managed files/modes and unrelated sentinel settings. Preview,
install, repeat, then log in only when chosen by the tester. Verify taskbar/tray,
Start launching, themes/cursors, Print/capture and snapping. Add optional clipboard
and wallpaper independently; confirm disabling them preserves the core. Upgrade
with a personal pin/theme edit, exercise conflict refusal, then test exact upgrade
undo and first-install removal. Check autostart at a tester-chosen normal login.
Use a snapshot/disposable VM; OS package updates are outside DoroShell undo.

When publishing, inspect `git diff` and the complete staged file list. Include
source, component notices and the existing catalogued artwork; exclude credentials,
personal config/history, real desktop screenshots, diagnostic records, journals,
caches and compiled programs. Update STATUS, HANDOFF, CHANGELOG and release evidence
with truthful results. Stage intended files before refreshing the inventory:

```sh
git add <reviewed-paths>
python source_release.py --refresh
python source_release.py
git add SOURCE-MANIFEST.json SOURCE-SCAN.json SHA256SUMS
python -m unittest discover -s tests -v
git diff --cached --check
```

Export the committed tree using `git archive`, extract it and check the inventory
and `sha256sum -c SHA256SUMS`. Re-run tests after relevant reconciliation changes.
Fetch/review current main before a normal fast-forward push; preserve newer commits.
Use the user's existing legitimate author identity, never invent one or change
global configuration. Push only when authorized and verify the exact remote SHA.
