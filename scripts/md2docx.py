# -*- coding: utf-8 -*-
"""
md2docx.py — a simple Hebrew Markdown file (guide, QA.md) → RTL Word document.

    python md2docx.py <in.md> <out.docx>

Supports: '# title', '## heading', '### sub-heading', paragraphs, '- ' bullets (indented
'   - ' sub-bullets), '1. ' numbered items, indented continuation lines, '| tables |',
``` code blocks (left-to-right, left-aligned) and $…$ inline math. Bold/italic markers are
dropped (whole-paragraph styling only).
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_docx import DocxBuilder
from mathtex import tex


def _inline(text):
    """'$..$' → math tokens; strip ** and ` markers."""
    text = text.replace('**', '').replace('`', '')
    out = []
    for i, part in enumerate(re.split(r'\$(.+?)\$', text)):
        if part:
            out.append(('math', tex(part)) if i % 2 else part)
    return out or ['']


def convert(md_path, out_path):
    b = DocxBuilder()
    lines = open(md_path, encoding='utf-8').read().splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if s.startswith('```'):
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                b.para(lines[i] or ' ', rtl=False, align='left', size=20, space_after=0,
                       color='1F3864')
                i += 1
            b.para('', space_after=60)
        elif s.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-{2,}:?', c) for c in cells):
                    rows.append([_inline(c) for c in cells])
                i += 1
            b.table(rows[1:], header=rows[0])
            b.para('', space_after=60)
            continue
        elif s.startswith('# '):
            b.title(s[2:])
        elif s.startswith('## '):
            b.heading(s[3:], level=1)
        elif s.startswith('### '):
            b.heading(s[4:], level=2)
        elif re.match(r'^\s{2,}- ', ln):
            b.para(['    ◦ '] + _inline(s[2:]), space_after=40)
        elif s.startswith('- '):
            b.para(['• '] + _inline(s[2:]), space_after=60)
        elif re.match(r'^\d+\. ', s):
            b.para(_inline(s), space_after=60)
        elif s and ln.startswith('   '):                         # continuation of a list item
            b.para(['    '] + _inline(s), space_after=60)
        elif s:
            b.para(_inline(s))
        i += 1
    b.save(out_path)
    return out_path


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    print(convert(sys.argv[1], sys.argv[2]))
