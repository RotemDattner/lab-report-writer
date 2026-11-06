# -*- coding: utf-8 -*-
"""
scope_intake.py — after the lab: inventory the scope captures and flag what looks wrong,
BEFORE anything is written into a report.

    python scope_intake.py <experiment_dir> [--supplies 5 10]

Reads <experiment_dir>/images/*: every picture, and next to it the settings file the scope saves
with a capture (Keysight InfiniiVision "*.txt": channel scales, trigger, XY/YT mode and the
automatic measurements). File names do not matter — students save captures as "1-b.png",
"2,2-1.png" or anything else; the tool identifies each capture from its settings.

Writes:
  images/INVENTORY.md  one row per capture in time order: mode (XY/YT), scales, measured
                       amplitudes and frequencies, and flags. Show it to the user and agree on
                       which capture goes to which step before embedding anything.
  lab.json             a draft of the per-experiment facts (only keys not already present):
                       date_performed (from the capture times), scope_serial (empty — read it off
                       the header line of any capture picture), date_submitted, measured {}.
Flags (each one is a question for the user, not a verdict):
  * an output amplitude that matches no supply voltage — a capture taken at another VDD than its
    label says (in the lab, a generator left at 0–10 V pumped a "5 V" supply to 7.2 V);
  * (note, not a warning) channels with the same frequency to 0.1 % — normal for a driven gate, but
    for a free-running oscillator it means it locked to the generator (in the lab, a sine was wired
    to the control input instead of a DC level);
  * the same file content saved twice.
"""
import os, re, sys, json, glob, hashlib, datetime

UNITS = {'': 1, 'm': 1e-3, 'u': 1e-6, 'µ': 1e-6, 'n': 1e-9, 'k': 1e3, 'M': 1e6}
PICS = ('.png', '.jpg', '.jpeg', '.bmp')


def value(s):
    """'10.7V' -> 10.7; '4.9974kHz' -> 4997.4; '500mV' -> 0.5."""
    m = re.match(r'\s*([-+]?\d+(?:\.\d+)?)\s*([kMmunµ]?)(V|Hz|s)?', s)
    return float(m.group(1)) * UNITS[m.group(2)] if m else None


def parse_keysight(path):
    txt = open(path, encoding='utf-8', errors='replace').read()
    if 'ANALOG' not in txt:                       # a capture without automatic measurements is still a capture
        return None
    info = {'channels': {}, 'meas': [], 'mode': 'YT', 'timebase': None, 'trigger': None,
            'digital': 'DIGITAL' in txt}          # MSO logic channels D0–D15 in use
    for m in re.finditer(r'Ch (\d) Scale ([^,]+), Pos ([^,]+),', txt):
        info['channels'][int(m.group(1))] = {'scale': m.group(2).strip(), 'pos': value(m.group(3))}
    hz = re.search(r'HORIZONTAL\s*\n\s*Mode ([^,\n]+)(?:.*?Main Scale ([^,\n]+))?', txt)
    if hz:
        info['mode'] = 'XY' if hz.group(1).strip() == 'XY' else 'YT'
        info['timebase'] = (hz.group(2) or '').strip() or None
    tr = re.search(r'TRIGGER\s*\n.*\n\s*Mode ([^\n]+)', txt)
    if tr:
        info['trigger'] = tr.group(1).strip()
    for m in re.finditer(r'^\+?\s*([A-Za-z\-]+)\((D?\d+)\), Cur ([^,]+),', txt, re.M):   # "+ Duty(2)", "Frequency(D3)"
        ch = int(m.group(2)) if m.group(2).isdigit() else m.group(2)
        info['meas'].append((m.group(1), ch, value(m.group(3)), m.group(3).strip()))
    src = re.search(r'Source (D?\d+|Ch \d)', txt)
    info['trigger_source'] = src.group(1) if src else None
    return info


def flags_for(info, supplies):
    out = []
    if supplies:
        for name, ch, v, raw in info['meas']:
            if name == 'Amplitude' and v and v > 1.0:
                near = min(supplies, key=lambda s: abs(s - v))
                if abs(near - v) / near > 0.08:
                    out.append(f'Amplitude({ch}) = {raw} – לא קרוב לאף מתח הזנה ({", ".join(f"{s:g}" for s in supplies)} V). '
                               f'לבדוק באיזה מתח הזנה הצילום נלקח')
    return out


def locked(info):
    """Channels that share the generator frequency to 0.1 %. Normal for a driven circuit (a gate output
    follows its input); for a FREE-RUNNING oscillator it means the oscillator is locked to the generator."""
    freqs = [(ch, v) for name, ch, v, raw in info['meas'] if name == 'Frequency' and v]
    same = set()
    for i in range(len(freqs)):
        for j in range(i + 1, len(freqs)):
            (c1, f1), (c2, f2) = freqs[i], freqs[j]
            if c1 != c2 and abs(f1 - f2) / max(f1, f2) < 1e-3:
                same |= {c1, c2}
    return sorted(same)


def _gen_freq(info):
    """The generator frequency of a capture: Frequency(1) (CH1 = generator in the lab's convention)."""
    for name, ch, v, raw in info['meas']:
        if name == 'Frequency' and ch == 1 and v:
            return v
    return None


def coverage(exp_dir, caps, supplies):
    """Required captures (captures.json, written with the self-study document) against the captures
    found. A capture that was never taken cost 3 points in validation (a triangle input in XY mode), and
    it can be noticed only by counting: the settings file does not tell a sine from a triangle."""
    path = os.path.join(exp_dir, 'captures.json')
    if not os.path.exists(path):
        return ['', '_אין captures.json – רשימת הצילומים הנדרשים נכתבת עם מסמך ההכנה העצמית; '
                'בלעדיה אי אפשר לבדוק מה חסר._']
    req = json.load(open(path, encoding='utf-8'))
    groups = {}
    for r in req:
        key = (r.get('mode', 'YT'), r.get('freq_hz'))
        groups.setdefault(key, []).append(r)
    L = ['', '## צילומים נדרשים מול צילומים שנמצאו', '',
         '| מצב | תדר מחולל | נדרשים | נמצאו | סעיפים | |', '|---|---|---|---|---|---|']
    missing = 0
    for (mode, f), rs in groups.items():
        found = [n for n, info in caps if info['mode'] == mode and
                 (f is None or (_gen_freq(info) and abs(_gen_freq(info) - f) / f < 0.05))]
        flag = '⚠ חסרים צילומים' if len(found) < len(rs) else ''
        missing += max(0, len(rs) - len(found))
        fs = f'{f:g} Hz' if f else '–'
        L.append(f'| {mode} | {fs} | {len(rs)} | {len(found)} | {", ".join(r["step"] for r in rs)} | {flag} |')
    L += ['', '### מה חייב להופיע על המסך – לאשר לכל צילום', '',
          '| סעיף | על המסך | מופיע בצילום? |', '|---|---|---|']
    for r in req:
        if r.get('measure') and r['measure'] != '–':
            L.append(f'| {r["step"]} | {r["measure"]} | ☐ |')
    L += ['', 'ערך שלא מופיע על המסך (סמן או מדידה אוטומטית) אינו מדידה: לא לחשב אותו מהתמונה ולהציג אותו '
              'כ"נמדד". לספר למשתמש לפני הכתיבה.']
    if missing:
        print(f'  ⚠ {missing} required capture(s) not found – see INVENTORY.md')
    return L


def main(exp_dir, supplies):
    img = os.path.join(exp_dir, 'images')
    pics = sorted(p for p in glob.glob(os.path.join(img, '*')) if p.lower().endswith(PICS))
    rows, seen = [], {}
    for p in pics:
        stem = os.path.splitext(p)[0]
        txt = stem + '.txt'
        info = parse_keysight(txt) if os.path.exists(txt) else None
        digest = hashlib.md5(open(p, 'rb').read()).hexdigest()
        dup = seen.get(digest)
        seen.setdefault(digest, os.path.basename(p))
        t = datetime.datetime.fromtimestamp(os.path.getmtime(p))
        rows.append((t, os.path.basename(p), info, dup))
    rows.sort(key=lambda r: r[0])

    L = ['# מלאי צילומי הסקופ', '',
         f'נוצר אוטומטית ({datetime.date.today():%d/%m/%Y}) מ־`scope_intake.py`. השעה היא שעת שמירת הקובץ; '
         'מספר סידורי ותאריך מופיעים גם בשורת הכותרת של כל צילום.', '',
         '| # | שעה | קובץ | מצב | סקאלות | מדידות הסקופ | הערות |', '|---|---|---|---|---|---|---|']
    for k, (t, name, info, dup) in enumerate(rows, 1):
        if dup:
            L.append(f'| {k} | {t:%H:%M:%S} | `{name}` | | | | העתק של `{dup}` |')
            continue
        if not info:
            L.append(f'| {k} | {t:%H:%M:%S} | `{name}` | ? | | | אין קובץ הגדרות – לזהות מהתמונה |')
            continue
        scales = ', '.join(f'CH{c} {v["scale"]}' for c, v in sorted(info['channels'].items()))
        if info['timebase']:
            scales += f', {info["timebase"]}'
        if info.get('digital'):
            scales += ', ערוצים דיגיטליים'
        if info.get('trigger_source'):
            scales += f', טריגר {info["trigger_source"]}'
        meas = ', '.join(f'{n}({c}) {raw}' for n, c, v, raw in info['meas'])
        fl = ['⚠ ' + f for f in flags_for(info, supplies)]
        lk = locked(info)
        if lk:
            fl.append('אותו תדר ב־' + ', '.join(f'CH{c}' for c in lk))
        L.append(f'| {k} | {t:%H:%M:%S} | `{name}` | {info["mode"]} | {scales} | {meas} | {" · ".join(fl)} |')
    L += coverage(exp_dir, [(name, info) for t, name, info, dup in rows if info and not dup], supplies)
    L += ['', 'לפני השיבוץ: לאשר עם המשתמש איזה צילום שייך לאיזה שלב, ולשאול על כל ⚠.',
          '"אותו תדר" רגיל במעגל שמונע מהמחולל (מוצא שער עוקב אחרי הכניסה). אבל אם הצילום הוא של מתנד '
          'שאמור לרוץ חופשי – המתנד ננעל על המחולל, וצריך לבדוק את החיבור לפני שמנתחים את התדר.']
    out = os.path.join(img, 'INVENTORY.md')
    open(out, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print(f'inventory: {out}  ({len(rows)} pictures)')

    labp = os.path.join(exp_dir, 'lab.json')
    lab = json.load(open(labp, encoding='utf-8-sig')) if os.path.exists(labp) else {}
    if rows and 'date_performed' not in lab:
        lab['date_performed'] = f'{rows[0][0]:%d/%m/%Y}'
    lab.setdefault('date_submitted', '')
    lab.setdefault('scope_serial', '')          # read it off the header line of a capture picture
    lab.setdefault('supplies', supplies or [])
    lab.setdefault('measured', {})              # measured component values, e.g. {"R1": "9.8 kΩ"}
    json.dump(lab, open(labp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'lab facts: {labp}')
    for t, name, info, dup in rows:
        if info:
            for f in flags_for(info, supplies):
                print(f'  ⚠ {name}: {f}')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    sup = []
    if '--supplies' in a:
        i = a.index('--supplies')
        sup = [float(x) for x in a[i + 1:] if re.match(r'^\d+(\.\d+)?$', x)]
        a = a[:i]
    main(a[0], sup)
