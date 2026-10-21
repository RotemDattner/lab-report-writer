function lab_fig(fig, outpng)
%LAB_FIG  House style + export for every report figure.
%   lab_fig(fig, outpng) applies grid/box/fonts to all axes in FIG, warns about axes without
%   axis labels (the QA checks that every graph has labelled axes with units) and exports a
%   white-background PNG at 200 dpi.
%
%   Usage in a simulation script:
%       addpath(fullfile(char(java.lang.System.getProperty('user.home')), '.claude','skills','lab-report-writer','assets','matlab'));
%       fig = figure('Visible','off','Position',[100 100 900 460]);
%       ... plot ...
%       lab_fig(fig, fullfile(fileparts(mfilename('fullpath')), 'q09.png'));

axs = findall(fig, 'type', 'axes');
noY = 0; noX = 0;
for a = axs'
    grid(a, 'on'); box(a, 'on');
    a.FontSize = 11; a.LineWidth = 0.8;
    noY = noY + isempty(a.YLabel.String); noX = noX + isempty(a.XLabel.String);
end
% every axis needs a y label; stacked plots may share one x label (time) at the bottom
if noY > 0
    warning('lab_fig:labels', '%d axes without a y label in %s', noY, outpng);
end
if noX == numel(axs) && noX > 0
    warning('lab_fig:labels', 'no axes with an x label in %s', outpng);
end
% cloud-synced folders (OneDrive) can hold a file for a moment: retry before failing
for attempt = 1:4
    try
        exportgraphics(fig, outpng, 'Resolution', 200, 'BackgroundColor', 'white');
        break
    catch err
        if attempt == 4, rethrow(err); end
        pause(1.5);
    end
end
fprintf('saved: %s\n', outpng);
end
