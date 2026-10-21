function lab_save(results, outjson)
%LAB_SAVE  Write a simulation's numeric results to JSON for the report build script.
%   lab_save(struct('T_ms', T*1e3, 'f_Hz', f), fullfile(here, 'c11_results.json'))
%   The Word documents read their numbers from these files, so every number printed in a
%   report is exactly what the simulation computed - nothing is retyped by hand.
fid = fopen(outjson, 'w', 'n', 'UTF-8');
fwrite(fid, jsonencode(results, 'PrettyPrint', true), 'char');
fclose(fid);
fprintf('results: %s\n', outjson);
end
