function err = lab_check(name, expected, simulated, unit, tol)
%LAB_CHECK  Print theory vs. simulation for one quantity and return the relative error [%].
%   err = lab_check('T (period)', T_theory, T_sim, 'ms')       % default tolerance 2 %
%   A mismatch above TOL is printed as MISMATCH — it is a finding to explain (model or hand
%   analysis is wrong), never something to hide.

if nargin < 4, unit = ''; end
if nargin < 5, tol = 2; end
err = 100 * abs(simulated - expected) / max(abs(expected), eps);
flag = 'OK';
if err > tol, flag = 'MISMATCH'; end
fprintf('%-30s theory=%11.5g  sim=%11.5g %-4s  err=%6.2f%%  %s\n', ...
        name, expected, simulated, unit, err, flag);
end
