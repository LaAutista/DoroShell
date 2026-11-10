# DoroShell source licensing

The original DoroShell source code is licensed under the GNU General Public License, version 2 or (at your option) any later version (`GPL-2.0-or-later`), except where an existing component or file notice specifies different terms. The license text is in [LICENSE](LICENSE). This covers original Python/C++ source, headers, tests, build/install scripts and original patch contributions outside the exceptions below. The code is provided without warranty, as detailed in the license.

No new claim of copyright ownership is made by this declaration. Existing copyright notices and attribution remain intact. Git history records contributions; a commit identity does not replace upstream attribution.

## Component boundaries

| Component | Applicable terms and provenance |
|---|---|
| `panel/` changes and scripts | Keep `LGPL-2.1-or-later`, as declared in its README and source notices. Preserve `panel/licenses/LGPL-2.1.txt`, `LXQt-AUTHORS` and upstream headers. The root GPL grant does not relicense this directory. |
| `screengrab/` modified native ScreenGrab code and patch | `GPL-2.0-or-later`, as stated in its README and upstream file notices. Preserve `screengrab/COPYING` and upstream attribution. Builder pins the upstream revision. Original ancillary scripts are covered by the root GPL grant. |
| `wallpaper/` PCManFM changes, renderer and decoder helper | `GPL-2.0-or-later`, as stated in its README/source notices. Preserve `wallpaper/COPYING` and upstream headers. Builder pins PCManFM's revision. |
| `display/` PCManFM integration and original helper/build code | `GPL-2.0-or-later`. The native header and patch are incorporated into the GPL PCManFM build; preserve PCManFM's existing notices. |
| Other original DoroShell source, including clipboard, app search, folder cascades and portable preferences | `GPL-2.0-or-later` under the root declaration. |

The source builders fetch upstream projects and retain their corresponding source and notices. Installed libraries and applications remain under their own licenses; this declaration does not relicense Qt/PySide, LXQt, KDE, FFmpeg or other dependencies. Distributing native binaries is a separate compliance step requiring the applicable corresponding source, build material and notices; this candidate packages source only.

Open-Shell, Spectacle and Smart Video Wallpaper Reborn are documented behavioral/design references. Their licenses are not asserted as licenses for DoroShell or its artwork; this declaration does not assert that upstream implementation code was copied. Any future reuse must preserve that source's applicable terms and attribution.

## Assets and non-code material

The source-code grant does not grant rights to Doro/NIKKE characters, third-party artwork, personal media, fonts, trademarks or upstream documentation. No such artwork/media is included in the source candidate. The neutral menu and clipboard SVGs are project-authored assets; no third-party ownership or artwork license is invented here. This code-only decision does not assign a new license to assets or prose documentation. Existing asset-specific terms, if any, remain controlling. See [asset policy](docs/assets.md).
