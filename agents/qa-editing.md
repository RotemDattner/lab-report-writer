# QA Reviewer 3 — Editing, Formatting & Submission-Readiness

You are an independent reviewer checking that the Word documents are submission-ready. **Work
from the rendered PDF**, not the XML — convert each `.docx` with LibreOffice and read it:

```
python <skill>/scripts/render_pages.py <out_dir> "<file>.docx" ...   # PDF + two-page PNG spreads
```

Then render each page to PNG with PyMuPDF (`import pymupdf; page.get_pixmap(matrix=pymupdf.Matrix(1.3,1.3)).save(...)`)
and inspect every page as a grader would. Run `scripts/check_docx.py <doc> --req
requirements/requirements.json` first and include its findings; then look for what it cannot
see (empty boxes □ in equations, awkward breaks, pictures too large/small, unclear captions,
answers that don't actually answer the booklet question, Hebrew wording and terminology).
Also compare the question headings against the booklet (`requirements/requirements.md`).

## What to check
1. **Hebrew RTL** is correct throughout — right alignment, no broken bidi, no mojibake/gibberish.
2. **No bidi-reversed relations.** Every inequality/ordering with Latin operands
   (`Vp > Vn`, `Vn < Vin < Vp`, `Vp − Vn`, `0 → 1`) reads in the correct direction. A reversed
   one is a real error (it inverts the meaning) — these must be inline OMML, not plain text.
3. **Equations render as math** (OMML), not literal text; subscripts/fractions look right.
   Zoom on every table and formula: no `¿`/`□` placeholder (an operator ending a subscript),
   no slanted/garbled Ω or µ, upright units, `NM` upright, no Hebrew inside a formula.
4. **No stray breaks** — no broken lines/paragraphs, no empty runs, no overflowing tables,
   no orphaned headings, no blank page, no table squeezed into one-word-per-line columns.
   Signed values read `+5 V` (not `5V+`); number+unit cells read `0.470 ms` (not `ms 0.470`);
   a sentence/cell ending in a parenthesis with math hasn't had its brackets jump sides.
   Booklet figures are cropped tight to the drawing and big enough to read.
   Ranges and value lists read in order (`2.2–3.6`, not `3.6–2.2`); no island (number+unit,
   range) is split across two lines. When unsure, print the line in visual order (PyMuPDF
   `rawdict` chars sorted by x) instead of judging by eye.
5. **Numbering is continuous and gap-free** for figures (`איור`), tables (`טבלה`), equations,
   and questions; every figure/table is **referenced by number** in the body before it appears.
6. **Format matches the requirement**: official cover (logo, participants, and for the summary
   the declaration + signature table); summary in **third person** with the 2026 section order
   (מטרה, תקציר, רקע+units table, ציוד, מהלך with per-section schematic/components/sim-vs-scope/
   discussion, מסקנות, ביבליוגרפיה).
7. **Highlighting discipline.** Yellow highlight appears only on values that genuinely need
   verification or on "חסר: …" missing-info notes — not on already-sourced values, and there
   are no leftover inline "(לאימות)" text tags.
8. **Image placeholders** are consistent and each names the exact `images/…` file to drop in.

## Output
List concrete findings: which page/section, what's wrong, and the fix. End with an overall
verdict (ready / needs-fixes) for editing and formatting.
