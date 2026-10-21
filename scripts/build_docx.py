# -*- coding: utf-8 -*-
"""
build_docx.py — dependency-free builder for Hebrew (RTL) .docx lab reports with real
OMML equations, RTL tables, embedded images and image placeholders.

A .docx is a ZIP of XML parts; OMML must be authored as XML (python-docx cannot), so we
build the XML directly. Import DocxBuilder and the equation helpers, compose a document,
then .save(path).

See references/word-generation.md for the mechanics this encodes.
"""
import zipfile, os, re, struct
from xml.sax.saxutils import escape as _xml_escape

# ---------------------------------------------------------------- namespaces
_NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"'
)

def esc(t):
    return _xml_escape(str(t))

# ---------------------------------------------------------------- OMML helpers
# Each returns an OMML fragment string; compose freely.
def mrun(t):
    """A math run (text token). Pass symbols as unicode or numeric entities."""
    return f'<m:r><m:t xml:space="preserve">{t}</m:t></m:r>'

def frac(num, den):
    return f'<m:f><m:num>{num}</m:num><m:den>{den}</m:den></m:f>'

def ssub(base, sub):
    return f'<m:sSub><m:e>{base}</m:e><m:sub>{sub}</m:sub></m:sSub>'

def ssup(base, sup):
    return f'<m:sSup><m:e>{base}</m:e><m:sup>{sup}</m:sup></m:sSup>'

def rad(radicand, degree=None):
    deg = f'<m:deg>{degree}</m:deg>' if degree else '<m:degHide m:val="1"/><m:deg/>'
    return f'<m:rad><m:radPr>{deg}</m:radPr><m:e>{radicand}</m:e></m:rad>'

def delim(inner, beg='(', end=')'):
    return (f'<m:d><m:dPr><m:begChr m:val="{beg}"/><m:endChr m:val="{end}"/></m:dPr>'
            f'<m:e>{inner}</m:e></m:d>')

def omath(inner):
    """Inline math run (flows inside a paragraph)."""
    return f'<m:oMath>{inner}</m:oMath>'

def omath_para(inner):
    """Display math (its own centered block)."""
    return f'<m:oMathPara><m:oMath>{inner}</m:oMath></m:oMathPara>'

# ---------------------------------------------------------------- bidi: LTR islands in Hebrew
# In an RTL paragraph a number that follows Hebrew takes the paragraph direction, so
# "0.470 ms" prints as "ms 0.470", "2.2–3.6" as "3.6–2.2", "1.1 / 1.7 / 2.1 V" reversed and
# "≥ 4.95" mirrored (Unicode bidi rules W7/N1 - Word and LibreOffice agree). Wrapping such a
# run in LEFT-TO-RIGHT MARKs makes its digits and separators resolve as LTR, so it prints in
# reading order. LRM is invisible and supported by every renderer (U+2066 isolates are not).
_LRM, _RLM = '‎', '‏'
_UNIT = (r'(?:[kMmµμunp]?(?:Hz|Ω|V|A|W|F|H|s)(?:\s?p-p)?(?![A-Za-z])'
         r'|°C|%|dB|ppm)')
# the optional space belongs to the sign only: "(?:≈ )?" - a bare "\s?" here pulled the space
# BEFORE the number into the island, so it printed on the wrong side ("הנתונים:0.986 ms .")
_NUM = r'(?:[≈~±≤≥<>+]\s?)?[-−]?\d+(?:[.,]\d+)?'
_ITEM = rf'{_NUM}(?:\s?{_UNIT})?'
# a range is "a–b" without spaces; " – " with spaces is a Hebrew sentence dash ("3, 4, …, 14, 3 – 12
# מצבים" became the range "12 – 3"); value lists use "/" with or without spaces
_ISLAND = re.compile(rf'(?<![\w.]){_ITEM}(?:(?:\s?/\s?|–){_ITEM})*')
# 'EN = "1"' printed as '"EN = "1': the quotes are neutral and follow the paragraph direction
_LEVEL = re.compile(r'(?<![\w])[A-Za-z][\w/̄]*\s?=\s?"[01]"')
# file names that start with digits ("5.5.2_scope_min.png") were split around the underscore
_FILE = re.compile(r'(?<![\w/])(?:[\w.\-]+/)*[\w.\-]+\.(?:png|jpg|jpeg|json|m|cir|md|docx|py)(?![\w])')
_NBSP, _WJ = ' ', '⁠'


def ltr_islands(text):
    """Wrap number+unit, ranges (a–b), value lists (a / b / c unit), logic levels (EN = "1")
    and file names in LRM marks so they print in reading order inside Hebrew text."""
    keep = []

    def stash(s):                       # protect a finished island from the next pattern
        keep.append(s)
        return f'{len(keep) - 1}'

    def fix(m):
        s = m.group(0)
        if not re.search(rf'\s?{_UNIT}|[/–]|^[≈~±≤≥<>+]', s):   # a lone number displays fine
            return s
        # keep the island on one line: a wrap inside it split "0.47 | ms" and "2%– | 4%" across
        # lines (NBSP for spaces, WORD JOINER around the dash)
        s = s.replace(' ', _NBSP).replace('–', _WJ + '–' + _WJ)
        # close with RLM, not LRM: a closing LRM made what FOLLOWS the island LTR too
        # ("4154 Hz; (3) סבולות" swallowed the "(3)"); RLM hands the direction back to Hebrew
        return stash(_LRM + s + _RLM)

    # a closing quote sits between "1" and Hebrew: an extra LRM after it keeps it on the LTR side
    text = _FILE.sub(lambda m: stash(_LRM + m.group(0) + _LRM + _RLM), text)
    text = _LEVEL.sub(lambda m: stash(_LRM + m.group(0).replace(' ', _NBSP) + _LRM + _RLM), text)
    text = _ISLAND.sub(fix, text)
    return re.sub('(\\d+)', lambda m: keep[int(m.group(1))], text)

# ---------------------------------------------------------------- image size
def _png_size(path):
    """Pixel size of a PNG or JPEG (scope photos are often JPEG) without any image library."""
    with open(path, 'rb') as f:
        data = f.read()
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return struct.unpack('>II', data[16:24])
    if data[:2] == b'\xff\xd8':                     # JPEG: find a SOFn marker
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker, seglen = data[i + 1], struct.unpack('>H', data[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack('>HH', data[i + 5:i + 9])
                return (w, h)
            i += 2 + seglen
    return (600, 400)

_EMU_PER_PX = 9525
_MAX_W_EMU = 5486400  # ~6.0 inch content width

# ---------------------------------------------------------------- builder
class DocxBuilder:
    def __init__(self, default_font="David", base_size=24, page_numbers=True):
        self._body = []           # list of block XML strings
        self._images = []         # list of (arcname, filepath)
        self._font = default_font
        self._size = base_size    # half-points (24 = 12pt)
        self.page_numbers = page_numbers

    # ---- low-level ----
    def raw(self, xml):
        self._body.append(xml)

    def page_break(self):
        self._body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

    def spacer(self):
        self._body.append('<w:p/>')

    # ---- run rendering (shared) ----
    # rPr children MUST follow the OOXML schema order (Word is strict; LibreOffice is not):
    #   rFonts, b, bCs, i, iCs, ..., color, ..., sz, szCs, highlight, ..., rtl, cs, ...
    # so bold/italic first, then color, size, highlight, and rtl LAST.
    def _rpr(self, rtl=True, bold=False, size=None, highlight=False, italic=False, color=None):
        parts = ''
        if bold:      parts += '<w:b/><w:bCs/>'
        if italic:    parts += '<w:i/><w:iCs/>'
        if color:     parts += f'<w:color w:val="{color}"/>'
        if size:      parts += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
        if highlight: parts += '<w:highlight w:val="yellow"/>'
        if rtl:       parts += '<w:rtl/>'
        return f'<w:rPr>{parts}</w:rPr>' if parts else ''

    def _render_tokens(self, content, rtl=True, bold=False, size=None, highlight=False,
                       italic=False, color=None):
        """content: str, or list of: str | ('math',omml) | ('hl',text) | ('hlmath',omml).
        'hl' marks a Hebrew segment for yellow highlight (needs-verification); 'math'/'hlmath'
        emit inline OMML (immune to bidi reordering of relations)."""
        if isinstance(content, str):
            content = [content]
        out = []
        for item in content:
            if isinstance(item, tuple):
                kind = item[0]
                if kind in ('math', 'hlmath'):
                    out.append(omath(item[1]))
                    continue
                text, hl = item[1], (kind == 'hl' or highlight)
            else:
                text, hl = item, highlight
            if rtl:
                text = ltr_islands(text)
            out.append(f'<w:r>{self._rpr(rtl, bold, size, hl, italic, color)}'
                       f'<w:t xml:space="preserve">{esc(text)}</w:t></w:r>')
        return ''.join(out)

    def para(self, content, align='right', bold=False, size=None, rtl=True,
             space_after=120, highlight=False, italic=False, color=None, keep_next=False,
             space_before=0, page_break_before=False):
        # pPr children MUST follow schema order: keepNext, pageBreakBefore, bidi, spacing, jc.
        # For RTL, bidi alone yields right alignment (matches the official template), so we
        # emit jc only for non-right alignment to avoid renderer ambiguity.
        # keepNext glues a heading/caption/picture to the paragraph after it (no orphans).
        # pageBreakBefore starts a new page without a separate break paragraph - such a
        # paragraph that lands exactly at a page end produces a blank page.
        ppr = ('<w:keepNext/>' if keep_next else '') + \
              ('<w:pageBreakBefore/>' if page_break_before else '') + ('<w:bidi/>' if rtl else '') + \
              f'<w:spacing w:before="{space_before}" w:after="{space_after}"/>'
        if align != 'right':
            ppr += f'<w:jc w:val="{align}"/>'
        runs = self._render_tokens(content, rtl=rtl, bold=bold, size=size, highlight=highlight,
                                   italic=italic, color=color)
        self._body.append(f'<w:p><w:pPr>{ppr}</w:pPr>{runs}</w:p>')

    def title(self, text):
        self.para(text, align='center', bold=True, size=36, keep_next=True)

    def heading(self, text, level=1, new_page=False):
        size = {1: 30, 2: 26, 3: 24}.get(level, 24)
        self.para(text, align='right', bold=True, size=size, space_after=80,
                  space_before=160 if level == 1 else 80, keep_next=True, page_break_before=new_page)

    def question(self, number, text):
        """Numbered question heading: 'N. text' (kept exactly as the requirement numbers)."""
        self.para([f'{number}. {text}'], align='right', bold=True, size=26, space_after=80,
                  space_before=160, keep_next=True)

    def subpart(self, letter, text):
        self.para([f'{letter}. {text}'], align='right', bold=True, size=24, space_after=60,
                  keep_next=True)

    def equation(self, omml_inner, number=None):
        """Display equation (numbering is handled by report_kit, which prepends '(n)')."""
        block = omath_para(omml_inner)
        self._body.append(f'<w:p><w:pPr><w:spacing w:before="60" w:after="60"/>'
                          f'<w:jc w:val="center"/></w:pPr>{block}</w:p>')

    # ---- cover ----
    def cover(self, lines):
        """lines: list of (text, {opts}) rendered centered; ends with a page break.
        opts keys: bold, size, space_after."""
        for text, opts in lines:
            self.para([text], align='center', bold=opts.get('bold', False),
                      size=opts.get('size'), space_after=opts.get('space_after', 200))
        self.page_break()

    # ---- tables (RTL) ----
    def table(self, rows, header=None, widths=None):
        """rows: list of list of (str | ('math', omml) | list of those); header: optional list.
        Column widths follow the content (twips): short tables stay compact, long text gets the
        full text width - fixed equal widths made explanation columns unreadably narrow."""
        ncol = len(header) if header else (len(rows[0]) if rows else 1)
        if not widths:
            widths = self._auto_widths(([header] if header else []) + rows, ncol)
        grid = ''.join(f'<w:gridCol w:w="{w}"/>' for w in widths)
        border = ('<w:tblBorders>' + ''.join(
            f'<w:{e} w:val="single" w:sz="6" w:space="0" w:color="000000"/>'
            for e in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV')) + '</w:tblBorders>')
        # tblPr children in schema order: bidiVisual, tblW, jc, tblBorders, tblLayout
        tblpr = (f'<w:tblPr><w:bidiVisual/><w:tblW w:w="{sum(widths)}" w:type="dxa"/>'
                 f'<w:jc w:val="center"/>{border}<w:tblLayout w:type="fixed"/></w:tblPr>')
        def cell(item, width, bold=False):
            runs = self._render_tokens(item if isinstance(item, list) else [item], bold=bold)
            return (f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>'
                    f'<w:vAlign w:val="center"/></w:tcPr>'
                    f'<w:p><w:pPr><w:bidi/><w:spacing w:before="20" w:after="20"/>'
                    f'<w:jc w:val="center"/></w:pPr>{runs}</w:p></w:tc>')
        trs = []
        if header:
            # tblHeader makes the header row repeat when the table breaks across pages
            trs.append('<w:tr><w:trPr><w:tblHeader/></w:trPr>'
                       + ''.join(cell(h, widths[i], bold=True) for i, h in enumerate(header)) + '</w:tr>')
        for row in rows:
            trs.append('<w:tr><w:trPr><w:cantSplit/></w:trPr>'
                       + ''.join(cell(c, widths[i]) for i, c in enumerate(row)) + '</w:tr>')
        self._body.append(f'<w:tbl>{tblpr}<w:tblGrid>{grid}</w:tblGrid>{"".join(trs)}</w:tbl>')
        self.spacer()

    @staticmethod
    def _cell_len(c):
        if isinstance(c, str):
            return len(c)
        if isinstance(c, tuple):                         # ('math', omml) / ('hl', text)
            return len(re.sub(r'<[^>]+>', '', c[1])) if c[0] in ('math', 'hlmath') else len(c[1])
        return sum(DocxBuilder._cell_len(x) for x in c)

    def _auto_widths(self, rows, ncol, total=9026, per_char=130, pad=360, min_w=900):
        """Natural width per column from its longest cell; if the table would exceed the text
        width, share the width by sqrt(length) so long columns get more room without starving
        short ones."""
        longest = [max([self._cell_len(r[i]) for r in rows if i < len(r)] or [4]) for i in range(ncol)]
        natural = [max(min_w, l * per_char + pad) for l in longest]
        if sum(natural) <= total:
            return natural
        w = [max(l, 4) ** 0.5 for l in longest]
        return [max(min_w, int(total * x / sum(w))) for x in w]

    # ---- images ----
    def image(self, path, caption=None, max_w_emu=_MAX_W_EMU, keep_next=False, exact_w_emu=None):
        w_px, h_px = _png_size(path)
        cx = w_px * _EMU_PER_PX
        cy = h_px * _EMU_PER_PX
        if exact_w_emu:                                  # requested width, up- or down-scaling
            cy = int(cy * exact_w_emu / cx); cx = exact_w_emu
        if cx > max_w_emu:
            cy = int(cy * max_w_emu / cx); cx = max_w_emu
        rid = f'rIdImg{len(self._images)+1}'
        ext = os.path.splitext(path)[1].lower().replace('.jpeg', '.jpg') or '.png'
        arc = f'media/image{len(self._images)+1}{ext}'
        self._images.append((arc, path, rid))
        keep = '<w:keepNext/>' if (caption or keep_next) else ''
        drawing = (
            f'<w:p><w:pPr>{keep}<w:jc w:val="center"/></w:pPr><w:r><w:drawing>'
            f'<wp:inline distT="0" distB="0" distL="0" distR="0">'
            f'<wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{len(self._images)}" name="img{len(self._images)}"/>'
            f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:pic><pic:nvPicPr><pic:cNvPr id="{len(self._images)}" name="img{len(self._images)}"/>'
            f'<pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
            f'</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'
        )
        self._body.append(drawing)
        if caption:
            self.para([caption], align='center', bold=True, size=20, space_after=160)

    def placeholder(self, label):
        """A visible image placeholder for the summary skeleton."""
        self.para([f'[[ {label} ]]'], align='center', bold=True, size=22, space_after=160)

    def image_or_placeholder(self, path, caption, placeholder_label=None):
        """Insert the image with a numbered caption if the file exists; otherwise a visible
        placeholder with the same caption. This is what makes 'user drops a file in images/,
        re-run the build, the picture appears' work with no code changes."""
        if path and os.path.exists(path):
            self.image(path, caption=caption)
        else:
            self.placeholder(placeholder_label or caption)

    # ---- save ----
    def _document_xml(self):
        body = ''.join(self._body)
        # sectPr children in schema order: footerReference, pgSz, pgMar, titlePg, bidi.
        # titlePg = different first page -> no page number on the cover.
        foot = '<w:footerReference w:type="default" r:id="rIdFooter"/>' if self.page_numbers else ''
        sect = (f'<w:sectPr>{foot}<w:pgSz w:w="11906" w:h="16838"/>'
                '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
                'w:header="708" w:footer="708" w:gutter="0"/>'
                f'{"<w:titlePg/>" if self.page_numbers else ""}<w:bidi/></w:sectPr>')
        return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<w:document {_NS}><w:body>{body}{sect}</w:body></w:document>')

    def _styles_xml(self):
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:docDefaults><w:rPrDefault><w:rPr>'
                f'<w:rFonts w:ascii="{self._font}" w:hAnsi="{self._font}" w:cs="{self._font}"/>'
                f'<w:sz w:val="{self._size}"/><w:szCs w:val="{self._size}"/></w:rPr></w:rPrDefault>'
                '<w:pPrDefault><w:pPr><w:spacing w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault>'
                '</w:docDefaults></w:styles>')

    def _content_types(self):
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Default Extension="png" ContentType="image/png"/>'
                '<Default Extension="jpg" ContentType="image/jpeg"/>'
                '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
                '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
                '<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>'
                '</Types>')

    def _settings_xml(self):
        """Without compatibilityMode=15 Word opens the file in Compatibility Mode (מצב תאימות),
        where equations may be treated as legacy objects. 15 = Word 2013+ (current)."""
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:compat><w:compatSetting w:name="compatibilityMode" '
                'w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat>'
                '</w:settings>')

    def _footer_xml(self):
        """Centered PAGE field."""
        r = lambda inner: f'<w:r>{inner}</w:r>'
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
                + r('<w:fldChar w:fldCharType="begin"/>')
                + r('<w:instrText xml:space="preserve"> PAGE </w:instrText>')
                + r('<w:fldChar w:fldCharType="separate"/>') + r('<w:t>1</w:t>')
                + r('<w:fldChar w:fldCharType="end"/>') + '</w:p></w:ftr>')

    def _doc_rels(self):
        rels = ['<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>',
                '<Relationship Id="rIdFooter" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>',
                '<Relationship Id="rIdSettings" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>']
        for arc, _path, rid in self._images:
            rels.append(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="{arc}"/>')
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                + ''.join(rels) + '</Relationships>')

    def save(self, path):
        doc = self._document_xml()
        # validate well-formedness before zipping
        from xml.dom import minidom
        minidom.parseString(doc.encode('utf-8'))
        root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                     '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                     '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                     '</Relationships>')
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('[Content_Types].xml', self._content_types())
            z.writestr('_rels/.rels', root_rels)
            z.writestr('word/document.xml', doc)
            z.writestr('word/_rels/document.xml.rels', self._doc_rels())
            z.writestr('word/styles.xml', self._styles_xml())
            z.writestr('word/footer1.xml', self._footer_xml())
            z.writestr('word/settings.xml', self._settings_xml())
            for arc, filepath, _rid in self._images:
                z.write(filepath, f'word/{arc}')
        return path


if __name__ == '__main__':
    # self-test
    b = DocxBuilder()
    b.title('בדיקת מנוע — DocxBuilder')
    b.para('פסקת בדיקה בעברית מיושרת לימין, עם טוקן לועזי MC14093 באמצע המשפט.')
    b.equation(mrun('f') + mrun('=') + frac(mrun('1'),
               mrun('2RC ') + mrun('&#183;ln') + delim(frac(ssub(mrun('V'), mrun('p')),
                                                             ssub(mrun('V'), mrun('n'))))))
    b.table([['5', '2.9', '1.9'], ['10', '5.9', '3.9']],
            header=['מתח הזנה [V]', 'Vp [V]', 'Vn [V]'])
    b.placeholder('תמונה: איור 4.1.1 – מתח מוצא על הסקופ')
    out = os.path.join(os.path.dirname(__file__), '_selftest.docx')
    b.save(out)
    print('OK', out)
