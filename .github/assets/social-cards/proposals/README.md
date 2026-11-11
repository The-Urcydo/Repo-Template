# Social card sources (1280x640)

The live card is `.github/assets/social-preview.png`, rendered from `b-paper-headline.html` (direction B, chosen by the owner). A and C are kept as alternates. The card from PR #28 is in `../../legacy/`.

Nothing here ships to generated projects: Copier copies only `template/`.

## The three directions

| File | Direction | Status |
|---|---|---|
| `b-paper-headline.html` | Light, type-led. The tagline is the picture; the five folders are the footer strip. Stands out in dark feeds. | **Live.** Its render is `../../social-preview.png`. |
| `a-sharper-tree.html` / `.png` | Dark, close to the #28 card. Bigger type, brighter secondary text, the proof line `python3 tools/check.py` with `ok`. | Alternate |
| `c-one-command.html` / `.png` | Dark, bold. The clone command, the check, and a giant `ok` (the first word of the real output). The command is the README's `copier copy` without the destination folder. | Alternate |

The tagline "One human. Several AI agents. One structure." and the five folder meanings come from the card merged in #28; "A Copier template for agent-ready repositories" follows the first line of `AGENTS.md`. On a freshly generated project `python3 tools/check.py` prints a line that starts with `ok` and then the number of placeholders left (`ok (15 placeholder(s); list them with: python3 tools/check.py --stubs)` on `main` at `532cd3e`); cards A and C show the first word.

## Built to avoid the problems found in the PR #30 concepts

- Readable at thumbnail size (about 400px wide, as Slack, X and LinkedIn show it): the title, headline and tagline stay legible. The smallest text is 22px on the 1280px canvas, about 7px at 400px, so it is a hint there, not something to read.
- No clipped text, no `...`, no wrapped commands, no studio controls on the page, so a screenshot is the card.
- Inside the 1120x520 safe zone (80px sides, 60px top and bottom).
- Fonts are embedded (`fonts.css`, subset Inter and DejaVu Sans Mono), so the PNG does not depend on the fonts installed on the machine.
- Text contrast is at least 4.5:1, or 3:1 for large text (the lowest measured is 5.65:1).

## Preview and render

Open any `.html` file in a browser. To write the live card after editing B:

```bash
npx playwright screenshot --viewport-size=1280,640 --wait-for-timeout=500 \
  "file://$(pwd)/.github/assets/social-cards/proposals/b-paper-headline.html" .github/assets/social-preview.png
```

For A or C, write the PNG next to its `.html`. This reproduced the committed PNGs pixel for pixel on the machine that made them.

## Fonts

`fonts.css` embeds Inter (SIL Open Font License 1.1) and DejaVu Sans Mono (Bitstream Vera / DejaVu free license) as subset woff2 data URIs. The licence texts are in [`FONT-LICENSES.md`](FONT-LICENSES.md). Subset: Basic Latin, Latin-1, common punctuation, arrows, box-drawing and the check mark. Add a character outside that set and it falls back to a system font, so re-subset the fonts first.

## Upload

Settings, Social preview, upload `.github/assets/social-preview.png`. This is an owner step.
