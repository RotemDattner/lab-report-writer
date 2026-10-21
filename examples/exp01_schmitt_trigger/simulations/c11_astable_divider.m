%% Circuit 1.1 (prep question 9) - MC14093 astable with a voltage divider
% Source: booklet figure 1.1 (requirements/figures/fig_01.png):
%   NAND inputs tied together = Schmitt inverter. Rx from the OUTPUT to node X,
%   100k from node X to GND, C = 10 nF from node X to GND, node X -> gate inputs.
%   Vdd = 6 V, given thresholds Vp = 3 V, Vn = 2 V.
% Seen from the capacitor, Rx and 100k form a Thevenin source:
%   output high (6 V): V_th = 6*100k/(Rx+100k),  R_th = Rx || 100k
%   output low  (0 V): V_th = 0,                 R_th = Rx || 100k
% The capacitor charges toward V_th (NOT toward 6 V) - this is the whole point of 9b/9c.
clear; clc;
addpath(fullfile(char(java.lang.System.getProperty('user.home')),'.claude','skills','lab-report-writer','assets','matlab'));
here = fileparts(mfilename('fullpath'));

Vdd = 6; Vp = 3; Vn = 2; C = 10e-9; R2 = 100e3; Rx = 60e3;
Rth = Rx*R2/(Rx+R2);  Vth = Vdd*R2/(Rx+R2);  tau = Rth*C;

% ---- theory
t1 = tau*log(Vth/(Vth-Vp));            % first charge 0 -> Vp
th = tau*log((Vth-Vn)/(Vth-Vp));       % steady-state charge Vn -> Vp (output high)
tl = tau*log(Vp/Vn);                   % discharge Vp -> Vn (output low)
T  = th + tl;  f = 1/T;  duty = th/T;
Rx_max = R2*(Vdd/Vp - 1);              % V_th must exceed Vp
fprintf('R_th = %.1f kOhm, V_th = %.3f V, tau = %.4f ms\n', Rth/1e3, Vth, tau*1e3);
fprintf('Rx_max = %.1f kOhm (strictly less than)\n', Rx_max/1e3);

% ---- simulation (exact exponential update per step; Schmitt switching on thresholds)
dt = tau/4000; tend = t1 + 2.4*T; N = ceil(tend/dt);
t = (0:N-1)*dt; Vc = zeros(1,N); Vo = zeros(1,N);
high = true; Vo(1) = Vdd;                       % Vc(0)=0 < Vn -> inverter output high
for k = 2:N
    tgt = Vth*high;
    Vc(k) = tgt + (Vc(k-1)-tgt)*exp(-dt/tau);
    if  high && Vc(k) >= Vp, high = false; end
    if ~high && Vc(k) <= Vn, high = true;  end
    Vo(k) = Vdd*high;
end
up = find(Vc(1:end-1) < Vp & Vc(2:end) >= Vp);  % rising crossings of Vp
dn = find(Vc(1:end-1) > Vn & Vc(2:end) <= Vn);  % falling crossings of Vn
t1_sim = t(up(1));
T_sim  = mean(diff(t(up)));
tl_sim = t(dn(1)) - t(up(1));
th_sim = T_sim - tl_sim;

fprintf('\n--- theory vs simulation ---\n');
lab_check('t1 (0 -> Vp)',      t1*1e3, t1_sim*1e3, 'ms');
lab_check('t_high (Vn -> Vp)', th*1e3, th_sim*1e3, 'ms');
lab_check('t_low (Vp -> Vn)',  tl*1e3, tl_sim*1e3, 'ms');
lab_check('T (period)',        T*1e3,  T_sim*1e3,  'ms');
lab_check('f',                 f,      1/T_sim,    'Hz');
fprintf('duty (output high) = %.1f %%\n', 100*duty);
lab_save(struct('Vdd',Vdd,'Vp',Vp,'Vn',Vn,'C_nF',C*1e9,'R2_k',R2/1e3,'Rx_k',Rx/1e3, ...
    'Rth_k',Rth/1e3,'Vth',Vth,'tau_ms',tau*1e3,'t1_ms',t1*1e3,'th_ms',th*1e3,'tl_ms',tl*1e3, ...
    'T_ms',T*1e3,'f_Hz',f,'duty_pct',100*duty,'Rx_max_k',Rx_max/1e3, ...
    't1_sim_ms',t1_sim*1e3,'th_sim_ms',th_sim*1e3,'tl_sim_ms',tl_sim*1e3,'T_sim_ms',T_sim*1e3, ...
    'f_sim_Hz',1/T_sim), fullfile(here,'c11_results.json'));

% ---- figure 1: two cycles from V(0)=0 (question 9a, 9c)
fig = figure('Visible','off','Position',[100 100 950 480]);
plot(t*1e3, Vc, 'b-', 'LineWidth', 1.7); hold on;
plot(t*1e3, Vo, 'r-', 'LineWidth', 1.2);
yline(Vp, '--k', 'V_p = 3 V', 'LabelHorizontalAlignment','left');
yline(Vn, '--k', 'V_n = 2 V', 'LabelHorizontalAlignment','left');
yline(Vth, ':', sprintf('V_{th} = %.2f V (asymptote)', Vth), 'Color',[0 0.5 0], ...
      'LineWidth',1.2, 'LabelHorizontalAlignment','right');
xlabel('time [ms]'); ylabel('Voltage [V]'); ylim([-0.4 6.8]); xlim([0 t(end)*1e3]);
legend({'V_C (capacitor)','V_O (output)'}, 'Location','northeast');
title(sprintf('Circuit 1.1: R_x = 60 k\\Omega  \\rightarrow  T = %.3f ms, f = %.2f kHz', T*1e3, f/1e3));
lab_fig(fig, fullfile(here,'c11_astable.png')); close(fig);

% ---- figure 2: why Rx must be < 100k (question 9b)
Rxs = linspace(5e3, 99e3, 400);
Rths = Rxs*R2./(Rxs+R2); Vths = Vdd*R2./(Rxs+R2);
Ts = Rths*C.*(log((Vths-Vn)./(Vths-Vp)) + log(Vp/Vn));
fig = figure('Visible','off','Position',[100 100 950 420]);
semilogy(Rxs/1e3, Ts*1e3, 'b-', 'LineWidth', 1.6); hold on;
xline(Rx_max/1e3, 'r--', 'R_{x,max} = 100 k\Omega', 'LineWidth',1.2, ...
      'LabelVerticalAlignment','middle', 'LabelHorizontalAlignment','left');
xlim([0 108]);
plot(Rx/1e3, T*1e3, 'ko', 'MarkerFaceColor','k');
text(Rx/1e3+2, T*1e3, sprintf('R_x = 60 k\\Omega: T = %.3f ms', T*1e3));
xlabel('R_x [k\Omega]'); ylabel('Period T [ms] (log scale)');
title('Period vs. R_x: as R_x \rightarrow 100 k\Omega, V_{th} \rightarrow V_p and the period diverges');
lab_fig(fig, fullfile(here,'c11_rx_sweep.png')); close(fig);
