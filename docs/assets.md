# Custom icons and rights

The bundled `menu/start.svg` is a simple project-authored geometric menu icon. No third-party art, character image, screenshots, or generated character variants are included. Rights to redistribute the prototype's Doro artwork were not established, so it is omitted even though this repository is private.

To customize a checkout for personal use, replace `menu/start.svg` with an SVG you created or have permission to use, then run `python install.py menu --apply`. Keep custom artwork local unless its license permits redistribution. The installer will record the new managed content. If LXQt caches the old icon, refresh the panel at a convenient time; do not restart the desktop session. For PNG artwork, update the icon source/target in `install.py` and the desktop entry Icon path together, then test the installer in a temporary home before applying it.

The original private desktop installation is independent of this sanitized source checkout; preparing this repository did not remove or change its personal icon.

## Doro mascot source research — 2026-11-08

### Approved visual direction

The approved mascot direction is a white, four-legged, potato-like creature with a pink fringe and side locks, round purple eyes, a tiny catlike mouth, and a rose bun with a purple ribbon. Preserve that silhouette and those facial details in future mascot work. Approval covers the visual direction only; it does not request replacement of working assets or publication of the concept sheet. The concept sheet and personal reference images are not bundled here. This approval does not change the asset provenance requirements below.

Doro is the requested mascot. The existing personal Start icon and animated GIF remain unchanged. This research adds no artwork to the repository or installer.

| Candidate | Source and suitability | Verification and reuse status |
| --- | --- | --- |
| Original-style Doro emotes | [Arca.live emote pack](https://arca.live/e/32606), linked by [Know Your Meme's origin account](https://knowyourmeme.com/memes/dororong). Compact emotes are a promising reference for a small Start icon. | The secondary account dates the pack to June 2023 and describes a composite of Dorothy's head and a pre-existing chibi body. The original pack could not be fetched in this research session; authorship and permission for a particular image remain unverified. |
| Transparent Doro stickers and animations | [MemeBako collection](https://memebako.com/en/meme/doro). Useful for browsing expressions and choosing a visual direction. | A collection/repost is not proof of the original artist's permission. No verified software-redistribution license was established. Do not bundle from this source on the strength of download buttons or personal-use claims. |
| Official-account artwork lead | [NIKKE English post](https://x.com/nikke_en/status/1975742959535726671), attributed as a source by [a Zerochan listing](https://www.zerochan.net/4613475). The listing credits Meiya Neon; a large ensemble image is less suitable as a tiny panel icon. | The original post returned HTTP 403. Artist credit and terms could not be independently confirmed; this is a lead, not a cleared asset. |

The [NIKKE EULA](https://nikke-en.com/pre/termsofservice/) does not establish a general license to redistribute character artwork as this toolkit's mascot. Its gameplay-video provisions are not evidence of permission for a software asset. This is a record of verification limits, not a conclusion that every possible fan use is prohibited.

For a future bundled asset, record the exact original image URL, author, applicable permission/license, required credit, permitted modifications and distribution scope before adding it. Credit alone is not a license. Keep an artwork-specific notice separate from the project's eventual source-code license. Until suitable permission is verified, retain the neutral bundled SVG and the local custom-asset workflow.
