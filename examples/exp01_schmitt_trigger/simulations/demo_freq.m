%% Demo (self-study): what sets the oscillator frequency (circuit 1.3, prep 7-8)
% (a) f vs R for C = 0.1 uF (VDD = 5 V, typ thresholds) - f is proportional to 1/(RC)
% (b) f vs VDD: booklet formula vs. full formula, and the spread allowed by the datasheet
%     min/max thresholds - what range a real chip can show in the lab.
clear; clc;
addpath(fullfile(char(java.lang.System.getProperty('user.home')),'.claude','skills','lab-report-writer','assets','matlab'));
here = fileparts(mfilename('fullpath'));

C = 0.1e-6; Rnom = 10e3;
VDDs = [5 10 15]; VPs = [2.9 5.9 8.8]; VNs = [1.9 3.9 5.8];
VPmin = [2.2 4.6 6.8]; VPmax = [3.6 7.1 10.8]; VNmin = [0.9 2.5 4.0]; VNmax = [2.8 5.2 7.4];
ffull = @(VDD,Vp,Vn,RC) 1./(RC.*(log((VDD-Vn)./(VDD-Vp)) + log(Vp./Vn)));
fbook = @(Vp,Vn,RC) 1./(2*RC.*log(Vp./Vn));

fig = figure('Visible','off','Position',[100 100 1000 430]);
tiledlayout(1,2,'TileSpacing','compact');
nexttile;
Rs = logspace(3, 5, 100);
loglog(Rs/1e3, ffull(5,2.9,1.9,Rs*C), 'b-','LineWidth',1.6); hold on;
plot(Rnom/1e3, ffull(5,2.9,1.9,Rnom*C), 'ro','MarkerFaceColor','r');
text(Rnom/1e3*1.15, ffull(5,2.9,1.9,Rnom*C), sprintf('R = 10 k\\Omega: %.0f Hz', ffull(5,2.9,1.9,Rnom*C)));
xlabel('R [k\Omega]  (C = 0.1 \muF)'); ylabel('f [Hz]'); title('(a) f \propto 1/(RC): 10\times R \rightarrow f/10');

nexttile;
VHmin = [0.3 1.2 1.6]; VHmax = [2.0 3.4 5.0];    % hysteresis limits also bound Vp - Vn
lo = zeros(1,3); hi = lo;
for i = 1:3
    [vp, vn] = meshgrid(linspace(VPmin(i), VPmax(i), 120), linspace(VNmin(i), VNmax(i), 120));
    ok = (vp - vn >= VHmin(i)) & (vp - vn <= VHmax(i));
    fs = ffull(VDDs(i), vp(ok), vn(ok), Rnom*C);
    lo(i) = min(fs); hi(i) = max(fs);
end
ft = ffull(VDDs, VPs, VNs, Rnom*C); fb = fbook(VPs, VNs, Rnom*C);
errorbar(VDDs, ft, ft-lo, hi-ft, 'bo-','LineWidth',1.4,'MarkerFaceColor','b'); hold on;
plot(VDDs, fb, 'rs--','LineWidth',1.2,'MarkerFaceColor','r');
set(gca, 'YScale', 'log'); ylim([300 8000]); xlim([3.5 16.5]);
xlabel('V_{DD} [V]'); ylabel('f [Hz] (log scale)');
legend({'full formula (bars: datasheet min/max)','booklet formula'},'Location','north');
title('(b) f vs V_{DD} and chip-to-chip spread');
lab_fig(fig, fullfile(here,'demo_freq.png')); close(fig);
fprintf('typ  f_full = %s Hz\n', mat2str(round(ft)));
fprintf('book f      = %s Hz\n', mat2str(round(fb)));
fprintf('datasheet spread: low = %s, high = %s Hz\n', mat2str(round(lo)), mat2str(round(hi)));
lab_save(struct('VDD',VDDs,'f_full_Hz',ft,'f_book_Hz',fb,'f_low_Hz',lo,'f_high_Hz',hi), ...
    fullfile(here,'demo_freq_results.json'));
