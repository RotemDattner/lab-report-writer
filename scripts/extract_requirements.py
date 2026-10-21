# -*- coding: utf-8 -*-
"""
extract_requirements.py — turn an experiment booklet (.docx) into a structured requirements
outline that the rest of the skill builds from.

    python extract_requirements.py <booklet.docx> <course_dir>

Creates (or reuses) <course_dir>/ניסוי NN - <title>/requirements/ containing:
    requirements.md    human-readable outline (Hebrew): questions, sub-parts, figures, values
    requirements.json  the same, machine-readable, for the build scripts
    figures/           every circuit drawing / formula image cropped from the booklet
    pages/             each booklet page as PNG (for visual cross-checking)
    source.pdf/.txt    the LibreOffice renderings everything was read from

Why LibreOffice + PyMuPDF instead of reading document.xml directly:
  * Question numbers ("1.", "א.") are Word auto-numbering; LibreOffice's text export computes
    them exactly as they print, in logical (not visual) order.
  * Circuits are often Word drawing shapes, not pictures; LibreOffice renders them to images
    in the PDF, where PyMuPDF can locate and crop them.
OMML equations are still read from document.xml, since the text export drops them.
"""
import sys, os, re, json, subprocess, zipfile, shutil
import xml.etree.ElementTree as ET
import pymupdf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from labenv import find_soffice

SOFFICE = find_soffice()                      # Windows / macOS / Linux, or $LAB_SOFFICE
W ='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
M = '{http://schemas.openxmlformats.org/officeDocument/2006/math}'

# ---------------------------------------------------------------- conversion
def soffice_convert(src, fmt, outdir, ext):
    subprocess.run([SOFFICE, '--headless', '--convert-to', fmt, '--outdir', outdir, src],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    p = os.path.join(outdir, os.path.splitext(os.path.basename(src))[0] + '.' + ext)
    if not os.path.exists(p):
        raise RuntimeError(f'LibreOffice could not convert {src} to {fmt}')
    return p

def clear_derived(out):
    """Empty the requirements folder without deleting the folder itself (Explorer/OneDrive may
    hold a handle on the directory). Everything in it is regenerated from the booklet."""
    os.makedirs(out, exist_ok=True)
    for name in os.listdir(out):
        p = os.path.join(out, name)
        try:
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
        except OSError:
            pass                                     # a locked file will simply be overwritten

def copy_with_retry(src, dst, tries=8, wait=2.0):
    """OneDrive (sync) or an antivirus scan can hold a file briefly; retry before giving up."""
    import time
    for k in range(tries):
        try:
            shutil.copyfile(src, dst)
            return
        except PermissionError:
            if k == tries - 1:
                raise RuntimeError(f'{src} is locked (OneDrive sync, antivirus, or open in '
                                   f'another program). Close it / wait for sync and retry.')
            time.sleep(wait)

# ---------------------------------------------------------------- text structure
SECTIONS = [  # (key, regex on a stripped line); order matters only for readability
    ('goal',      r'^מטר(?:ה|ות)(?:\s+הניסוי)?\s*:'),
    ('prep',      r'^דו"?ח\s+מכין\s*:?\s*$'),
    ('bib',       r'^ביבליוגרפיה\s*:?\s*$'),
    ('theory',    r'^חומר\s+תאורטי\s*:?\s*$'),
    ('parts',     r'^רכיבים\s+המצויים\s+במעבדה\s*:?\s*$'),
    ('procedure', r'^מהלך\s+הניסוי\s*:?\s*$'),
]
RE_TITLE = re.compile(r"ניסוי\s*(?:מס'?)?\s*(\d+)\s*[-–]\s*(.+)")
RE_NUM   = re.compile(r'^(\d{1,2})\.\s*(.*)$')
RE_SUB   = re.compile(r'^([א-ת])\.\s*(.*)$')
RE_BUL   = re.compile(r'^[•◦▪\uf0b7\-]\s+(.*)$')
RE_FIG   = re.compile(r'תרשים\s*-?\s*(\d+\.\d+)')
RE_SKIP  = re.compile(r'בהצלחה')

def classify(text):
    if 'סימולציה' in text:
        return 'simulation'
    if 'סכמת חיבורים' in text or 'מטריצה' in text:
        return 'wiring'
    if re.search(r'דפי\s*(ה)?נתונים', text):
        return 'datasheet'
    return 'question'

def new_item(num, text):
    return {'num': int(num), 'text': text.strip(), 'subs': [], 'notes': [],
            'bullets': [], 'fig_refs': [], 'figures': []}

def parse_text(lines):
    out = {'number': None, 'title': '', 'goals': [], 'bib': [], 'theory': [], 'parts': [],
           'prep': {'intro': [], 'items': []}, 'procedure': {'intro': [], 'items': []}}
    section, item = None, None
    for raw in lines:
        s = raw.strip()
        if not s or RE_SKIP.search(s):
            continue
        if not out['title']:
            m = RE_TITLE.search(s)
            if m:
                out['number'], out['title'] = int(m.group(1)), m.group(2).strip()
                continue
        hit = next((k for k, rx in SECTIONS if re.match(rx, s)), None)
        if hit:
            section, item = hit, None
            if hit == 'goal':                       # "מטרה: …" may carry inline content
                rest = re.sub(SECTIONS[0][1], '', s).strip()
                if rest:
                    out['goals'].append(rest)
            continue
        if section in ('goal',):
            out['goals'].append(RE_BUL.sub(r'\1', s)); continue
        if section in ('bib', 'theory'):
            out[section].append(RE_SUB.sub(r'\2', RE_NUM.sub(r'\2', s))); continue
        if section == 'parts':
            out['parts'] += [p.strip() for p in s.split('\t') if p.strip()]; continue
        if section not in ('prep', 'procedure'):
            continue
        block = out[section]
        refs = RE_FIG.findall(s)
        m_num, m_sub, m_bul = RE_NUM.match(s), RE_SUB.match(s), RE_BUL.match(s)
        if re.match(r'^תרשים', s):                 # a bare caption line: belongs to current item
            pass
        elif m_num:
            item = new_item(*m_num.groups()); block['items'].append(item)
        elif m_sub and item is not None:
            item['subs'].append({'letter': m_sub.group(1), 'text': m_sub.group(2).strip(), 'notes': []})
        elif m_bul and item is not None:
            item['bullets'].append(m_bul.group(1).strip())
        elif item is None:
            block['intro'].append(s)
        elif not item['subs']:
            item['text'] += ' ' + s                  # continuation of the question itself
        else:
            item['notes'].append({'after': item['subs'][-1]['letter'], 'text': s})
        # attach figure references AFTER deciding which item this line belongs to
        if item is not None:
            for ref in refs:
                if ref not in item['fig_refs']:
                    item['fig_refs'].append(ref)
    for sec in ('prep', 'procedure'):
        for it in out[sec]['items']:
            it['kind'] = classify(it['text'])
    return out

# ---------------------------------------------------------------- OMML equations
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
    if tag == 'sSubSup':
        return f"{_kids(e.find(M+'e'))}_{_kids(e.find(M+'sub'))}^{_kids(e.find(M+'sup'))}"
    if tag == 'rad':
        return f"sqrt({_kids(e.find(M+'e'))})"
    if tag == 'd':
        return '(' + ', '.join(_kids(x) for x in e.findall(M+'e')) + ')'
    return _kids(e)

def _kids(e):
    return '' if e is None else ''.join(_lin(c) for c in e)

R_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
A_BLIP = '{http://schemas.openxmlformats.org/drawingml/2006/main}blip'
V_IMG = '{urn:schemas-microsoft-com:vml}imagedata'

def _is_context(txt):
    """A paragraph worth using as 'what came before': real Hebrew prose, not a shape label."""
    return len(txt) > 12 and re.search(r'[א-ת]{3}', txt) is not None

def scan_docx(docx):
    """One document-order pass: OMML equations and embedded pictures, each with the text that
    precedes it. Nested paragraphs (text boxes) are visited once, so nothing is double counted."""
    z = zipfile.ZipFile(docx)
    root = ET.fromstring(z.read('word/document.xml'))
    rels = {}
    if 'word/_rels/document.xml.rels' in z.namelist():
        for r in ET.fromstring(z.read('word/_rels/document.xml.rels')):
            rels[r.get('Id')] = r.get('Target')
    eqs, media, seen, last = [], [], set(), ''
    # labels typed inside drawing text-boxes (e.g. "U1A 4093", "R1 10K") — not in the text export
    shape_text = ' '.join(t.text or '' for tb in root.iter(W + 'txbxContent') for t in tb.iter(W + 't'))
    for el in root.iter():
        if el.tag == W + 'p':
            txt = ''.join(t.text or '' for t in el.iter(W + 't')).strip()
            if _is_context(txt):
                last = txt
        elif el.tag == M + 'oMath' and id(el) not in seen:
            for sub in el.iter(M + 'oMath'):
                seen.add(id(sub))
            lin = _kids(el).strip()
            if lin and not any(e['text'] == lin and e['context'] == last[:80] for e in eqs):
                eqs.append({'context': last[:80], 'text': lin})
        elif el.tag in (A_BLIP, V_IMG):
            rid = el.get(R_NS + 'embed') or el.get(R_NS + 'id')
            tgt = rels.get(rid)
            if tgt and not any(m['target'] == tgt for m in media):
                media.append({'target': tgt, 'context': last[:80]})
    return eqs, media, shape_text

def export_media(docx, media, out_dir):
    """Copy embedded pictures out of the booklet; convert WMF/EMF (old-style equation objects
    and vector drawings) to PNG so they can be viewed and embedded."""
    z = zipfile.ZipFile(docx)
    mdir = os.path.join(out_dir, 'media')
    os.makedirs(mdir, exist_ok=True)
    for k, m in enumerate(media, 1):
        name = 'word/' + m['target'].lstrip('/').replace('word/', '')
        if name not in z.namelist():
            continue
        ext = os.path.splitext(name)[1].lower()
        raw = os.path.join(mdir, f'media_{k:02d}{ext}')
        open(raw, 'wb').write(z.read(name))
        m['file'] = f'media/media_{k:02d}{ext}'
        if ext in ('.wmf', '.emf'):
            try:                                       # vector -> PDF -> tight PNG crop
                pdf = soffice_convert(raw, 'pdf', mdir, 'pdf')
                page = pymupdf.open(pdf)[0]
                boxes = [pymupdf.Rect(b[:4]) for b in page.get_text('blocks')]
                boxes += [d['rect'] for d in page.get_drawings()]
                boxes += [pymupdf.Rect(i['bbox']) for i in page.get_image_info()]
                boxes = [b for b in boxes if 0 < b.width < 0.95 * page.rect.width]
                clip = page.rect
                if boxes:
                    clip = boxes[0]
                    for b in boxes[1:]:
                        clip = clip | b
                    clip = (clip + (-6, -6, 6, 6)) & page.rect
                png = os.path.join(mdir, f'media_{k:02d}.png')
                page.get_pixmap(matrix=pymupdf.Matrix(3, 3), clip=clip).save(png)
                page.parent.close()
                os.remove(pdf)
                m['file'] = 'media/' + os.path.basename(png)
            except Exception:
                pass                                   # keep the original vector file
    return [m for m in media if 'file' in m]

# ---------------------------------------------------------------- figures (PDF)
def _clusters(rects, gap=12):
    """Union-find over rectangles whose gap-expanded boxes intersect."""
    parent = list(range(len(rects)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    grown = [r + (-gap, -gap, gap, gap) for r in rects]
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            if grown[i].intersects(grown[j]):
                parent[find(i)] = find(j)
    groups = {}
    for i, r in enumerate(rects):
        groups.setdefault(find(i), []).append(r)
    out = []
    for g in groups.values():
        u = g[0]
        for r in g[1:]:
            u = u | r
        out.append((u, len(g)))
    return out

def _ink_bbox(page, clip, pad=6, thr=245):
    """Shrink a crop to the area that actually has ink. A drawing's canvas is often much wider
    than the circuit (figure 1.2 was ~40% circuit, 60% blank), and once the picture is scaled
    to the report's width the blank part makes the circuit tiny."""
    # 3 px per pt: at 1 px/pt thin light lines (pink ground symbols) blur to near-white and read
    # as blank, which cut the ground off figure 1.2
    z = 3
    pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), clip=clip, colorspace=pymupdf.csGRAY)
    w, h, s, st = pix.width, pix.height, pix.samples, pix.stride
    rows = [y for y in range(h) if min(s[y * st:y * st + w]) < thr]
    if not rows:
        return clip
    cols = [x for x in range(0, w, 2) if any(s[y * st + x] < thr for y in range(rows[0], rows[-1] + 1, 2))]
    ink = pymupdf.Rect(clip.x0 + cols[0] / z, clip.y0 + rows[0] / z,
                       clip.x0 + (cols[-1] + 2) / z, clip.y0 + (rows[-1] + 1) / z)
    return (ink + (-pad, -pad, pad, pad)) & clip


def extract_figures(pdf_path, out_dir, zoom=2.5):
    """Crop every graphic cluster; attach caption number and owning item number."""
    doc = pymupdf.open(pdf_path)
    os.makedirs(os.path.join(out_dir, 'figures'), exist_ok=True)
    os.makedirs(os.path.join(out_dir, 'pages'), exist_ok=True)
    figs, section, cur_item = [], 'header', None
    for pno, page in enumerate(doc):
        page.get_pixmap(matrix=pymupdf.Matrix(1.6, 1.6)).save(
            os.path.join(out_dir, 'pages', f'page_{pno+1}.png'))
        W_, H_ = page.rect.width, page.rect.height
        rects = [pymupdf.Rect(i['bbox']) for i in page.get_image_info()]
        rects = [r for r in rects if r.width * r.height > 400]
        for d in page.get_drawings():
            r = d['rect']
            if r.width > 0.85 * W_ or (r.height < 1.5 and r.width > 150):
                continue                              # page frames / underlines
            rects.append(r)
        clusters = [(r, n) for r, n in _clusters(rects) if r.width * r.height > 1500]
        captions = page.search_for('תרשים')
        blocks = page.get_text('blocks', sort=True)
        # walk text blocks and figures together in reading order (top to bottom)
        events = [('blk', b[1], b) for b in blocks] + [('fig', r.y0, (r, n)) for r, n in clusters]
        for kind, _, obj in sorted(events, key=lambda e: e[1]):
            if kind == 'blk':
                t = obj[4]
                if re.search(r'מהלך\s+הניסוי', t) and len(t.strip()) < 25:
                    section, cur_item = 'procedure', None
                elif re.search(r'דו"?ח\s+מכין', t) and len(t.strip()) < 25:
                    section, cur_item = 'prep', None
                m = re.match(r'^\s*(\d{1,2})\s*\n?\s*\.', t)
                if m:
                    cur_item = int(m.group(1))
                continue
            r, _n = obj
            # a text block on the same line as a "תרשים" hit is part of the caption ("1.3" is
            # often its own block, positioned a little higher than the word)
            on_cap = lambda br: any(br.y0 < c.y1 + 4 and br.y1 > c.y0 - 4 for c in captions)
            for b in blocks:                         # absorb short labels next to the drawing
                br = pymupdf.Rect(b[:4])             # (e.g. "out", "100k", "Vcc") so they aren't cut
                if len(b[4].strip()) <= 12 and not on_cap(br) and (r + (-25, -25, 25, 25)).intersects(br):
                    r = r | br
            # 'תרשים' also matches body text ("בתרשים 1.2 מתואר…"), so prefer a caption below
            # or inside the drawing over one above it, and only grow the crop for a short,
            # caption-like line (never pull a sentence of body text into the picture).
            cap, cands = None, []
            for c in captions:
                near = (r.y0 - 45 <= c.y1) and (c.y0 <= r.y1 + 45)
                if near and c.x1 > r.x0 - 60 and c.x0 < r.x1 + 60:
                    line_txt = page.get_text('text', clip=pymupdf.Rect(0, c.y0 - 1, W_, c.y1 + 1))
                    num = re.search(r'(\d+\.\d+)', line_txt)
                    if num:
                        above = c.y0 < r.y0
                        cands.append((above, abs(c.y0 - r.y1), c, num.group(1), len(line_txt.strip())))
            # the caption only supplies the number: the report writes its own caption, so the
            # booklet's "תרשים 1.x" label is kept OUT of the crop (it was duplicated under the picture)
            cap_top = None
            if cands:
                cands.sort(key=lambda x: (x[0], x[1]))
                cap = cands[0][3]
                above, _, cc = cands[0][:3]
                if not above:
                    # The caption line under the drawing can overlap it (figure 1.2: the text box
                    # spans y 222-250, the ground symbol ends at 237), so no crop line separates
                    # them. Instead remove only the caption TEXT from the in-memory page (the
                    # drawing is untouched), and reach down to the caption so small parts that
                    # formed their own cluster (that ground symbol) are kept.
                    band = pymupdf.Rect(r.x0 - 40, cc.y0 - 1, r.x1 + 40, cc.y1 + 1)
                    page.add_redact_annot(band)
                    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                                          graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
                    r.y1 = max(r.y1, cc.y1)
            # keep sentences of body text out of the picture (a drawing that reaches up to a text
            # line pulled "…מתנד עם בקרת הפעלה." into the crop of figure 1.3)
            mt = mb = 4
            for b in blocks:
                br = pymupdf.Rect(b[:4])
                if len(b[4].strip()) > 25 and br.intersects(r + (-6, -6, 6, 6)):
                    if (br.y0 + br.y1) / 2 < (r.y0 + r.y1) / 2:
                        r.y0 = max(r.y0, br.y1 + 1); mt = 1
                    else:
                        r.y1 = min(r.y1, br.y0 - 1); mb = 1
            clip = _ink_bbox(page, (r + (-8, -mt, 8, mb)) & page.rect)
            name = f'fig_{len(figs)+1:02d}.png'
            page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip).save(
                os.path.join(out_dir, 'figures', name))
            labels = ' '.join(page.get_text('text', clip=clip).split())
            figs.append({'file': f'figures/{name}', 'page': pno + 1, 'caption': cap,
                         'section': section, 'item': cur_item, 'labels': labels[:160]})
    return figs, len(doc)

# ---------------------------------------------------------------- values
VALUE_PATTERNS = {
    'ics':          r'\b(?:MC|CD|HEF)?1?4[05]\d{2}B?\b|\b(?:DAC|ADC)\d{4}\b|\b(?:MPSA|BS|2N)-?\d{2,4}\b',
    'resistors':    r'\b\d+(?:\.\d+)?\s*(?:k|K|M|meg)?\s*(?:Ω|ohm|Ohm)\b|\b\d+(?:\.\d+)?\s*[kKM](?=\s|$|,)',
    'capacitors':   r'\b\d+(?:\.\d+)?\s*(?:p|n|u|µ|μ|m)F\b',
    'frequencies':  r'\b\d+(?:\.\d+)?\s*(?:k|M)?Hz\b',
    'voltages':     r'\b\d+(?:\.\d+)?\s*V\b',
    'times':        r'\b\d+(?:\.\d+)?\s*(?:m|u|µ|n)?sec\b|\b\d+(?:\.\d+)?\s*(?:ms|us|µs|ns)\b',
}

def extract_values(text):
    vals = {}
    for k, rx in VALUE_PATTERNS.items():
        found = []
        for v in re.findall(rx, text):
            v = re.sub(r'\s+', '', v)
            if v not in found:
                found.append(v)
        vals[k] = found
    return vals

def datasheet_families(ics):
    fam = {}
    for ic in ics:
        core = re.sub(r'^(MC|CD|HEF)', '', ic).rstrip('B')
        if re.fullmatch(r'14\d{3}', core):
            core = core[1:]                          # MC14093 -> 4093 family
        fam.setdefault(core, []).append(ic)
    return fam

# ---------------------------------------------------------------- output
def exp_folder(course_dir, number, title):
    prefix = f'ניסוי {number:02d}'
    for d in os.listdir(course_dir):
        if d.startswith(prefix) and os.path.isdir(os.path.join(course_dir, d)):
            return os.path.join(course_dir, d)       # reuse an existing experiment folder
    safe = re.sub(r'[\\/:*?"<>|]', '', title).strip()
    return os.path.join(course_dir, f'{prefix} - {safe}')

def link_figures(req, figs):
    for f in figs:
        for sec in ('prep', 'procedure'):
            for it in req[sec]['items']:
                by_caption = f['caption'] and f['caption'] in it['fig_refs']
                by_position = f['section'] == sec and f['item'] == it['num'] and not f['caption']
                if by_caption or by_position:
                    it['figures'].append(f['file'])
                    f.setdefault('linked_to', []).append(f'{sec}:{it["num"]}')

def link_media(req, media):
    """Attach each embedded picture to the item whose text it follows. Pictures appear in document
    order, so when the same context text matches several items (e.g. two questions both starting
    'נתון המעגל הבא:') take the first match AFTER the previously linked item."""
    norm = lambda t: re.sub(r'\s+', ' ', t)
    seq = [(sec, it) for sec in ('prep', 'procedure') for it in req[sec]['items']]
    last = -1
    for m in media:
        ctx = norm(m['context']).strip()[:25]
        if not ctx:
            continue
        hits = []
        for idx, (sec, it) in enumerate(seq):
            texts = [it['text']] + [s['text'] for s in it['subs']] + [n['text'] for n in it['notes']]
            if any(ctx in norm(t) for t in texts):
                hits.append(idx)
        if not hits:
            continue
        idx = next((h for h in hits if h > last), next((h for h in hits if h >= last), hits[0]))
        sec, it = seq[idx]
        it.setdefault('media', []).append(m['file'])
        m['linked_to'] = [f'{sec}:{it["num"]}']
        last = idx

KIND_HE = {'simulation': 'סימולציה', 'wiring': 'סכמת חיבורים', 'datasheet': 'דפי נתונים',
           'question': 'שאלה'}

def write_md(req, path):
    L = [f"# דרישות — ניסוי {req['number']}: {req['title']}", '',
         f"מקור: `{os.path.basename(req['source'])}` · עמודים: {req['pages']} · "
         f"שאלות מכין: {len(req['prep']['items'])} · סעיפי מהלך: {len(req['procedure']['items'])} · "
         f"שרטוטים: {len(req['figures'])}", '']
    if req['goals']:
        L += ['## מטרות', *[f'- {g}' for g in req['goals']], '']

    def render(block, title, level_name):
        L.append(f'## {title}')
        for s in block['intro']:
            L.append(f'> {s}')
        for it in block['items']:
            tag = '' if it['kind'] == 'question' else f"  `[{KIND_HE[it['kind']]}]`"
            L.append(f"\n**{level_name} {it['num']}.** {it['text']}{tag}")
            for b in it['bullets']:
                L.append(f'  - {b}')
            for s in it['subs']:
                L.append(f"  - **{s['letter']}.** {s['text']}")
                for n in it['notes']:
                    if n['after'] == s['letter']:
                        L.append(f"    - _{n['text']}_")
            if it['fig_refs']:
                L.append(f"  - תרשימים מוזכרים: {', '.join(it['fig_refs'])}")
            for f in it['figures']:
                L.append(f'  - ![]({f})')
            for f in it.get('media', []):
                L.append(f'  - תמונה מוטמעת (נוסחה/שרטוט): ![]({f})')
        L.append('')

    render(req['prep'], 'דוח מכין', 'שאלה')
    render(req['procedure'], 'מהלך הניסוי (מגדיר את סעיפי הדוח המסכם)', 'סעיף')
    if req['procedure']['items']:
        L += ['## סעיפי הדוח המסכם הנגזרים', *[
            f"- **5.{it['num']}** {it['text'][:70]}" + (f" ({len(it['subs'])} תתי־סעיפים)" if it['subs'] else '')
            for it in req['procedure']['items']], '']
    if req['equations']:
        L += ['## נוסחאות בחוברת (OMML)', *[f"- `{e['text']}` — אחרי: \"{e['context']}\"" for e in req['equations']], '']
    L += ['## שרטוטים', '| קובץ | עמוד | כיתוב | שויך ל | תוויות |', '|---|---|---|---|---|']
    for f in req['figures']:
        L.append(f"| `{f['file']}` | {f['page']} | {f['caption'] or '—'} | "
                 f"{', '.join(f.get('linked_to', [])) or '⚠ לא שויך'} | {f['labels'][:60]} |")
    L.append('')
    if req['media']:
        L += ['## תמונות מוטמעות בחוברת', '| קובץ | שויך ל | מופיע אחרי |', '|---|---|---|']
        for m in req['media']:
            L.append(f"| `{m['file']}` | {', '.join(m.get('linked_to', [])) or '—'} | {m['context'][:50]} |")
        L.append('')
    v = req['values']
    L += ['## ערכים ורכיבים שזוהו (לאימות מול השרטוטים)',
          '> ערכים שמופיעים **בתוך** שרטוט רסטרי (למשל 10K, 0.1uF) לא נקראים אוטומטית — '
          'יש לקרוא אותם מקובצי figures/ ולרשום במפורש לפני החישובים.'] + \
         [f"- **{k}:** {', '.join(v[k]) or '—'}" for k in v] + ['']
    if req['datasheets']:
        L += ['## דפי נתונים נדרשים', *[f"- {k}: {', '.join(vs)}" for k, vs in req['datasheets'].items()], '']
    if req['parts']:
        L += ['## רכיבים זמינים במעבדה', '- ' + ' · '.join(req['parts']), '']
    if req['bib'] or req['theory']:
        L += ['## ביבליוגרפיה / חומר תאורטי', *[f'- {b}' for b in req['bib'] + req['theory']], '']
    unlinked = [f['file'] for f in req['figures'] if not f.get('linked_to')]
    if unlinked:
        L += ['## ⚠ לבדיקה', f"שרטוטים שלא שויכו אוטומטית לשאלה: {', '.join(unlinked)}", '']
    open(path, 'w', encoding='utf-8').write('\n'.join(L))

def main(booklet, course_dir):
    booklet = os.path.abspath(booklet)
    tmp = os.path.join(course_dir, '_req_tmp')
    os.makedirs(tmp, exist_ok=True)
    # Work on a plain-ASCII copy: LibreOffice sometimes refuses to load files straight from a
    # OneDrive folder (pinned/placeholder attributes) or with non-ASCII paths; a copy always loads.
    src = os.path.join(tmp, 'booklet.docx')
    copy_with_retry(booklet, src)
    txt = soffice_convert(src, 'txt:Text (encoded):UTF8', tmp, 'txt')
    pdf = soffice_convert(src, 'pdf', tmp, 'pdf')
    lines = open(txt, encoding='utf-8-sig').read().splitlines()
    req = parse_text(lines)
    if req['number'] is None:
        raise RuntimeError('could not find the experiment title/number in the booklet')
    exp_dir = exp_folder(course_dir, req['number'], req['title'])
    out = os.path.join(exp_dir, 'requirements')
    clear_derived(out)                               # regenerate cleanly (derived files only)
    shutil.move(pdf, os.path.join(out, 'source.pdf'))
    shutil.move(txt, os.path.join(out, 'source.txt'))
    eqs, media, shape_text = scan_docx(src)          # read the copy: the original may be locked
    media = export_media(src, media, out)
    shutil.rmtree(tmp, ignore_errors=True)
    figs, npages = extract_figures(os.path.join(out, 'source.pdf'), out)
    link_figures(req, figs)
    link_media(req, media)
    # values/ICs come from what the experiment actually asks (not the "parts available" list)
    chunks = list(req['goals'])
    for sec in ('prep', 'procedure'):
        chunks += req[sec]['intro']
        for it in req[sec]['items']:
            chunks += [it['text']] + it['bullets'] + [s['text'] for s in it['subs']] + \
                      [n['text'] for n in it['notes']]
    alltext = '\n'.join(chunks) + '\n' + ' '.join(f['labels'] for f in figs) + '\n' + shape_text
    req.update({'source': booklet, 'pages': npages, 'figures': figs, 'media': media,
                'equations': eqs, 'values': extract_values(alltext)})
    req['datasheets'] = datasheet_families(req['values']['ics'])
    json.dump(req, open(os.path.join(out, 'requirements.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    write_md(req, os.path.join(out, 'requirements.md'))
    print(f"OK  ניסוי {req['number']}: prep={len(req['prep']['items'])} "
          f"procedure={len(req['procedure']['items'])} figures={len(figs)} "
          f"unlinked={sum(1 for f in figs if not f.get('linked_to'))} -> {out}")
    return out

if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.stdout.reconfigure(encoding='utf-8')
    main(sys.argv[1], sys.argv[2])
