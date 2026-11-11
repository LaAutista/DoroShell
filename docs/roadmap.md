# DoroShell scope and remaining work

DoroShell customizes an existing LXQt desktop; it is not a replacement desktop or
an exact Open-Shell/Windows/Spectacle reproduction. Current source, test evidence
and recorded activation are separated in the [acceptance record](final-acceptance.md).
The older optional and core archives are historical; their smaller test counts
and deployment notes do not describe current main.

## Source-shipped capabilities

- Start: two-column pins/recent apps, ranked local installed-app search, folder
  cascades and editing, portrait cropping, configurable confirmed session actions,
  path-free portable Start preferences and wallpaper-glass rendering fixes.
- Native panel: launcher identity/icon fallback, filter-safe pins, pin/unpin and
  ordering, tray overflow, keyboard menus, attention/auto-hide cleanup, clock and
  calendar, Show Desktop and bounded density/scaling behavior.
- Screenshots: full desktop/window/area capture, editable annotations, text controls,
  redaction/blur/pixelate, delayed recapture and optional native ScreenGrab import.
- Native wallpaper: isolated decoder and Background controls with static fallback,
  mute/volume/pause/Off; guarded optional Advanced display controls are separate.
- Setup: selected modules, previews, original backups, conflict refusal and rollback.
  It does not perform a desktop reset or install packages automatically.

## Completed bounded acceptance

[Identity](taskbar-identity.md) and [filtered pins](taskbar-filters.md) have private
native checks and recorded independent live acceptance. [Tray lifecycle](tray-lifecycle.md)
covers focus, attention, auto-hide, Escape/outside/disconnect and keyboard menus.
[Show Desktop](show-desktop.md) now covers pre-minimized/sticky windows, two virtual
desktops, create/close, repeated toggle, drag-hover and live orientation changes
inside a disposable Openbox session. [Density](panel-density.md) covers long labels,
an enlarged font, 12 tasks and 60 hidden icons at 150%/200% on one narrow Xvfb screen.
These latter source upgrades remain staged; those checks are not a live deployment
or physical mixed-DPI test. Current build/package verification is in the
[release record](../RELEASE-CANDIDATE.md).

## Deliberate appearance boundary

Lightweight wallpaper-derived glass is the accepted direction. True transparency
through moving windows and live Aero/compositor experimentation were dropped by
the user, not left as an overnight implementation task. Personal artwork remains
local; source ships neutral assets. No exact visual parity is claimed.

## Remaining work, without expanding this release

1. Later, explicitly chosen activation and representative real-app/notifier checks
   for the staged panel. Preserve clients, settings and rollback paths.
2. Broader notifier/app diversity, legacy XEmbed, long-session behavior and a
   keyboard-only entry path to tray overflow. Grouped previews and supported
   progress/overlay data are broader feature work, not claimed complete.
3. Physical multi-monitor/mixed-DPI, other WMs and Wayland; additional fonts and
   layouts beyond the documented bounded fixtures.
4. File/settings search, richer menu composition, full-machine portable backups,
   video capture and app sharing remain outside the current implemented scope.
5. Fresh-login and clean-system install/upgrade/rollback are user-deferred, as are
   disruptive hardware/locker acceptance. Existing private tests do not close them.

The next non-disruptive step is a read-only staged-versus-installed provenance
review and a concrete later activation/rollback plan, not another speculative
feature. See the [feature-family inventory](open-shell-parity.md) for wider scope.

## One-desktop contract

The optional module persists Openbox `desktops/number=1` and `desktops/firstdesk=1`,
preserves original configuration and refuses conflicting placement rules. It does
not migrate live windows. One virtual desktop does not mean one physical monitor.
Any future live migration needs explicit intent and independent preservation and
rollback checks; this release pass did not change desktop count or personal windows.
