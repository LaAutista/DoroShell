# Launcher and window identity

The native panel resolves explicit X11 desktop-file/application IDs before matching
`StartupWMClass` (either WM_CLASS component), then desktop basenames against class
names. It uses the same resolution for grouping, Pin/Unpin and launcher icons.
Among equal-strength matches, a unique explicitly pinned launcher wins. Ties
with multiple pinned launchers (or no pins) remain unresolved. A stronger
application-ID match always wins over weaker pinned class matches. Executable
command strings, window titles and process ancestry are never used as guessed
application identity.
This supports wrappers and Wine applications when they provide an application ID
or an unambiguous launcher class; missing or shared identities cannot reliably
identify an individual launcher.

The X11 backend reports application-ID changes so a window can join its pin even
when it publishes its ID after mapping. Class-based icon mode first uses the
resolved launcher icon, then a real class-themed icon, then the window icon, with
a generic application icon as the last fallback. Window-icon mode retains its
preference for the application's own icon.

Build normally with `panel/build.py`. Its third patch requires the existing
native panel and wallpaper-glass patches. No installed panel is selected or
restarted by this source change.

Run the standard unit suite, then the opt-in native regression:

```sh
python -m unittest discover -s tests -v
python tests/check_taskbar_identity_x11.py --run --xvfb /path/to/Xvfb \
  --binary /path/to/candidate/lxqt-panel --evidence /private/output
```

The test uses disposable applications, a temporary home, private D-Bus and an
authenticated private X11 display. It does not launch games or read the personal
clipboard. It checks application-ID grouping, multiple windows, wrapper classes,
instance matching, system/Flatpak class duplicates with one or two pins, stronger
app-ID precedence over pinned class matches, late changes and both icon modes.
For the missing-native-icon assertion only, it briefly pauses its disposable Openbox
process because Openbox otherwise replaces absent icons with its own generic
icon; the test always resumes that process in a finally block. Existing
`check_taskbar_pin_menu_x11.py` and `check_start_export_x11.py` cover pin actions
and drag-to-pin integration. Run these from the repository root.

## Verified acceptance

An independent repeat of the expanded private-X11 regression passed. A controlled
panel-only activation of the successor was then verified with already-open
Fluorine and Discord windows: each reused its proper pinned button, and taskbar
pixels showed no duplicate entry. All existing application windows survived;
the panel configuration remained byte-for-byte unchanged.

This establishes those two real-application cases in that X11 session. It does
not establish broader application coverage, Wayland runtime behavior, normal
login or clean-install acceptance. Those remain separate checks.
