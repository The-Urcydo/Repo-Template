# Social Card Design Studio (`1280×640`), archived

> **Archived (PR #30).** Kept so the concepts can be edited and reused. The live card is `../../social-preview.png`; its source is `../../social-cards/proposals/b-paper-headline.html`. Do not write captures from this studio to `.github/assets/social-preview.png`, which is the live card.

This folder holds the editable HTML source for five `Repo-Template` social preview card concepts (`1280×640`, the GitHub OpenGraph 2:1 size). It lives under `.github/assets/` so it never ships inside generated Copier projects (`template/`).

## Known issues (found when #30 was reviewed; none fixed here)

- **The Exit button shows in every `?card=N` render**, so a plain capture puts "Exit 1280×640 Isolation (ESC)" in the PNG. Hide `.exit-isolation-btn` before capturing (snippet below).
- **Fonts are not bundled** (no `@font-face`), so the output depends on the fonts installed on the machine.
- **Small text:** counted by characters, 59%, 62% and 65% of the text in concepts 2, 3 and 4 is 13px or smaller on the 1280px canvas (concept 1: 29%, concept 5: 28%; smallest sizes 10–12px). In a 400px-wide render only concept 05 reads clearly (a visual check).
- **Layout:** concept 1 ends five descriptions in `…`, concept 3 splits "Repo-" and "Template", concept 2 wraps its clone URL and footer command; in concept 4 the badge crowds the "CORE KERNEL (ALWAYS KEPT)" header and pushes "KEPT)" onto a second line, and `.copier-answers` is an 8th tile in the "7 modules" grid.
- **Safe zone:** text in concepts 1, 2 and 4 sits outside the `1120×520` safe zone.

## Files

- [`index.html`](index.html): Self-contained interactive HTML/CSS studio containing **5 distinct social card concepts**:
  1. **Concept 01 — The Volatility Architecture** *(Flagship evolution of PR #28's split layout with lifecycle speed badges and `check.py --strict` status bar)*
  2. **Concept 02 — Human-Agent Orchestration Blueprint** *(1 Human Decision Authority ↔ Tool-Neutral Harness ↔ N Parallel Sibling Worktrees)*
  3. **Concept 03 — Context Budget Pyramid & Verification Pipeline** *(3-tier progressive context loading + `transition.py` independent role gate)*
  4. **Concept 04 — Cuttable Modular Matrix** *(Immutable Core Kernel + 7 detachable Copier modules via `remove_module.py`)*
  5. **Concept 05 — Swiss Typographic Manifesto** *(High-contrast light editorial poster)*

## How to use it

1. **Preview all 5 cards side-by-side:** Open `.github/assets/legacy/social-card-concepts/index.html` in any browser.
2. **Check the safe zone (`1120×520`):** Click **Toggle Safe Zone (1120×520)** in the top bar (or append `?safezone=1`) to see the `80px` horizontal and `60px` vertical margins.
3. **Isolate a single `1280×640` card:** Click `1280×640 #01`..`#05` in the header, or open `index.html?card=1` (through `5`). The studio header and toolbar disappear and the chosen card sits at `(0, 0)`; only the Exit button remains.
4. **Capture it to a PNG** with the Exit button hidden. Run it from the repository root; it needs the Node `playwright` package (`npm i playwright`) and writes `concept-01.png` into the current folder, so delete the file or write it outside the repository. Replace `1` with the concept number and `concept-01.png` with a name that is not the live card:
   ```bash
   node -e "
   const { pathToFileURL } = require('url');
   const { chromium } = require('playwright');
   (async () => {
     const b = await chromium.launch();
     const p = await b.newPage({ viewport: { width: 1280, height: 640 } });
     await p.goto(pathToFileURL(process.cwd() + '/.github/assets/legacy/social-card-concepts/index.html').href + '?card=1');
     await p.addStyleTag({ content: '.exit-isolation-btn{display:none!important}' });
     await p.screenshot({ path: 'concept-01.png' });
     await b.close();
   })();"
   ```
5. **Edit tokens or copy:** All palette tokens (`--accent-teal`, `--bg-obsidian`, font stacks) live at the top of `index.html` under `:root`, and each concept is scoped under `#card-01` through `#card-05`.
