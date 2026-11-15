# Read-only Start power availability

Start checks whether Shut down, Restart, Sleep and Hibernate are currently reported
available to the calling user. Previously it checked only for an installed LXQt
desktop entry. The primary button, its selection menu and the power menu now use
both checks, with visible reasons on unavailable menu entries and explanatory
tooltips. A saved primary action remains selected even if it becomes unavailable;
Start does not rewrite the preference or silently choose another action.

| Service reply | Direct Start action | Meaning shown |
| --- | --- | --- |
| `yes` | Enabled if the LXQt entry exists | Reported available without further authentication |
| `challenge` | Enabled with explicit notice | Authorization required after confirmation through LXQt |
| `no` | Disabled | Not permitted for this user |
| `na` | Disabled | Reported unsupported by current hardware/kernel/drivers |
| Inhibitor replies | Disabled | Inhibited; no override is attempted |
| Absent service, denied query, timeout, error or unknown reply | Disabled | Availability unknown, with a fixed reason |

These are the meanings of the [logind capability methods](https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.login1.html).
They are an advisory snapshot, not physical hardware testing or a guarantee that a
later request succeeds. Actual behavior remains with LXQt and the system. Existing
Log out, Lock screen and **All session options…** retain their launcher-based
behavior. No locker discovery, configuration or security behavior is changed.
The native options dialog remains reachable when this optional capability service
is unavailable or the desktop uses a different backend.

## Query scope and timing

The optional Qt D-Bus helper sends only `CanPowerOff`, `CanReboot`, `CanSuspend` and
`CanHibernate` to `org.freedesktop.login1.Manager` at `/org/freedesktop/login1` on
the system bus. It does not introspect other services, list sessions/inhibitors,
start a daemon, launch a privilege agent, or call any modifying method. Both service
activation and interactive authorization flags are explicitly disabled, using
[Qt's message flags](https://doc.qt.io/qt-6/qdbusmessage.html).
Missing Qt D-Bus or a missing/unreachable service leaves the result unknown; neither
is installed or enabled automatically. Existing package requirements are unchanged.

Checks occur when Start is shown and when **Refresh power availability** is chosen.
No capability polling or hidden-window capability timer runs. The four requests are asynchronous, each
with a 1,500 ms [Qt reply timeout](https://doc.qt.io/qt-6/qdbusconnection.html#asyncCall),
plus a 1,600 ms single-shot UI deadline. Pending refreshes coalesce. These timeouts
run through Qt's event loop and are not a hard real-time guarantee if that loop is
blocked. Hiding/closing discards pending results; a late reply cannot revive a
cancelled or newer check. Completed callbacks are bound to their Qt owner.

The result is not watched continuously: reopen Start or explicitly refresh after
capability changes. No result is persisted, logged or sent elsewhere. Error text
uses fixed labels; raw service strings and identifiers are not displayed or logged.

## Confirmation and preference handling

Queries never execute an action, request authentication or queue a future action.
Unknown/pending/denied states cannot be chosen as a new primary action. Selecting
an available primary action only saves that preference through the existing
conflict-safe settings path. It does not execute the action or authenticate.

Direct actions retain the existing Cancel-default confirmation and safe GIO launch
of the installed LXQt desktop entry, without shell interpolation. A `challenge`
adds an authorization explanation before that same confirmation. The cached state
is checked before confirmation and again afterward; if it changed to unavailable,
dispatch stops. There is no automatic retry after a later successful query. No
power/session/lock call is added to the capability helper. Native LXQt handling and
existing session-history exclusions remain unchanged.

## Verification boundary

Tests use fake Qt D-Bus responses, synthetic catalogs, disposable HOME/XDG paths and
fake/blocked launch/session dispatch. Real Qt message flags/watchers, timeout and
stale-result handling, disabled primary/menu consistency, capability changes,
absence/errors, challenge vs yes/no/na, owner destruction and actual offscreen
Cancel/Yes dialog interaction are covered. Temporary installation/repeat/conflict
refusal/exact rollback cover both helper copies; installed imports and widgets are
also checked. No personal system/session bus is probed, no credentials are requested
and no real power, sleep, logout or lock action is executed.

This does not establish live logind/LXQt/polkit compatibility, physical sleep/resume,
inhibitor behavior on hardware, AT-SPI/screen-reader, live X11, login or clean-OS
acceptance. No blocked Xvfb probe, package/service/security change or session refresh
is part of this source candidate.
