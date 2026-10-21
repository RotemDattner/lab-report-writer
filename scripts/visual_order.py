# -*- coding: utf-8 -*-
"""
visual_order.py — print PDF text lines in true on-screen order (left to right), to check
bidi results objectively instead of by eye.

    python visual_order.py <file.pdf> [page_index] [filter_text]

Hebrew appears reversed (that's its visual order); what matters is LTR islands: "0.470 ms",
"2.2–3.6", "1.1 / 1.7 / 2.1 V" must appear exactly as typed. "ms 0.470" or "3.6–2.2" means the
island was reordered by the bidi algorithm. Invisible marks (LRM/RLM) are removed from output.
"""
import sys
import pymupdf


def lines(pdf, pno):
    raw = pymupdf.open(pdf)[pno].get_text('rawdict')
    rows = {}
    for b in raw['blocks']:
        for l in b.get('lines', []):
            for s in l['spans']:
                for c in s['chars']:
                    key = round((c['bbox'][1] + c['bbox'][3]) / 2 / 4)   # baseline band
                    rows.setdefault(key, []).append((c['bbox'][0], c['c']))
    for k in sorted(rows):
        t = ''.join(ch for _, ch in sorted(rows[k]))
        # drop the invisible bidi/no-break helpers ltr_islands inserts, so lines compare as typed
        yield (t.replace('‎', '').replace('‏', '').replace('⁠', '')
                .replace(' ', ' '))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    pno = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    filt = sys.argv[3] if len(sys.argv) > 3 else ''
    for t in lines(sys.argv[1], pno):
        if filt in t:
            print('|' + t + '|')
