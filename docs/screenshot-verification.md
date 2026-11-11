# Screenshot verification

Print uses a DoroShell Qt Widgets overlay on X11. Its interaction follows the Plasma 6.4 capture announcement. KDE’s CaptureOverlay.qml carries LGPL-2.0-or-later and uses private Spectacle components. DoroShell implements its overlay independently and does not bundle KDE code. The optional private build of ScreenGrab 3.2.0 adds a PNG input flag and shows the imported pixmap in its native main window. The builder pins the upstream commit and keeps its corresponding source. The changes to ScreenGrab are licensed under GPL-2.0-or-later, matching the modified upstream files. The upstream license text is included in `screengrab/COPYING`. [Plasma 6.4 announcement](https://kde.org/announcements/plasma/6/6.4.0/) · [Spectacle overlay source](https://github.com/KDE/spectacle/blob/v6.4.0/src/Gui/CaptureOverlay.qml) · [LXQt ScreenGrab CLI source](https://github.com/lxqt/screengrab/blob/3.2.0/src/core/core.cpp).

## Precision selection

With **Select** active, drag to create, move or resize a region. The magnifier shows an 11 × 11 patch of the frozen image around the pointer. Each source pixel fills a 7 × 7 logical-pixel cell. The outlined center cell marks the sampled pixel. Black padding marks space outside the image. The lens stays on the target screen, clears the handles and both toolbars, and hides if there is insufficient room.

After releasing the mouse, use the arrow keys to move the crop. Each press moves 15 logical pixels along one axis, converted to frozen-image pixels and rounded to the nearest integer (half up). At 100% this is 15 pixels, at 150% it is 23, and at 200% it is 30. Shift reduces the step to one frozen-image pixel and shows the lens at the adjusted edge. Alt resizes from the fixed top-left corner. Right and Down grow the crop, Left and Up shrink it, and Shift+Alt resizes by one pixel. Movement preserves the crop size at desktop boundaries. Resizing stops at the image boundary or a minimum of one pixel per axis. The overlay consumes these controls only for a completed region in Select mode. Stock Openbox binds Shift+Alt+arrows to desktop actions, so that combination reaches the overlay only when the window manager leaves it available.

Releasing the drag or Shift hides the lens. Annotation tools and window picking hide it as well. Copy, Save and ScreenGrab use the frozen crop and its annotations. The interaction was implemented independently using the tagged [Spectacle 6.4 selection editor](https://github.com/KDE/spectacle/blob/v6.4.0/src/Gui/SelectionEditor.cpp) and [capture overlay](https://github.com/KDE/spectacle/blob/v6.4.0/src/Gui/CaptureOverlay.qml) as references.

## Checks

- On a private X11 display, real Print input froze an open Start menu before dismissal. A selected region retained the expected menu pixels. Escape before selection and during a drag preserved the previous clipboard contents.
- Global Print in a private LXQt/Openbox environment produced the expected crop, ignored incomplete work, and survived setup repeat and rollback. Writer and Draw pasted every expected pixel after the capture UI process exited. The separate X11 clipboard owner released its window when another client replaced the contents.
- Offscreen tests exercised full-desktop Enter, moving and resizing, drawing and undo/redo, saving final PNG pixels, cancelling the save dialog, negative virtual coordinates and mixed image densities. A changed Print command is refused, and a matching command renumbered by LXQt can be updated and restored.
- Two private Xephyr Xinerama heads at 640×480 each were arranged side by side. The same drag spanning the boundary produced an 80×60 image with pixels from both heads at 100% and 150%. Qt exposed their combined Xinerama desktop as one surface. Physical mixed-DPI hardware and Wayland remain unverified.
- On private Openbox/X11 at 100% and 150%, the Window tool selected the upper client in an overlap and clipped a decorated lower client at the screen edge. Every output pixel matched the original frozen desktop after the underlying window changed color.
- A private-display check opened a 260×180 annotated crop in the native ScreenGrab window and used its own Copy command. Every pixel matched the rendered crop. Repeat installation retained the importer and screenshot rollback removed its managed executable. Color and stroke width changes on successive marks were checked against final pixels. The overlay provides raster annotations, rectangular cropping and X11 window selection using the visible client stacking order and window-manager frame extents. It does not reproduce Spectacle’s complete tool set, video or sharing integrations.

From the checkout, the clipboard and cross-monitor checks are:

```sh
python tests/check_window_capture_x11.py --run --xvfb /path/to/Xvfb
python tests/check_screengrab_import_x11.py --run --xvfb /path/to/Xvfb --binary /path/to/import-enabled/screengrab
python tests/check_menu_clipboard_x11.py --run --xvfb /path/to/Xvfb
python tests/check_overlay_multimonitor_x11.py --run --xvfb /path/to/Xvfb --xephyr /path/to/Xephyr
```

The clipboard test requires LibreOffice and Python UNO. These checks use private displays, temporary homes and synthetic pixels. The full core check also exercises the installed Print binding and rollback. See [core release verification](verification.md).

## Independent editing interaction check

`tests/check_overlay_editing_x11.py` uses real XTest pointer input on a private X11 desktop to select, resize and move a crop, redact pixels and undo/redo the annotation. The real Qt save dialog is canceled once, then used to save a PNG; every output pixel matches the final annotated crop and cancellation leaves the editor open. Enter without a selection confirms the full frozen desktop. The private clipboard sentinel remains unchanged throughout. The test uses Qt's non-native dialog to avoid dependence on an external portal and does not claim native portal-dialog coverage.

```sh
python tests/check_overlay_editing_x11.py --run --xvfb /path/to/Xvfb
```
