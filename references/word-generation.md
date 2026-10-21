# Word Generation (Hebrew RTL + OMML equations)

How to produce a `.docx` with correct right-to-left Hebrew and **real, editable** Word
equations — validated end to end (built from raw XML, rendered by LibreOffice, read back
as PDF). No third-party library is required: a `.docx` is a ZIP of XML parts, and OMML
equations must be injected as XML anyway (python-docx cannot author OMML), so building the
XML directly is both dependency-free and gives full control over the tricky parts.

Day-to-day you write documents with **`scripts/report_kit.py`** (below). The low-level writer
is `scripts/build_docx.py`; the rest of this file documents the mechanics it encodes, so the
output can be understood, extended, and debugged.

## Authoring with report_kit (use this)

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.expanduser('~'), '.claude','skills','lab-report-writer','scripts'))
from report_kit import Report, build_prep, build_study, build_summary, write_images_readme, M, HL

EXP = os.path.dirname(os.path.abspath(__file__))          # build.py lives in the experiment folder

def q8(r):
    r.p('התדר הצפוי מסוכם ב' + r.ref('tab:f') + ', לפי ' + r.ref('eq:f') + '.')
    r.eq('f', r'f=\frac{1}{2RC\ln\left(\frac{V_p}{V_n}\right)}')
    r.calc('f', r'\frac{1}{2\cdot10k\cdot0.1\mu F\cdot\ln\frac{2.9}{1.9}}', r'1182\,\text{Hz}')
    r.table('f', rows, ['$V_{DD}$ [V]', '$f$ [Hz]'], 'תדר התנודות הצפוי', explain='…')

r = Report(EXP, 'prep'); build_prep(r, {'q8': q8, …}); r.save()
write_images_readme(EXP)
```

- `r.p("… $V_p>V_n$ … ==ערך לאימות==")` — `$…$` is inline LaTeX math, `==…==` is a yellow
  highlight. Write **every** symbol, subscript and relation as `$…$`, never as plain text.
- `r.ref('fig:key' | 'tab:key' | 'eq:key')` → `איור 3` / `טבלה 2` / `נוסחה (4)`; call it in the
  sentence *before* the object; the object then reuses the same number.
- `r.eq(key, latex)` numbered display equation · `r.math(latex)` unnumbered step ·
  `r.calc(formula, substitution, result)` the house calculation line.
- `r.figure(key, path, caption, explain)` · `r.booklet_figure(key, caption_no='1.3', caption=…)` ·
  `r.table(key, rows, header, caption, explain)` — cells accept the same markup.
- `r.note(...)` small italic remark (assumptions) · `r.todo(...)` user-to-write placeholder ·
  `r.bullets([...])` · `r.h1/h2/h3` · `r.page_break()`.

LaTeX subset (`mathtex.py`): `\frac \sqrt \sqrt[n]` `_ ^ {}` `\left( \right)` `\text{}` `\ln \log
\exp \sin \cos` Greek letters, `\cdot \times \approx \le \ge \ne \pm \to \infty \parallel \propto`,
spacing `\, \; \quad`. Units in `\text{…}` (upright): `1182\,\text{Hz}`.

## Minimum viable .docx: the five parts

```
[Content_Types].xml            # declares part content-types
_rels/.rels                    # points to word/document.xml
word/document.xml              # the content
word/_rels/document.xml.rels   # points to styles.xml
word/styles.xml                # default fonts/sizes + named styles
```

Write them into a ZIP with stdlib `zipfile` (`ZIP_DEFLATED`). Validate every
`document.xml` by reparsing it (`xml.dom.minidom.parseString`) before zipping — a
malformed part makes Word refuse the file silently.

## Element ordering — the silent Word-breaker (READ THIS)

OOXML defines a **required child order** for `<w:pPr>` and `<w:rPr>`. **Word enforces it and
silently drops out-of-order children; LibreOffice ignores the order** — so a docx can look
perfect in a LibreOffice→PDF check yet render wrong in Word. This bit us once: `jc` placed
before `spacing` made Word drop the alignment and left the text left-aligned. Always emit in
schema order:

- `w:pPr` order: `pStyle → keepNext → … → bidi → spacing → ind → jc → …`
  (so **keepNext, bidi, spacing, then jc**). For RTL paragraphs, `bidi` alone right-aligns —
  emit `jc` only for center/left/justify. `keepNext` glues headings and pictures to what
  follows (no orphaned heading at a page bottom, no picture separated from its caption).
- `w:rPr` order: `rFonts → b → bCs → i → iCs → … → color → … → sz → szCs → highlight → … → rtl → cs`
  (so bold/italic, color, size, **highlight before rtl, and `rtl` last**).
- `w:sectPr` order: `footerReference → pgSz → pgMar → titlePg → bidi` — a `bidi` placed first
  (as an early version did) is out of order. `titlePg` gives a cover without a page number;
  the PAGE field lives in `word/footer1.xml`.
- Table header rows carry `<w:trPr><w:tblHeader/></w:trPr>` so they repeat across pages.

`build_docx.py` already encodes this in `_rpr()` and `para()`. When hand-writing XML, match
the official template (`docs/עמוד ראשון חדש.docx`), which is a known-good ordering reference.

## Highlighting values that need verification

The user does NOT want inline "(לאימות)" text notes. Instead, **highlight in yellow** any
value the reader must verify (datasheet figures, assumed component values, results pending
missing inputs). In `build_docx.py` use the `('hl', text)` token inside `para(...)`/table
cells, or `highlight=True` for a whole paragraph — it emits `<w:highlight w:val="yellow"/>`.
Genuinely *missing* information is different: don't guess — mark it with a short highlighted
"חסר: …" note AND ask the user for it (or fetch a datasheet from the web with permission).

## Right-to-left Hebrew

RTL is set at three levels; all three are needed for reliable rendering:

1. **Section** — inside `<w:sectPr>` add `<w:bidi/>`.
2. **Paragraph** — inside `<w:pPr>` add `<w:bidi/>` (and usually `<w:jc w:val="both"/>` or
   `right`).
3. **Run** — inside `<w:rPr>` add `<w:rtl/>` for Hebrew text runs.

A Hebrew paragraph helper:

```python
def he_para(text, style=None):
    sp = f'<w:pStyle w:val="{style}"/>' if style else ''
    return (f'<w:p><w:pPr>{sp}<w:bidi/></w:pPr>'
            f'<w:r><w:rPr><w:rtl/></w:rPr>'
            f'<w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>')
```

Always XML-escape user/text content (`&`, `<`, `>`). Use `xml:space="preserve"` so
leading/trailing spaces survive.

**Fonts**: set a Hebrew-capable default in `styles.xml` docDefaults (e.g. `David`) for
`w:ascii`, `w:hAnsi`, and `w:cs`. Latin tokens (component names, units) render fine in the
same run; keep them as plain text inside the RTL paragraph — Word's bidi algorithm places
them left-to-right automatically.

**Known cosmetic bidi quirk**: parentheses/brackets that wrap a Latin token inside Hebrew
(e.g. `(RTL)`, `(ניסוי 1)`) can look mirrored in LibreOffice's PDF. Word itself renders
them correctly, so don't chase it. If it must be forced, wrap the Latin token + its
parentheses in their own run with an explicit LTR mark (`‎`).

**Correctness-critical bidi rule — relational expressions.** A relational/ordered
expression with Latin operands written as plain text in an RTL run gets **reordered** by
the bidi algorithm and can display *reversed* — `Vp > Vn` may render as `Vn > Vp`,
silently flipping the meaning. This is a real error, not cosmetic. So any inequality,
ordering, or relation (`Vp > Vn`, `Vn < Vin < Vp`, `T ≈ 1.1 ms`, `A → B`) must be emitted
as **inline OMML**, not as text — pass it as a `('math', mrun('Vp > Vn'))` token inside
`para(...)`. Inline math has its own left-to-right direction and is immune to the flip.
The editing-QA pass explicitly checks for reversed relations.

## OMML equations (real, editable math)

Declare the math namespace on the document root:
`xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"`.

Wrap a display equation in `<m:oMathPara><m:oMath>…</m:oMath></m:oMathPara>` inside a
centered paragraph. Building blocks (composable):

```python
def r(t):                       # a math run (text token)
    return f'<m:r><m:t xml:space="preserve">{t}</m:t></m:r>'

def frac(num, den):             # fraction
    return f'<m:f><m:num>{num}</m:num><m:den>{den}</m:den></m:f>'

def ssub(base, sub):            # subscript, e.g. V_p
    return f'<m:sSub><m:e>{base}</m:e><m:sub>{sub}</m:sub></m:sSub>'

def ssup(base, sup):            # superscript / power
    return f'<m:sSup><m:e>{base}</m:e><m:sup>{sup}</m:sup></m:sSup>'

def rad(radicand, degree=None): # square/nth root
    deg = f'<m:deg>{degree}</m:deg>' if degree else '<m:degHide m:val="1"/><m:deg/>'
    return f'<m:rad><m:radPr>{deg}</m:radPr><m:e>{radicand}</m:e></m:rad>'

def delim(inner, beg='(', end=')'):   # (…) parentheses that scale
    return (f'<m:d><m:dPr><m:begChr m:val="{beg}"/><m:endChr m:val="{end}"/></m:dPr>'
            f'<m:e>{inner}</m:e></m:d>')
```

Example — `f = 1 / (2RC · ln(V_p / V_n))`:

```python
vp_over_vn = frac(ssub(r("V"), r("p")), ssub(r("V"), r("n")))
den = r("2RC ") + r("&#183;ln") + delim(vp_over_vn)     # &#183; = middle dot ·
eq  = r("f") + r("=") + frac(r("1"), den)
omath = ('<m:oMathPara xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
         f'<m:oMath>{eq}</m:oMath></m:oMathPara>')
```

Use HTML numeric entities for symbols that are awkward to embed literally (`&#183;` ·,
`&#215;` ×, `&#8722;` −, `&#8804;` ≤, `&#8805;` ≥, `&#8734;` ∞, `&#960;` π, `&#937;` Ω,
`&#956;` µ). Greek letters render as normal `m:t` text.

An equation numbered inline in the text uses `<m:oMath>` (no `oMathPara`) inside a normal
run so it flows with the sentence.

### Rendering rules learned the hard way (all verified on rendered pages, Exp 1, 2026-10)

mathtex.py already applies the first three; the rest are writing rules for `build.py` content.

1. **Operator ending a group** (`V_{T+}`, `V_{T-}`, `V_{T+}=2.9`): LibreOffice shows `¿` and can
   swallow the rest of the expression into the subscript. `m:sty`, `m:nor`, `m:lit` do **not**
   help. mathtex appends an invisible operand (U+2060 WORD JOINER) after the operator.
2. **Units and capital Greek** (`\text{k}\Omega`, `0.1\,\mu\text{F}`, `\Delta`): emitted as
   normal text (`<m:rPr><m:nor/></m:rPr>`). With `m:sty p` or italic, LibreOffice draws Ω/µ
   slanted and overlapping ("0.1µF" garbled in table cells). Function names (`\ln`) stay `sty p`.
3. **No Hebrew inside `$…$`** (check_docx ERROR): a math zone is LTR and reverses Hebrew. Put the
   words in the sentence around the formula (`r.p('קבל שנטען מ־$0\,\text{V}$…')` then `r.calc(…)`).
4. **Upright multi-letter symbols**: `\mathrm{NM}_H`, not `NM_H` (which reads as N·M).
5. **A signed value in an RTL cell/sentence** (`+5V`) shows as `5V+`: write it as math
   `$+5\,\text{V}$`.
6. **Do not end a Hebrew sentence or table cell with a parenthesis that holds math or Latin**
   (`… (או עולה ולא הגיע ל־$V_p$)`, `… ($T_{sim}=0.47$).`): at a line end the parentheses and
   the period jump sides. Rephrase so the formula sits mid-sentence.
7. **Don't open a sentence with `ב־` + Latin + comma** (`ב־NAND, "0" …`): the bidi algorithm
   reorders the opening. Lead with a Hebrew word (`בשער NAND מספיק "0" …`).
8. **Number+unit table cells** (`0.470 ms`) are converted to math by `Report.table` (an RTL
   cell would print `ms 0.470`); pass them as plain strings, no `$` needed.
8a. **Numbers in Hebrew sentences are handled automatically** (`build_docx.ltr_islands`, applied
   to every RTL text run): a number+unit (`0.470 ms`), a range (`2.2–3.6`, `2%–4%`) or a value
   list (`1.1 / 1.7 / 2.1 V`) is wrapped as LRM … RLM, with NBSP and word-joiners inside so it
   never wraps. Without it the bidi algorithm prints `ms 0.470`, `3.6–2.2` and reversed lists
   (found by the editing QA agent on all three Exp 1 documents; LibreOffice and Word agree). The
   closing mark must be RLM: a closing LRM pulled the following `; (3)` into the island.
   check_docx WARNs on any unprotected island. Still write comparisons as words or math
   (`מינימום 4.95 (טיפוסי 5.0)`, not `≥ 4.95 (typ 5.0)` in a cell).
8a'. **A formula next to a number+unit in the same cell/phrase** (`$R_X$ = 10 kΩ`) still comes out
   reversed ("10 kΩ = R_X"): the math object and the text island are separate runs. Write the
   whole relation as one formula: `$R_X=10\,\text{k}\Omega$`.
8a''. **Arrows in Hebrew text**: a chain that mixes Latin and Hebrew ("CO → מהפך → PE") or digits
   ("0→15") is reordered and reads backwards. Write it in words ("CO דרך מהפך אל PE", "מ־0 עד 15").
   A chain of Latin tokens only ("CO → CI") is one LTR run and is fine; in checklists use "←" for
   "save as" so the arrow points along the Hebrew reading direction.
8a'''. **Wiring / pin tables**: one connection per row (columns `מ־` / `אל`), plain text such as
   `4013, הדק 5 (D)` and `VDD`/`Q̄` (Unicode macron) instead of `$V_{DD}$`/`$\overline{Q}$`.
   A cell that chains several connections with math in between ("R1 להדק 4; $R_X$ = 100 kΩ …")
   is reordered beyond recognition. Values go in the explanation line under the table. Also
   avoid ending a cell or sentence with a list such as "0, 5, 10 V" or "1 kHz, 50%": rephrase
   ("בשלוש רמות", "1 kHz ובמחזור עבודה של 50%").
8b. **Several references at once**: `r.refs('fig:a', 'fig:b', 'fig:c')` → `איורים 4, 6 ו־8`
   (sorted); never `(איור 8, איור 4, איור 6)`. `r.ref('eq:x')` already says `נוסחה (3)`, so don't
   write `הנוסחה «ref»` (prints `הנוסחה נוסחה (3)`) — write `«ref»` or `(«ref»)`.
8c. **Verifying bidi objectively**: don't judge mixed-direction lines by eye. Print the PDF line
   in true visual order (PyMuPDF `rawdict` chars sorted by x) and compare: an LTR island must
   appear exactly as typed.
9. **Compatibility Mode**: a package without `word/settings.xml` declaring
   `<w:compatSetting w:name="compatibilityMode" … w:val="15"/>` opens in Word as "מצב תאימות"
   (legacy mode, where equations may be treated as old objects). DocxBuilder writes it; a
   hand-built docx must too (part + content-type override + relationship).
10. **Writing backslashes from a shell**: in this Windows Bash tool, heredocs collapse `\\`, so a
   patch to `build.py` (non-raw strings need `\\text`) silently becomes `\t` = TAB. Edit
   `build.py` with the Edit tool, and compile with `python -W error::SyntaxWarning`.

### Layout behaviour built into the engine (don't re-implement)

- **Tables**: `w:tblLayout fixed` + `dxa` widths. Without `widths`, `_auto_widths` sizes each
  column by its longest cell (`len·130+360` twips, min 900), shrinking by square-root share when
  the total exceeds the text width (9026 twips). Rows are `cantSplit`; the header row repeats.
  `tblPr` child order: `bidiVisual, tblW, jc, tblBorders, tblLayout`.
- **New page**: `heading(…, new_page=True)` / `r.h1(…, new_page=True)` set `w:pageBreakBefore` on
  the heading itself. A separate page-break paragraph that lands exactly at a page end produces
  a blank page (that happened before the quiz solutions).
- **Image width**: `Report.figure(..., width_cm=)` is an exact width (booklet figures default
  11 cm), not a maximum, so small booklet crops are not left tiny.
- **Booklet figure crops** (`extract_requirements.py`): short labels are absorbed, body-text
  lines are trimmed out, and the crop is shrunk to the inked area (`_ink_bbox`, at 3 px/pt so
  thin light lines count), because a drawing canvas is often much wider than the circuit. The
  booklet's own "תרשים 1.x" label is removed (the report writes its own caption): its TEXT is
  redacted from the in-memory page (graphics kept), because the label's text box can overlap the
  drawing (figure 1.2's ground symbol) so no crop line separates them. Default width 9.5 cm.

## Images (simulation figures, later scope photos)

Embed a PNG by adding it as a part (`word/media/imageN.png`), a relationship in
`document.xml.rels` (`.../image`), and a `<w:drawing>` inline anchor referencing that
rId, with an EMU size (`1 px ≈ 9525 EMU`; keep width ≤ ~5,760,000 EMU to fit the page).
Follow the picture with a centered caption paragraph (`איור <n> – …`).

## Self-verification loop (do this for every generated .docx)

LibreOffice renders the file the way Word roughly will, so convert and **read the PDF**:

```bash
soffice --headless \
  --convert-to pdf --outdir "<out dir>" "<file>.docx"
```

(The `Could not find platform independent libraries` warning is harmless; check exit code
and that the PDF appeared.) Then open the PDF with the Read tool and confirm: RTL alignment,
equations rendered as math (not literal text), figures present and sized, captions and
numbering continuous. This is the objective check the editing-QA pass relies on — never
declare a document correct from the XML alone.

Practical page review: copy each .docx to an ASCII name in the scratchpad first (OneDrive
locks/Unicode paths break soffice), convert, then render with PyMuPDF
(`page.get_pixmap(dpi=85)`) as two-page spreads and look at **every** spread. Zoom
(`clip=`) on any table or formula that looks off. Things to look for specifically: `¿` or `□`
in math, slanted/garbled Ω µ, a period or parenthesis on the wrong side, numbers like
`ms 0.470`, blank pages, tables squeezed to one-word columns, tiny booklet figures.

**Note**: only one LibreOffice process can convert at a time per profile; convert files
sequentially, or pass a unique `-env:UserInstallation` per parallel job.
