# Screenshot verification

Print uses a DoroShell Qt Widgets overlay on X11. Its interaction follows the Plasma 6.4 capture announcement. KDE’s CaptureOverlay.qml carries LGPL-2.0-or-later and uses private Spectacle components. DoroShell implements its overlay independently and does not bundle KDE code. The optional private build of ScreenGrab 3.2.0 adds a PNG input flag and shows the imported pixmap in its native main window. The builder pins the upstream commit and keeps its corresponding source. The changes to ScreenGrab are licensed under GPL-2.0-or-later, matching the modified upstream files. The upstream license text is included in `screengrab/COPYING`. [Plasma 6.4 announcement](https://kde.org/announcements/plasma/6/6.4.0/) · [Spectacle overlay source](https://github.com/KDE/spectacle/blob/v6.4.0/src/Gui/CaptureOverlay.qml) · [LXQt ScreenGrab CLI source](https://github.com/lxqt/screengrab/blob/3.2.0/src/core/core.cpp).

## New capture, monitor and pointer options

Print freezes the desktop immediately. When Start is open, its menu remains visible in that first frozen frame. Enter with no region selected copies the full frame.

Choose **New capture…** in the overlay for a fresh frame. Each opening defaults to full desktop, zero delay and pointer off. On X11, **Monitor under pointer** takes only the head containing the pointer hotspot at capture time. After a monitor capture, Enter copies that monitor. A delay of 1–60 seconds shows a countdown. Move the pointer to the desired monitor before it ends. **Cancel** in the options or countdown returns to the previous edit, including its annotations and crop. Escape in the editor cancels the entire capture. A successful retake replaces the previous edit and opens the new frame for editing before anything is copied.

The editor and countdown close before sampling, with a short repaint interval. An explicit retake sees the then-visible desktop, so a Start menu already dismissed after the initial Print is absent. **Include pointer** reads the X11 XFixes cursor image and hotspot in native root pixels. At monitor edges only the visible portion is included. Unsupported root geometry, missing XFixes or capture failure returns to the previous edit. The cursor and desktop are separate server reads, so a rapidly moving or animated pointer can differ slightly in time from the desktop pixels. Private X11 coverage includes a timed color change, countdown cancellation, exact hotspot placement and two Xinerama heads at 100% and 150%. Physical mixed-DPI monitors, third-party compositor animations and Wayland recapture are unverified.

## Window borders

Press **W** or click **Window**. **Include titlebar and borders** starts checked for each capture. Clear it, or press **B**, to crop to the client area. The preview follows the setting. Clicking the topmost window’s titlebar selects that window in either mode. After selection, Enter copies the crop and Escape cancels. The choice lasts for this frozen editor.

Both rectangles come from the X11 geometry recorded at freeze time. The frame uses the window manager’s reported frame extents. Where extents are absent, both modes use the client rectangle. Titlebars drawn by the application itself remain part of the client image. Crops are clipped to the captured screen or monitor. They include any overlapping windows exactly as they appeared in the frozen image. A frame whose client is entirely outside the captured area can only be selected with borders included. Popups are not grouped with their parent, and no extra margin is added for compositor shadows.

## Precision selection

With **Select** active, drag to create, move or resize a region. The magnifier shows an 11 × 11 patch of the frozen image around the pointer. Each source pixel fills a 7 × 7 logical-pixel cell. The outlined center cell marks the sampled pixel. Black padding marks space outside the image. The lens stays on the target screen, clears the handles and both toolbars, and hides if there is insufficient room.

After releasing the mouse, use the arrow keys to move the crop. Each press moves 15 logical pixels along one axis, converted to frozen-image pixels and rounded to the nearest integer (half up). At 100% this is 15 pixels, at 150% it is 23, and at 200% it is 30. Shift reduces the step to one frozen-image pixel and shows the lens at the adjusted edge. Alt resizes from the fixed top-left corner. Right and Down grow the crop, Left and Up shrink it, and Shift+Alt resizes by one pixel. Movement preserves the crop size at desktop boundaries. Resizing stops at the image boundary or a minimum of one pixel per axis. The overlay consumes these controls only for a completed region in Select mode.

**On stock Openbox, use Ctrl+Shift+arrow to resize by one frozen-image pixel.** Openbox reserves Shift+Alt+arrows for desktop actions. Both resize chords work when delivered to the overlay, including when a toolbar button has focus. While editing the stroke width, arrows operate the spin box.

Releasing the drag or Shift hides the lens. Annotation tools and window picking hide it as well. Copy, Save and ScreenGrab use the frozen crop and its annotations. The interaction was implemented independently using the tagged [Spectacle 6.4 selection editor](https://github.com/KDE/spectacle/blob/v6.4.0/src/Gui/SelectionEditor.cpp) and [capture overlay](https://github.com/KDE/spectacle/blob/v6.4.0/src/Gui/CaptureOverlay.qml) as references.

## Editing existing annotations

Choose **Edit marks** and click an annotation. A dashed outline identifies the selected mark. Where marks overlap, the uppermost mark under the pointer wins. Blur and Pixelate sit below the other marks. Click the outline of a hollow rectangle or ellipse, the ink of a freehand stroke or arrow, the filled area of a redaction, or the text label. Click empty space to clear the selection.

Drag the selected mark to move it, press **Delete** to remove it, or double-click a text label (or select it and press **F2**) to edit its contents. Cancelling the text dialog or submitting an empty label retains the original text. Each completed move, deletion or text replacement takes one undo step. Undo restores the mark at its original stacking position. Redo reapplies the edit. A fresh edit clears redo history.

Edits preserve the crop and the mark’s color and stroke width. Marks can cross the crop boundary. Export clips the artwork to the crop and omits the selection outline. Switch to **Select** to move or resize the crop with the mouse or arrow keys. Escape in the overlay cancels the capture.

## Text labels

Choose **Text** and click where the label’s baseline should start. The dialog opens with the overlay font and current ink color. Enter a single line, choose the font family and point size, and set bold, italic and color as needed. **OK** applies the label. Cancelling discards the draft, including formatting changes.

To restyle an existing label, choose **Edit marks**, click the label, then choose **Edit text…**. Double-click and **F2** open the same dialog. Each label keeps its formatting when moved. Confirming changes to the wording, font and color together takes one undo step. Escape inside the text dialog returns to the overlay. Escape in the overlay cancels the capture and preserves the clipboard.

## Straight lines and numbered stamps

Choose **Line** and drag between two points. Hold **Shift** while dragging or releasing to snap to the nearest multiple of 45°. Snapping keeps the pointer distance from the fixed endpoint, rounded to whole logical coordinates. A click or a drag back to the start adds no mark and preserves redo history. Lines use the current ink color and stroke width.

Choose **Number** and click to stamp a filled circle. Each new stamp uses the smallest unused positive integer, starting at 1. For example, deleting 2 from a set of 1, 2 and 3 leaves 1 and 3 in place, and the next stamp gets 2. Undo and redo restore the original labels. In **Edit marks**, double-click a stamp or select it and press **F2** to set its number. Manually assigned labels may repeat. Stamps use the current ink color, a contrasting label and a circle sized to fit its digits.

In **Edit marks**, drag either mark to move it or press **Delete** to remove it. Click a line first to expose its endpoint handles. Drag a handle to reshape the line, optionally holding Shift. Dropping one endpoint exactly on the other restores the original line. Each completed change takes one undo step. Crop boundaries clip the exported artwork. The toolbars wrap on narrow screens. Layout checks cover widths of 320, 400 and 600 logical pixels at a height of 480 with the default font and with the font enlarged by three points.

## Blur, Pixelate and solid Redact

Choose **Blur** or **Pixelate** and drag a rectangle in any direction. **These effects visually obscure detail. They do not securely remove information.** Use solid black **Redact** to cover sensitive pixels in the exported image. The frozen original remains available in the editor until the capture closes.

Both effects sample only the covered region of the frozen image. Blur uses Qt’s smooth downsampling followed by bilinear enlargement. Pixelate enlarges its samples into flat blocks. The sample count on each axis is the covered size in frozen pixels divided by 6 for Blur or 12 for Pixelate, rounded up. A small region may become one averaged color. A single frozen pixel retains its original color. Effect strength is fixed.

Effects paint first. Where two effects overlap, the most recently drawn effect supplies the pixels from its own frozen-source samples. Ink, stamps, text and black redactions paint above all effects in their original order. **Edit marks** picks the top visible mark. Drag an effect to resample the new location, or press Delete to remove it. Movement keeps the entire rectangle inside the desktop. Undo and redo restore its location and stacking order. Selection outlines stay in the editor. Cropping applies after annotation rendering.

## Checks

- On a private X11 display, real Print input froze an open Start menu before dismissal. A selected region retained the expected menu pixels. Escape before selection and during a drag preserved the previous clipboard contents.
- Global Print in a private LXQt/Openbox environment produced the expected crop, ignored incomplete work, and survived setup repeat and rollback. Writer and Draw pasted every expected pixel after the capture UI process exited. The separate X11 clipboard owner released its window when another client replaced the contents.
- Offscreen tests exercised full-desktop Enter, moving and resizing, drawing and undo/redo, saving final PNG pixels, cancelling the save dialog, negative virtual coordinates and mixed image densities. A changed Print command is refused, and a matching command renumbered by LXQt can be updated and restored.
- Two private Xephyr Xinerama heads at 640×480 each were arranged side by side. The same drag spanning the boundary produced an 80×60 image with pixels from both heads at 100% and 150%. Qt exposed their combined Xinerama desktop as one surface. Physical mixed-DPI hardware and Wayland remain unverified.
- On private Openbox/X11 at 100% and 150%, the Window tool selected the upper client in an overlap and clipped a decorated lower client at the screen edge. Every output pixel matched the original frozen desktop after the underlying window changed color.
- A private-display check opened a 260×180 annotated crop in the native ScreenGrab window and used its own Copy command. Every pixel matched the rendered crop. Repeat installation retained the importer and screenshot rollback removed its managed executable. Color and stroke width changes on successive marks were checked against final pixels. The overlay provides raster annotations, rectangular cropping and X11 window selection using the visible client stacking order and window-manager frame extents. It does not reproduce Spectacle’s complete tool set, video or sharing integrations.

From the checkout, the clipboard and cross-monitor checks are:

```sh
python tests/check_recapture_x11.py --run --xvfb /path/to/Xvfb
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
