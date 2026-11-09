# Social Card Design Studio (`1280×640`)

This folder holds the editable HTML source for `Repo-Template`'s social preview card concepts (`1280×640` GitHub OpenGraph 2:1 standard). It lives under `.github/assets/social-cards/` so it never ships inside generated Copier projects (`template/`).

## Files

- [`index.html`](index.html): Self-contained interactive HTML/CSS studio containing **5 distinct social card concepts**:
  1. **Concept 01 — The Volatility Architecture** *(Flagship evolution of PR #28's split layout with lifecycle speed badges and `check.py --strict` status bar)*
  2. **Concept 02 — Human-Agent Orchestration Blueprint** *(1 Human Decision Authority ↔ Tool-Neutral Harness ↔ N Parallel Sibling Worktrees)*
  3. **Concept 03 — Context Budget Pyramid & Verification Pipeline** *(3-tier progressive context loading + `transition.py` independent role gate)*
  4. **Concept 04 — Cuttable Modular Matrix** *(Immutable Core Kernel + 7 detachable Copier modules via `remove_module.py`)*
  5. **Concept 05 — Swiss Typographic Manifesto** *(High-contrast light editorial poster)*

## How Designer Agents & Reviewers Can Collaborate via PR

1. **Preview all 5 cards side-by-side:** Open `.github/assets/social-cards/index.html` in any browser.
2. **Check the safe zone (`1120×520`):** Click **Toggle Safe Zone (1120×520)** in the top bar (or append `?safezone=1`) to verify that all text and badges clear the `80px` horizontal and `60px` vertical clipping margins.
3. **Isolate a single `1280×640` card for PNG rendering:**
   - Click `1280×640 #01`..`#05` in the header, or open `index.html?card=1` (through `5`).
   - In isolation mode, all studio chrome disappears and the chosen `1280×640` card sits at `(0, 0)` with zero margin, ready for deterministic headless browser capture:
     ```bash
     npx playwright screenshot --viewport-size="1280,640" \
       "file://$(pwd)/.github/assets/social-cards/index.html?card=1" \
       .github/assets/social-preview.png
     ```
4. **Edit tokens or copy:** All palette tokens (`--accent-teal`, `--bg-obsidian`, font stacks) live at the top of `index.html` under `:root`, and each concept is scoped under `#card-01` through `#card-05`.
