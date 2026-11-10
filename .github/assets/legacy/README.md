# Legacy social cards

Earlier social card designs, kept so they can be edited and reused. The live card is `../social-preview.png`; its source is `../social-cards/proposals/b-paper-headline.html`.

## v1 (PR #28): `social-preview-v1.svg` and `social-preview-v1.png`

Dark split layout: title and tagline on the left, a `my-app/` folder tree on the right.

Re-render the PNG from the SVG:

```bash
rsvg-convert -w 1280 -h 640 .github/assets/legacy/social-preview-v1.svg -o social-preview-v1.png
```

This reproduces the committed PNG exactly. Do not render the SVG in a browser: Chromium ignores `xml:space="preserve"`, so the spaces that line up the descriptions collapse and the tree columns lose their alignment. The text uses `Inter` and `DejaVu Sans Mono` by name (not embedded), so a machine without them falls back to other fonts.
