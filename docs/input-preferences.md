# Mouse and touchpad preferences — feature candidate

DoroShell Settings has a **Mouse & Touchpad** page, with a link to the native LXQt
input settings. Refresh reads device properties only. Save and apply records the
selected device preference and attempts its supported X11 property change. This
candidate does not change drivers, install packages, edit Xorg rules or restart
any component. There is no Wayland backend.

For identified evdev mice exposing `Device Accel Profile`, disabling acceleration
selects Xorg's **-1 / none profile**. This removes velocity-dependent acceleration;
it preserves constant deceleration and is not the same operation as changing the
Xorg `AccelerationScheme`. See the [X.Org pointer acceleration documentation](https://www.x.org/Development/Documentation/PointerAcceleration/).
Libinput mice are reported unsupported for this evdev-specific control; they are
not silently converted. An evdev device with no profile property is also reported
unsupported. A system `AccelerationScheme none` rule may remove that property,
but absence alone does not establish the effective scheme.

Touchpads are classified using udev's `ID_INPUT_TOUCHPAD`, not names. Only the
selected touchpad's `Device Enabled` property changes. An enabled, identified USB
or Bluetooth mouse outside the virtual-device tree is required; keyboard consumer
controls, touchscreens and virtual pointers do not satisfy the guard. The backend
checks again just before disabling. It does not change external mouse properties.
This is a conservative apply-time guard, not protection against a mouse being
unplugged afterward. Keep the external mouse connected or use keyboard navigation
to restore the touchpad. No continuous input-monitor service is installed.

## Persistence and restoration

Preferences live in `~/.config/doroshell/input-preferences.json`. Device identity
uses name plus udev serial/path/vendor/product metadata; numerical XInput IDs are
never persisted as lookup identities. Missing or duplicate identities are refused.
A single user autostart entry retries configured preferences once at LXQt login.
Reconnected devices require Refresh and Save and apply; there is no hotplug daemon.
Other settings writers can override properties later; configured and observed
state are shown separately. Actual normal-login application is not yet tested.

Before changing a property, the helper records its current value and intended
value. A marker on the X server distinguishes restoration receipts between server
sessions. Unchecking restores the saved value only for the same device instance
and server session, and only if the current property still matches an expected
value. External edits produce a visible refusal. New sessions use their own
baseline; old-session values are not forced onto a new session. Apply failures
retain configured intent and restoration evidence; they are not labelled applied.
Opting out of all successfully restored preferences removes the owned autostart
entry. Symlinked files, changed autostart entries, stale UI saves and unsupported
record schemas are refused rather than overwritten.

An absent or unsupported selected device can retain a configured preference
without applying it. Restoration of a changed device instance is intentionally
refused rather than guessed. The helper does not undo an independently installed
system rule. Opt out and restore input settings before removing the component;
removal integration is an installer-owner responsibility, not implemented here.

## Integration boundary

This topic is based on main `fa8808c` and deliberately does not modify deployment
recovery, shared source inventories or installer logic. The installer owner must
add **input_preferences.py** to the toolkit file-copy list in `install.targets`,
and update release inventories/checksums before integration. Without that copy,
installed Settings shows an explicit missing-component notice; existing pages
continue to work. Source-tree Settings runs the candidate directly. Keep that
source location while its generated autostart entry is in use.

No user screenshot is included. Reference inspection identified native LXQt's
Mouse and Touchpad page; this implementation adds a DoroShell page and native link,
not a patch to LXQt's own UI. No live input changes were made during development.

## Verification scope

Tests use synthetic devices, temporary homes and a private authenticated Xvfb.
They exercise persistence/reload, per-session baseline restoration, evdev/unsupported
and absent-device handling, duplicate identities, last-mouse and virtual-pointer
guards, failed writes, external-property conflicts, opt-out and autostart removal,
symlink/CAS/schema refusals, Wayland refusal, and rendered settings actions.
A private transport check writes and reads a new synthetic property on Xvfb's
virtual pointer; it does not change acceleration or enable/disable properties.

Physical evdev profile changes, real touchpad disabling, normal login order and
hotplug behavior are unverified. The existing system's evdev rule and read-only
properties are observations, not proof of motion response or successful activation.
Review this candidate and installer integration before any live input application.

Candidate verification on the `fa8808c` source baseline: **297 unit tests passed**
(including 12 focused input tests), existing narrow/large-font Settings layout
checks passed, and the private rendered UI/synthetic-property transport check
passed. No physical input property was changed. Concurrent main `e18026e` changes
installer recovery and its docs/tests; this feature does not include or replace
that work. Integration should retain those fixes and rerun aggregate checks.
