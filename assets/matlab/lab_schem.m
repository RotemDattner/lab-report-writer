function S = lab_schem(titleStr, sz)
%LAB_SCHEM Minimal schematic drawing kit for lab reports (gates, ICs, R, C, switch, rails).
%   S = lab_schem('title', [w h]) opens an invisible figure and returns function handles:
%     P = S.ic(name, x, y, w, h, L, R, T, B)  IC box at (x,y) lower-left; L/R/T/B are cell arrays
%                                            of 'label:pin' strings, spread evenly on that side.
%                                            Returns a struct of pin-tip coordinates; the field is
%                                            the label without TeX: V_{SS}->P.VSS, C_X/R_X->P.CX_RX,
%                                            \overline{Q}->P.nQ.
%     G = S.gate(type, x, y, nIn)            'and','nand','or','nor','not','buf','xor'; (x,y) =
%                                            centre of the input side. G.in(k,:), G.out.
%     S.wire([x y; x y; ...])                orthogonal polyline;   S.dot([x y]) junction
%     S.res(p1, p2, label)  S.cap(p1, p2, label)  S.pot(p1, p2, label)   along a straight segment
%     S.gnd(p)   S.vdd(p, label)   S.txt(x, y, str, halign)   S.sw(p_common, p_a, p_b, label)  (SPDT)
%     S.spst(p1, p2, label)                   single-pole switch, drawn open
%     S.save(file)                            exports a 200-dpi PNG and closes the figure
%   Units are arbitrary (about 1 unit = one pin pitch). Pin labels use TeX: '\overline{Q}'.
if nargin < 2, sz = [900 520]; end
fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100 100 sz]);
ax = axes(fig, 'Position', [0.02 0.02 0.96 0.90]); hold(ax, 'on'); axis(ax, 'equal'); axis(ax, 'off');
if nargin >= 1 && ~isempty(titleStr), title(ax, titleStr, 'FontSize', 12); end
lw = 1.3; fs = 9;
S.ic = @ic; S.gate = @gate; S.wire = @wire; S.dot = @dot; S.res = @res; S.cap = @cap;
S.pot = @pot; S.gnd = @gnd; S.vdd = @vdd; S.txt = @txt; S.sw = @sw; S.spst = @spst; S.save = @save_; S.ax = ax;

    function P = ic(name, x, y, w, h, L, R, T, B)
        if nargin < 9, B = {}; end
        if nargin < 8, T = {}; end
        rectangle(ax, 'Position', [x y w h], 'LineWidth', lw);
        text(ax, x + w/2, y + h/2, name, 'HorizontalAlignment', 'center', 'FontWeight', 'bold', 'FontSize', fs + 1);
        P = struct();
        P = side(P, L, x, y, h, 'L'); P = side(P, R, x + w, y, h, 'R');
        P = sideTB(P, T, x, y + h, w, 'T'); P = sideTB(P, B, x, y, w, 'B');
    end
    function P = side(P, pins, x0, y0, h, s)
        n = numel(pins);
        for k = 1:n
            [lab, num] = split_(pins{k});
            yy = y0 + h - k * h / (n + 1);
            d = 0.6 * (2 * (s == 'R') - 1);
            line(ax, [x0 x0 + d], [yy yy], 'Color', 'k', 'LineWidth', lw);
            tx(ax, x0 - sign(d) * 0.15, yy, lab, 'HorizontalAlignment', ifelse(s == 'L', 'left', 'right'), 'FontSize', fs);
            if ~isempty(num), text(ax, x0 + d/2, yy + 0.22, num, 'HorizontalAlignment', 'center', 'FontSize', fs - 2); end
            P.(key(lab)) = [x0 + d yy];
        end
    end
    function P = sideTB(P, pins, x0, y0, w, s)
        n = numel(pins);
        for k = 1:n
            [lab, num] = split_(pins{k});
            xx = x0 + k * w / (n + 1);
            d = 0.6 * (2 * (s == 'T') - 1);
            line(ax, [xx xx], [y0 y0 + d], 'Color', 'k', 'LineWidth', lw);
            tx(ax, xx, y0 - sign(d) * 0.3, lab, 'HorizontalAlignment', 'center', 'FontSize', fs);
            if ~isempty(num), text(ax, xx + 0.18, y0 + d/2, num, 'FontSize', fs - 2); end
            P.(key(lab)) = [xx y0 + d];
        end
    end
    function G = gate(type, x, y, nIn)
        if nargin < 4, nIn = 2; end
        h = max(1.2, 0.6 * nIn); w = 1.4; th = linspace(-pi/2, pi/2, 40);
        bub = any(strcmp(type, {'nand', 'nor', 'not', 'xnor'}));
        switch type
            case {'and', 'nand'}
                % closed outline: bottom edge, arc, top edge, and back down the input side
                xs = [x x + w/2, x + w/2 + (h/2) * cos(th), x + w/2, x, x]; ys = [y - h/2, y - h/2, y + (h/2) * sin(th), y + h/2, y + h/2, y - h/2];
                plot(ax, xs, ys, 'k', 'LineWidth', lw); xo = x + w/2 + h/2;
            case {'or', 'nor', 'xor'}
                t = linspace(-1, 1, 40);
                back = x + 0.3 * (1 - t.^2);                       % concave input side
                a = linspace(0, pi/2, 30);
                plot(ax, back, y + t * h/2, 'k', 'LineWidth', lw);
                plot(ax, x + (w + 0.4) * sin(a), y + h/2 * cos(a), 'k', 'LineWidth', lw);
                plot(ax, x + (w + 0.4) * sin(a), y - h/2 * cos(a), 'k', 'LineWidth', lw);
                if strcmp(type, 'xor'), plot(ax, back - 0.2, y + t * h/2, 'k', 'LineWidth', lw); end
                xo = x + w + 0.4;
            otherwise   % not / buf
                plot(ax, [x x x + w x], [y - h/2 y + h/2 y y - h/2], 'k', 'LineWidth', lw); xo = x + w;
        end
        if bub
            r = 0.13; tt = linspace(0, 2*pi, 30);
            plot(ax, xo + r + r * cos(tt), y + r * sin(tt), 'k', 'LineWidth', lw); xo = xo + 2 * r;
        end
        line(ax, [xo xo + 0.4], [y y], 'Color', 'k', 'LineWidth', lw);
        G.out = [xo + 0.4 y];
        if any(strcmp(type, {'not', 'buf'})), nIn = 1; end
        G.in = zeros(nIn, 2);
        for k = 1:nIn
            yy = y + h/2 - k * h / (nIn + 1);
            xin = x + (any(strcmp(type, {'or', 'nor', 'xor'})) * 0.3 * (1 - ((yy - y) / (h/2))^2));
            line(ax, [x - 0.4 xin], [yy yy], 'Color', 'k', 'LineWidth', lw);
            G.in(k, :) = [x - 0.4 yy];
        end
    end
    function wire(p), plot(ax, p(:, 1), p(:, 2), 'k', 'LineWidth', lw); end
    function dot(p), plot(ax, p(1), p(2), 'k.', 'MarkerSize', 14); end
    function txt(x, y, s, ha)
        if nargin < 4, ha = 'center'; end
        tx(ax, x, y, s, 'HorizontalAlignment', ha, 'FontSize', fs);
        plot(ax, x, y + 0.4, '.', 'Color', 'none');      % so axis tight keeps the text inside
    end
    function res(p1, p2, lab), comp(p1, p2, lab, 'r'); end
    function cap(p1, p2, lab), comp(p1, p2, lab, 'c'); end
    function pot(p1, p2, lab), comp(p1, p2, lab, 'p'); end
    function comp(p1, p2, lab, kind)
        v = p2 - p1; L = norm(v); u = v / L; n = [-u(2) u(1)];
        a = p1 + u * (L/2 - 0.5); b = p1 + u * (L/2 + 0.5);
        wire([p1; a]); wire([b; p2]);
        switch kind
            case {'r', 'p'}
                k = 0:6; pts = a + (k' / 6) * (b - a) + (mod(k', 2) * 2 - 1) .* (k' > 0 & k' < 6) * 0.18 .* n;
                plot(ax, pts(:, 1), pts(:, 2), 'k', 'LineWidth', lw);
                if kind == 'p'
                    m = (a + b) / 2; q = m + 0.55 * n;
                    quiver(ax, q(1), q(2), m(1) - q(1), m(2) - q(2), 0, 'k', 'LineWidth', lw, 'MaxHeadSize', 1.5);
                end
            case 'c'
                m1 = p1 + u * (L/2 - 0.08); m2 = p1 + u * (L/2 + 0.08);
                wire([a; m1]); wire([m2; b]);
                wire([m1 - 0.3 * n; m1 + 0.3 * n]); wire([m2 - 0.3 * n; m2 + 0.3 * n]);
        end
        if abs(u(2)) > 0.9                                  % vertical part: label beside it
            m = (a + b) / 2 + [0.4 0];
            tx(ax, m(1), m(2), lab, 'HorizontalAlignment', 'left', 'FontSize', fs);
        else
            m = (a + b) / 2 - 0.55 * sign(n(2) + (n(2) == 0)) * n;
            tx(ax, m(1), m(2), lab, 'HorizontalAlignment', 'center', 'FontSize', fs);
        end
    end
    function gnd(p)
        wire([p; p - [0 0.3]]);
        for k = 0:2, wire([p(1) - 0.3 + 0.1 * k, p(2) - 0.3 - 0.12 * k; p(1) + 0.3 - 0.1 * k, p(2) - 0.3 - 0.12 * k]); end
    end
    function vdd(p, lab)
        if nargin < 2, lab = 'V_{DD}'; end
        wire([p; p + [0 0.3]]); wire([p + [-0.3 0.3]; p + [0.3 0.3]]);
        text(ax, p(1), p(2) + 0.6, lab, 'HorizontalAlignment', 'center', 'FontSize', fs);
    end
    function spst(p1, p2, lab)
        % single-pole switch drawn open: contacts at p1 and p2, lever from p1 tilted toward p2
        r = 0.08; tt = linspace(0, 2*pi, 20);
        for q = {p1, p2}, plot(ax, q{1}(1) + r * cos(tt), q{1}(2) + r * sin(tt), 'k', 'LineWidth', lw); end
        v = p2 - p1; n = [-v(2) v(1)] / norm(v);
        wire([p1; p1 + 0.85 * v + 0.35 * norm(v) * n]);
        if nargin >= 3, m = (p1 + p2) / 2 + 0.5 * n; tx(ax, m(1), m(2), lab, 'HorizontalAlignment', 'center', 'FontSize', fs); end
    end
    function sw(pc, pa, pb, lab)
        r = 0.08; tt = linspace(0, 2*pi, 20);
        for q = {pc, pa, pb}, plot(ax, q{1}(1) + r * cos(tt), q{1}(2) + r * sin(tt), 'k', 'LineWidth', lw); end
        wire([pc; pa + [0 -0.12]]);
        if nargin >= 4, text(ax, pc(1), pc(2) + 0.45, lab, 'HorizontalAlignment', 'center', 'FontSize', fs); end
    end
    function save_(file)
        axis(ax, 'tight'); xl = xlim(ax); yl = ylim(ax);
        xlim(ax, xl + [-0.5 0.5]); ylim(ax, yl + [-0.5 0.5]);
        exportgraphics(fig, file, 'Resolution', 200, 'BackgroundColor', 'white');
        close(fig); fprintf('saved: %s\n', file);
    end
end

function [lab, num] = split_(s)
i = strfind(s, ':');
if isempty(i), lab = s; num = ''; else, lab = s(1:i(end) - 1); num = s(i(end) + 1:end); end
end

function k = key(lab)
% pin key: TeX markup dropped -> 'V_{SS}'->VSS, 'C_X/R_X'->CX_RX, '\overline{Q}'->nQ
k = regexprep(lab, '\\overline\{([^}]*)\}', 'n$1'); k = regexprep(k, '[{}_\\^]', '');
k = regexprep(k, '[^A-Za-z0-9]', '_');
if isempty(k) || ~isletter(k(1)), k = ['p_' k]; end
end

function o = ifelse(c, a, b)
if c, o = a; else, o = b; end
end

function tx(ax, x, y, s, varargin)
% the default TeX interpreter has no \overline: such labels go through LaTeX (math mode)
if contains(s, '\overline')
    s = ['$' regexprep(s, '([A-Za-z]+)_\{?([A-Za-z0-9]+)\}?', '$1_{$2}') '$'];
    text(ax, x, y, s, 'Interpreter', 'latex', varargin{:}, 'FontSize', 11);
else
    text(ax, x, y, s, varargin{:});
end
end
