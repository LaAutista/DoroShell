# One desktop and future modules

This is the original planning snapshot. The working tree now includes optional modules and settings; see the README and verification report for implemented behavior and current limits. Live workspace migration and post-login acceptance remain outstanding.

Exactly one virtual desktop, with all ordinary application windows accessible on it, is a required future setup default. This does not mean disabling multiple monitors.

The current installer does not implement workspace changes. A live prototype was separately repaired to one Openbox desktop, with its existing windows moved without closing applications and the saved count verified. Persistence across logout/reboot remains untested.

The eventual module must detect the active window manager and effective config path, back up original content/mode, and change only owned settings. For Openbox, the desired persisted values are desktops/number=1 and desktops/firstdesk=1. Check conflicting application-placement rules and session startup tools. Use dry run, repeatable application, atomic file writes and scoped rollback; refuse conflicting personal edits.

For an expressly requested live migration, inventory clients, move ordinary windows to EWMH desktop 0, preserve sticky windows, select desktop 0, and reduce the count to 1. Verify no original clients were lost and minimized windows can be restored. Keep the panel/window manager intact. Never force logout or reboot to test persistence.

Acceptance requires a user-initiated new login and a clean-install VM check: one desktop, current index 0, and windows accessible through taskbar/Alt-Tab. Add equivalent config support for other window managers only after verifying their behavior.

Other future modules are screenshots, taskbar behavior, snapping and Dolphin defaults. Each requires its own dependency plan, narrow changes, backups, tests and rollback. They are not implemented or enabled by this release.
