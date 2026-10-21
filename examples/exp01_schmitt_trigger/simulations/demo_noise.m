%% Demo (self-study): why hysteresis defeats noise - and its limit (prep question 1)
% A slow ramp with additive noise is fed to an ordinary inverter (one threshold) and to a
% Schmitt inverter with Vp/Vn = 2.9/1.9 V (MC14093B typ @ 5 V, VH = 1.0 V), for two noise
% levels: peak-to-peak noise SMALLER than VH (clean) and LARGER than VH (some chatter returns).
clear; clc; rng(7);
addpath(fullfile(char(java.lang.System.getProperty('user.home')),'.claude','skills','lab-report-writer','assets','matlab'));
here = fileparts(mfilename('fullpath'));

VDD = 5; Vp = 2.9; Vn = 1.9; Vth = 2.4;          % single threshold = middle of the band
t = linspace(0, 4e-3, 8000);
ramp = VDD*(1 - abs(2*mod(t/4e-3,1) - 1));        % 0 -> 5 -> 0 V over 4 ms
base = randn(size(t));
levels = [0.11 0.25];                             % noise rms [V]
fig = figure('Visible','off','Position',[100 100 1000 760]);
tiledlayout(3,2,'TileSpacing','compact');
out = struct('rms',levels,'pp',[0 0],'n_plain',[0 0],'n_schmitt',[0 0],'VH',Vp-Vn);
for j = 1:2
    % a real input is clamped to the rails by the protection diodes; the transition counts are
    % illustrative (white noise per sample, so they depend on the sampling grid)
    vin = min(max(ramp + levels(j)*base, 0), VDD);
    vcmp = VDD*(vin < Vth);
    vsch = zeros(size(t)); high = vin(1) < Vp;
    for k = 1:numel(t)
        if  high && vin(k) >= Vp, high = false; end
        if ~high && vin(k) <= Vn, high = true;  end
        vsch(k) = VDD*high;
    end
    pp = max(levels(j)*base) - min(levels(j)*base);
    nc = sum(abs(diff(vcmp)) > 0); ns = sum(abs(diff(vsch)) > 0);
    out.pp(j) = pp; out.n_plain(j) = nc; out.n_schmitt(j) = ns;
    fprintf('noise p-p = %.2f V (VH = %.2f V): plain inverter %d transitions, Schmitt %d (ideal 2)\n', ...
            pp, Vp-Vn, nc, ns);
    nexttile(j); plot(t*1e3, vin, 'Color',[0.35 0.35 0.35]); hold on;
    yline(Vp,'--b','V_p'); yline(Vn,'--b','V_n');
    yline(Vth,':r','single threshold','LabelHorizontalAlignment','left');   % keep clear of V_p/V_n
    xlabel('time [ms]'); ylabel('V_{in} [V]');
    title(sprintf('input: noise %.2f V p-p %s V_H', pp, char(60 + 2*(pp > Vp-Vn))));
    nexttile(j+2); plot(t*1e3, vcmp, 'r-'); ylim([-0.5 5.8]); xlabel('time [ms]'); ylabel('V_{out} [V]');
    title(sprintf('ordinary inverter: %d transitions', nc));
    nexttile(j+4); plot(t*1e3, vsch, 'b-', 'LineWidth', 1.4); ylim([-0.5 5.8]);
    xlabel('time [ms]'); ylabel('V_{out} [V]');
    title(sprintf('Schmitt trigger: %d transitions', ns));
end
lab_fig(fig, fullfile(here,'demo_noise.png')); close(fig);
lab_save(out, fullfile(here,'demo_noise_results.json'));
