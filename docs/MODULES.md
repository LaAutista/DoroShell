# Modules and lifecycle

`deploy.py` orchestrates the core/optional modules; `setup.py` and Settings expose
the existing granular adapters. Each module owns a limited target set and manifest.
The shared interface is preview → apply/update → conflict-checked restoration.

| Module | Runtime and configuration | Dependency/lifecycle |
| --- | --- | --- |
| `menu` | `.local/share/lxqt-comfort/`, installed toolkit/settings, launchers; Start preferences under `.config/lxqt-comfort/` | Python/PySide6/GIO/Xlib + udev; search, folder cascade, portable and opt-in input preferences ship with it. User choices are retained. `menu-install.json` records originals. Active input choices/receipts block helper removal. |
| `native-panel` | Separate `.config/doroshell/panel.conf`, launcher and user LXQt autostart override | Start + private pinned LXQt build. Next-login staging. Upgrades retain panel config; `native-panel.json` keeps first baseline. |
| `theme` | Four generated palettes, Openbox/KDE styles and selected LXQt palette keys | Openbox/Qt/Breeze icons. Existing selection retained on deployment updates. `theme.json`; unrelated settings preserved. |
| `cursor` | Inherited `DoroShell-Loading` Xcursor theme, LXQt/default cursor selection | Pillow + Breeze cursors. GIF/APNG sources included; ordinary pointer inherited. Legacy `cursor-install.json` retained. |
| `single-desktop` | Existing Openbox desktop count/initial desktop only | Default config or explicit bounded `--config-root`; phased ownership and journal-5 recovery. No environment/live migration. See [root inventory and limits](config-roots.md). |
| `snapping` | X11/Openbox helper, autostart and owned keybinding block | Python Xlib/PySide6; startup at next login. Explicit legacy `--live` exists but deploy never uses it. |
| `screenshots` | Independent overlay/helper, owned Print keys | Xlib/PySide6/GIO. Optional native ScreenGrab importer built separately. No personal capture during tests. |
| `start-shortcut` | Optional Alt+F1 binding in `.config/lxqt/globalkeyshortcuts.conf` | Menu + lxqt-globalkeys; explicit custom replacement flag. Whole-file ownership/phase record, exact original bytes/mode, no live reload. Restore before other shortcut edits; see INSTALL. |
| `maintenance` | `doroshell-update` and `doroshell-remove` launchers | Permanent source checkout; existing shared module manifest engine. Does not run in the background. |
| `clipboard` | In-memory history helper, autostart, fixed panel button | Optional native panel + menu; never serializes clipboard content. Removing files does not force-stop an active helper in this orchestrator. |
| `wallpaper` | Native PCManFM + video worker and native Background preferences | Optional libfm-qt/Qt Multimedia build. Format-2/3 integrity checks; native/system fallback. Media selection/enabling remains explicit. |
| `display` | Advanced tab and separate mode guard in the wallpaper build | Optional `wallpaper` build flag. Removing this selection restores the stock desktop via wallpaper removal. NVIDIA setting applies to future OpenGL clients, not all apps/Vulkan. Hardware recovery remains unverified. |
| `wallpaper-glass` | Cached wallpaper blur/tint and configuration | Optional Pillow; no compositor, moving-window capture or animation requirement. |

Existing low-level choices (`taskbar-size`, legacy taskbar/DockBarX drag,
single-desktop, Kate/Dolphin associations and dark themes) remain in `setup.py` and
Settings. The new installer does not silently select these personal preferences.
Profile picture editing remains a Start setting; it is not an independent service.
Native ScreenGrab is optional; overlay Copy/Save work without it.

Module names and runtime package declarations are in `setup.PACKAGES`; existing
optional adapters are in `modules.MODULES`. `deploy.ORDER` defines core ordering and
native dependency expansion. When adding a module, update those declarations,
installed-helper payload lists, docs and disposable-home lifecycle tests together.
Do not replace all configuration with a machine snapshot or introduce a second
preferences database without a tested migration.
