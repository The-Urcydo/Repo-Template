# Social card proposals (1280x640)

Three redesign directions for the repository social preview. They sit beside the card merged in PR #28 (`.github/assets/social-preview.svg` / `.png`, which stays as it is) and the concept studio in PR #30 (`.github/assets/social-cards/index.html`). These files have their own names, so they do not overlap either PR.

Nothing here ships to generated projects: Copier copies only `template/`.

## The three directions

| File | Direction | Idea |
|---|---|---|
| `a-sharper-tree` | Dark, close to #28 | Same layout and brand, bigger type, brighter secondary text, the proof line `python3 tools/check.py` with `ok`. The chips are gone. |
| `b-paper-headline` | Light, type-led | The tagline is the picture. The five folders are the footer strip. Stands out in dark feeds. |
| `c-one-command` | Dark, bold | The real command and the real result. A giant `ok` is the picture. |

Each direction has a `.html` source and a `.png` render. The copy comes from the README tagline and the `my-app/` tree from PR #28. `python3 tools/check.py` prints `ok` on a freshly generated project (checked on `main` at `532cd3e`).

## What they fix compared with the PR #30 concepts

- Legible at thumbnail size (about 400px wide, as Slack, X and LinkedIn show it): smallest text is 22px on the 1280px canvas.
- No clipped text, no `...`, no wrapped commands, no studio controls on the page, so a screenshot is the card.
- Inside the 1120x520 safe zone (80px sides, 60px top and bottom).
- Fonts are embedded (`fonts.css`, subset Inter and DejaVu Sans Mono), so the PNG does not depend on the fonts installed on the machine.
- Text contrast is at least 4.5:1, or 3:1 for large text (the lowest measured is 5.65:1).

## Preview and render

Open any `.html` file in a browser. To write the PNG:

```bash
npx playwright screenshot --viewport-size=1280,640 --wait-for-timeout=500 \
  "file://$(pwd)/.github/assets/social-cards/proposals/a-sharper-tree.html" a-sharper-tree.png
```

This reproduced the committed PNGs pixel for pixel on the machine that made them.

## Fonts

`fonts.css` embeds Inter (SIL Open Font License 1.1) and DejaVu Sans Mono (Bitstream Vera / DejaVu free license) as subset woff2 data URIs. Subset: Basic Latin, Latin-1, common punctuation, arrows, box-drawing and the check mark. Add a character outside that set and it falls back to a system font, so re-subset the fonts first.

## Not decided here

The owner picks the winner and uploads the PNG in Settings, Social preview. Whether to keep the dark teal brand (A and C) or go light (B) is a taste call.
