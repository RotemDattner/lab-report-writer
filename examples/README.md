# Worked example — Experiment 1 (MC14093B Schmitt-trigger NAND)

A complete experiment that passed all QA layers: deterministic checks (0 errors / 0 warnings),
page-by-page review, and three independent QA agents with the booklet as the source of truth.
**Read it before writing a new experiment** and imitate its structure, not its content.

| File | What to learn from it |
|---|---|
| `exp01_schmitt_trigger/build.py` | How a build script is organised: one function per prep question (`q1`…`q11`, sub-parts `q7a`…), numbers read from `simulations/*_results.json` through `fm()` slots (never retyped), datasheet values in one `DS` dict, assumptions highlighted with `==…==`, summary sections (`s51`, `s52`) with sim/scope image pairs, and the self-study content (`CONCEPTS`, `FORMULAS` with worked examples, circuits with simulation figures, `PITFALLS`, `CHECKLIST`, `QUIZ`, `CHEAT`). |
| `exp01_schmitt_trigger/simulations/*.m` | One MATLAB script per circuit: values with their booklet source at the top, `lab_check` theory-vs-simulation, `lab_save` results JSON, `lab_fig` figures; demo simulations for the study document (`demo_noise`, `demo_freq`). |
| `exp01_schmitt_trigger/simulations/*.cir`, `multisim_build.md` | Self-contained netlists (hysteretic switch model of the Schmitt gate) and a step-by-step Multisim guide naming every screenshot file. |

The example runs only inside a real experiment folder (it needs `requirements/` from the
booklet and the simulation results); it is reference material here.
