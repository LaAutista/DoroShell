# DoroShell 0.3.0-rc.1

This candidate builds DoroShell's applications, setup, updater and rollback tools in C++20. It targets Arch-based LXQt/X11 desktops with Openbox. The release sources include the reviewed LXQt, PCManFM and ScreenGrab patches, their upstream revision pins, and the files needed to build them.

RC2's existing updater downloads a new Git revision, invokes its source verifier, and then calls `python3 deploy.py` directly. The small adapter at that path passes the revision, channel and arguments to the native bootstrap. The new runtime uses native executables for setup and subsequent updates.

The source-code license is in [LICENSE](LICENSE). The [artwork catalog](assets/catalog.json) records the origins and separate license status of the graphics and wallpaper media the owner chose to distribute. The release export includes bundled assets and their checksums. It excludes personal configuration, user histories, login credentials, local build caches and development backups.

See the [verification notes](docs/native-rewrite.md) for isolated session, installation and recovery tests and for hardware coverage.
