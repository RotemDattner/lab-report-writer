# -*- coding: utf-8 -*-
"""
scope_trace.py — read the traces back out of a scope screenshot (Keysight InfiniiVision 3000/4000 X,
800×632 PNG), so a value the scope did not measure can still be read FROM the capture instead of
being guessed: switching thresholds, a capacitor's peak, an XY loop rebuilt from a YT capture.

    python scope_trace.py <capture.png> [--in 1] [--out 2] [--csv out.csv]

The channel scale and offset come from the settings file saved next to the picture (<capture>.txt).
Screen geometry (measured on the grid of these scopes): 60 px per vertical division with the
centre line at y = 331, 64 px per horizontal division with the centre at x = 337; graticule rows
93–570, columns 20–655. Volts per pixel row:  V = Pos + (331 − y) / 60 × scale.
Trace colours: CH1 yellow, CH2 green, CH3 blue, CH4 pink.

Prints, for a YT capture with an input channel (--in) and a switching output (--out): the input
voltage at every output transition — Vp (output falls) and Vn (output rises) — with their spread.
Accuracy is about ±1 pixel (scale/60): ±0.08 V at 5 V/div. Say so when a value comes from here.

As a library:
    from scope_trace import traces, thresholds
    t, v = traces('images/1-b3.png')          # t [s] per column, v = {1: array, 2: array}
    vp, vn = thresholds(v[1], v[2])
"""
import os, re, sys
import numpy as np
from PIL import Image

GEOM = dict(cy=331, px_v=60, cx=337, px_h=64, top=93, bottom=570, left=20, right=655, size=(800, 632))
UNITS = {'': 1, 'm': 1e-3, 'u': 1e-6, 'µ': 1e-6, 'n': 1e-9, 'k': 1e3}


def _num(s):
    m = re.match(r'\s*([-+]?\d+(?:\.\d+)?)\s*([kmunµ]?)', s)
    return float(m.group(1)) * UNITS[m.group(2)]


def settings(png):
    """{ch: (volts_per_div, offset_V)}, seconds_per_div (None in XY mode) from <capture>.txt."""
    txt = os.path.splitext(png)[0] + '.txt'
    if not os.path.exists(txt):
        raise FileNotFoundError(f'{txt}: no settings file; pass the scales by hand (traces(..., scales=...))')
    s = open(txt, encoding='utf-8', errors='replace').read()
    ch = {int(m.group(1)): (_num(m.group(2)), _num(m.group(3)))
          for m in re.finditer(r'Ch (\d) Scale ([^,]+), Pos ([^,]+),', s)}
    tb = re.search(r'Main Scale ([^,\n]+)', s)
    return ch, (_num(tb.group(1)) if tb and 'Mode XY' not in s else None)


def _mask(img, ch):
    R, G, B = img[..., 0], img[..., 1], img[..., 2]
    return {1: (R > 150) & (G > 150) & (abs(R - G) < 45) & (B < 90),          # yellow
            2: (G > 150) & (R < 110) & (B < 90),                              # green
            3: (B > 150) & (R < 110) & (G < 200) & (B - G > 40),              # blue
            4: (R > 170) & (B > 90) & (G < 120)}[ch]                          # pink


def traces(png, channels=(1, 2), scales=None):
    """t [s] per screen column (relative to the centre), and {ch: volts per column}; columns where any
    requested trace is missing are dropped so the arrays stay aligned."""
    img = np.asarray(Image.open(png).convert('RGB')).astype(int)
    if img.shape[1::-1] != GEOM['size']:
        print(f'⚠ {os.path.basename(png)} is {img.shape[1]}×{img.shape[0]}, not {GEOM["size"]}: '
              f'the screen geometry may differ – check one value against a cursor reading')
    sc, tdiv = (scales, None) if scales else settings(png)
    g = GEOM
    masks = {c: _mask(img, c)[g['top']:g['bottom']] for c in channels}
    t, v = [], {c: [] for c in channels}
    for x in range(g['left'], g['right']):
        rows = {c: np.where(masks[c][:, x])[0] + g['top'] for c in channels}
        if all(len(r) for r in rows.values()):
            t.append((x - g['cx']) / g['px_h'] * (tdiv or 0))
            for c in channels:
                y = np.median(rows[c])
                v[c].append(sc[c][1] + (g['cy'] - y) / g['px_v'] * sc[c][0])
    return np.array(t), {c: np.array(a) for c, a in v.items()}


def thresholds(vin, vout):
    """Input voltage at each output transition: (Vp list – output fell, Vn list – output rose)."""
    high = vout > (vout.max() + vout.min()) / 2
    edges = np.where(np.diff(high.astype(int)) != 0)[0]
    vp = [float(vin[i]) for i in edges if high[i] and not high[i + 1]]
    vn = [float(vin[i]) for i in edges if not high[i] and high[i + 1]]
    return vp, vn


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    opt = lambda k, d: int(a[a.index(k) + 1]) if k in a else d
    cin, cout = opt('--in', 1), opt('--out', 2)
    t, v = traces(a[0], (cin, cout))
    sc, _ = settings(a[0])
    print(f'{os.path.basename(a[0])}: {len(t)} columns; CH{cin} {v[cin].min():.2f}…{v[cin].max():.2f} V, '
          f'CH{cout} {v[cout].min():.2f}…{v[cout].max():.2f} V  (±{sc[cin][0] / 60:.2f} V per pixel on CH{cin})')
    vp, vn = thresholds(v[cin], v[cout])
    for name, xs in (('Vp (output falls)', vp), ('Vn (output rises)', vn)):
        if xs:
            print(f'  {name}: {np.mean(xs):.2f} V  (n = {len(xs)}, spread {np.ptp(xs):.2f} V)')
    if '--csv' in a:
        out = a[a.index('--csv') + 1]
        np.savetxt(out, np.column_stack([t, v[cin], v[cout]]), delimiter=',', fmt='%.6g',
                   header=f't_s,ch{cin}_V,ch{cout}_V', comments='')
        print(f'  -> {out}')
