# Report Format

Structures and conventions for the three documents. `report_kit.py` implements them; this
file explains the *why* so content written into the scaffolds fits.

## Course config — `<course>/course.json`

Copy `assets/course.example.json` and fill it in (all fields optional except `lab`):

```json
{"lab": "מעבדה 2", "faculty": "הפקולטה להנדסה",
 "department": "המחלקה להנדסת חשמל ואלקטרוניקה", "logo": "logo.png",
 "students": [{"name": "<שם מלא>", "id": "<ת.ז.>", "contact": "<דוא\"ל / טלפון>"}],
 "scope_serial": "", "simulator": "Multisim", "booklets_dir": "<תיקיית החוברות>",
 "max_pages_summary": 15, "scope_width_cm": 11}
```

`logo` is looked up in the course folder first, then in `assets/`. The public skill ships no
logo: each user puts their institution's logo in the course folder. A missing logo just leaves
the cover without one. `max_pages_summary` is the page budget of a summary report;
`render_pages.py` warns when it is exceeded. `scope_width_cm` is the default width of every
picture whose file name contains `scope`.

## Per-experiment facts — `<experiment>/lab.json`

Filled after the lab. `scope_intake.py` writes a draft, and the user confirms it:

```json
{"date_performed": "19/10/2026", "date_submitted": "26/10/2026", "scope_serial": "MY…",
 "supplies": [5, 10], "measured": {"R1": "9.8 kΩ", "C1": "0.103 µF"}}
```

The cover takes both dates and the serial from it; `lab.json` overrides `course.json` for the
serial. When the file is missing, the cover leaves `____________` blanks. `measured` is for
`build.py`: show each value as "nominal (נמדד measured)" in the component table and compute
with the measured value. Up to 3 students fit the table.
These are personal details: they stay in the user's own course folder, never in the skill.

## Cover (official Ariel-University template, `docs/עמוד ראשון חדש.docx`)

Logo · faculty · department · `<lab> – דוח מכין/מסכם מספר N` · `שם הניסוי: ניסוי מס' N – <title>`
· execution/submission dates · participants table (`שמות המבצעים | מס' ת.ז. | דוא"ל / טלפון |
מס' סידורי - סקופ`). The **summary** adds the integrity declaration and a `תאריך | חתימה` table.
No page number on the cover (title page), numbers on all other pages (required by the 2026
guidelines).

## Numbering & captions (identical in all documents)

- **Continuous** across the document: `איור 1, 2, …`, `טבלה 1, 2, …`, equations `(1), (2), …`.
- Figure caption **below** the picture; table caption **above** the table; equation number on the
  left: `(n)  f = …` — as in the official guidelines' examples.
- **Under every figure and table, one line explaining what it shows** (2026 guideline).
- Every figure/table/equation is **referenced in the text before it appears** — use
  `r.ref('fig:key')` inside the sentence; the number is fixed at first reference.
- Booklet circuits are embedded from `requirements/figures/` with the caption noting
  `(תרשים X.Y מחוברת הניסוי)`.

## Preparatory report (דוח מכין)

- One heading per booklet question, **verbatim and with the booklet's own numbering**, including
  lettered sub-parts and the question's bullets — `build_prep` generates these from
  `requirements.json`, so numbering cannot drift. Answers are supplied per key: `q7`, `q7ב`.
- Calculations: formula → substitution → result with units (`r.calc`). Derivations as numbered
  equations. State every assumption; if it is one the user must confirm, highlight it.
- The simulation question: per circuit, the MATLAB graph(s), a slot for the user's Multisim
  screenshot (`images/q<NN>_<circuit>_multisim.png`), a short explanation, and a
  theory-vs-simulation table.
- The wiring question: a slot for the matrix wiring drawing (`images/q<NN>_matrix.png`) plus a
  textual connection list (which IC pin goes where) the user can wire from.
- Bibliography = the booklet's list (+ datasheets used).

## Self-study document (מסמך הכנה עצמית) — personal, not submitted

Goal: the user understands the experiment well enough to pass the short pre-lab quiz and to
run the lab confidently. **Visual first**: every idea that can be shown is shown with a graph
from the experiment's simulations or a dedicated demo simulation.

1. הניסוי בדקה — goal, the circuits, what is measured.
2. מושגי יסוד — table of terms with one-line explanations.
3. הרכיב — pinout, truth table, the datasheet numbers that matter (with VDD dependence).
4. נוסחאות מפתח — each: equation, meaning, **when it is valid**, units, worked example.
5. מעגלי הניסוי צעד אחר צעד — what each circuit does, expected waveforms (simulation graphs),
   what to expect on the scope.
6. סימולציות הדגמה — e.g. a noisy input with vs. without hysteresis; frequency vs. R and C;
   what changes when an assumption breaks. One graph + 2–3 lines of insight each.
7. מלכודות נפוצות — the mistakes people make (and that this project made once).
8. צ'קליסט למעבדה — what to build, measure, and save (with the image file names).
9. בוחן לדוגמה — 10–12 questions (multiple choice, conceptual, numeric); solutions in a separate
   section at the end, each with a short explanation.
10. דף נוסחאות — one page.

## Summary report (דוח מסכם) — official 2026 structure

Authoritative source: `docs/הנחיות לדוח מסכם 2026.pdf`. **Third person / passive only**
("נמדד", "נבנה המעגל") — check_docx flags first-person words.

1. `מטרת הניסוי` — a few lines.
2. `תקציר` — what was done and the main results (after the lab).
3. `רקע תאורטי` — only what is *new* in this experiment: components, figures (each explained),
   numbered equations, and the units table (`גדלים ויחידותיהם`).
4. `ציוד נדרש` — with component values.
5. `מהלך הניסוי` — **one section 5.k per booklet "מהלך הניסוי" part**, and inside it the booklet's
   own steps (א, ב, …). Per section: circuit (booklet figure) + explanation, components table,
   equation references; per measuring step a **simulation picture and a scope picture** with a
   comparison sentence; per question step an answer; a theory/simulation/measured/error table;
   a discussion.
6. `מסקנות` — written by the user (guiding questions provided as placeholders), or from the
   user's points when they ask.

After the lab, follow the content policy in SKILL.md ("After the lab"):
- one capture per measured step, plus a simulation only where it explains something;
- only the booklet formula in section 5;
- measured component values;
- fair deviation columns;
- one sentence for every anomaly;
- few highlights;
- the page budget.
7. `ביבליוגרפיה`.

## Image slots and names (`images/README.txt` is generated — never hand-edit it)

`r.figure(key, path, caption, explain)` embeds the file if it exists, else prints a red
placeholder with the exact file name. Names stay ASCII; booklet step letters become numbers
(א=1, ב=2, …):

- summary: `images/<sec>.<step>_sim.png`, `images/<sec>.<step>_scope.png`, e.g. `5.1.2_scope.png`
  = section 5.1, step ב; extra variants get a suffix (`5.2.2_scope_10V.png`).
- preparatory: `images/q<NN>_<what>.png`, e.g. `q10_c13_multisim.png`, `q11_matrix.png`.
- PNG or JPG. After the user saves files, re-run the experiment's `build.py`.

## Placeholders (what check_docx expects)

- `[[ … ]]` grey italic = for the **user** to write (summary before/after the lab).
- red `[[ איור n – יש לשמור את התמונה בשם … ]]` = image slot.
- yellow `[[ חסר: … ]]` = missing answer — an ERROR in a preparatory report.
- Yellow highlight on normal text = **verify this** (assumption, value read from an image or
  datasheet). Never the text tag "(לאימות)".
