# Optional native settings

Run `doroshell-modules MODULE --plan` to preview a module. Use `--apply` to save it, `--status` to inspect ownership, `--undo` to remove it and `--recover` to finish an interrupted transaction. The helper uses the standard configuration paths under the selected home. LXQt and Openbox read the staged changes on their next normal startup.

| Module | Setting |
| --- | --- |
| `clipboard` | Add the clipboard quick-launch button immediately before Status Notifier on the DoroShell panel and start the history service at login. |
| `dolphin`, `kate` | Set the directory or plain-text MIME association in both user MIME defaults files. |
| `dolphin-dark`, `kate-dark` | Set the application’s colour scheme to Breeze Dark when that setting is independent of the managed DoroShell theme. Requires the Breeze Dark colour scheme. |
| `single-desktop` | Set the Openbox desktop count and initial desktop to one. Existing rules assigning an application to another desktop must be reviewed first. |
| `wallpaper-glass` | Enable the wallpaper-derived glass setting. |
| `taskbar-size` | Set the icon size and task-button width on the DoroShell panel with `--taskbar-size small`, `medium` or `large`. |
| `taskbar` | Set the stock LXQt panel1 taskbar style with `--taskbar-style icons` or `standard`. Applying this module detaches DockBarX from panel1. |
| `taskbar-drag` | Check for the configured native taskbar, whose task-button implementation includes drag support. |
| `start-shortcut` | Assign Alt+F1 to DoroShell Start. A personal binding needs `--replace-start-shortcut`. If the native session setup already owns the binding, it keeps ownership. |

Each independent change records original file contents, permissions and the values it manages under `~/.local/state/doroshell-native/modules/`. Undo preserves unrelated edits. A conflicting edit to a managed key stops the operation for review. RC2-owned optional modules retain their RC2 rollback records. The maintenance command can use `--claim ID` to distinguish modules it added from pre-existing personal selections.

Before changing a shared base file, maintenance runs `--suspend --claim ID` on its optional modules in reverse installation order. Suspension restores the underlying values and retains the selected options. After the base change, `--resume --claim ID` reapplies each selection in installation order and records the new underlying values for the next rollback. Both operations can be retried. `--recover` finishes an interrupted transition, and `--undo` on a suspended module drops its selection while leaving the base configuration intact.

Temporary-home tests exercise the CLI, exact restore, edits made after setup, overlapping MIME/panel changes, explicit shortcut replacement, inherited settings, claim conflicts and interrupted multi-file recovery.
