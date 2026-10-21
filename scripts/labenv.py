# -*- coding: utf-8 -*-
"""
labenv.py — locate external tools so the skill runs on any machine (Windows / macOS / Linux).

    from labenv import SKILL_DIR, find_soffice
    soffice = find_soffice()          # raises with an install hint if LibreOffice is missing

Override with environment variables when a tool is in an unusual place:
    LAB_SOFFICE=/path/to/soffice
"""
import os, sys, shutil, glob

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SOFFICE_CANDIDATES = [
    r'C:\Program Files\LibreOffice\program\soffice.exe',
    r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
    '/Applications/LibreOffice.app/Contents/MacOS/soffice',
    '/usr/bin/soffice', '/usr/local/bin/soffice', '/usr/bin/libreoffice', '/snap/bin/libreoffice',
    '/opt/homebrew/bin/soffice',
]


def find_soffice():
    """Path of the LibreOffice command-line binary (soffice)."""
    env = os.environ.get('LAB_SOFFICE')
    if env and os.path.exists(env):
        return env
    for name in ('soffice', 'libreoffice'):
        p = shutil.which(name)
        if p:
            return p
    for p in _SOFFICE_CANDIDATES + glob.glob(r'C:\Program Files\LibreOffice*\program\soffice.exe'):
        if os.path.exists(p):
            return p
    raise RuntimeError('LibreOffice not found. Install it from https://www.libreoffice.org '
                       '(free), or set LAB_SOFFICE to the full path of soffice.')


def check_python():
    """(ok, message) for the Python side: version and PyMuPDF."""
    if sys.version_info < (3, 9):
        return False, f'Python {sys.version.split()[0]} is too old (need 3.9+)'
    try:
        import pymupdf  # noqa: F401
    except ImportError:
        return False, 'PyMuPDF missing: run  python -m pip install pymupdf'
    return True, f'Python {sys.version.split()[0]} + PyMuPDF OK'
