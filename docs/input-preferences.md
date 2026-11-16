# Mouse and touchpad preferences

DoroShell Settings has a **Mouse & Touchpad** page, with a link to the native LXQt
input settings. Refresh reads device properties only. Save and apply records the
selected device preference and attempts its supported X11 property change. This
page does not change drivers, install packages, edit Xorg rules or restart
any component. There is no Wayland backend.

For identified evdev mice exposing `Device Accel Profile`, disabling acceleration
selects Xorg's **-1 / none profile**. This removes velocity-dependent acceleration;
it preserves constant deceleration and is not the same operation as changing the
Xorg `AccelerationScheme`. See the [X.Org pointer acceleration documentation](https://www.x.org/Development/Documentation/PointerAcceleration/).
For identified libinput mice whose `libinput Accel Profiles Available` includes
flat, disabling acceleration sets `libinput Accel Profile Enabled` to flat
(`0, 1` or `0, 1, 0` depending on the libinput version). The previous flags are
recorded and restored exactly on opt-out. Libinput mice that don't offer flat are
reported unsupported. The driver is never switched. An evdev device with no
profile property is also reported unsupported. A system `AccelerationScheme none` rule may remove that property,
but absence alone does not establish the effective scheme.

Refresh now shows **runtime profile capability**, **system-rule intent**, and
**current-initialization evidence** separately from your saved preference. Profile
-1 is described as no velocity-dependent acceleration, not a universal statement
that all acceleration/deceleration is disabled. The system scheme is read-only on
this page.

The diagnostic reads `/etc/X11/xorg.conf` and `*.conf` files in the standard
`/etc/X11/xorg.conf.d` and `/usr/share/X11/xorg.conf.d` directories as the current
user, only on Refresh/reload. It reads at most 64 files, 64 KiB per file and 256 KiB
total; symlinks/nonregular files are refused. It recognizes a conservative subset
of InputClass product/path/type selectors. Unsupported selectors, malformed,
unreadable, changed or oversized evidence are reported as incomplete. Different
matching scheme requests are reported as conflicting; precedence is not guessed.
Custom configuration locations, command-line overrides and runtime overrides are
not inferred. This is configuration intent, even when a matching `none` rule exists.
Selector semantics follow the [Xorg InputClass manual](https://man.archlinux.org/man/xorg.conf.5#INPUTCLASS_SECTION);
this bounded diagnostic is not a replacement for Xorg's configuration parser.

**Current Xorg initialization remains unverified by this page.** The available
XInput inventory exposes no trustworthy binding between a log entry, the current
server and this device's initialization instance. The diagnostic deliberately does
not read historical logs, `/proc`, privileged sources or session markers, and never
promotes an absent profile, log/name match or old configuration timestamp to a
verified status. It performs no physical motion test and writes no diagnostic log.
The existing apply/restoration controls retain their separate explicit lifecycle.

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
The menu installer copies the helper into the permanent installed toolkit.
A single user autostart entry starts the helper at LXQt login. It applies saved
preferences, then keeps running to reapply them whenever XInput reports an added or
enabled device, and exits once nothing needs managing. Saving on the page also
starts it if it isn't running; a lock under `~/.local/state/doroshell/` keeps one
watcher per user. Creating the entry requires an installed helper; it never points
to a temporary checkout. Python Xlib and `udevadm` (Arch package `systemd`) are
declared dependencies.

**No acceleration on all mice** is one switch at the top of the page. While it
is on, every supported mouse with a unique identity, including ones connected later,
gets an automatic acceleration rule. Touchpads are not affected. A choice saved for
one mouse below overrides the switch for that mouse. Turning the switch off restores
each automatically managed mouse the same way unchecking it individually would.
Other settings writers can override properties later; configured and observed
state are shown separately. Actual normal-login application is not yet tested.

Before changing a property, the helper records its current value and intended
value. A marker on the X server distinguishes restoration receipts between server
sessions. Unchecking restores the saved value only for the same device instance
and server session, and only if the current property still matches an expected
value. External edits produce a visible refusal. When the only identity match is a
new device instance (the mouse was reconnected), the old instance no longer exists,
so its receipt is archived with reason `device-reconnected` and the new instance is
treated from its own driver defaults. Because X can reuse both the XInput ID and the
event node, the watcher also records every device removal it sees and archives that
instance's receipt (reason `device-removed`), so a replacement that reuses both is
never restored to the old mouse's value. A removal while no watcher is running is
not observed; the watcher runs whenever anything is managed. The watcher also
re-reads preferences every 5 seconds, so it exits soon after you opt out, and a
pass blocked by the page's lock stays pending until it runs. New sessions use their own
baseline; old-session values are not forced onto a new session. Before retiring a
receipt from an ended X server session, its complete evidence is written privately
under `~/.local/state/doroshell/input-restoration/` and the result is reported. These
records can contain device identity metadata; do not upload them. Apply failures
retain configured intent and restoration evidence; they are not labelled applied.
Opting out of all successfully restored preferences removes the owned autostart
entry. Symlinked files, changed autostart entries, stale UI saves and unsupported
record schemas are refused rather than overwritten.

An absent or unsupported selected device can retain a configured preference
without applying it. **Stop managing and restore** opts out of all saved choices,
including absent devices, and attempts only supported, owned current-session
restorations. An absent/ambiguous device, unsupported property
or external edit leaves its receipt and helper intact. It never guesses a prior
value, silently retries an enabled preference after opt-out, or undoes a system rule.
If restoration stays unresolved, preserve the receipt and inspect the reported
cause. A new X server session can retire an old-session receipt with archived
evidence; do not restart a session automatically to bypass a refusal.

## Installation, updates and removal

Menu/toolkit install and repeat/update copy the helper with normal first-install
backups and byte/mode conflict checks. They do not create input preferences or
an autostart entry, enable an input rule, or connect to XInput. Settings loads the
installed helper alongside search, folders and portable preferences.

Program removal and an exact upgrade undo that would replace/remove the input
helper refuse while enabled choices, pending receipts or owned autostart remain.
Use **Stop managing and restore** first. An unchanged-helper repeat-deployment undo
can proceed while preserving those files. Removal and undo never change a device;
saved inactive choices, private archived receipts and the synchronization lock
remain after program removal. The lock inode is retained for waiting clients.

Autostart ownership and interrupted creation/removal are recorded before writes.
Unknown/unowned entries, changed bytes or modes, deleted installed entries and
symlinks cause refusal, not overwrite. The original unintegrated feature had no
ownership marker; any preexisting entry from it requires manual inspection rather
than guessed adoption. Valid preference/receipt data remain readable. The first
installation baseline and previous-upgrade undo remain separate; input preferences
are user data and are never rolled back by a program upgrade.

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
Physical input activation remains a separate user action; publication is not activation.

Historical feature verification on the `fa8808c` source baseline: **297 unit tests passed**
(including 12 focused input tests), existing narrow/large-font Settings layout
checks passed, and the private rendered UI/synthetic-property transport check
passed. No physical input property was changed. Integration is based on main
`e18026e` and retains its completed-output/journal recovery protections. The
integrated suite and installed-toolkit acceptance are recorded in RELEASE-CANDIDATE.

## System acceleration scheme and future activation

Xorg's `AccelerationScheme` is chosen when the device is initialized; it is not
`Device Accel Profile`. With scheme `none`, profile controls can be absent. A
matching configuration file proves configured intent. A matching Xorg initialization
log reporting `selected scheme none/0` is stronger evidence of the scheme selected
at that initialization, but neither proves physical motion response or absence of
application-side acceleration. The development host had both that initialization
evidence and evdev properties without a profile; no hardware was changed to test it.

For a future system-rule/scheme change, plan a separately approved **new Xorg
session** so configuration is reread and the device initialized. Refreshing Settings,
LXQt panel or desktop is insufficient. Reboot is not inherently required; device
reinitialization may be another route, but is not tested or performed here. Changing
an exposed profile through this page is a supported runtime property operation
and does not require a session restart. See the [X.Org initialization/configuration
manual](https://www.x.org/archive/X11R7.0/doc/html/xorg.conf.5.html) and
[pointer acceleration initialization notes](https://www.x.org/Development/Documentation/PointerAcceleration/).

## Can acceleration be disabled universally? — 2026-11-15 finding

On X11, for every pointer that offers a no-acceleration mode, yes. It takes one
setting per driver:

- **evdev pointers**: Xorg `Option "AccelerationScheme" "none"`, or the runtime
  profile -1 this page already applies.
- **libinput pointers**: the runtime property `libinput Accel Profile Enabled` set to
  flat (`0, 1, 0`). A normal user can set it through XInput, but only on devices whose
  `libinput Accel Profiles Available` includes flat. The Xorg equivalent is
  `Option "AccelProfile" "flat"`. This page applies the runtime flat profile
(added 2026-11-15; see above).

Hotplugged devices start from their defaults. There are two ways to cover them:

- A user-session process can listen for XInput device additions and reapply the
  runtime property without root. DoroShell's login helper now does this (see
  Persistence above).
- A root-owned `/etc/X11/xorg.conf.d` InputClass with `MatchIsPointer "on"` sets
  defaults when each device initializes, from the next X server start. DoroShell's
  user-level design does not write it.

Neither approach can make a device offer a flat profile it does not support.

A read-only check on the development machine found a mix. One evdev mouse is
already set to `AccelerationScheme none` by a system rule. Two libinput pointer
interfaces, a keyboard's built-in mouse interface and a virtual HID mouse, still use
the default adaptive profile, and both advertise flat. A read-only capability check
with the updated code offers the flat control for exactly those two and leaves the
evdev mouse alone. Nothing was applied to the live session. Wayland compositors use their own settings and are out of scope.
