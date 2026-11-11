# Optional modules: installation and restore

The optional update installs the direct Start portrait picker, GIO catalog notifications, the corrected coordinated-theme selector and a Wallpaper controls button. All selections default to Keep unchanged; installing the helpers does not apply a palette or enable animated wallpaper.

These instructions apply to modules now present on published main. The old
102-test optional archive and 84-test core release are historical artifacts;
[current source/test/activation status](final-acceptance.md) supersedes their
deployment notes. Follow the [core runtime/build dependencies](../README.md#dependencies), [native panel build requirements](../panel/README.md), [theme instructions](themes.md) and [wallpaper dependencies/build instructions](../wallpaper/README.md). No binaries, personal configuration, media or desktop screenshots are bundled. Native builds fetch pinned upstream source and require development dependencies; setup never installs packages automatically.

Preview the desired modules before applying them. `python setup.py menu` previews helper installation; add `--apply` to install. `python setup.py menu --packages` prints runtime package requirements without installing them. Select theme, native-panel or wallpaper explicitly and follow their separate preparation steps. The default module is menu, theme defaults to Keep unchanged, and fresh wallpaper configuration defaults to disabled/muted. Existing user choices are preserved on repeat installation. No logout, application restart or wallpaper handoff is performed by staging.

Managed files include:

- `.local/share/lxqt-comfort/start_menu.py` and its existing launcher/desktop entry.
- `.local/share/doroshell/toolkit/settings.py`, `themes.py`, `modules.py`, `setup.py`, the toolkit's menu copy and existing runtime helpers.
- `.local/share/doroshell/toolkit/wallpaper/control.py` and `wallpaper/install.py`.

The installed Settings launcher opens those toolkit files. Wallpaper controls can prepare media choices and preview a file, but actual desktop animation requires the separately documented native wallpaper build and explicit next-login setup. That desktop switch is not implied by installing the controls.

The theme-capable panel with Pin/Unpin actions is a separate build. The reversible profile switch updates `.local/bin/doroshell-native-panel`, `.config/autostart/lxqt-panel.desktop` and its managed `.config/doroshell/panel.conf`. Staging does not replace the running panel; it selects the executable for the next normal panel/session startup. The development installation subsequently received an explicitly authorized panel-only refresh, recorded below. Staging this update preserves the current panel configuration byte for byte, including personal pins, tray and clock settings.

Backups remain in `.local/state/lxqt-comfort/menu-install.json` and `.local/state/doroshell/native-panel.json`. A private `optional-install-before-*` checkpoint also holds pre-upgrade managed file contents/modes and the previous prepared panel profile. These private files must not be published. The menu installer preserves its initial baseline across updates; its rollback uninstalls the managed menu rather than selectively reverting only this upgrade.

To restore the original panel selection without restarting it:

```sh
python setup.py native-panel --rollback --keep-panel-edits
```

The original panel returns at the following normal startup. To remove Start and its toolkit after restoring panel/legacy integration, use `python setup.py menu --rollback`. If a palette was explicitly applied later, restore it separately with `python setup.py theme --rollback`. Wallpaper controls provide Off; the optional native wallpaper module has its own rollback. All managed rollback paths refuse conflicting edits.

Start builds a fresh catalog each time its normal launcher opens it. An already-open menu now also follows GIO catalog-change notifications. System Monitor appears by its desktop-entry display name, under System, and through search; it is not automatically added to Pinned. Missing favorites are retained in the saved pin records.

## Historical controlled deployment checkpoints

On the development installation, the Pin/Unpin panel was subsequently activated using only LXQt's panel-module stop/start. Existing client windows and monitored processes survived, and panel settings, pins, palette and wallpaper settings stayed unchanged. The real closed-pin menu displayed Open and Unpin. This is a panel refresh, not normal-login acceptance.

At this earlier checkpoint, the resource-corrected wallpaper launchers were staged and the older renderer was active with animation off. Later native-preferences activation and user-reported animation success are recorded in the current acceptance matrix. The original autostart baseline, including its existing Dolphin startup hook, is retained for rollback. Staging preserved the then-running desktop, media and system binary. No live desktop handoff was performed. Use `python setup.py wallpaper --rollback` to restore the original desktop selection before its next startup; use Wallpaper controls → Off to disable animation independently.

Printers now opens the installed KDE management module through kcmshell6 when available, or an installed standalone printer manager. It never treats ConfigurePrinter's per-device helper as the general manager. Missing tools or launch failures produce a visible error.

The subsequent drag/contrast panel refresh preserved all seven existing client windows and seven monitored processes, plus panel settings and personal preferences. Start now exports copy-only application launchers, the grouped taskbar accepts valid local application drops, and the desktop retains its native Copy here prompt and launcher-trust behavior. The hidden-icons popup has a dark background for white notification icons, including hover and keyboard focus. The shutdown split-arrow glyph is centered at small and large font sizes.
