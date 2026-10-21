# -*- coding: utf-8 -*-
"""
selftest.py — check that this machine can run the lab-report-writer skill.

    python selftest.py

Checks Python + PyMuPDF, finds LibreOffice, builds a small Hebrew test report (RTL text,
inline and display equations, a table, numbers with units), runs the document checker on it,
renders it to PDF and verifies that "0.470 ms" and "2.2–3.6" print in the right order.
Everything happens in a temporary folder; nothing is written next to the skill.
Exit code 0 = ready.
"""
import os, sys, tempfile, shutil, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OK, BAD = '[ OK ]', '[FAIL]'


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    fails = 0
    from labenv import check_python, find_soffice
    ok, msg = check_python()
    print(OK if ok else BAD, msg)
    if not ok:
        return 1
    try:
        soffice = find_soffice()
        print(OK, 'LibreOffice:', soffice)
    except RuntimeError as e:
        print(BAD, e)
        return 1

    import pymupdf
    from build_docx import DocxBuilder
    from mathtex import tex
    from check_docx import check
    from visual_order import lines

    tmp = tempfile.mkdtemp(prefix='lab_selftest_')
    try:
        b = DocxBuilder()
        b.title('בדיקת התקנה')
        b.para(['זמן המחזור הוא 0.470 ms והספים בתחום 2.2–3.6 V, כאשר ', ('math', tex(r'V_n<V_{in}<V_p')),
                ' ו־', ('math', tex(r'R=10\,\text{k}\Omega')), '.'])
        b.equation(tex(r'f=\frac{1}{2RC\ln\left(\frac{V_p}{V_n}\right)}'))
        b.table([['5', '2.9', '1.9'], ['10', '5.9', '3.9']], header=['VDD [V]', 'Vp [V]', 'Vn [V]'])
        path = os.path.join(tmp, 'selftest_הכנה.docx')        # "הכנה" -> checked as a study doc
        b.save(path)
        print(OK, 'Word document built (Hebrew RTL, OMML equations, table)')

        rep, nerr = check(path)
        print(OK if nerr == 0 else BAD, f'document checker ran: {nerr} errors')
        fails += nerr > 0

        ascii_copy = os.path.join(tmp, 'selftest.docx')
        shutil.copyfile(path, ascii_copy)
        subprocess.run([soffice, '--headless', '--convert-to', 'pdf', '--outdir', tmp, ascii_copy],
                       capture_output=True, timeout=180)
        pdf = os.path.join(tmp, 'selftest.pdf')
        if not os.path.exists(pdf):
            print(BAD, 'LibreOffice did not produce a PDF (is another LibreOffice window open?)')
            return 1
        print(OK, f'rendered to PDF ({len(pymupdf.open(pdf))} page)')

        shown = ' '.join(lines(pdf, 0))
        for want in ('0.470 ms', '2.2–3.6 V'):
            good = want in shown
            print(OK if good else BAD, f'bidi: "{want}" prints in reading order')
            fails += not good
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print('\nMATLAB is optional but recommended: install the "MATLAB MCP Core Server" add-on and run')
    print('shareMATLABSession in MATLAB before asking Claude to simulate (see the guide).')
    print('\nREADY' if fails == 0 else f'\n{fails} problem(s) - see [FAIL] lines above')
    return 0 if fails == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
