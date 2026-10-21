# -*- coding: utf-8 -*-
"""
mathtex.py — a small LaTeX-subset → OMML converter, so equations are written the way an
engineer thinks ( tex(r"f=\\frac{1}{2RC\\ln\\left(\\frac{V_p}{V_n}\\right)}") ) instead of
hand-nesting OMML helpers. Output is the *inner* OMML (no <m:oMath> wrapper), so it plugs
into DocxBuilder.equation(...) and inline ('math', ...) tokens unchanged.

Supported:  \\frac{a}{b}  \\sqrt{x}  \\sqrt[n]{x}  x_{sub}  x^{sup}  x_a^b  {group}  \\overline{x}
            \\left( … \\right)  with ( ) [ ] | \\{ \\}
            \\text{…}  \\mathrm{…}  function names \\ln \\log \\exp \\sin \\cos \\tan \\max \\min
            Greek \\alpha … \\Omega,  \\cdot \\times \\approx \\le \\ge \\ne \\pm \\to \\rightarrow
            \\Rightarrow \\infty \\circ \\%  and spacing \\, \\; \\quad \\
Writing every relation (V_p>V_n, V_n<V_{in}<V_p, V_p-V_n, 0\\to1) through tex() also guarantees
the bidi rule: inline math keeps its own left-to-right direction inside Hebrew text.
"""
from xml.sax.saxutils import escape

SYMBOLS = {
    'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'delta': 'δ', 'epsilon': 'ε', 'varepsilon': 'ε',
    'theta': 'θ', 'lambda': 'λ', 'mu': 'µ', 'pi': 'π', 'rho': 'ρ', 'sigma': 'σ', 'tau': 'τ',
    'phi': 'φ', 'varphi': 'φ', 'omega': 'ω', 'Gamma': 'Γ', 'Delta': 'Δ', 'Theta': 'Θ',
    'Lambda': 'Λ', 'Pi': 'Π', 'Sigma': 'Σ', 'Phi': 'Φ', 'Omega': 'Ω',
    'cdot': '⋅', 'times': '×', 'approx': '≈', 'le': '≤', 'leq': '≤', 'ge': '≥', 'geq': '≥',
    'ne': '≠', 'neq': '≠', 'pm': '±', 'to': '→', 'rightarrow': '→', 'leftarrow': '←',
    'Rightarrow': '⇒', 'infty': '∞', 'circ': '°', 'degree': '°', 'propto': '∝', '%': '%',
    'ldots': '…', 'parallel': '∥', 'sim': '~',
    'uparrow': '↑', 'downarrow': '↓', 'leftrightarrow': '↔', 'Leftrightarrow': '⇔', 'cdots': '⋯',
    'oplus': '⊕', 'wedge': '∧', 'vee': '∨', 'neg': '¬',
}
FUNCS = {'ln', 'log', 'exp', 'sin', 'cos', 'tan', 'cot', 'arcsin', 'arccos', 'arctan',
         'sinh', 'cosh', 'tanh', 'max', 'min', 'lim', 'det', 'sup', 'inf', 'arg', 'deg'}
SPACES = {',': ' ', ';': ' ', 'quad': ' ', 'qquad': '  ', ' ': ' '}
DELIMS = {'(': '(', ')': ')', '[': '[', ']': ']', '|': '|', '\\{': '{', '\\}': '}', '.': ''}


def _run(text, plain=False, normal=False):
    # plain  = upright math (m:sty p): function names, spacing.
    # normal = "normal text" (m:nor): units and \text{}. LibreOffice ignores m:sty for Greek and
    #          draws Ω/µ as slanted, overlapping glyphs ("0.1µF"); only m:nor renders them upright
    #          and clean (verified in paragraphs and in table cells). Word supports m:nor natively.
    sty = '<m:rPr><m:nor/></m:rPr>' if normal else '<m:rPr><m:sty m:val="p"/></m:rPr>' if plain else ''
    return f'<m:r>{sty}<m:t xml:space="preserve">{escape(text)}</m:t></m:r>'


class _P:
    def __init__(self, s):
        self.s, self.i = s, 0

    def peek(self):
        return self.s[self.i] if self.i < len(self.s) else ''

    def cmd(self):                                   # after a backslash
        j = self.i
        if j < len(self.s) and not self.s[j].isalpha():
            self.i = j + 1
            return self.s[j]
        while j < len(self.s) and self.s[j].isalpha():
            j += 1
        name, self.i = self.s[self.i:j], j
        return name

    def group(self):                                 # {…} or a single atom
        while self.peek() == ' ':
            self.i += 1
        if self.peek() == '{':
            self.i += 1
            inner = self.seq(stop='}')
            self.i += 1
            return inner
        atoms = self.atom()
        return ''.join(atoms)

    def raw_group(self):                             # literal text inside {…}
        if self.peek() != '{':
            return ''
        depth, j = 1, self.i + 1
        while j < len(self.s) and depth:
            depth += {'{': 1, '}': -1}.get(self.s[j], 0)
            j += 1
        txt, self.i = self.s[self.i + 1:j - 1], j
        return txt

    def delim_char(self):
        while self.peek() == ' ':
            self.i += 1
        if self.peek() == '\\':
            self.i += 1
            c = self.cmd()
            return DELIMS.get('\\' + c, c)
        c = self.peek()
        self.i += 1
        return DELIMS.get(c, c)

    def atom(self):
        """Return a list of OMML atoms (usually one) for the next token."""
        c = self.peek()
        if c == '\\':
            self.i += 1
            name = self.cmd()
            if name == 'frac':
                num, den = self.group(), self.group()
                return [f'<m:f><m:num>{num}</m:num><m:den>{den}</m:den></m:f>']
            if name == 'sqrt':
                deg = ''
                if self.peek() == '[':
                    j = self.s.index(']', self.i)
                    deg = _P(self.s[self.i + 1:j]).seq()
                    self.i = j + 1
                body = self.group()
                if deg:
                    return [f'<m:rad><m:radPr/><m:deg>{deg}</m:deg><m:e>{body}</m:e></m:rad>']
                return [f'<m:rad><m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/>'
                        f'<m:e>{body}</m:e></m:rad>']
            if name == 'left':
                beg = self.delim_char()
                inner = self.seq(stop='\\right')
                self.i += len('\\right')
                end = self.delim_char()
                return [f'<m:d><m:dPr><m:begChr m:val="{escape(beg)}"/><m:endChr m:val="{escape(end)}"/>'
                        f'</m:dPr><m:e>{inner}</m:e></m:d>']
            if name in ('overline', 'bar'):       # logic NOT / mean value: bar over the argument
                body = self.group()
                return [f'<m:bar><m:barPr><m:pos m:val="top"/></m:barPr><m:e>{body}</m:e></m:bar>']
            if name in ('text', 'mathrm', 'textrm'):
                return [_run(self.raw_group(), normal=True)]
            if name in FUNCS:
                return [_run(name, plain=True)]
            if name in SPACES:
                return [_run(SPACES[name], plain=True)]
            if name in SYMBOLS:
                # capital Greek (Ω, Δ…) and µ are upright: they are units/prefixes (kΩ, µF) or
                # operators (ΔV), never italic variables. Italic Ω also renders as a garbled
                # glyph in LibreOffice tables.
                return [_run(SYMBOLS[name], normal=name[0].isupper() or name == 'mu')]
            return [_run('\\' + name)]               # unknown command: show it, don't crash
        if c == '{':
            return [self.group()]
        if c == ' ':
            self.i += 1
            return []
        self.i += 1
        if c == '-':
            c = '−'                                  # true minus sign
        return [_run(c)]

    def seq(self, stop=None):
        atoms = []
        while self.i < len(self.s):
            if stop and self.s.startswith(stop, self.i):
                break
            c = self.peek()
            if c in '_^':
                base = atoms.pop() if atoms else _run('')
                self.i += 1
                first = self.group()
                sub = sup = None
                if c == '_':
                    sub = first
                else:
                    sup = first
                nxt = self.peek()                    # NB: '' in '_^' is True — guard end-of-input
                if nxt and nxt in '_^' and nxt != c:
                    self.i += 1
                    second = self.group()
                    sub, sup = (sub, second) if c == '_' else (second, sup)
                if sub is not None and sup is not None:
                    atoms.append(f'<m:sSubSup><m:e>{base}</m:e><m:sub>{sub}</m:sub>'
                                 f'<m:sup>{sup}</m:sup></m:sSubSup>')
                elif sub is not None:
                    atoms.append(f'<m:sSub><m:e>{base}</m:e><m:sub>{sub}</m:sub></m:sSub>')
                else:
                    atoms.append(f'<m:sSup><m:e>{base}</m:e><m:sup>{sup}</m:sup></m:sSup>')
                continue
            atoms.extend(self.atom())
        # an operator that ENDS a group (V_{T+}, V_{T-}) has no right operand; LibreOffice's math
        # importer then shows a placeholder (¿) and can even swallow what follows into the
        # subscript. m:sty / m:nor / m:lit do NOT help (verified). An invisible operand does:
        # append U+2060 WORD JOINER (zero width, no line break; invisible in Word too).
        for op in ('+', '−', '=', '<', '>'):
            if atoms and atoms[-1] == _run(op):
                atoms.append(_run('⁠'))
        return ''.join(atoms)


def tex(s):
    """LaTeX-subset string -> inner OMML."""
    return _P(s).seq()


if __name__ == '__main__':
    for t in [r"f=\frac{1}{2RC\ln\left(\frac{V_p}{V_n}\right)}", r"V_n<V_{in}<V_p",
              r"T=RC\left(\ln\frac{V_{cc}-V_n}{V_{cc}-V_p}+\ln\frac{V_p}{V_n}\right)\approx0.47\,\text{ms}",
              r"V_C(t)=V_{th}\left(1-e^{-t/\tau}\right)", r"R_{th}=R_x\parallel100k"]:
        print(t, '->', len(tex(t)), 'chars')
