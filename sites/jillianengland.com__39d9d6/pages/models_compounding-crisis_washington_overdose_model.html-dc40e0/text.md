This interactive model needs JavaScript.
Please allow JavaScript for this page (some browsers and script-blocking extensions block it for files opened from disk), then reload.
See README.md → Troubleshooting.
Washington Overdose Model ⓘ How it works Overdose deaths • 2018 — 2024 — — Total deaths V2/V1 OD deaths (growth-rate period) V2 — — — V1 — — — time to double — years Calculated from State data • — Actual 2024 • projection start — — 2024 Est.
2025 • current slider settings — — Est.
2025 Predicted 2026 • current slider settings — — Pred.
2026 Growth rate from observed period: 2019–2023 — Addiction high growth years 2018–2024 — All data years Chooses the V1–V2 date range that sets the natural (no-policy) annual growth rate, time to double or half-life of the modeled series.
Projections always start from the actual 2024 count.
OD Cause OD deaths Fentanyl deaths Opiates OD deaths Oxy deaths Heroin deaths Cocaine deaths Switches the model (baseline, projections, t-double or half-life, chart, lives saved) between total, fentanyl, opiate, oxycodone (Rx opioid), heroin, and cocaine deaths.
Policy Levers Discourage Addict Migration / Inflow Reduce net arrival of active users 0 % 0% (status quo) 100% (strong discouragement) Criminalize Use & Distribution Enforcement + deterrence impact 0 % 0% (current approach) 100% (strong enforcement) Projection horizon 6 years (2025– 2030 ) Default: 6 years (through 2030, the end of the next state Senate term); maximum 10.
Beyond a few years the lines show what pure compounding implies, not a forecast.
Reset to Baseline Copy summary HOW THE MODEL WORKS Growth comes from two drivers: • Inflow/migration of new users (35% of growth) • Lethality + distribution among existing users (65%) Sliders reduce the compounding growth rate in proportion to those shares; both at 100% turn growth into a decline.
Projections start from the actual 2024 count. t-double or half-life = ln(2) / |growth rate|, per the equations.
BASELINE (no change) — Projected deaths in — WITH POLICY CHANGES — Projected deaths in — LIVES SAVED — cumulative vs. baseline trajectory BASELINE t-double — years time to double (t-double > 0 when V₂/V₁ > 1) POLICY — t-Double or Half-Life — — Projected OD Deaths Observed years, then projection Observed Baseline With policies Chart unavailable (chart.umd.min.js did not load).
The numbers and table still work.
Year-by-year: observed, then projected Scroll for more years → Year Baseline With Policies Difference T_d / Half-life (observed: from first row · projected: from 2024) This is a simplified exponential model for illustrative purposes.
Real-world outcomes depend on many variables including supply, treatment access, and enforcement consistency.
Paid for by Friends of Jillian England (AKA FOJE), P.O.
Box 30064, Seattle, WA 98113.
This model is paid for and authorized by the committee to elect Jillian England as defined on the C1. © # Friends of Jillian England.
Licensed under AGPL-3.0-or-later .
See project README.md / LICENSE.txt for details. ⓘ How it works How the Model Works hide × This interactive simulation is built from Washington State Department of Health counts of confirmed overdose deaths among Washington residents (2018–2024).
During the 2019–2023 surge, total deaths compounded at about 28.7% a year — doubling roughly every 2.7 years (about every 4.2 years if you use all 2018–2024 data, which includes the 2024 dip).
The model projects that compounding forward year by year from the actual 2024 count; observed years are shown as actual data and are never changed by the sliders.
The two sliders reduce the compounding growth rate in targeted ways: Discourage Migration/Inflow lowers the arrival of new active addicts into the pool (treated as 35% of the growth).
Criminalize Use & Distribution reduces lethality and frequency of fatal use among the existing population through stronger enforcement and deterrence (treated as 65% of the growth).
Each slider removes its share of the growth rate.
With both at 100% the trend reverses into a decline half as fast as the original growth (a doubling time of T years becomes a half-life of 2T years).
For a series that is already declining, the sliders make it decline faster.
The policy line is never allowed to fall by more than 50% per year (unless the series is already falling faster on its own).
Move the sliders to see how policy changes bend the curve and how many lives could be saved: Lives saved is the cumulative difference between baseline and policy deaths over the projection years.
The chart, table, and T_double / half-life metrics update live.
This is a simplified illustrative model — the 35%/65% split and the strength of the levers are assumptions, not measured effects, and real results depend on consistent implementation in an open system — but it shows the power of addressing the two core drivers of the crisis.
Observed Washington State Overdose Deaths (source data) Year Total OD Opiates OD Heroin Fentanyl Oxy Meth Cocaine The radio buttons above choose the series and years that define the natural growth rate (T_d) used by the model.
Substance columns overlap (one death can involve several drugs), so they do not add up to the total.
Continuous Compounding Mathematics This is an exponential (compounding) growth-or-decay model showing the Time-to-double or Half-Life of overdose deaths in Washington State: Data Sources and Methodology Source: Washington State Department of Health (death certificates), “Confirmed Overdose Deaths among Washington Residents,” by year and substance, 2018–2024 — DOH Opioid and Drug Use Data Dashboard .
Values are from DOH’s downloadable overdose-deaths data (statewide, annual counts; data file dated Sept.
14, 2026), which include DOH’s March 2026 revision of 2024 (3,145 deaths; previously reported as a preliminary 3,086) and minor revisions to earlier years.
2025 counts are still preliminary and are not used.
Column names: Fentanyl = synthetic opioids; Oxy = prescription opioids other than fentanyl; Opiates = any opioid; Meth = psychostimulants.
Open the verification graphic full size · the 2025 row is a compounding estimate from the 2018–2024 trend, not DOH data.
