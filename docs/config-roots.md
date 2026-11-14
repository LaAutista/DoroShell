# Explicit configuration roots: bounded Openbox adapter

The bounded custom-root adapter supports **`single-desktop`**, **`snapping`**, or both.
Single-desktop changes the existing Openbox `desktops/number` and `firstdesk` values to 1, using the existing
XML parser, application-rule refusal and byte-preserving edit/backup engine.
Snapping stages its existing W-Left/W-Right/W-Down XML block and autostart entry
under the selected root. Its helper/launcher remain under `.local/share/doroshell`
and `.local/bin`; these programs do not read a config-root path at runtime.
No environment variable, session, data/cache root or running desktop changes.

## Source inventory behind this boundary

| Area | Current source assumptions | Why blanket relocation is unsafe |
| --- | --- | --- |
| Menu/toolkit | `install.py` writes programs, entries and toolkit under `.local/share`, launchers under `.local/bin`, original backups under `.local/state/lxqt-comfort`; it copies default `.config/lxqt` snapshots | Runtime Start/portable preferences honor config-root selection separately. An installer-only change would split runtime and ownership paths. |
| Start/preferences | `menu/start_menu.py`, `portable_settings.py`, `menu/wallpaper_glass.py` read `XDG_CONFIG_HOME` for selected preferences | `settings.py` launches managed commands with default config paths, while `input_preferences.py` has fixed `.config` preferences/autostart and `.local/state` receipts. GUI-wide relocation is unimplemented. |
| Native panel/clipboard | `panel/profile.py` and `clipboard/install.py` mix `.config` profile/autostart and `.local` program, entry, build and manifest paths | Prepared profiles, launchers, companion modules and recovery records need a coordinated adapter. |
| Theme/cursor | `themes.py` mixes `.config` Openbox/LXQt/KDE files and `.local/share` generated assets; `cursor.py` also uses `.icons` | Moving config alone is not a full path migration. |
| Wallpaper/display | `wallpaper/install.py` owns fixed autostart paths; native controls use Qt config/runtime locations, `wallpaper/control.py` reads `XDG_CONFIG_HOME`; display diagnostics read `XDG_STATE_HOME` | Installed launcher/record and runtime resolution are separate contracts. |
| Capture | `modules.py` combines config keybindings/autostart with `.local/share` helpers and `.local/bin` launchers | Capture remains unsupported with alternate roots. |
| Cache/build/runtime | `menu/wallpaper_glass.py` keeps an in-memory pixel cache; native builds are durable `.local/share/doroshell/builds`; native wallpaper uses Qt RuntimeLocation | No global cache migration or persistent cache-root guarantee is introduced. The adapters do not migrate cache files. |
| Openbox adapters | `modules.py` single-desktop edits one existing XML file; ownership remains in `.local/state/doroshell` | Single-desktop needs no runtime helper. Snapping additionally relocates its autostart entry; program/state paths remain fixed and lifecycle-tested. |

## Usage

From the source checkout, for an **already initialized** alternate configuration:

```sh
python deploy.py --modules single-desktop --config-root "$HOME/Config with spaces"
# Snapping alone or both adapters (explicit module selection):
python deploy.py --modules snapping --config-root "$HOME/Config with spaces"
python deploy.py --modules snapping single-desktop --config-root "$HOME/Config with spaces" --apply
python deploy.py --modules single-desktop --config-root "$HOME/Config with spaces" --apply
python deploy.py --modules single-desktop --apply                 # reuse owned root
python deploy.py --modules single-desktop --remove --apply       # restore original values
```

`setup.py single-desktop --config-root PATH` and installed
`modules.py single-desktop --config-root PATH` provide preview, `--apply` and `--rollback`. Local bootstrap accepts
`--modules single-desktop --config-root PATH`; paths with spaces are one quoted
argument. The smaller README download wrapper does not accept this advanced option.
The same commands accept `snapping` or both module names (installed `modules.py`
handles one at a time). Settings GUI, core/other module combinations, native-panel selection and custom roots
outside the selected home are unsupported. No existing config is copied or moved.

The root must be absolute, canonical and home-contained. Path components of roots, ownership records and every managed target (XML, autostart
and program) through the selected home are checked for symlinks,
including aliases that resolve elsewhere inside the same home. The XML must exist
and validate. Module/setup preflight shares these checks, with another component
check before a custom target write. Missing paths refuse without creating
config directories. A custom root cannot overlap `.config`, `.local`, `.cache` or
`.icons`, or the configured cache/runtime directory; choosing the exact default `.config` retains legacy behavior. Alternate
data/state roots remain refused. A set `XDG_CONFIG_HOME` must match the explicitly
selected or previously owned root; an environment value alone never opts in.
The selected file is staged only. Openbox will use it only if its separately chosen
startup configuration actually resolves there; this tool does not set that up or
prove it. No reconfigure/restart or live workspace migration is performed.

## Ownership and recovery

Each module manifest records the home-relative root, fixed target inventory, original
bytes/mode and pending/complete/restoring phase. Explicitly choosing a different root
while ownership exists refuses; restore first. Legacy default-root ownership cannot
be silently moved. Removing or changing root metadata cannot retarget the records.
Unrelated files and XML content remain intact. Later changes to managed desktop
values, snapping block/program/autostart content or file modes refuse; an unrelated XML edit is retained during module removal.
Exact byte/mode restoration occurs when there are no intervening unrelated edits.

Deployment journal 5 also records the chosen root and pre-ownership config snapshot.
It rejects a changed config before ownership/recovery and checks the reviewed file
again after prerequisite/build work. Completed-output checks and exact upgrade undo
reuse the existing journal engine. `--apply --recover` uses the saved root; an override
refuses. `--apply --undo TRANSACTION` uses its recorded paths (no `--config-root`
override). Removal restores the first baseline; undo restores the prior transaction.
Pre-config-root installers reject journal 5. The prior single-desktop-only reader
rejects snapping/combined journal requests; its module engine rejects
`root-snapkeys`/`root-file` before writes. Existing schemas are unchanged, with no migration
of pending records. Keep the same source until an interrupted transaction finishes.

Both custom-root adapters take the snapping and single-desktop writer locks in
that order. Combined selection requires the same recorded root; differing ownership
roots refuse before package work. The two modules own disjoint XML fields and may be
removed individually; the other module's fields and unrelated XML remain intact.
Missing/malformed/ambiguous keyboard XML or conflicting supported W-key bindings
refuse before writes. New combined records are rejected by older single-module
journal readers; keep the same source for recovery.

Combined recovery succeeds between completed steps. If a process dies after the
second adapter changes shared XML but before deployment records step completion,
the existing completed-output guard refuses that ambiguous state; it does not
infer that the changed file is safe. Preserve the journal/module records for manual
inspection. No automatic overlap merge or recovery-schema change is introduced.

Custom-root operations use the shared writer locks. File-level conflict checks
are conservative, not a lock on external programs: an unrelated application can
still race filesystem operations. No forced overwrite or daemon coordination exists.
Plan/config validation precedes deployment records and module package offers; earlier
bootstrap Git/Python prerequisites may still be required to run Python validation.

Validation is disposable-home and mocked-command testing, including installed toolkit
CLI and exact XML bytes/modes. Actual custom-root Openbox/autostart startup, login and clean OS
installation remain unverified. No custom-root live behavior is claimed.
