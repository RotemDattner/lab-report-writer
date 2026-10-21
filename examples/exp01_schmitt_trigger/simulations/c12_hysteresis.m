%% Circuit 1.2 (prep 5, 6; procedure part 1) - Schmitt inverter driven by a 5 kHz signal
% Source: booklet figure 1.2 (requirements/figures/fig_02.png): one MC14093 NAND with both
% inputs tied to Vin, output Vout. Procedure: sine at 5 kHz with a DC level chosen so the
% signal stays inside 0..VDD; VDD = 5 V and 10 V; then triangle and square inputs.
% Thresholds: MC14093B datasheet, typical @25C (datasheets/MC14093B.pdf, p.3):
%   VDD =  5 V: VT+ = 2.9, VT- = 1.9 ;  10 V: 5.9 / 3.9 ;  15 V: 8.8 / 5.8
% Assumptions for question 6 (stated in the report, highlighted for the user):
%   Vin = VDD/2*(1 - cos(2*pi*f*t)): full 0..VDD swing, Vin(0) = 0 at power-up.
clear; clc;
addpath(fullfile(char(java.lang.System.getProperty('user.home')),'.claude','skills','lab-report-writer','assets','matlab'));
here = fileparts(mfilename('fullpath'));

fsig = 5e3; w = 2*pi*fsig; Tsig = 1/fsig;
VDDs = [5 10 15]; VPs = [2.9 5.9 8.8]; VNs = [1.9 3.9 5.8];

% ---- question 6: time the output stays '1' after power-up, and steady-state high time
fprintf('--- Q6: output = 1 from t=0 until Vin first reaches Vp ---\n');
q6 = zeros(3,4); q6sim = zeros(3,2);
t = linspace(0, 3*Tsig, 60001);
for i = 1:3
    VDD = VDDs(i); Vp = VPs(i); Vn = VNs(i);
    t1 = acos(1 - 2*Vp/VDD)/w;                                  % first '1' interval
    thigh = (acos(1 - 2*Vp/VDD) + acos(1 - 2*Vn/VDD))/w;        % '1' per period (steady)
    vin = VDD/2*(1 - cos(w*t));
    hi = schmitt_inv(vin, Vp, Vn, VDD) > VDD/2;
    t1_sim = t(find(~hi, 1));                          % first 1 -> 0 transition
    rise = t([diff(hi) == 1, false]); fall = t([diff(hi) == -1, false]);
    thigh_sim = fall(2) - rise(1);                     % one full steady-state '1' interval
    lab_check(sprintf('t1 @ VDD=%2d V', VDD), t1*1e6, t1_sim*1e6, 'us');
    lab_check(sprintf('t_high/period @ VDD=%2d V', VDD), thigh*1e6, thigh_sim*1e6, 'us');
    q6(i,:) = [VDD, t1*1e6, thigh*1e6, 100*thigh/Tsig];
    q6sim(i,:) = [t1_sim*1e6, thigh_sim*1e6];
end
disp('   VDD   t1[us]  t_high[us]  duty[%]'); disp(round(q6,1));
lab_save(struct('f_sig_Hz',fsig,'VDD',VDDs,'Vp',VPs,'Vn',VNs,'t1_us',q6(:,2)', ...
    't_high_us',q6(:,3)','duty_pct',q6(:,4)','t1_sim_us',q6sim(:,1)','t_high_sim_us',q6sim(:,2)', ...
    'T_sig_us',Tsig*1e6), fullfile(here,'c12_results.json'));

% ---- figure 1: time domain (YT) at 5 V and 10 V
fig = figure('Visible','off','Position',[100 100 950 620]);
tiledlayout(2,1,'TileSpacing','compact');
t = linspace(0, 3*Tsig, 30001);
for i = 1:2
    VDD = VDDs(i); Vp = VPs(i); Vn = VNs(i);
    vin = VDD/2*(1 - cos(w*t)); vout = schmitt_inv(vin, Vp, Vn, VDD);
    nexttile; plot(t*1e6, vin, 'b-', 'LineWidth',1.4); hold on;
    plot(t*1e6, vout, 'r-', 'LineWidth',1.2);
    yline(Vp,'--k',sprintf('V_p=%.1f V',Vp),'LabelHorizontalAlignment','left');
    yline(Vn,'--k',sprintf('V_n=%.1f V',Vn),'LabelHorizontalAlignment','left','LabelVerticalAlignment','bottom');
    xlabel('time [\mus]'); ylabel('Voltage [V]'); ylim([-0.5 VDD*1.12]);
    title(sprintf('V_{DD} = %d V: sine input 5 kHz and Schmitt-inverter output', VDD));
    legend({'V_{in}','V_{out}'},'Location','eastoutside');
end
lab_fig(fig, fullfile(here,'c12_yt.png')); close(fig);

% ---- figure 2: XY hysteresis loops (what the scope shows in XY mode)
fig = figure('Visible','off','Position',[100 100 950 460]);
cols = {[0 0.35 0.8],[0.85 0.33 0.1]};
h = gobjects(1,2);
for i = [2 1]                             % 10 V first, so it doesn't cover the 5 V loop's bottom
    VDD = VDDs(i); Vp = VPs(i); Vn = VNs(i);
    vin = VDD/2*(1 - cos(w*t)); vout = schmitt_inv(vin, Vp, Vn, VDD);
    h(i) = plot(vin, vout, '-', 'Color', cols{i}, 'LineWidth', 1.8); hold on;
    text(Vp, VDD*0.5, sprintf(' V_p=%.1f', Vp), 'Color', cols{i});
    text(Vn, VDD*0.5, sprintf('V_n=%.1f ', Vn), 'Color', cols{i}, 'HorizontalAlignment','right');
end
xlabel('V_{in} [V]  (scope X, channel 1)'); ylabel('V_{out} [V]  (scope Y, channel 2)');
title('Hysteresis curve (XY mode): output falls at V_p, rises at V_n');
legend(h, {'V_{DD} = 5 V','V_{DD} = 10 V'},'Location','northeast'); xlim([-0.5 10.5]); ylim([-0.6 10.8]);
lab_fig(fig, fullfile(here,'c12_xy.png')); close(fig);

% ---- figure 3: sine vs triangle vs square input (procedure steps e, f, g), VDD = 5 V
VDD = 5; Vp = 2.9; Vn = 1.9;
ph = mod(t/Tsig, 1);
% the square wave gets finite (2 us) edges like a real generator: the output only switches
% when the edge crosses Vp / Vn, so in XY the trace runs along the loop and DWELLS at the
% two corners (0, VDD) and (VDD, 0) - a straight diagonal would be a plotting artefact.
tr = 2e-6/Tsig;
sq = VDD*min(1, max(0, min(ph/tr, (0.5 - ph)/tr + 1)));
sq(ph >= 0.5) = VDD*max(0, 1 - (ph(ph >= 0.5) - 0.5)/tr);
inputs = {VDD/2*(1 - cos(w*t)), VDD*(1 - abs(2*ph - 1)), sq};
names = {'sine','triangle','square'};
fig = figure('Visible','off','Position',[100 100 1000 760]);
tiledlayout(3,2,'TileSpacing','compact');
for i = 1:3
    vin = inputs{i}; vout = schmitt_inv(vin, Vp, Vn, VDD);
    nexttile; plot(t*1e6, vin,'b-','LineWidth',1.3); hold on; plot(t*1e6, vout,'r-','LineWidth',1.1);
    yline(Vp,'--k'); yline(Vn,'--k'); ylim([-0.4 5.6]);
    title(sprintf('%s input: time domain', names{i})); xlabel('time [\mus]'); ylabel('V [V]');
    nexttile;
    if i < 3
        plot(vin, vout, 'm-', 'LineWidth', 1.6);
    else                                      % faint fast traces + bright dwell points
        plot(vin, vout, '-', 'Color', [1 0.7 1], 'LineWidth', 1.0); hold on;
        plot([0 VDD], [VDD 0], 'mo', 'MarkerSize', 11, 'MarkerFaceColor', 'm');
        text(0.25, VDD-0.45, 'dwell (V_{in}=0)'); text(VDD-0.25, 0.45, 'dwell (V_{in}=V_{DD})', ...
             'HorizontalAlignment','right');
    end
    xlim([-0.4 5.4]); ylim([-0.4 5.6]);
    title(sprintf('%s input: XY', names{i})); xlabel('V_{in} [V]'); ylabel('V_{out} [V]');
end
lab_fig(fig, fullfile(here,'c12_inputs.png')); close(fig);

function vout = schmitt_inv(vin, Vp, Vn, VDD)
%SCHMITT_INV ideal Schmitt inverter: out falls when vin >= Vp, rises when vin <= Vn.
vout = zeros(size(vin)); high = vin(1) < Vp;   % at power-up below Vp -> output '1'
for k = 1:numel(vin)
    if  high && vin(k) >= Vp, high = false; end
    if ~high && vin(k) <= Vn, high = true;  end
    vout(k) = VDD*high;
end
end
