# Optional coordinated themes

Windows Doro (pink), Polar Doro (blue), Heretic Doro (charcoal/red) and Spring Doro (green/cream) are optional palettes. Select one under **DoroShell Settings → Apps & Themes → Coordinated Doro theme**, preview, then apply. Keep unchanged is the default. No personal artwork is bundled or replaced.

From source:

```sh
python setup.py theme --theme polar          # preview
python setup.py theme --theme polar --apply
python setup.py theme --rollback
```

The theme covers Start, the theme-capable DoroShell panel, LXQt Qt palettes, Dolphin, Kate including its editor, and Openbox titlebars. Breeze icons use the palette where supported. It does not recolor GTK applications, browser page content or third-party artwork. Fusion provides consistent Qt widget geometry. These are coordinated palettes inspired by the reference, not pixel-identical Windows skins.

Settings are saved for normal application/desktop startup; no application, panel or session is stopped. Some LXQt palette changes may appear immediately. Openbox and the panel take the new colors on their next normal startup. The previously published core panel does not read these optional palettes: build the updated panel into a separate directory and use the documented next-login profile workflow. Do not overwrite a running build.

Each managed setting and generated theme file has a backup. Repeated application and theme switching preserve the original baseline. Restore refuses conflicting edits and preserves unrelated app settings and MIME associations. Restore overlapping Kate/Dolphin dark-theme modules in reverse application order. Avoid switching themes while another program is saving its appearance preferences. A write failure attempts to recover the previous theme; an ongoing disk failure or concurrent edit can still require recovery from `.local/state/doroshell/theme.json`.

Click the portrait above Start's folder column to choose a local image directly. Enter or Space also opens the picker when the portrait has focus. Cancel preserves the current image. This is independent from the Start-button image.

Validation uses temporary homes for switch/repeat/restore, conflicting edits and write failures. A private X11 session renders the actual Dolphin, Kate, Openbox, Start and separately built panel in all four palettes. This is not a clean-install or normal-login acceptance test. Personal preview images are excluded from release packaging.

## Non-composited appearance

The existing opaque gradients in all four palettes provide an Aero-inspired finish on non-composited X11. This is **simulated glass**, not background blur or transparency. No compositor is required, installed, configured or launched by the theme module. No new animation, polling timer or background capture has been added. Keep unchanged remains the default; existing theme apply/rollback behavior is unchanged.

A small additional highlight/bevel experiment was tested privately and omitted. It showed no extra sustained repainting, but Heretic's synthetic search p95 increased in the paired measurements; the cause is uncertain. The small visual benefit did not justify that uncertainty. The existing styles and personal session remain unchanged. [Measurement method, results and limitations](opaque-theme-verification.md).
