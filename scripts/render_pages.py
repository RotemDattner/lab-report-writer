# -*- coding: utf-8 -*-
"""
render_pages.py — render Word documents to PDF and to two-page PNG spreads for page review.

    python render_pages.py <out_dir> <doc1.docx> [doc2.docx ...] [--dpi 85]

For each document: copies it to an ASCII name inside <out_dir> (OneDrive locks and non-ASCII
paths break LibreOffice), converts to <name>.pdf, and writes spreads <name>_s01.png, … (two
pages side by side). Look at EVERY spread; zoom on tables/formulas with PyMuPDF clips, and
check mixed-direction lines with visual_order.py instead of by eye.
A locked .docx (open in Word) is still readable through a shared-read copy.
"""
import sys, os, shutil, subprocess, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from labenv import find_soffice
import pymupdf


def _copy(src, dst):
    try:
        shutil.copyfile(src, dst)
    except PermissionError:                 # Word holds the file: PowerShell copies with shared read
        if os.name != 'nt':
            raise
        subprocess.run(['powershell', '-NoProfile', '-Command',
                        f"Copy-Item -LiteralPath '{src}' -Destination '{dst}'"], check=True)


def render(out_dir, docs, dpi=85):
    os.makedirs(out_dir, exist_ok=True)
    profile = tempfile.mkdtemp(prefix='lo_profile_')        # own profile: parallel-safe
    soffice = find_soffice()
    result = {}
    out_dir = os.path.abspath(out_dir)                     # LibreOffice failed on relative paths
    for i, src in enumerate(docs, 1):
        src = os.path.abspath(src)
        stem = f'doc{i}'
        dst = os.path.join(out_dir, stem + '.docx')
        _copy(src, dst)
        subprocess.run([soffice, f'-env:UserInstallation=file:///{profile.replace(os.sep, "/")}',
                        '--headless', '--convert-to', 'pdf', '--outdir', out_dir, dst],
                       capture_output=True, timeout=300)
        pdf = os.path.join(out_dir, stem + '.pdf')
        if not os.path.exists(pdf):
            raise RuntimeError(f'LibreOffice could not convert {src}')
        doc = pymupdf.open(pdf)
        w, h = doc[0].rect.width, doc[0].rect.height
        sheet = pymupdf.open()
        for k in range(0, len(doc), 2):
            pg = sheet.new_page(width=2 * w + 10, height=h)
            for j in range(2):
                if k + j < len(doc):
                    pg.show_pdf_page(pymupdf.Rect(j * (w + 10), 0, j * (w + 10) + w, h), doc, k + j)
            pg.draw_line((w + 5, 0), (w + 5, h), color=(0.5, 0.5, 0.5))
        for k, pg in enumerate(sheet, 1):
            pg.get_pixmap(dpi=dpi).save(os.path.join(out_dir, f'{stem}_s{k:02d}.png'))
        result[src] = (pdf, len(doc), len(sheet))
        print(f'{os.path.basename(src)} -> {stem}.pdf: {len(doc)} pages, {len(sheet)} spreads')
        limit = page_budget(src)
        if limit and len(doc) > limit:
            print(f'  ⚠ {len(doc)} pages – over the page budget of {limit} (course.json "max_pages_summary"). '
                  f'Shrink scope pictures (scope_width_cm), drop pictures that repeat a point, cut text.')
    shutil.rmtree(profile, ignore_errors=True)
    return result


def page_budget(docx_path):
    """max_pages_summary from <course>/course.json, for a summary report (דוח מסכם*) only."""
    if not os.path.basename(docx_path).startswith('דוח מסכם'):
        return None
    d = os.path.dirname(docx_path)
    for _ in range(3):                                      # experiment folder, then the course folder
        cfg = os.path.join(d, 'course.json')
        if os.path.exists(cfg):
            import json
            return json.load(open(cfg, encoding='utf-8-sig')).get('max_pages_summary')
        d = os.path.dirname(d)
    return None


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    dpi = 85
    if '--dpi' in a:
        dpi = int(a[a.index('--dpi') + 1]); del a[a.index('--dpi'):a.index('--dpi') + 2]
    render(a[0], a[1:], dpi)
