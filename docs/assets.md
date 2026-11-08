# Custom icons and rights

The bundled `menu/start.svg` is a simple project-authored geometric menu icon. No third-party art, character image, screenshots, or generated character variants are included. Rights to redistribute the prototype's Doro artwork were not established, so it is omitted even though this repository is private.

To customize a checkout for personal use, replace `menu/start.svg` with an SVG you created or have permission to use, then run `python install.py menu --apply`. Keep custom artwork local unless its license permits redistribution. The installer will record the new managed content. If LXQt caches the old icon, refresh the panel at a convenient time; do not restart the desktop session. For PNG artwork, update the icon source/target in `install.py` and the desktop entry Icon path together, then test the installer in a temporary home before applying it.

The original private desktop installation is independent of this sanitized source checkout; preparing this repository did not remove or change its personal icon.
