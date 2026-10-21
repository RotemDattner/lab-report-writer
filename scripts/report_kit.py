# -*- coding: utf-8 -*-
"""
report_kit.py — the layer every experiment build script uses (on top of build_docx.py).

What it adds, and why:
  * Automatic, continuous numbering of figures / tables / equations. Captions are written as
    "איור N – …" (below figures) and "טבלה N – …" (above tables); equations as "(N)". Refer to
    anything before it appears with r.ref('fig:key') -> "איור 3" — the number is fixed at first
    use, so text references and captions can never disagree.
  * Light authoring markup in Hebrew prose: $…$ = inline LaTeX math (via mathtex — also the
    bidi-safe way to write V_p>V_n), ==…== = yellow highlight (something the user must verify).
  * Image slots: r.figure(...) embeds a picture if the file exists, otherwise prints a visible
    placeholder naming the exact file to save. Every slot is recorded, and
    write_images_readme() turns them into images/README.txt — so the naming convention in the
    README is generated from the documents themselves and can't drift from them.
  * Scaffolds driven by requirements/requirements.json (from extract_requirements.py):
      build_prep    — every question/sub-part exactly as numbered in the booklet; answers are
                      supplied per key ('q7', 'q7ב'); anything unanswered is flagged.
      build_summary — official 2026 structure; section 5.k per "מהלך הניסוי" part, with
                      per-step slots (simulation vs. scope pictures, answers, tables).
      build_study   — the self-study / quiz-prep document.
  * Course details (logo, students, lab name) come from <course>/course.json.
"""
import os, re, json
from build_docx import DocxBuilder
from mathtex import tex

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAP_COLOR = '1F3864'
HEB_ORD = {c: i + 1 for i, c in enumerate('אבגדהוזחטיכלמנסעפצקרשת')}

DOC_NAMES = {'prep': 'דוח מכין.docx', 'summary': 'דוח מסכם.docx',
             'study': 'מסמך הכנה עצמית.docx'}

# ---------------------------------------------------------------- course / requirements
def load_course(course_dir):
    path = os.path.join(course_dir, 'course.json')
    cfg = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}
    cfg.setdefault('lab', 'מעבדה')
    cfg.setdefault('faculty', 'הפקולטה להנדסה')
    cfg.setdefault('department', 'המחלקה להנדסת חשמל ואלקטרוניקה')
    cfg.setdefault('logo', 'logo.png')               # put your institution's logo in the course folder
    cfg.setdefault('scope_width_cm', 11)              # scope screenshots: readable, and saves pages
    cfg.setdefault('max_pages_summary', None)         # page budget of the summary report, if any
    cfg.setdefault('students', [])
    # a relative logo is looked up in the course folder first (a friend's own logo), then in assets/
    if not os.path.isabs(cfg['logo']):
        for base in (course_dir, os.path.join(SKILL_DIR, 'assets')):
            if os.path.exists(os.path.join(base, cfg['logo'])):
                cfg['logo'] = os.path.join(base, cfg['logo'])
                break
    return cfg

def load_lab(exp_dir):
    """Per-experiment facts filled after the lab (scope_intake.py writes a draft):
    date_performed, date_submitted, scope_serial, measured {"R1": "9.8 kΩ", …}."""
    path = os.path.join(exp_dir, 'lab.json')
    return json.load(open(path, encoding='utf-8-sig')) if os.path.exists(path) else {}

def edited_by_hand(docx_path):
    """True if Word has saved this file since we built it: Word stamps every paragraph with
    w:rsid* revision ids, and build_docx never writes them. Such a file holds the user's edits."""
    import zipfile
    try:
        with zipfile.ZipFile(docx_path) as z:
            return b'w:rsidR' in z.read('word/document.xml')
    except (OSError, KeyError, zipfile.BadZipFile):
        return False

def load_requirements(exp_dir):
    req = json.load(open(os.path.join(exp_dir, 'requirements', 'requirements.json'), encoding='utf-8'))
    req['bib'] = bib_entries(req)
    return req

# Booklets file their references under "ביבליוגרפיה" or under "חומר תאורטי"; the second list
# also carries a recommendation sentence and a component list ("4013 (D-FF)\t4071 (OR)").
_NOT_A_REFERENCE = re.compile(r'^(מומלץ|יש להיעזר|כדאי|רצוי)|^\d{4}\s*\(')

def bib_entries(req):
    return [b for b in req.get('bib', []) + req.get('theory', [])
            if b.strip() and not _NOT_A_REFERENCE.match(b.strip())]

# ---------------------------------------------------------------- inline markup
_TOKEN = re.compile(r'(\$[^$]+\$|==.+?==)')
_NUM_UNIT = re.compile(r'^([-+≈~]?\d[\d.,]*)\s*((?:[kKMGmunpµμ]?(?:Hz|V|A|W|Ω|F|H|s))|ms|µs|us|ns|kΩ|MΩ|%)$')

def M(s):
    """Inline math token from LaTeX."""
    return ('math', tex(s))

def HL(s):
    """Highlighted (needs-verification) text token."""
    return ('hl', s)

def parse_inline(text):
    out = []
    for part in _TOKEN.split(text):
        if not part:
            continue
        if len(part) > 1 and part[0] == '$' and part[-1] == '$':
            out.append(('math', tex(part[1:-1])))
        elif part.startswith('==') and part.endswith('==') and len(part) > 4:
            for sub in parse_inline(part[2:-2]):     # math inside a highlight is still math
                out.append(('hl', sub) if isinstance(sub, str) else sub)
        else:
            out.append(part)
    return out

def _content(parts):
    out = []
    for p in parts:
        out += parse_inline(p) if isinstance(p, str) else [p]
    return out

# ---------------------------------------------------------------- the Report
class Report:
    """One Word document of one experiment."""

    def __init__(self, exp_dir, kind, req=None, course=None):
        assert kind in DOC_NAMES
        exp_dir = os.path.abspath(exp_dir)              # "." would make the course folder ""
        self.exp_dir, self.kind = exp_dir, kind
        self.req = req if req is not None else load_requirements(exp_dir)
        self.course = course if course is not None else load_course(os.path.dirname(exp_dir))
        self.lab = load_lab(exp_dir)
        self.b = DocxBuilder()
        self.count = {'fig': 0, 'tab': 0, 'eq': 0}
        self.numbers = {}
        self.slots = []          # image slots: {'file','label','present'}
        self.missing = []        # answer keys with no content

    # ---- numbering -------------------------------------------------------------
    def num(self, key):
        kind = key.split(':', 1)[0]
        if key not in self.numbers:
            self.count[kind] += 1
            self.numbers[key] = self.count[kind]
        return self.numbers[key]

    def ref(self, key):
        n = self.num(key)
        return {'fig': f'איור {n}', 'tab': f'טבלה {n}', 'eq': f'נוסחה ({n})'}[key.split(':')[0]]

    def refs(self, *keys):
        """Several objects of one kind in one phrase: 'איורים 4, 6 ו־8' (not 'איור 8, איור 4, …').
        Write it after a preposition with a maqaf-free join: f'ב{r.refs(...)}' -> 'באיורים 4 ו־6'."""
        kind = keys[0].split(':')[0]
        nums = sorted(self.num(k) for k in keys)
        if len(nums) == 1:
            return self.ref(keys[0])
        word = {'fig': 'איורים', 'tab': 'טבלאות', 'eq': 'נוסחאות'}[kind]
        fmt = (lambda n: f'({n})') if kind == 'eq' else str
        return f"{word} {', '.join(fmt(n) for n in nums[:-1])} ו־{fmt(nums[-1])}"

    # ---- text --------------------------------------------------------------------
    def p(self, *parts, **kw):
        self.b.para(_content(parts), **kw)

    def note(self, *parts):
        """Small italic remark (e.g. an assumption)."""
        self.b.para(_content(parts), italic=True, size=21, color='404040')

    def bullets(self, items, size=None):
        for it in items:                             # an item is a string/token or a list of them
            parts = it if isinstance(it, list) else [it]
            self.b.para(['• '] + _content(parts), size=size, space_after=60)

    def h1(self, text, new_page=False):
        self.b.heading(text, 1, new_page=new_page)

    def h2(self, text):
        self.b.heading(text, 2)

    def h3(self, text):
        self.b.heading(text, 3)

    def page_break(self):
        self.b.page_break()

    def todo(self, text):
        """Placeholder the USER fills in (e.g. conclusions) — counted by check_docx."""
        self.b.para([f'[[ {text} ]]'], italic=True, color='7F7F7F', space_after=120)

    def missing_answer(self, key):
        self.missing.append(key)
        self.b.para([('hl', f'[[ חסר: תשובה לסעיף {key} ]]')], space_after=120)

    # ---- math --------------------------------------------------------------------
    def eq(self, key, latex):
        """Numbered display equation, shown '(n)  …' like the official 2026 example."""
        n = self.num('eq:' + key)
        self.b.equation(tex(f'\\text{{({n})}}\\quad ' + latex))
        return n

    def math(self, latex):
        """Unnumbered display math (intermediate steps)."""
        self.b.equation(tex(latex))

    def calc(self, formula, substituted, result):
        """The house style for a calculation: formula -> substitution -> result with units."""
        self.b.equation(tex(f'{formula}={substituted}={result}'))

    # ---- figures / tables -------------------------------------------------------
    def _caption(self, text, keep_next=False):
        self.b.para(_content([text]), align='center', italic=True, size=20, color=CAP_COLOR,
                    space_after=100, keep_next=keep_next)

    def figure(self, key, path, caption, explain=None, width_cm=None):
        """Picture + caption below + one-line explanation (required by the 2026 guidelines).
        If the file is missing, a placeholder names exactly where to save it."""
        n = self.num('fig:' + key)
        rel = os.path.relpath(path, self.exp_dir).replace('\\', '/') if path else ''
        present = bool(path) and os.path.exists(path)
        if rel.startswith('images/'):
            self.slots.append({'file': rel, 'label': f'איור {n} – {caption}', 'present': present})
        if width_cm is None and 'scope' in os.path.basename(rel).lower():
            width_cm = self.course.get('scope_width_cm', 11)     # scope screenshots: smaller by default
        if present:
            if width_cm:                                 # exact width, scaling small crops up
                self.b.image(path, exact_w_emu=int(width_cm * 360000), keep_next=True)
            else:
                self.b.image(path, keep_next=True)
        else:
            self.b.para([f'[[ איור {n} – יש לשמור את התמונה בשם {rel} ]]'], align='center',
                        bold=True, size=21, color='C00000', space_after=60, keep_next=True)
        self._caption(f'איור {n} – {caption}')
        if explain:
            self.p(explain, size=22)
        return n

    def booklet_figure(self, key, caption_no=None, item=None, caption='', explain=None,
                       width_cm=9.5):
        """Embed a circuit drawing cropped from the booklet (requirements/figures)."""
        figs = self.req.get('figures', [])
        f = None
        if caption_no:
            f = next((x for x in figs if x.get('caption') == caption_no), None)
        if f is None and item:
            f = next((x for x in figs if item in x.get('linked_to', [])), None)
        path = os.path.join(self.exp_dir, 'requirements', f['file']) if f else None
        src = f' (תרשים {caption_no} מחוברת הניסוי)' if caption_no else ' (מתוך חוברת הניסוי)'
        return self.figure(key, path, caption + src, explain, width_cm)

    def table(self, key, rows, header, caption, explain=None, widths=None):
        n = self.num('tab:' + key)
        self._caption(f'טבלה {n} – {caption}', keep_next=True)

        def conv(c):
            # "0.470 ms" in an RTL cell is reordered to "ms 0.470"; a number+unit cell is
            # emitted as math, which keeps its own left-to-right order (as in the 2026 example).
            if isinstance(c, str) and '$' not in c:
                m = _NUM_UNIT.match(c.strip())
                if m:
                    return [('math', tex(m.group(1) + r'\,\text{' + m.group(2) + '}'))]
            return _content([c]) if isinstance(c, str) else ([c] if isinstance(c, tuple) else c)
        self.b.table([[conv(c) for c in row] for row in rows],
                     header=[conv(h) for h in header], widths=widths)
        if explain:
            self.p(explain, size=22)
        return n

    # ---- cover ---------------------------------------------------------------------
    def cover(self, kind_he, declaration=False):
        c, req = self.course, self.req
        logo = c['logo'] if os.path.isabs(c['logo']) else os.path.join(SKILL_DIR, 'assets', c['logo'])
        if os.path.exists(logo):
            self.b.image(logo, max_w_emu=1500000)
        self.b.para(c['faculty'], align='center', bold=True, size=28, space_after=60)
        self.b.para(c['department'], align='center', bold=True, size=28, space_after=400)
        self.b.para(f"{c['lab']} – {kind_he} מספר {req['number']}", align='center', bold=True,
                    size=32, space_after=300)
        self.b.para([f"שם הניסוי: ניסוי מס' {req['number']} – {req['title']}"], align='center',
                    bold=True, size=26, space_after=300)
        lab = self.lab
        blank = '____________'
        performed = lab.get('date_performed') or blank
        submitted = lab.get('date_submitted') or blank
        self.b.para(f'תאריך הביצוע: {performed}          תאריך ההגשה: {submitted}',
                    align='center', size=24, space_after=300)
        serial = lab.get('scope_serial') or c.get('scope_serial') or '____'
        rows = [[s.get('name', ''), s.get('id', ''), s.get('contact', ''), serial]
                for s in c['students']] or [['', '', '', '']]
        self.b.table(rows, header=['שמות המבצעים', "מס' ת.ז.", 'דוא"ל / טלפון', "מס' סידורי - סקופ"])
        if declaration:
            self.b.para('בחתימתם מצהירים הסטודנטים כי הדוח המסכם הנ"ל הינו פרי עבודתם האישית '
                        'והבלעדית, וכי כל התכנים הכלולים בו – לרבות סכמות חשמליות, סימולציות, '
                        'תמונות סקופ, טקסטים וכל רכיב אחר – שייכים להם בלבד. כל חריגה מהצהרה זו, '
                        'לרבות הגשת חומרים שאינם פרי עבודתם, תטופל בהליך משמעתי בפני ועדת משמעת '
                        'בחשד להעתקה.', size=22, space_after=200)
            self.b.table([[lab.get('date_submitted') or blank, blank]], header=['תאריך', 'חתימה'])
        self.b.page_break()

    # ---- save ----------------------------------------------------------------------
    def save(self):
        name = DOC_NAMES[self.kind]
        path = os.path.join(self.exp_dir, name)
        os.makedirs(os.path.join(self.exp_dir, 'images'), exist_ok=True)
        json.dump(self.slots, open(os.path.join(self.exp_dir, 'images', f'.slots_{self.kind}.json'),
                                   'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        if edited_by_hand(path):
            # the user has edited this document in Word: never overwrite it. Build next to it, and
            # carry further changes into their file with scripts/docx_edit.py.
            alt = path[:-5] + ' - בנייה חדשה.docx'
            print(f'  ⚠ {name} was edited in Word – NOT overwritten. New build: {os.path.basename(alt)}.\n'
                  f'    Carry changes into the edited file with scripts/docx_edit.py (see SKILL.md, '
                  f'"after manual edits").')
            path = alt
        try:
            self.b.save(path)
            print(f'  saved: {os.path.basename(path)}  (figs={self.count["fig"]} tabs={self.count["tab"]} '
                  f'eqs={self.count["eq"]} missing={len(self.missing)})')
        except PermissionError:
            print(f'  SKIPPED (open/locked in Word): {name}')
        return path

# ---------------------------------------------------------------- images README
def write_images_readme(exp_dir):
    idir = os.path.join(exp_dir, 'images')
    os.makedirs(idir, exist_ok=True)
    he = {'prep': 'דוח מכין', 'summary': 'דוח מסכם', 'study': 'מסמך הכנה עצמית'}
    L = ['תיקיית תמונות — שמור כאן את התמונות בשמות שלהלן, ואמור "רוץ מחדש".',
         'כל קובץ ייכנס למקומו בדוח עם כיתוב ומספור. (קובץ זה נוצר אוטומטית מהמסמכים.)',
         'PNG או JPG. ✓ = התמונה כבר קיימת ושובצה; ✗ = עדיין חסרה.', '']
    for kind in ('prep', 'summary', 'study'):
        p = os.path.join(idir, f'.slots_{kind}.json')
        if not os.path.exists(p):
            continue
        slots = json.load(open(p, encoding='utf-8'))
        if not slots:
            continue
        L.append(f'== {he[kind]} ==')
        for s in slots:
            label = re.sub(r'\\[a-zA-Z]+|[${}]', '', s['label'])       # "$V_p$" -> "V_p" (plain file)
            L.append(f"  {'✓' if s['present'] else '✗'}  {os.path.basename(s['file']):<28} {label}")
        L.append('')
    # a file used by several documents is produced once
    files = {os.path.basename(s['file']) for kind in he
             for s in (json.load(open(os.path.join(idir, f'.slots_{kind}.json'), encoding='utf-8'))
                       if os.path.exists(os.path.join(idir, f'.slots_{kind}.json')) else [])}
    L.append(f'סה"כ {len(files)} קבצים שונים (קובץ שמופיע בשני מסמכים נשמר פעם אחת).')
    open(os.path.join(idir, 'README.txt'), 'w', encoding='utf-8').write('\n'.join(L))

# ---------------------------------------------------------------- answers
def _render(r, value):
    if value is None:
        return
    if callable(value):
        value(r)
    elif isinstance(value, (list, tuple)) and not (isinstance(value, tuple) and value[0] in ('math', 'hl')):
        for v in value:
            _render(r, v)
    else:
        r.p(value)

# ---------------------------------------------------------------- preparatory report
def build_prep(r, answers):
    """answers: {'q1': …, 'q7': …, 'q7א': …} each a callable(r), a string, or a list."""
    r.cover('דוח מכין')
    for it in r.req['prep']['items']:
        q = f"q{it['num']}"
        r.b.question(it['num'], it['text'])
        for bl in it['bullets']:
            r.b.para(['• ' + bl], bold=True, size=22, space_after=40, keep_next=True)
        _render(r, answers.get(q))
        for s in it['subs']:
            r.b.subpart(s['letter'], s['text'])
            k = q + s['letter']
            if k in answers:
                _render(r, answers[k])
            elif q not in answers:
                r.missing_answer(f"{it['num']}{s['letter']}")
        if not it['subs'] and q not in answers:
            r.missing_answer(str(it['num']))
    if r.req.get('bib'):
        r.h1('ביבליוגרפיה')
        for i, b in enumerate(r.req['bib'], 1):
            r.p(f'{i}. {clean_bib(b)}')

# booklet bibliographies carry typos and mixed punctuation ("אלקטרוניקה ספרתית חלק ב'-יאן לרון",
# "הוצאת האונברסיטה הפתוחה- מט"ח"); normalise them so every entry reads the same way
_BIB_TYPOS = {'האונברסיטה': 'האוניברסיטה', 'אונברסיטה': 'אוניברסיטה',
              'מערכות ספרתיות מרדכי': 'מערכות ספרתיות – מרדכי'}     # title and author with no separator

def clean_bib(b):
    for wrong, right in _BIB_TYPOS.items():
        b = b.replace(wrong, right)
    # a separating hyphen (spaced, or between Hebrew words) becomes an en dash; "2-Input" stays
    b = re.sub(r"\s+-\s*|\s*-\s+|(?<=[א-ת'])-(?=[א-ת])", ' – ', b)
    b = re.sub(r'\s+', ' ', b).strip().rstrip('.')
    return b + '.'

# ---------------------------------------------------------------- summary report (2026)
UNITS = [('מתח', 'V'), ('זרם', 'A'), ('התנגדות', 'Ω'), ('שגיאה יחסית', '%'),
         ('ערך יעיל', ('math', tex('V_{RMS}'))), ('תדר', 'Hz'), ('זמן', 's'), ('הספק', 'W'),
         ('סליל', 'H'), ('קבל', 'F'),
         ('קילו', ('math', tex('k=10^{3}'))), ('מגה', ('math', tex('M=10^{6}'))),
         ('מילי', ('math', tex('m=10^{-3}'))), ('מיקרו', ('math', tex('\\mu=10^{-6}'))),
         ('ננו', ('math', tex('n=10^{-9}'))), ('פיקו', ('math', tex('p=10^{-12}')))]

def step_kind(text):
    t = text.strip()
    if t.endswith('?') or re.match(r'^(מה|מהם|מהי|מהו|מדוע|הסבר|השווה|האם|הוכח)', t):
        return 'question'
    if re.search(r'(הצג|מדוד|מדד|הראה)', t):
        return 'measure'
    return 'action'

def slot_name(sec, letter, what):
    """Image file names stay ASCII: step letters map to numbers (א=1, ב=2, …)."""
    return f"images/{sec}.{HEB_ORD.get(letter, letter)}_{what}.png" if letter else f"images/{sec}_{what}.png"

def default_section(r, sec, it):
    """Generic 2026 section: circuit, components, per-step slots, results table, discussion."""
    r.todo('תיאור מהלך הסעיף בגוף שלישי: מה נבנה, איך חובר ומה נמדד')
    r.p(f"הסכמה החשמלית של המעגל מוצגת ב{r.ref('fig:sch' + sec)}, וערכי הרכיבים מרוכזים "
        f"ב{r.ref('tab:cmp' + sec)}.")
    if it.get('figures'):
        r.booklet_figure(f'sch{sec}', item=f"procedure:{it['num']}",
                         caption='סכמה חשמלית של המעגל',
                         explain='[[ הסבר קצר על המעגל ]]')
    else:
        r.figure(f'sch{sec}', os.path.join(r.exp_dir, slot_name(sec, '', 'sch')),
                 'סכמה חשמלית של המעגל', '[[ הסבר קצר על המעגל ]]')
    r.table(f'cmp{sec}', [['[[ R ]]', '[[ ערך ]]'], ['[[ C ]]', '[[ ערך ]]'], ['VDD', '[[ ערך ]]']],
            ['רכיב', 'ערך'], 'רכיבי המעגל')
    for s in it['subs']:
        r.b.para([f"{s['letter']}. {s['text']}"], bold=True, size=22, space_after=60, keep_next=True)
        k = step_kind(s['text'])
        if k == 'measure':
            ks, kc = f"fig:sim{sec}{s['letter']}", f"fig:scope{sec}{s['letter']}"
            r.p(f'תוצאת הסימולציה מוצגת ב{r.ref(ks)}, והמדידה המעשית בסקופ ב{r.ref(kc)}.')
            r.figure(ks[4:], os.path.join(r.exp_dir, slot_name(sec, s['letter'], 'sim')),
                     'תוצאת הסימולציה (Multisim)', '[[ מה רואים בסימולציה ]]')
            r.figure(kc[4:], os.path.join(r.exp_dir, slot_name(sec, s['letter'], 'scope')),
                     'צילום סקופ מהמעבדה', '[[ האם התוצאה המעשית תואמת את הסימולציה? הסבר ]]')
        elif k == 'question':
            r.todo('תשובה')
        else:
            r.todo('מה בוצע בשלב זה')
    r.p(f"השוואת הערכים התאורטיים, תוצאות הסימולציה והמדידות מרוכזת ב{r.ref('tab:res' + sec)}.")
    r.table(f'res{sec}', [['[[ גודל ]]', '[[ ]]', '[[ ]]', '[[ ]]', '[[ % ]]']],
            ['גודל', 'תאורטי', 'סימולציה', 'מעשי', 'שגיאה יחסית'], 'השוואת תאוריה, סימולציה ומדידה')
    r.todo('דיון בתוצאות: התאמה לתאוריה ולסימולציה, ומקורות שגיאה')

def build_summary(r, content):
    """content keys (all optional): goal, abstract, theory (callable), equipment (list),
    titles {k: section title}, sections {k: callable(r, sec, item)}, conclusions_guide (list),
    conclusions (callable/list, after the lab - replaces the guide)."""
    req = r.req
    r.cover('דוח מסכם', declaration=True)
    r.h1('1. מטרת הניסוי')
    _render(r, content.get('goal') or ' '.join(req.get('goals', [])))
    r.h1('2. תקציר')
    _render(r, content.get('abstract') or (lambda r: r.todo('תקציר בגוף שלישי — יושלם אחרי המדידות')))
    r.h1('3. רקע תאורטי')
    _render(r, content.get('theory') or (lambda r: r.todo('רקע תאורטי')))
    r.p(f"הגדלים והיחידות שבהם נעשה שימוש בדוח מרוכזים ב{r.ref('tab:units')}.")
    r.table('units', [[q, u] for q, u in UNITS], ['גודל', 'יחידות'], 'גדלים ויחידותיהם',
            explain='היחידות לפי מערכת SI; קידומות העשרוניות משמשות בכל ערכי הרכיבים והמדידות בדוח.')
    r.h1('4. ציוד נדרש')
    eq = content.get('equipment') or (['מטריצה', 'ספק כוח DC', 'מחולל אותות', 'סקופ + USB', 'רב־מודד'] +
                                      [f'רכיב {k}' for k in req.get('datasheets', {})] +
                                      ['נגדים וקבלים (ערכים בכל סעיף)'])
    r.bullets(eq)
    r.h1('5. מהלך הניסוי')
    for it in req['procedure']['items']:
        sec = f"5.{it['num']}"
        # a section title: given explicitly, else the booklet's first sentence. Split only on a
        # '.'/':' that is not inside a number ("בתרשים 1.2 …" once became "בתרשים -1").
        title = content.get('titles', {}).get(it['num']) or \
            (re.split(r'(?<!\d)[.:](?!\d)', it['text'])[0].strip()[:80] or it['text'][:80])
        r.h2(f'{sec} {title}')
        fn = content.get('sections', {}).get(it['num'])
        (fn or default_section)(r, sec, it)
    r.h1('6. מסקנות')
    if content.get('conclusions'):          # written after the lab (from the measurements)
        _render(r, content['conclusions'])
    else:
        for g in content.get('conclusions_guide', ['האם התוצאות המעשיות תואמות את התאוריה ואת הסימולציה?',
                                                   'מהם מקורות השגיאה העיקריים, ומה גודלם?',
                                                   'מה ניתן ללמוד מהתוצאות על הרכיב ועל המעגלים?']):
            r.todo(g)
    r.h1('7. ביבליוגרפיה')
    for i, b in enumerate(req.get('bib', []), 1):
        r.p(f'{i}. {clean_bib(b)}')

# ---------------------------------------------------------------- self-study document
def build_study(r, content):
    """Quiz-readiness document. content keys: minute, concepts [(term, expl)], component
    (callable), formulas [{key, latex, name, meaning, valid, units, example}], circuits
    [callable], demos [callable], pitfalls [str], checklist [str],
    quiz [{q, options?, answer, explain}], cheatsheet [(name, latex)]."""
    req = r.req
    n = iter(range(1, 50))
    # a section left empty becomes a placeholder, which check_docx reports as an ERROR for the
    # study document - an empty self-study document used to pass the checker silently
    REQUIRED = {'minute': 'הניסוי בדקה', 'concepts': 'טבלת מושגים', 'formulas': 'נוסחאות מפתח עם דוגמאות',
                'circuits': 'מעגלי הניסוי עם תוצאות סימולציה', 'pitfalls': 'מלכודות נפוצות',
                'checklist': "צ'קליסט למעבדה", 'quiz': 'בוחן לדוגמה עם פתרונות'}
    gap = lambda key: None if content.get(key) else r.todo(f'יש לכתוב: {REQUIRED[key]}')
    r.b.para(f"מסמך הכנה עצמית – ניסוי {req['number']}: {req['title']}", align='center',
             bold=True, size=36, space_after=120)
    r.b.para('לשימוש אישי – הכנה לניסוי ולבוחן הקצר (לא להגשה)', align='center', italic=True,
             size=22, color='595959', space_after=300)
    r.h1(f'{next(n)}. הניסוי בדקה')
    _render(r, content.get('minute'))
    gap('minute')
    r.h1(f'{next(n)}. מושגי יסוד')
    gap('concepts')
    if content.get('concepts'):
        r.p(f"המושגים שחשוב להכיר לפני הניסוי מרוכזים ב{r.ref('tab:concepts')}.")
        r.table('concepts', [[t, e] for t, e in content['concepts']], ['מושג', 'הסבר'], 'מושגי יסוד')
    r.h1(f'{next(n)}. הרכיב')
    _render(r, content.get('component'))
    r.h1(f'{next(n)}. נוסחאות מפתח')
    gap('formulas')
    for f in content.get('formulas', []):
        r.h3(f['name'])
        r.eq(f['key'], f['latex'])
        if f.get('meaning'):
            r.p('משמעות: ' + f['meaning'])
        if f.get('valid'):
            r.p('תקפה כאשר: ' + f['valid'])
        if f.get('units'):
            r.p('יחידות: ' + f['units'])
        if f.get('example'):
            r.p('דוגמה פתורה:', bold=True)
            _render(r, f['example'])
    r.h1(f'{next(n)}. מעגלי הניסוי צעד אחר צעד')
    gap('circuits')
    for c in content.get('circuits', []):
        _render(r, c)
    if content.get('demos'):
        r.h1(f'{next(n)}. סימולציות הדגמה')
        for d in content['demos']:
            _render(r, d)
    r.h1(f'{next(n)}. מלכודות נפוצות')
    gap('pitfalls')
    r.bullets(content.get('pitfalls', []))
    r.h1(f"{next(n)}. צ'קליסט למעבדה")
    gap('checklist')
    for c in content.get('checklist', []):
        r.p('☐  ' + c if isinstance(c, str) else c, space_after=60)
    quiz = content.get('quiz', [])
    if not quiz:
        r.h1(f'{next(n)}. בוחן לדוגמה')
        gap('quiz')
    if quiz:
        r.h1(f'{next(n)}. בוחן לדוגמה')
        r.note('נסה לענות לבד, ורק אחר כך עבור לפתרונות בסוף המסמך.')
        for i, q in enumerate(quiz, 1):
            r.p(f'{i}. ' + q['q'], bold=True)
            for j, o in enumerate(q.get('options') or [], 0):
                r.p(f"   {'אבגד'[j]}. {o}", space_after=40)
    if content.get('cheatsheet'):
        r.h1(f'{next(n)}. דף נוסחאות')
        for name, latex in content['cheatsheet']:
            r.p(name + ':', bold=True, space_after=20, keep_next=True)
            r.math(latex)
    if quiz:
        r.h1('פתרונות הבוחן', new_page=True)
        for i, q in enumerate(quiz, 1):
            r.p(f'{i}. תשובה: ' + q['answer'], bold=True)
            if q.get('explain'):
                _render(r, q['explain'])
