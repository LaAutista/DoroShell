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
[Synthetic XEmbed/SNI coexistence](xembed-tray.md) now covers docking, pixels,
input and client restart; real-client variants remain unverified.
These native upgrades are included in the ten-patch runtime observed on November 14.
Their private checks remain distinct from live acceptance or physical mixed-DPI evidence. Current build/package verification is in the
[release record](../RELEASE-CANDIDATE.md).

## Deliberate appearance boundary

Lightweight wallpaper-derived glass is the accepted direction. True transparency
through moving windows and live Aero/compositor experimentation were dropped by
the user, not left as an overnight implementation task. Personal artwork remains
local; source ships neutral assets. No exact visual parity is claimed.

## Remaining work, without expanding this release

1. Representative real-app/notifier checks at an explicitly chosen safe point
   for the now-observed ten-patch panel. Preserve clients, settings and rollback paths.
2. Broader notifier/app diversity, real-client XEmbed variants, long-session behavior and a
   configured [native tray shortcut](tray-shortcut.md) acceptance beyond the synthetic fixture. Pointer-free entry is implemented with no default binding; AT-SPI popup-label export remains a known limitation. Grouped previews and supported
   progress/overlay data are broader feature work, not claimed complete.
3. Physical multi-monitor/mixed-DPI, other WMs and Wayland; additional fonts and
   layouts beyond the documented bounded fixtures.
4. File/settings search, richer menu composition, full-machine portable backups,
   video capture and app sharing remain outside the current implemented scope.
5. Fresh-login and clean-system install/upgrade/rollback are user-deferred, as are
   disruptive hardware/locker acceptance. Existing private tests do not close them.

The November 14 read-only provenance review confirms the selected/running
ten-patch panel. No redundant activation is needed for this documentation pass. See the [feature-family inventory](open-shell-parity.md) for wider scope.

## One-desktop contract

The optional module persists Openbox `desktops/number=1` and `desktops/firstdesk=1`,
preserves original configuration and refuses conflicting placement rules. It does
not migrate live windows. One virtual desktop does not mean one physical monitor.
Any future live migration needs explicit intent and independent preservation and
rollback checks; this release pass did not change desktop count or personal windows.

## Optional animated lock-screen decoration

[Feasibility and next test gate](animated-lock-screen-design.md): a graphics client
for the existing XScreenSaver host, not a replacement locker. Design only; no renderer
integration, live lock test or authentication change is implemented. Next step is a
bounded fake-host embedding probe with synthetic frames and no locker registration.
