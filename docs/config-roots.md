# Explicit configuration roots: bounded Openbox adapter

The first custom-root adapter supports only **`single-desktop`**. It changes the
existing Openbox `desktops/number` and `firstdesk` values to 1, using the existing
XML parser, application-rule refusal and byte-preserving edit/backup engine.
No environment variable, session, data path, cache path or running desktop changes.

## Source inventory behind this boundary

| Area | Current source assumptions | Why blanket relocation is unsafe |
| --- | --- | --- |
| Menu/toolkit | `install.py` writes programs, entries and toolkit under `.local/share`, launchers under `.local/bin`, original backups under `.local/state/lxqt-comfort`; it copies default `.config/lxqt` snapshots | Runtime Start/portable preferences honor config-root selection separately. An installer-only change would split runtime and ownership paths. |
| Start/preferences | `menu/start_menu.py`, `portable_settings.py`, `menu/wallpaper_glass.py` read `XDG_CONFIG_HOME` for selected preferences | `settings.py` launches managed commands with default config paths, while `input_preferences.py` has fixed `.config` preferences/autostart and `.local/state` receipts. GUI-wide relocation is unimplemented. |
| Native panel/clipboard | `panel/profile.py` and `clipboard/install.py` mix `.config` profile/autostart and `.local` program, entry, build and manifest paths | Prepared profiles, launchers, companion modules and recovery records need a coordinated adapter. |
| Theme/cursor | `themes.py` mixes `.config` Openbox/LXQt/KDE files and `.local/share` generated assets; `cursor.py` also uses `.icons` | Moving config alone is not a full path migration. |
| Wallpaper/display | `wallpaper/install.py` owns fixed autostart paths; native controls use Qt config/runtime locations, `wallpaper/control.py` reads `XDG_CONFIG_HOME`; display diagnostics read `XDG_STATE_HOME` | Installed launcher/record and runtime resolution are separate contracts. |
| Capture/snapping | `modules.py` combines config keybindings/autostart with `.local/share` helpers and `.local/bin` launchers | A future adapter must cover both lifecycle and runtime. |
| Cache/build/runtime | `menu/wallpaper_glass.py` keeps an in-memory pixel cache; native builds are durable `.local/share/doroshell/builds`; native wallpaper uses Qt RuntimeLocation | No global cache migration or persistent cache-root guarantee is introduced. The config-only adapter does not access `XDG_CACHE_HOME`. |
| Config-only Openbox | `modules.py` single-desktop edits one existing XML file; ownership remains in `.local/state/doroshell` | This is the coherent first subset: no runtime helper, assets, launcher or autostart relocation. |

## Usage

From the source checkout, for an **already initialized** alternate configuration:

```sh
python deploy.py --modules single-desktop --config-root "$HOME/Config with spaces"
python deploy.py --modules single-desktop --config-root "$HOME/Config with spaces" --apply
python deploy.py --modules single-desktop --apply                 # reuse owned root
python deploy.py --modules single-desktop --remove --apply       # restore original values
```

`setup.py single-desktop --config-root PATH` and installed `modules.py single-desktop
--config-root PATH` provide preview, `--apply` and `--rollback`. Local bootstrap accepts
`--modules single-desktop --config-root PATH`; paths with spaces are one quoted
argument. The smaller README download wrapper does not accept this advanced option.
Settings GUI, core/mixed module presets, native-panel selection and custom roots
outside the selected home are unsupported. No existing config is copied or moved.

The root must be absolute, canonical, home-contained and free of symlink components;
its `openbox/rc.xml` must exist and validate. Missing paths refuse without creating
config directories. A custom root cannot overlap `.config`, `.local`, `.cache` or
`.icons`, or the configured cache/runtime directory; choosing the exact default `.config` retains legacy behavior. Alternate
data/state roots remain refused. A set `XDG_CONFIG_HOME` must match the explicitly
selected or previously owned root; an environment value alone never opts in.
The selected file is staged only. Openbox will use it only if its separately chosen
startup configuration actually resolves there; this tool does not set that up or
prove it. No reconfigure/restart or live workspace migration is performed.

## Ownership and recovery

The module manifest records the home-relative root, fixed XML target, original
bytes/mode and pending/complete/restoring phase. Explicitly choosing a different root
while ownership exists refuses; restore first. Legacy default-root ownership cannot
be silently moved. Removing or changing root metadata cannot retarget the records.
Unrelated files and XML content remain intact. Later changes to managed desktop
values or file mode refuse; an unrelated XML edit is retained during module removal.
Exact byte/mode restoration occurs when there are no intervening unrelated edits.

Deployment journal 5 also records the chosen root and pre-ownership config snapshot.
It rejects a changed config before ownership/recovery and checks the reviewed file
again after prerequisite/build work. Completed-output checks and exact upgrade undo
reuse the existing journal engine. `--apply --recover` uses the saved root; an override
refuses. `--apply --undo TRANSACTION` uses its recorded paths (no `--config-root`
override). Removal restores the first baseline; undo restores the prior transaction.
Older installers reject journal 5, and older module engines reject the new
`root-desktop`/`root-firstdesk` edit kinds before writing. Existing schemas are unchanged, with no migration
of pending records. Keep the same source until an interrupted transaction finishes.

Custom-root operations use the single-desktop writer lock. File-level conflict checks
are conservative, not a lock on external programs: an unrelated application can
still race filesystem operations. No forced overwrite or daemon coordination exists.
Plan/config validation precedes deployment records and module package offers; earlier
bootstrap Git/Python prerequisites may still be required to run Python validation.

Validation is disposable-home and mocked-command testing, including installed toolkit
CLI and exact XML bytes/modes. Actual custom-root Openbox startup, login and clean OS
installation remain unverified. No custom-root live behavior is claimed.
