# Simulation (MATLAB primary, Multisim SPICE secondary)

For every circuit-bearing question, produce **two** artifacts: a MATLAB script (the
primary, auto-run engine) and a SPICE netlist for Multisim (secondary, user-run). The
user prefers MATLAB and verifies both.

## Before simulating: get the circuit right

Take topology and values **only from the booklet figure** (`requirements/figures/`, opened and
read by you) and the datasheet in `datasheets/`. Write them at the top of the script with the
source (`% Fig 1.1 of the booklet: Rx from output to node, 100k node->gnd, C=10nF`). A wrong
topology silently produces a beautiful, self-consistent, wrong simulation — it happened once
with a value copied from an old report.

## MATLAB house helpers (`assets/matlab/`)

```matlab
% user.home works on Windows, macOS and Linux (USERPROFILE is Windows-only)
addpath(fullfile(char(java.lang.System.getProperty('user.home')),'.claude','skills','lab-report-writer','assets','matlab'));
lab_check('T (period)', T_theory, T_sim, 'ms');        % prints theory/sim/error, flags MISMATCH > 2%
lab_fig(fig, fullfile(fileparts(mfilename('fullpath')),'c11_wave.png'));   % style + 200-dpi PNG
```

`lab_fig` warns about axes without labels — every graph needs labelled axes with units, a
legend for multiple traces, and threshold/reference lines where they help reading.
Name scripts and PNGs by circuit/purpose (`c11_astable.m`, `c12_hysteresis_xy.m`,
`demo_noise.m`) and keep one figure per message.

## Schematics (`lab_schem.m`)

Circuits the student designs (not drawn in the booklet) get a clean schematic with real pin
numbers from the datasheet, drawn in MATLAB (`x_schem.m` → `sch_*.png`):

```matlab
S = lab_schem('', [950 480]);                                  % title, figure size [px]
P = S.ic('MC14538B', 0, 0, 4.4, 4.2, {'A:4', '\overline{B}:5'}, {'Q:6'}, {'C_X/R_X:2'}, {'V_{SS}:8'});
S.wire([P.A; P.A - [2 0]]);  S.res(p1, p2, 'R_X 100k');  S.gnd(P.VSS);  S.vdd(p, 'V_{DD}');
g = S.gate('nand', x, y, 2);  S.wire([g.out; P.A]);            % g.in(k,:), g.out
S.save(fullfile(here, 'sch_debounce.png'));
```

Pin structs are keyed without TeX (`V_{SS}`→`VSS`, `C_X/R_X`→`CX_RX`, `\overline{Q}`→`nQ`,
`U/D`→`U_D`). Also `S.cap`, `S.pot`, `S.sw` (SPDT), `S.spst`, `S.dot`, `S.txt`; gates: and,
nand, or, nor, not, buf, xor. View every PNG: wires must not cross IC bodies, labels must not overlap.

## Demo simulations (for the self-study document)

Beyond the experiment's own circuits, add small simulations whose only purpose is
understanding — the user learns best from graphs. Good demos: the same input with and without
hysteresis (noise immunity), a parameter sweep (frequency vs. R or C, vs. VDD), the effect of
breaking an assumption (symmetric formula vs. full formula), and "what happens if" questions
the booklet asks (sine → triangle → square input). Each demo: one clear graph + 2–3 lines of
insight in the study document. Prefix them `demo_` in `simulations/`.

## MATLAB (primary)

Runs against a live MATLAB session via the MATLAB MCP (`run_matlab_file` /
`evaluate_matlab_code`). Available toolboxes on this machine: Simulink, Simscape, Simscape
Electrical, Stateflow, Symbolic Math, Signal Processing, DSP, Control System.

### Choosing the modeling approach
- **Analog circuits** (Schmitt-trigger oscillator, sample & hold, DAC ladders, RC timing):
  Simscape Electrical for a faithful circuit model, or a direct numeric ODE/closed-form
  model when that is simpler and clearer. Either is fine as long as it captures the physics
  and is cross-checked (below).
- **Digital / logic** (counters, flip-flops, shift registers, encoders/decoders,
  adders/subtractors): a logic/timing simulation is usually clearest — model the truth
  table / state transitions and plot the waveforms. Stateflow or Simulink can be used for
  sequential logic; plain MATLAB is fine for combinational.
- **Symbolic derivations** (proving a frequency/transfer formula, quantization step): use
  Symbolic Math (`syms`, `simplify`, `solve`) so the derivation is exact and re-checkable.

### Conventions
- One script per question: `simulations/q<NN>.m`. Header comment states the experiment,
  the question, and the parameter values used (cite the requirement/datasheet).
- Run **headless**: `figure('Visible','off')`, export with
  `exportgraphics(f, fullfile(fileparts(mfilename('fullpath')),'q<NN>.png'), 'Resolution',150)`.
- Print the key numeric results to stdout so the run output is self-documenting.
- Save the figure next to the script; the report embeds the PNG.

### Always cross-check against theory
Compute the analytic/expected value in the same script and print both, plus the error:

```matlab
fprintf('expected  = %.4g\n', expected);
fprintf('simulated = %.4g\n', simulated);
fprintf('error     = %.2f %%\n', 100*abs(simulated-expected)/expected);
```

A mismatch is a **finding**, not noise to bury — it usually means either the model or the
hand analysis is wrong. Surface it to the physics-QA pass. (In validation, this caught a
reference report that applied `T=2RC·ln(Vp/Vn)` outside its `Vp+Vn=Vcc` symmetry
assumption — the simulation gave the correct period and the report's number was off ~15%.)

## Multisim (SPICE netlist, secondary)

Produce `simulations/q<NN>.cir` — a Berkeley/ngspice-style netlist the user imports into
Multisim (`File ▸ Open`/import) — plus `q<NN>_build.md`, a short build guide (component
list, node connections, which analysis to run: `.tran`, `.dc`, `.ac`).

### Netlist conventions
- Standard SPICE cards: `R`, `C`, `L`, `V`, `D`, `Q`, `M`, `.model`, `.tran`, `.dc`, `.ac`,
  `.probe`/`.save`, `.end`. Node `0` is ground. Comment with `*`.
- Keep component references aligned with the schematic in the report (R1, C1 …).

### Modeling a Schmitt trigger / hysteretic part in a self-contained netlist
A voltage-controlled switch with hysteresis makes a netlist self-contained and runnable in
any SPICE (ngspice/Multisim) without a vendor model: `.model SWMOD SW(Ron=1m Roff=1e9
Vt=<mid> Vh=<half-hyst>)` closes above `Vt+Vh` and opens below `Vt−Vh`. E.g. thresholds
Vn=2/Vp=3 → `Vt=2.5 Vh=0.5`. The output stage is a pull-up `RPU vdd out 1` and the switch(es)
from `out` to ground (a NAND = two switches in series). See `ניסוי 01/simulations/c1*.cir`.
- **Keep the output stage ideal**: pull-up 1 Ω, Ron 1 mΩ. A 100 Ω pull-up adds to the timing
  resistor and a large Ron lifts the low level; together they biased Exp 1's oscillator by
  ~1.6%, which a student would read as a real discrepancy (found by QA review, 2026-10).
- Use the plain 3-argument `SIN(VO VA F)`; a 6th phase argument is an ngspice extension that
  Multisim's import may reject.
- In the build guide, warn that Multisim's library model of the IC has its own thresholds:
  compare against the formula evaluated with the thresholds **read off the Multisim trace**.
Cross-check the resulting period against the closed form and the MATLAB result.

### Importing a netlist into Multisim (put these steps in every q<NN>_build.md)
`File ▸ Open` (file type = SPICE netlist `*.cir`) or `File ▸ Import ▸ SPICE Netlist`; Multisim
builds a schematic. Run `Simulate ▸ Analyses ▸ Transient` with the `.tran` stop/step from the
netlist, add the probed nodes to Selected variables, Run, and read the Grapher. Always also
give the **manual-build fallback** (place the real part from Multisim's library + R/C + scope),
since Multisim's import of behavioral models is not guaranteed.

### ICs without a ready SPICE model (important, common here)
Many course parts (MC14093, MC14538B, MC14516B, CD4013B, MC14094B, DAC0800, ADC0804,
CD4066, CD4504) have no drop-in SPICE model. Do **not** fake one silently. Instead:
- Put the **surrounding passive circuit** in the netlist (the part SPICE handles well).
- In `q<NN>_build.md`, instruct the user to place the IC itself **from the Multisim library**
  and wire it to the marked nodes, or give a documented behavioral subcircuit if one is
  genuinely available and appropriate.
- State this limitation plainly in the report near that simulation. The MATLAB behavioral
  model remains the trustworthy result for these parts.
- Note: the ADC0804 A/D part historically doesn't simulate in Multisim — such a requirement
  may be waived by the course; check the requirement before spending effort.

## Embedding results
Embed each `q<NN>.png` into the preparatory report under the relevant question (and into the
summary report where a simulated waveform is compared to a measured one), with a numbered
`איור` caption. Reference every figure by number in the body text.
