# Native DoroShell development build

The rewrite starts from the public RC2 source at `5b67c0a`. Its applications are C++20 executables with a CMake build. Qt 6 supplies the UI, GIO launches desktop entries, libnm talks to NetworkManager, and XCB supplies X11 input and window operations. The existing C++ LXQt and PCManFM changes are built from their pinned upstream revisions. The native maintenance tool builds and selects the private runtime. An existing RC2 account is identified by its installation receipts.

## Build in a private directory

From this source checkout, with the LXQt development packages installed, run:

```sh
cmake -S . -B "$HOME/.cache/doroshell-native-build" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DDOROSHELL_BUILD_LXQT_PANEL=ON
cmake --build "$HOME/.cache/doroshell-native-build" --target doroshell-bundle --parallel 4
```

The assembled applications are under `native/upstream/runtime/bin` inside that build directory. Keep the build directory in place because the private panel and the unified input dialog use libraries and plugins from the build. Building does not register launchers, change the display or restart the desktop. The optional upstream targets fetch the reviewed LXQt sources via Git. The CMake default without the option builds only local components.

The Settings hub opens the native Start preferences, network chooser, input dialog, wallpaper and display preferences, and appearance controls. For a disposable test user, the following commands preview and register the applications and shortcuts. Invoke these from the assembled bin directory.

```sh
./doroshell-setup --plan
./doroshell-setup --apply
./doroshell-setup --session --plan
./doroshell-setup --session --apply
```

`--session` registers Print, Alt+F1, the three Openbox snapping shortcuts and next-login services for snapping and Recent programs. Native setup refuses competing key bindings. `--desktop` independently stages the PCManFM wallpaper desktop. Each scope has `--undo` and `--recover` and keeps a user-local journal. `doroshell-panel-profile` manages the next-login panel separately. The launcher registrar refuses to take over existing unowned desktop entries. Use a separate account to exercise all scopes on a machine with an existing RC2 install.

## Verification

Use `ctest --test-dir BUILD --output-on-failure` after building the default targets, including tests. Xvfb, Openbox, xauth and a private D-Bus session enable desktop integration tests. Configure `DOROSHELL_PRIVATE_XVFB` with the path to Xvfb. For the private NetworkManager fixture install python-dbusmock, an external test tool. No Python interpreter is needed by the new application binaries. The original RC2 source and its tests remain available for compatibility checks.

| Component | Native behavior |
| --- | --- |
| Start | Pinned list, search, GIO launching and actions, recent foreground programs, folder and portrait controls, desktop-file drag, session controls |
| Panel | All 16 release patches, including notification overflow input, network button, calendar and clock |
| Network | Wi-Fi scans, hotspots, credentials, Ethernet, and saved-connection context actions |
| Clipboard | Session-only history, format-preserving acquisition in a bounded child process, password hints, and coexistence with LXQt clipboard retention |
| Screenshots | Frozen desktop, region/window selection, annotations, crop precision controls, PNG output, clipboard ownership and handoff of the edited image to ScreenGrab |
| Window snapping | Openbox keyboard bindings, edge drag and geometry restore tied to the window lifetime |
| Display and pointer | Native refresh-rate confirmation/rollback helper, unified pointer controls, flat profiles, hotplug and per-device receipts |
| Wallpaper | Patched desktop, native preferences, isolated video worker and a checked next-login fallback to stock PCManFM |
| Appearance | Four Doro palettes and native theme installation and restore; cursor generation accepts a personal animation and includes a pink loading spinner in the neutral source distribution |

## Installation and upgrade verification

The native bootstrap built the complete private runtime from a Git mirror of the development checkout in a temporary account on CachyOS. Pacman checked the host's existing dependencies. The staged update command selected the same revision on a repeat run. Removal restored the original absence of the Openbox config, panel and desktop autostarts and maintenance aliases.

A separate private Xvfb test started the real LXQt session manager and observed the bundled panel, PCManFM desktop, Recent programs tracker and snap helper running together. That test used a fresh temporary home, private session bus, and isolated autostart directories. It did not run a display manager, change a physical monitor or connect to a wireless network.

The RC2 migration tests cover launcher ownership, existing panel pins and configuration, interrupted writes, repeat application, updates and restoring the original RC2 paths. The native release-switch tests cover failure during an update, a withdrawn selection, rollback and a missing shared-library dependency. The screenshot suite exercises PNG handoff to the real patched ScreenGrab editor on a private X11 display.

The affected laptop, a physical Wi-Fi connection and the monitor manufacturer's refresh-rate behavior still require hardware acceptance. The public release is a candidate.
