# Legacy social cards

Earlier social card designs, kept so they can be edited and reused. The live card is `../social-preview.png`; its source is `../social-cards/proposals/b-paper-headline.html`.

| Folder or file | What it is |
|---|---|
| `social-preview-v1.svg` / `.png` | The card from PR #28: dark split layout, title and tagline on the left, a `my-app/` folder tree on the right. |
| `social-card-concepts/` | The five-concept design studio from PR #30, with its known issues listed in its README. |

## v1 (PR #28)

Re-render the PNG from the SVG (run from the repository root; this overwrites the committed PNG with an identical render):

```bash
rsvg-convert -w 1280 -h 640 .github/assets/legacy/social-preview-v1.svg -o .github/assets/legacy/social-preview-v1.png
```

This reproduces the committed PNG exactly. Do not render the SVG in a browser: Chromium ignores `xml:space="preserve"`, so the spaces that line up the descriptions collapse and the tree columns lose their alignment. The text uses `Inter` and `DejaVu Sans Mono` by name (not embedded), so a machine without them falls back to other fonts.
