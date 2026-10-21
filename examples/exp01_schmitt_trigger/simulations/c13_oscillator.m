%% Circuit 1.3 (prep 7, 8; procedure part 2) - oscillator with enable (control) input
% Source: booklet figure 1.3 (requirements/figures/fig_03.png): MC14093 gate A,
%   pin 1 = Vcontrol (enable), pin 2 = capacitor node, pin 3 = output,
%   R1 = 10 kOhm from output (3) to pin 2, C1 = 0.1 uF from pin 2 to GND. Vcc = Vcontrol.
% Thresholds: MC14093B datasheet typical @25C (datasheets/MC14093B.pdf p.3).
% Booklet formula: f = 1/(2 R C ln(Vp/Vn)) - exact only if Vp + Vn = VDD (symmetric).
clear; clc;
addpath(fullfile(char(java.lang.System.getProperty('user.home')),'.claude','skills','lab-report-writer','assets','matlab'));
here = fileparts(mfilename('fullpath'));

R = 10e3; C = 0.1e-6; tau = R*C;
VDDs = [5 10 15]; VPs = [2.9 5.9 8.8]; VNs = [1.9 3.9 5.8];
VPmin = [2.2 4.6 6.8]; VPmax = [3.6 7.1 10.8]; VNmin = [0.9 2.5 4.0]; VNmax = [2.8 5.2 7.4];
VHmin = [0.3 1.2 1.6]; VHmax = [2.0 3.4 5.0];   % hysteresis limits also bound Vp - Vn

fprintf('--- Q8: expected frequency (typ thresholds) ---\n');
res = zeros(3,7); spread = zeros(3,2); duty = zeros(1,3); t1s = zeros(1,3);
for i = 1:3
    VDD = VDDs(i); Vp = VPs(i); Vn = VNs(i);
    f_book = 1/(2*tau*log(Vp/Vn));
    th = tau*log((VDD-Vn)/(VDD-Vp)); tl = tau*log(Vp/Vn);
    f_full = 1/(th+tl);
    [t, vc] = osc(VDD, Vp, Vn, tau, 0, 12e-3);           % control high from t = 0
    up = find(vc(1:end-1) < Vp & vc(2:end) >= Vp);
    f_sim = 1/mean(diff(t(up(2:end))));
    t1 = tau*log(VDD/(VDD-Vp));                           % first '1' after power-up
    lab_check(sprintf('f full-formula @%2dV', VDD), f_full, f_sim, 'Hz');
    % the booklet formula is NOT expected to match (Vp + Vn ~= VDD): report the gap, don't test it
    fprintf('   expected deviation (asymmetry) @%2dV: booklet %.0f Hz vs sim %.0f Hz = %.2f %%\n', ...
            VDD, f_book, f_sim, 100*(f_book - f_sim)/f_sim);
    % datasheet spread: scan every (Vp, Vn) allowed by the VT+, VT- AND VH limits
    [vp, vn] = meshgrid(linspace(VPmin(i), VPmax(i), 120), linspace(VNmin(i), VNmax(i), 120));
    ok = (vp - vn >= VHmin(i)) & (vp - vn <= VHmax(i));
    fs = 1./(tau*(log((VDD-vn(ok))./(VDD-vp(ok))) + log(vp(ok)./vn(ok))));
    res(i,:) = [VDD, Vp, Vn, f_book, f_full, f_sim, (Vp+Vn)/VDD];
    spread(i,:) = [min(fs) max(fs)]; duty(i) = 100*th/(th+tl); t1s(i) = t1*1e3;
    fprintf('   datasheet spread @%2dV: f = %.0f .. %.0f Hz;  duty = %.1f %%;  t1 = %.3f ms\n', ...
            VDD, min(fs), max(fs), 100*th/(th+tl), t1*1e3);
end
disp('   VDD   Vp   Vn   f_booklet  f_full  f_sim  (Vp+Vn)/VDD'); disp(round(res,3));
lab_save(struct('R_k',R/1e3,'C_uF',C*1e6,'tau_ms',tau*1e3,'VDD',res(:,1)','Vp',res(:,2)','Vn',res(:,3)', ...
    'f_book_Hz',res(:,4)','f_full_Hz',res(:,5)','f_sim_Hz',res(:,6)','sym_ratio',res(:,7)', ...
    'f_min_Hz',spread(:,1)','f_max_Hz',spread(:,2)','duty_pct',duty,'t1_ms',t1s), ...
    fullfile(here,'c13_results.json'));

% ---- figure 1: Vc and Vout at 5 V and 10 V (procedure 2b, 2d)
fig = figure('Visible','off','Position',[100 100 950 640]);
tiledlayout(2,1,'TileSpacing','compact');
for i = 1:2
    VDD = VDDs(i); Vp = VPs(i); Vn = VNs(i);
    [t, vc, vo] = osc(VDD, Vp, Vn, tau, 0, 4e-3);
    nexttile; plot(t*1e3, vc, 'b-','LineWidth',1.6); hold on; plot(t*1e3, vo, 'r-','LineWidth',1.1);
    yline(Vp,'--k',sprintf('V_p=%.1f V',Vp),'LabelHorizontalAlignment','left');
    yline(Vn,'--k',sprintf('V_n=%.1f V',Vn),'LabelHorizontalAlignment','left','LabelVerticalAlignment','bottom');
    up = find(vc(1:end-1) < Vp & vc(2:end) >= Vp); f_sim = 1/mean(diff(t(up(2:end))));
    title(sprintf('V_{CC} = V_{control} = %d V:  f = %.0f Hz', VDD, f_sim));
    xlabel('time [ms]'); ylabel('Voltage [V]'); ylim([-0.4 VDD*1.12]);
    legend({'V_C (pin 2)','V_{out} (pin 3)'},'Location','eastoutside');
end
lab_fig(fig, fullfile(here,'c13_osc.png')); close(fig);

% ---- figure 2: the enable input (prep 7b truth table) - control low, then high at t = 2 ms
VDD = 5; Vp = 2.9; Vn = 1.9;
[t, vc, vo, vctl] = osc(VDD, Vp, Vn, tau, 2e-3, 6e-3);
fig = figure('Visible','off','Position',[100 100 950 460]);
plot(t*1e3, vctl+0.08, 'Color',[0 0.55 0],'LineWidth',1.4); hold on;
plot(t*1e3, vc, 'b-','LineWidth',1.6); plot(t*1e3, vo, 'r-','LineWidth',1.1);
yline(Vp,'--k'); yline(Vn,'--k');
xline(2,':k','control 0 \rightarrow 1','LabelOrientation','horizontal', ...
      'LabelVerticalAlignment','top','LabelHorizontalAlignment','right');   % above the traces
xlabel('time [ms]'); ylabel('Voltage [V]'); ylim([-0.4 5.8]);
legend({'V_{control} (pin 1, drawn +0.08 V)','V_C (pin 2)','V_{out} (pin 3)'},'Location','eastoutside');
title('Enable input: control = 0 \Rightarrow output stuck at 1; control = 1 \Rightarrow oscillation');
lab_fig(fig, fullfile(here,'c13_enable.png')); close(fig);

function [t, vc, vo, vctl] = osc(VDD, Vp, Vn, tau, t_enable, tend)
%OSC NAND(control, Vc) with hysteresis on the Vc input; R-C feedback from output to Vc.
dt = tau/4000; t = 0:dt:tend; n = numel(t);
vc = zeros(1,n); vo = zeros(1,n); vctl = VDD*(t >= t_enable);
cap_high = false;                       % Schmitt state of the capacitor input (Vc > Vp seen)
for k = 1:n
    if k > 1
        vc(k) = vo(k-1) + (vc(k-1) - vo(k-1))*exp(-dt/tau);   % charge toward the output
    end
    if ~cap_high && vc(k) >= Vp, cap_high = true;  end
    if  cap_high && vc(k) <= Vn, cap_high = false; end
    vo(k) = VDD*~(vctl(k) > VDD/2 && cap_high);              % NAND
end
end
