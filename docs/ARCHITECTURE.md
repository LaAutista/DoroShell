# Architecture

DoroShell extends an existing LXQt/X11/Openbox session. Native system packages stay
installed. No compositor or replacement session is introduced.

| Layer | Implementation and communication |
| --- | --- |
| Acquisition | `bootstrap.sh` fetches a reviewed Git revision into a separate permanent source directory. `release.json` declares development/stable and configuration schema. `source_release.py` verifies the complete tracked inventory, code and catalogued media. |
| Orchestration | `deploy.py` reads `compatibility.py` capability probes, checks package versions, offers an official pacman full-update transaction, builds missing native runtimes, then calls existing module APIs. Preview is default. |
| Existing installers | `install.py` owns menu/toolkit files. `modules.py` owns narrow file/INI/XML edits. `cursor.py` owns generated cursor/config files. `panel/profile.py` owns the next-login panel selection. `setup.py` remains the explicit low-level module dispatcher used by Settings. |
| Start | PySide6 UI in `menu/start_menu.py`. GIO provides visible installed desktop entries, actions and launching. `app_search.py` ranks an in-memory catalog; `folder_cascade.py` lazily reads bounded directory listings; `portrait_crop.py` handles a saved crop without modifying the original image. A local resident process toggles the menu and detects helper changes. |
| Preferences | `settings.py` presents independent module operations; `portable_settings.py` validates versioned, path-free Start preferences. Existing legacy `lxqt-comfort` paths are intentional compatibility interfaces. |
| Input preferences | Installed `input_preferences.py` uses XInput/Xlib and udev identity for opt-in supported evdev profiles and guarded touchpad disabling. User choices and per-session restoration receipts live separately from program manifests. Recorded autostart ownership and a shared writer/removal lock prevent helper removal while input restoration is pending. |
| Native panel | `panel/build.py` applies eleven ordered patches to pinned LXQt Panel 2.4.1, selects matching pinned LXQt 2.4/2.5 build tools from development metadata, and stages into a private prefix using DESTDIR. GIO desktop launching, LXQt task/tray behavior and configuration are retained. Upgrades change the launcher target while retaining the user's panel profile. |
| Capture/snapping | Independent helpers under `runtime/`, using X11/Openbox and PySide6. Screenshot ownership persists in a helper. Optional native ScreenGrab import is separately built from its pinned revision. |
| Clipboard | `clipboard/clipboard.py` stores session history in memory. A managed autostart entry and fixed Quick Launch icon connect it to the native panel. |
| Wallpaper | `wallpaper/build.py` patches the installed PCManFM-Qt release (reviewed revisions verified), rebuilds itself after library-breaking updates ([native-rebuild](native-rebuild.md)), adds native Background preferences and a separate video decoder process. The validated file-based wallpaper configuration controls the decoder. Off releases the backend. The ordinary PCManFM package remains a fallback. |
| Display | `display/` adds Advanced controls and a separate transaction guard. RandR/NVIDIA queries and writes use validated argv. Keep/Revert and external-change protection are independent of the preferences process. Format-3 build records pin executable/video/display helper hashes. Failure records contain fixed allowlisted labels only. |
| Assets/themes | `assets/catalog.json` identifies owner-requested media; `themes.py` generates palettes/Openbox/KDE styles; `cursor.py` generates Xcursors from the bundled APNG. Existing custom choices are retained on upgrades. |

The deployment journal supplements existing manifests. Module removal restores
the **first installation baseline** using those manifests. A completed deployment's
`--undo` restores **the immediately preceding upgrade**, including old manifests,
only if installed bytes and modes still match. Failed module operations retain
their pending state; recovery reuses the same source and existing conflict checks.
The module set is sequential, not one atomic filesystem transaction. OS package
updates are managed by pacman and are not reverted by DoroShell.

Native builders pin source revisions because arbitrary new APIs cannot be assumed
compatible. Platform detection is capability-based: Arch lineage/pacman, LXQt/X11,
initialized single-panel layout or explicit standard-panel selection, and Openbox
config. Explicit choices use the same profile adapter before module package/build writes;
missing acquisition/validation prerequisites have separately announced, user-approved
pacman stages before that check, with a required recheck before configuration writes,
with deployment pointer format 2 and journal format 3 retaining the choice. Unknown layouts are refused
without guessing. CMake is the final ABI/dependency check. This allows tested
adaptation without claiming future releases will automatically work.

There is no search telemetry, personal-file indexing, remote app search, automatic
display tuning, mandatory video, or mandatory compositor. Native runtime paths are
generated for the target home; build trees must remain at their installation prefix.
