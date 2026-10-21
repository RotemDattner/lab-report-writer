# -*- coding: utf-8 -*-
"""
docx_edit.py — change a report the user already edited in Word, WITHOUT rebuilding it.

Once the user has opened a generated report in Word and changed it (report_kit's edited_by_hand()
tells: Word stamps w:rsidR, build_docx never does), build.py must not regenerate it — that wipes
their edits. Make each requested change directly in the document XML instead:

    python docx_edit.py dump "<report>.docx"        # numbered paragraphs, tables, pictures, comments

    from docx_edit import Doc
    d = Doc(r'…\\דוח מסכם.docx')                      # makes a backup in _archive\\ first
    p = d.find_par('במצב YT נמדדו רמות הסף')          # exactly one paragraph must contain the text
    d.replace_in(p, 'old words', 'new words')         # inside the runs: keeps the user's formatting
    d.set_text(d.cell(d.table_after('טבלה 4'), 1, 5), '−12%')
    d.delete(d.find_par('a paragraph to drop'))
    d.renumber(fig={6: 5, 7: 6}, tab={4: 2})          # after removing figures/tables: every "איור 7" → "איור 6"
    d.remove_comments()                               # once each of the user's comments is handled
    d.scale_images(11, only=lambda target: 'scope' in target)
    d.save()                                          # in place; if Word holds the file: "<name> - מעודכן.docx"

Text matching ignores the invisible direction marks (LRM/RLM/WJ) and treats NBSP as a space, so
pass the text as it reads on screen. New text goes through ltr_islands (number+unit islands), the
same as generated text. Equations: explicit_delims() writes "(" ")" into every m:d — Word drops the
default on save and some viewers then show none. After saving: check_docx.py (copy to the report's
standard name first — it infers the type from the name), render_pages.py, and validate.py of the
docx skill when available.
Needs lxml (pip install lxml).
"""
import os, re, sys, copy, shutil, zipfile, datetime
from lxml import etree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_docx import ltr_islands

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
WP = 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
q = lambda ns, t: f'{{{ns}}}{t}'
XML_SPACE = '{http://www.w3.org/XML/1998/namespace}space'
INV = {'‎', '‏', '⁠'}
EMU_PER_CM = 360000
COMMENT_PARTS = ('comments.xml', 'commentsExtended.xml', 'commentsIds.xml', 'commentsExtensible.xml')


def norm(s):
    return ''.join(' ' if c == ' ' else c for c in s if c not in INV)


def text_of(el):
    return norm(''.join(t.text or '' for t in el.iter(q(W, 't'), q(M, 't'))))


class Doc:
    def __init__(self, path, backup=True):
        self.path = os.path.abspath(path)
        with zipfile.ZipFile(self.path) as z:
            self.parts = {n: z.read(n) for n in z.namelist()}
        self.tree = etree.fromstring(self.parts['word/document.xml'])
        self.body = self.tree.find(q(W, 'body'))
        rels = etree.fromstring(self.parts['word/_rels/document.xml.rels'])
        self.rid = {r.get('Id'): r.get('Target') for r in rels}
        self.backup = self._backup() if backup else None

    def _backup(self):
        d = os.path.join(os.path.dirname(self.path), '_archive')
        os.makedirs(d, exist_ok=True)
        stem = os.path.splitext(os.path.basename(self.path))[0]
        dst = os.path.join(d, f'{stem} - גיבוי {datetime.datetime.now():%Y-%m-%d %H%M}.docx')
        shutil.copyfile(self.path, dst)
        return dst

    # ---------------------------------------------------------------- finding
    def paragraphs(self):
        return list(self.body.iter(q(W, 'p')))

    def find_par(self, sub, where=None):
        """The one paragraph whose visible text contains `sub` (asserts exactly one)."""
        pool = where if where is not None else self.paragraphs()
        hits = [p for p in pool if norm(sub) in text_of(p)]
        if len(hits) != 1:
            raise LookupError(f'{len(hits)} paragraphs contain: {sub[:60]}')
        return hits[0]

    def table_after(self, caption_sub):
        """The table that follows the caption paragraph containing `caption_sub` (captions sit above tables)."""
        starts = [p for p in self.paragraphs() if text_of(p).strip().startswith(norm(caption_sub))]
        el = (starts[0] if len(starts) == 1 else self.find_par(caption_sub)).getnext()
        while el is not None and el.tag != q(W, 'tbl'):
            el = el.getnext()
        if el is None:
            raise LookupError(f'no table after: {caption_sub}')
        return el

    def cell(self, tbl, row, col):
        """First paragraph of cell (row, col), 0-based, in the order of the XML (column 0 = rightmost in RTL)."""
        return tbl.findall(q(W, 'tr'))[row].findall(q(W, 'tc'))[col].find('.//' + q(W, 'p'))

    def pictures(self):
        """[(paragraph, media target)] for every embedded picture."""
        return [(p, self.rid.get(b.get(q(R, 'embed')))) for p in self.paragraphs() for b in p.iter(q(A, 'blip'))]

    # ---------------------------------------------------------------- changing text
    def replace_in(self, p, old, new, islands=True):
        """Replace `old` by `new` inside the runs of p, keeping the run formatting. `old` must occur once."""
        ts = list(p.iter(q(W, 't')))
        whole = ''.join(t.text or '' for t in ts)
        keep = [i for i, c in enumerate(whole) if c not in INV]
        visible = norm(''.join(whole[i] for i in keep))
        k = visible.find(norm(old))
        if k < 0:
            raise LookupError(f'not found: {old[:60]}')
        if visible.find(norm(old), k + 1) >= 0:
            raise LookupError(f'ambiguous: {old[:60]}')
        s, e = keep[k], keep[k + len(norm(old)) - 1] + 1
        new = ltr_islands(new) if islands and new else new
        pos, first = 0, True
        for t in ts:
            txt = t.text or ''
            a, b = pos, pos + len(txt)
            pos = b
            if b <= s or a >= e:
                continue
            t.text = (txt[:s - a] if a < s else '') + (new if first else '') + (txt[e - a:] if b > e else '')
            t.set(XML_SPACE, 'preserve')
            first = False

    def set_text(self, p, text, islands=True):
        """Replace a paragraph's whole content by one run with the first run's formatting."""
        r0 = p.find('.//' + q(W, 'r'))
        rpr = r0.find(q(W, 'rPr')) if r0 is not None else None
        rpr = copy.deepcopy(rpr) if rpr is not None else None
        for ch in list(p):
            if ch.tag != q(W, 'pPr'):
                p.remove(ch)
        r = etree.SubElement(p, q(W, 'r'))
        if rpr is not None:
            r.append(rpr)
        t = etree.SubElement(r, q(W, 't'))
        t.text = ltr_islands(text) if islands else text
        t.set(XML_SPACE, 'preserve')

    def add_after(self, p, text):
        """New paragraph after p, same paragraph and run format as p."""
        new = copy.deepcopy(p)
        for d in list(new.iter(q(W, 'drawing'))):
            d.getparent().getparent().remove(d.getparent())
        self.set_text(new, text)
        p.addnext(new)
        return new

    def delete(self, el):
        el.getparent().remove(el)

    def unhighlight(self, el):
        for h in list(el.iter(q(W, 'highlight'))):
            h.getparent().remove(h)

    # ---------------------------------------------------------------- whole-document operations
    def renumber(self, fig=None, tab=None, eq=None):
        """Apply old→new maps to every 'איור N', 'איורים N ו־M', 'טבלה N', 'נוסחה (N)' in the text."""
        fig, tab, eq = fig or {}, tab or {}, eq or {}
        pat = re.compile(r'(איור(?:ים)?|טבל(?:ה|אות))([\s ]+)(\d+)(?:([\s ]+ו־)(\d+))?')

        def sub(m):
            mp = fig if m.group(1).startswith('איור') else tab
            s = m.group(1) + m.group(2) + str(mp.get(int(m.group(3)), int(m.group(3))))
            if m.group(5):
                s += m.group(4) + str(mp.get(int(m.group(5)), int(m.group(5))))
            return s
        eqp = re.compile(r'(נוסח(?:ה|אות)[\s ]+\()(\d+)(\))')
        for t in self.body.iter(q(W, 't')):
            if t.text:
                t.text = pat.sub(sub, t.text)
                if eq:
                    t.text = eqp.sub(lambda m: m.group(1) + str(eq.get(int(m.group(2)), int(m.group(2)))) + m.group(3), t.text)

    def comments(self):
        """[(id, author, comment text, the text it is anchored to)] — the user's notes to work through."""
        if 'word/comments.xml' not in self.parts:
            return []
        out, anchored, open_ids = [], {}, set()
        for el in self.body.iter():
            if el.tag == q(W, 'commentRangeStart'):
                open_ids.add(el.get(q(W, 'id')))
            elif el.tag == q(W, 'commentRangeEnd'):
                open_ids.discard(el.get(q(W, 'id')))
            elif el.tag == q(W, 't') and el.text:
                for i in open_ids:
                    anchored[i] = anchored.get(i, '') + el.text
        for c in etree.fromstring(self.parts['word/comments.xml']).iter(q(W, 'comment')):
            i = c.get(q(W, 'id'))
            out.append((i, c.get(q(W, 'author')), text_of(c), norm(anchored.get(i, ''))))
        return out

    def remove_comments(self):
        for tag in ('commentRangeStart', 'commentRangeEnd'):
            for el in list(self.body.iter(q(W, tag))):
                self.delete(el)
        for ref in list(self.body.iter(q(W, 'commentReference'))):
            run = ref.getparent()
            run.getparent().remove(run)
        for name in COMMENT_PARTS:
            key = 'word/' + name
            if key in self.parts:
                root = etree.fromstring(self.parts[key])
                for ch in list(root):
                    root.remove(ch)
                self.parts[key] = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)

    def explicit_delims(self):
        """Write begChr '(' / endChr ')' into every equation delimiter that relies on the default."""
        order = ['begChr', 'sepChr', 'endChr', 'grow', 'shp', 'ctrlPr']
        n = 0
        for d in self.body.iter(q(M, 'd')):
            dpr = d.find(q(M, 'dPr'))
            if dpr is None:
                dpr = etree.Element(q(M, 'dPr')); d.insert(0, dpr)
            for tag, ch in (('begChr', '('), ('endChr', ')')):
                if dpr.find(q(M, tag)) is None:
                    el = etree.SubElement(dpr, q(M, tag)); el.set(q(M, 'val'), ch); n += 1
            kids = sorted(dpr, key=lambda e: order.index(etree.QName(e).localname)
                          if etree.QName(e).localname in order else 99)
            for k in kids:
                dpr.append(k)                       # re-append in schema order
        return n

    def scale_images(self, width_cm, only=None):
        """Set the width of pictures (keeping the aspect ratio); `only(target)` picks which, e.g. by media name.
        Never enlarges past the current size."""
        n = 0
        for inline in self.body.iter(q(WP, 'inline'), q(WP, 'anchor')):
            blip = inline.find('.//' + q(A, 'blip'))
            if blip is None or (only and not only(self.rid.get(blip.get(q(R, 'embed')), ''))):
                continue
            ext = inline.find(q(WP, 'extent'))
            cx, cy = int(ext.get('cx')), int(ext.get('cy'))
            new_cx = int(width_cm * EMU_PER_CM)
            if new_cx >= cx:
                continue
            new_cy = round(cy * new_cx / cx)
            ext.set('cx', str(new_cx)); ext.set('cy', str(new_cy))
            for a_ext in inline.iter(q(A, 'ext')):
                if a_ext.get('cx'):
                    a_ext.set('cx', str(new_cx)); a_ext.set('cy', str(new_cy))
            n += 1
        return n

    # ---------------------------------------------------------------- saving
    def save(self, out=None):
        """Write the document ([Content_Types].xml first). If the target is locked (open in Word), saves as
        '<name> - מעודכן.docx' next to it and says so. Returns the path written."""
        self.parts['word/document.xml'] = etree.tostring(self.tree, xml_declaration=True, encoding='UTF-8',
                                                         standalone=True)
        out = os.path.abspath(out or self.path)
        names = ['[Content_Types].xml'] + [n for n in self.parts if n != '[Content_Types].xml']
        tmp = out + '.tmp'
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
            for n in names:
                z.writestr(n, self.parts[n])
        try:
            os.replace(tmp, out)
        except PermissionError:
            alt = os.path.splitext(out)[0] + ' - מעודכן.docx'
            os.replace(tmp, alt)
            print(f'⚠ {os.path.basename(out)} is open in Word: saved as {os.path.basename(alt)}. '
                  f'Tell the user which file is the current one.')
            out = alt
        return out


def dump(path):
    """Print the body in order: P### paragraphs (* = has highlight), tables, pictures, then the comments."""
    d = Doc(path, backup=False)
    n = 0
    for el in d.body:
        if el.tag == q(W, 'p'):
            pics = [d.rid.get(b.get(q(R, 'embed'))) for b in el.iter(q(A, 'blip'))]
            t = text_of(el) + ''.join(f' [IMG {x}]' for x in pics)
            if t.strip():
                n += 1
                hl = '*' if el.find('.//' + q(W, 'highlight')) is not None else ' '
                print(f'P{n:03d}{hl} {t}')
        elif el.tag == q(W, 'tbl'):
            print('  [TABLE]')
            for row in el.iter(q(W, 'tr')):
                print('   | ' + ' | '.join(text_of(c) for c in row.iter(q(W, 'tc'))))
    cs = d.comments()
    if cs:
        print('\n== COMMENTS ==')
        for i, author, text, anchor in cs:
            print(f'C{i} ({author}) on "{anchor[:50]}": {text}')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv) == 3 and sys.argv[1] == 'dump':
        dump(sys.argv[2])
    else:
        sys.exit(__doc__)
