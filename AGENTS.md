# DoroShell project guidance

DoroShell is an LXQt customization/setup toolkit with Plasma-like features, not a standalone desktop environment or replacement shell. Read README.md before editing. Keep changes small and reversible.

Do not restart the desktop session, close applications, or execute logout/power actions during tests. Test installer changes with temporary homes first. Live panel integration requires explicit user intent; avoid unrelated workspace changes.

Use GIO for desktop-entry launching and standard user-directory APIs for folders. Never parse desktop Exec strings with a shell. Keep package changes explicit. Preserve personal settings, backup original values, support repeat installation and rollback, and refuse conflicting edits.

Run `python -m unittest discover -s tests -v`. Distinguish mocks, local desktop checks and fresh-install tests. Never claim login or clean-install testing without doing it.

Do not commit personal configs, private paths, screenshots from real desktops, credentials, caches, binaries, or unlicensed third-party artwork. The neutral SVG is the default. Keep runtime legacy paths compatible unless implementing a tested migration.
