# Updating an RC2 install

The maintenance command selects `doroshell-migrate` when it finds RC2 installation receipts. The migration keeps the selected modules and routes existing shortcuts to the installed native bundle. Changes take effect as the applications launch. The desktop, input startup and panel selections take effect at the next normal login.

Run `doroshell-migrate --plan` from the installed bundle to preview the affected paths. `--apply` records each original RC2 file, its mode and its native replacement in `~/.local/state/doroshell-native/migration.json` before writing the first launcher. `--refresh` selects an updated bundle only if the migration is still installed. `--recover` resumes an interrupted change. `--undo` restores the RC2 launchers and the original updater. The restored RC2 removal command can then uninstall the original modules using their existing rollback records.

The migrator checks menu hashes, panel hashes and per-module file evidence before changing a managed path. A conflicting edit stops the transaction. Panel pins, menu favorites, recent programs, personal theme and wallpaper settings, and the RC2 deployment records stay in their existing locations. The current input preference controls whether its watcher should exist. Undo respects changes to that preference made since migration. An incomplete RC2 transaction needs recovery through the RC2 installer first. An RC2 panel widget change already staged for login must complete before migration.

Legacy shortcut paths receive a native executable that forwards arguments directly to the selected bundle. Panel and input launchers check for unresolved shared-library symbols. A broken selection requests a background repair and starts the distribution component. Desktop startup delegates its integrity checks and stock fallback to `doroshell-desktop`.

The native `doroshell-wallpaper` command opens the wallpaper preferences by default. It also supports `off`, `pause`, `resume` and `status`. The mutation commands use the same configuration file and lock as the graphical wallpaper controls.
