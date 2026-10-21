# -*- coding: utf-8 -*-
"""
progress.py — regenerate <course>/מדד התקדמות.md from what is actually on disk.

    python progress.py <course_dir>

Per experiment folder ("ניסוי NN - …"): requirements parsed?, which documents exist and their
check_docx error count, MATLAB simulations (.m with a matching .png), images filled vs. needed,
and whether a QA.md exists. Generated from the files, so it can't go stale.
"""
import os, sys, re, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_docx import check
from report_kit import DOC_NAMES


def exp_status(d):
    st = {'name': os.path.basename(d)}
    req_path = os.path.join(d, 'requirements', 'requirements.json')
    req = json.load(open(req_path, encoding='utf-8')) if os.path.exists(req_path) else None
    st['req'] = f"{len(req['prep']['items'])} ש' / {len(req['procedure']['items'])} סע'" if req else '—'
    for kind, fname in DOC_NAMES.items():
        p = os.path.join(d, fname)
        if not os.path.exists(p):
            st[kind] = '⬜'
            continue
        try:
            _, nerr = check(p, req)
            st[kind] = '✅' if nerr == 0 else f'⚠ {nerr}'
        except Exception:
            st[kind] = '❓'
    sims = glob.glob(os.path.join(d, 'simulations', '*.m'))
    # a script "ran" if lab_save wrote <prefix>_results.json whose prefix starts its name
    # (c11_astable_divider.m -> c11_results.json), or a .png carries its exact name
    res = [os.path.basename(f)[:-len('_results.json')]
           for f in glob.glob(os.path.join(d, 'simulations', '*_results.json'))]
    def produced(s):
        # schematic/demo scripts write files with other names ('sch_div2.png'): any output file
        # named in the script that exists counts as "ran"
        try:
            names = re.findall(r"'([\w.\-]+\.(?:png|json))'", open(s, encoding='utf-8', errors='ignore').read())
        except OSError:
            names = []
        return any(os.path.exists(os.path.join(os.path.dirname(s), n)) for n in names)
    ok = [s for s in sims if os.path.exists(s[:-2] + '.png') or produced(s)
          or any(os.path.basename(s)[:-2].startswith(p) for p in res)]
    st['sims'] = f'{len(ok)}/{len(sims)}' if sims else '—'
    # one file can fill slots in several documents (a Multisim screenshot is in both the prep
    # and the summary): count unique files, which is what the user has to produce
    files = set()
    for f in glob.glob(os.path.join(d, 'images', '.slots_*.json')):
        files.update(s['file'] for s in json.load(open(f, encoding='utf-8')))
    have = sum(os.path.exists(os.path.join(d, p)) for p in files)
    st['images'] = f'{have}/{len(files)}' if files else '—'
    st['qa'] = '✅' if os.path.exists(os.path.join(d, 'QA.md')) else '⬜'
    return st


def main(course_dir):
    dirs = sorted(x for x in glob.glob(os.path.join(course_dir, 'ניסוי *'))
                  if os.path.isdir(x) and re.match(r'ניסוי \d{2}', os.path.basename(x)))
    L = ['# מדד התקדמות', '', '(נוצר אוטומטית — `progress.py`. ✅ = עבר בדיקה אוטומטית; ⚠ n = n שגיאות; ⬜ = טרם נוצר)', '',
         '| ניסוי | דרישות | דוח מכין | הכנה עצמית | דוח מסכם | סימולציות | תמונות | QA |',
         '|---|---|:---:|:---:|:---:|:---:|:---:|:---:|']
    for d in dirs:
        s = exp_status(d)
        L.append(f"| {s['name']} | {s['req']} | {s['prep']} | {s['study']} | {s['summary']} | "
                 f"{s['sims']} | {s['images']} | {s['qa']} |")
    out = os.path.join(course_dir, 'מדד התקדמות.md')
    open(out, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
