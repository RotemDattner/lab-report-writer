# -*- coding: utf-8 -*-
"""
check_docx.py — deterministic QA of a generated report (complements the three QA agents).

    python check_docx.py <file.docx> [--req requirements.json] [--out report.md]

Kind (prep / summary / study) is inferred from the file name. Exit code = number of ERRORs.

ERROR  numbering gap/duplicate (איור / טבלה / equation (n)), reference to a non-existent
       number, question numbers/sub-parts differ from the booklet, a missing answer in the
       preparatory report, the forbidden "(לאימות)" tag, first person in a summary report,
       any placeholder left in the self-study document.
WARN   number+unit / range / value list in Hebrew text without LRM marks (prints reversed),
       figure/table never referenced in the text, no explanation under a figure, table header
       not repeating across pages, Latin relation written as plain text (bidi risk), runs of
       empty paragraphs, no page numbers.
INFO   highlighted (to-verify) items, image slots still empty, user to-do placeholders.
"""
import sys, re, json, zipfile, os
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_docx import ltr_islands

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
M = '{http://schemas.openxmlformats.org/officeDocument/2006/math}'

FIRST_PERSON = ['מדדתי', 'מדדנו', 'בניתי', 'בנינו', 'חיברתי', 'חיברנו', 'ראיתי', 'ראינו',
                'ביצעתי', 'ביצענו', 'הרכבתי', 'הרכבנו', 'קיבלתי', 'קיבלנו', 'השתמשתי',
                'השתמשנו', 'הצגתי', 'הצגנו', 'חישבתי', 'חישבנו', 'אני', 'אנחנו', 'אנו',
                'שלנו', 'שלי', 'נמדוד', 'נבנה את', 'הבחנתי', 'הבחנו', 'למדנו', 'למדתי']
RE_REL = re.compile(r'[A-Za-z][\w]*\s*[<>≤≥]\s*[A-Za-z(]|[A-Za-z]\w*\s+[−-]\s+[A-Za-z]\w*')


def _lin(e):
    tag = e.tag.replace(M, '')
    if tag == 't':
        return e.text or ''
    if tag.endswith('Pr'):
        return ''
    if tag == 'f':
        return f"({_kids(e.find(M+'num'))})/({_kids(e.find(M+'den'))})"
    if tag == 'sSub':
        return f"{_kids(e.find(M+'e'))}_{_kids(e.find(M+'sub'))}"
    if tag == 'sSup':
        return f"{_kids(e.find(M+'e'))}^{_kids(e.find(M+'sup'))}"
    if tag == 'd':
        return '(' + _kids(e.find(M + 'e')) + ')'
    return _kids(e)


def _kids(e):
    return '' if e is None else ''.join(_lin(c) for c in e)


def para_info(p):
    """Text of a paragraph with math linearized, its plain-text-only part, highlights, flags."""
    text, plain, hls, maths = [], [], [], []
    for el in p.iter():
        if el.tag == W + 'r' and el.find(W + 't') is not None:
            t = ''.join(x.text or '' for x in el.iter(W + 't'))
            text.append(t); plain.append(t)
            rpr = el.find(W + 'rPr')
            if rpr is not None and rpr.find(W + 'highlight') is not None and t.strip():
                hls.append(t.strip())
        elif el.tag == M + 'oMath':
            text.append(_kids(el))
            maths.append(_kids(el))
    ppr = p.find(W + 'pPr')
    jc = ppr.find(W + 'jc') if ppr is not None else None
    shown = re.sub('[‎‏⁠]', '', ''.join(text)).replace(' ', ' ').strip()
    return {'text': shown, 'plain': ''.join(plain), 'hl': hls, 'maths': maths,
            'math': p.find('.//' + M + 'oMath') is not None and not ''.join(plain).strip(),
            'drawing': p.find('.//' + W + 'drawing') is not None,
            'bold': p.find('.//' + W + 'b') is not None,
            'center': jc is not None and jc.get(W + 'val') == 'center'}


def check(path, req=None):
    name = os.path.basename(path)
    kind = 'summary' if 'מסכם' in name else 'study' if 'הכנה' in name else 'prep'
    root = ET.fromstring(zipfile.ZipFile(path).read('word/document.xml'))
    body = root.find(W + 'body')
    blocks = []                                      # top-level sequence: ('p', info) / ('tbl', el)
    for ch in body:
        if ch.tag == W + 'p':
            blocks.append(('p', para_info(ch)))
        elif ch.tag == W + 'tbl':
            blocks.append(('tbl', ch))
    E, Wn, I = [], [], []
    paras = [b[1] for b in blocks if b[0] == 'p']
    cell_text = ' '.join(''.join(t.text or '' for t in tbl.iter(W + 't')) for k, tbl in blocks if k == 'tbl')

    # ---- numbering of captions and equations
    caps = {'איור': [], 'טבלה': []}
    eqs = []
    for idx, (k, b) in enumerate(blocks):
        if k != 'p':
            continue
        m = re.match(r'^(איור|טבלה) (\d+) – ', b['text'])
        if m and b['center']:
            caps[m.group(1)].append((int(m.group(2)), idx))
        if b['math']:
            me = re.match(r'^\((\d+)\)', b['text'])
            if me:
                eqs.append(int(me.group(1)))
    for label, items in list(caps.items()) + [('נוסחה', [(n, None) for n in eqs])]:
        nums = [n for n, _ in items]
        if nums and nums != list(range(1, len(nums) + 1)):
            E.append(f'מספור {label} לא רציף/כפול: {nums}')
    # ---- adjacency: figure caption after a picture/placeholder; table caption before a table
    for n, idx in caps['איור']:
        prev = blocks[idx - 1] if idx else None
        if not prev or prev[0] != 'p' or not (prev[1]['drawing'] or prev[1]['text'].startswith('[[')):
            Wn.append(f'איור {n}: הכיתוב לא מופיע מיד מתחת לתמונה')
        nxt = blocks[idx + 1] if idx + 1 < len(blocks) else None
        if not nxt or nxt[0] != 'p' or not nxt[1]['text'] or re.match(r'^(איור|טבלה) \d+ – ', nxt[1]['text']) \
                or nxt[1]['bold']:
            Wn.append(f'איור {n}: אין שורת הסבר מתחת לאיור (נדרש בהנחיות 2026)')
    for n, idx in caps['טבלה']:
        nxt = blocks[idx + 1] if idx + 1 < len(blocks) else None
        if not nxt or nxt[0] != 'tbl':
            E.append(f'טבלה {n}: הכיתוב לא מופיע מיד מעל טבלה')
    # ---- references
    body_text = ' '.join(b['text'] for b in paras
                         if not re.match(r'^(איור|טבלה) \d+ – ', b['text'])
                         and not b['text'].startswith('[[')) + ' ' + cell_text
    # plural references ("איורים 4, 6 ו־8", "טבלאות 4 ו־5") count for every number listed
    plural = {'איור': 'איורים', 'טבלה': 'טבלאות'}
    for single, many in plural.items():
        for m in re.finditer(rf'{many} ((?:\d+, )*\d+ ו־\d+)', body_text):
            body_text += ' ' + ' '.join(f'{single} {n}' for n in re.findall(r'\d+', m.group(1)))
    for label, items in caps.items():
        have = {n for n, _ in items}
        for n in have:
            if not re.search(rf'{label} {n}(?!\d)', body_text):
                Wn.append(f'{label} {n} לא מוזכר בטקסט')
        for ref in set(int(x) for x in re.findall(rf'{label} (\d+)', body_text)):
            if ref not in have:
                E.append(f'הפניה ל{label} {ref} שאינו קיים')
    # ---- question structure vs the booklet
    if kind == 'prep' and req:
        got = []
        for b in paras:
            m = re.match(r'^(\d{1,2})\. ', b['text'])
            if m and b['bold']:
                got.append(int(m.group(1)))
        want = [it['num'] for it in req['prep']['items']]
        if got != want:
            E.append(f'מספור השאלות שונה מהחוברת: בדוח {got}, בחוברת {want}')
    # ---- placeholders, forbidden tags, highlights, first person, bidi, empties
    empties = 0
    for b in paras:
        t = b['text']
        for ph in re.findall(r'\[\[(.+?)\]\]', t):
            ph = ph.strip()
            if 'חסר' in ph:
                (E if kind == 'prep' else I).append(f'חסר: {ph}')
            elif 'יש לשמור את התמונה' in ph:
                I.append(f'תמונה חסרה: {ph}')
            else:
                (E if kind == 'study' else I if kind == 'summary' else Wn).append(f'למילוי: {ph}')
        cmd = re.search(r'\\[A-Za-z]+', t)
        if cmd:
            E.append(f'פקודת LaTeX שלא פוענחה ("{cmd.group(0)}") — תודפס כטקסט גולמי: "{t[:60]}"')
        for mt in b['maths']:
            if re.search(r'[א-ת]', mt):
                E.append(f'עברית בתוך נוסחה (תתהפך/תתבלגן) — להעביר לטקסט שמחוץ לנוסחה: "{mt[:50]}"')
        if '$' in b['plain']:
            E.append(f'סימן $ בטקסט — נוסחה שלא פוענחה: "{b["plain"][:60]}"')
        if '(לאימות)' in t:
            E.append(f'תגית "(לאימות)" אסורה — יש להשתמש בהדגשה צהובה: "{t[:60]}"')
        for h in b['hl']:
            if not h.startswith('[['):
                I.append(f'מודגש לאימות: {h[:90]}')
        if kind == 'summary':                        # placeholders are guidance, not report text
            clean = re.sub(r'\[\[.*?\]\]', '', t)
            words = re.findall(r'[א-ת"\']+', clean)
            for fp in FIRST_PERSON:
                if (' ' in fp and fp in clean) or fp in words:
                    E.append(f'גוף ראשון במסכם ("{fp}"): "{t[:60]}"')
        bare = (b['plain'].replace('‎', '').replace('‏', '').replace('⁠', '')
                .replace(' ', ' '))           # undo what ltr_islands adds, then re-run it
        if re.search(r'[א-ת]', bare) and ltr_islands(bare).count('‎') > b['plain'].count('‎'):
            Wn.append(f'מספר+יחידה / טווח בטקסט עברי בלי סימני LRM — יוצג הפוך ("ms 0.470"): "{bare[:60]}"')
        if RE_REL.search(b['plain']) and not re.match(r'^\d{1,2}\. |^[א-ת]\. ', t):
            Wn.append(f'יחס בטקסט רגיל (סיכון bidi) — עדיף $…$: "{b["plain"][:60]}"')
        empties = empties + 1 if not t and not b['drawing'] else 0
        if empties == 3:
            Wn.append('שלוש פסקאות ריקות ברצף (קפיצת שורות מיותרת)')
    # ---- tables & page numbers
    for k, tbl in blocks:
        if k == 'tbl':
            first = tbl.find(W + 'tr')
            if first is not None and first.find(f'{W}trPr/{W}tblHeader') is None:
                Wn.append('טבלה ללא שורת כותרת חוזרת בין עמודים')
    sect = body.find(W + 'sectPr')
    if sect is None or sect.find(W + 'footerReference') is None:
        Wn.append('אין מספור עמודים (חובה לפי ההנחיות)')

    figs, tabs = len(caps['איור']), len(caps['טבלה'])
    head = (f'# בדיקה אוטומטית — {name}\n\nסוג: {kind} · איורים: {figs} · טבלאות: {tabs} · '
            f'נוסחאות ממוספרות: {len(eqs)} · **שגיאות: {len(E)} · אזהרות: {len(Wn)}**\n')
    sec = lambda title, xs: (f'\n## {title} ({len(xs)})\n' + '\n'.join(f'- {x}' for x in dict.fromkeys(xs))) if xs else ''
    report = head + sec('❌ שגיאות', E) + sec('⚠ אזהרות', Wn) + sec('ℹ לידיעה / לאימות שלך', I) + '\n'
    return report, len(E)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    req = out = None
    if '--req' in args:
        req = json.load(open(args[args.index('--req') + 1], encoding='utf-8'))
    if '--out' in args:
        out = args[args.index('--out') + 1]
    rep, nerr = check(args[0], req)
    print(rep)
    if out:
        open(out, 'w', encoding='utf-8').write(rep)
    sys.exit(nerr)
