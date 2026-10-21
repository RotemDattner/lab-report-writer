# QA Layer — three review passes

Before any report is marked "ready to submit", it passes three **independent** review
passes. Run them as separate reviewers (subagents via the Agent tool) so each looks with
fresh eyes and isn't anchored on the drafting rationale. Each returns findings ranked by
severity; the skill fixes them and re-runs the relevant pass. Nothing ships until all three
are clean (or every remaining item is explicitly justified).

Independence matters: the value is a second look, not a rubber stamp. A reviewer that only
re-reads what the author already believed adds nothing. **Give every reviewer the booklet
(`requirements/` incl. `figures/`) as the source of truth** — in validation, a reviewer without
the booklet approved a period computed for the wrong circuit topology.

## Step 0 — deterministic check (before the agents)

`python scripts/check_docx.py <doc> --req requirements/requirements.json` on every document.
It catches numbering gaps, unreferenced/unexplained figures, question numbering that differs
from the booklet, missing answers, "(לאימות)" tags, first person in the summary, plain-text
relations (bidi risk), missing page numbers, non-repeating table headers. Fix all ERRORs first;
the agents then spend their attention on substance.

## Step 0.5 — look at every page

Render each document (LibreOffice → PDF → PyMuPDF page PNGs) and view every page yourself:
equations rendered as math (no empty boxes □ — a sign of a malformed sub/superscript), RTL,
pictures sized and next to their captions, no orphaned headings, nothing cut at a page edge.

## Pass 1 — Simulations & code
Checks the MATLAB scripts and SPICE netlists.
- Every MATLAB script **runs** via the MCP with no error and produces its PNG.
- Results are **physically sensible** (right order of magnitude, correct units, no
  non-physical values — negative resistances, voltages beyond the rails, etc.).
- The script's analytic cross-check is present and its error is small; if not, the
  discrepancy is understood and explained (which of model vs. analysis is right?).
- The netlist is well-formed; ICs without SPICE models are handled per
  `references/simulation.md` (not silently faked); the build guide matches the schematic.
- Parameter values trace back to the requirement/datasheet, not invented.

## Pass 2 — Calculations, formulas & physics
Checks every numeric answer and derivation in the reports.
- Each calculation is **numerically correct** — recompute independently (MATLAB / Symbolic
  Math), don't eyeball.
- Derivations are valid step to step, and any **assumption is stated and actually holds**
  for the given values (the classic failure: applying a symmetric-case formula to an
  asymmetric case).
- **Units are consistent** and carried through; final units match the quantity.
- Answers are physically reasonable and consistent with the simulation from Pass 1.
- Datasheet-dependent values are either verified against `datasheets/` or **highlighted in
  yellow** for the user (never a "(לאימות)" text tag — check_docx rejects it).

## Pass 3 — Editing, formatting & submission-readiness
Checks the rendered Word documents (work from the LibreOffice-rendered PDF, not the XML).
- **Hebrew RTL** is correct throughout — alignment, no broken bidi, no mojibake.
- **No stray line/paragraph/page breaks**, no empty runs, no overflowing tables.
- **Equations render as math** (OMML), not as literal text.
- **No bidi-reversed relations**: every inequality/ordering with Latin operands
  (`Vp > Vn`, `Vn < Vin < Vp`) reads in the correct direction — these must be inline OMML,
  never plain text in an RTL run (plain text flips them and inverts the meaning).
- **Numbering is continuous and gap-free** for figures (`איור`), tables (`טבלה`), and
  questions; every figure/table is **referenced by number** in the body before it appears.
- Image placeholders in the summary skeleton are consistent and keyed to `images/…` files;
  once photos are inserted, captions and numbers are correct and in order.
- The document matches the required format (header block, the fixed 6 summary sections,
  question numbering identical to the requirement).
- Cross-document consistency: the same symbol/notation/value is used everywhere it appears.

## Reporting
Summarize QA results to the user per experiment: what passed, what was fixed, and anything
left highlighted in yellow for them to confirm. The user's job is to verify simulations, confirm
the writing, and write conclusions — QA exists to make that final check fast and safe, not
to replace the user's sign-off.
