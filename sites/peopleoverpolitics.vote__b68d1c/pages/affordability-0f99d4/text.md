PEOPLE OVER POLITICS About Anthony Events Affordability Tax Math Bills to Watch Cherokee Elections Community Poll Register to Vote Interactive Infographic // No DB // Versioned Inputs GEORGIA AFFORDABILITY SIMULATOR A self-contained page that lets you change assumptions and see the mechanical tradeoffs.
Every default number is sourced; estimates are labeled as estimates.
Baseline (FY2024) Where state revenue comes from Source Income tax (individual) $16B Source Sales & use tax (state net) $9B Source Sales tax (total collected) $18B Source Derived (transparent math) Taxable sales base estimate from FY2024 total sales tax ÷ assumed combined rate.
Source $242B Using 7.50% combined rate Local property tax (calendar year 2023) Context baseline used as the default for “revenue to replace” in the scenario controls.
Source $17B Note: calendar-year (Census) vs fiscal-year (DOR) baselines.
FY2026 Budget Lens Where it goes (education + healthcare) A simple spending framing: two large agency totals (Education and Community Health) shown against the FY2026 revenue estimate.
Source Revenue estimate (state funds) $38B Source Education (Dept. of Education) $14B 36.1% of revenue estimate (State Funds) Total Funds: $16B Source Healthcare (Community Health) $6B 14.6% of revenue estimate (State Funds) Total Funds: $25B (includes federal match) Source Note: This uses the highlights revenue estimate as a denominator.
It is a high-level framing and may not match any one “state funds appropriations total” table exactly.
Monthly Budget Can wages cover the basics?
This lens is intentionally simple: gross monthly income minus your estimated monthly essentials.
Inflation / buying power (CPI-U) Base CPI: 312.1 • Current CPI: 320.2 Change: 2.6% • Budget deflation: Off Source Healthcare premiums (benchmark) KFF covered-worker contribution: single ≈ $114 /mo • family ≈ $525 /mo Budget uses: $0 /mo ( manual input ) Source Monthly gross income $1,257 Monthly essentials (estimate) $3,100 246.7% of gross income Leftover -$1,843 Negative means the math doesn’t work.
Expense breakdown (monthly) Distribution Who pays more (by income group) Net change is computed as: extra sales tax paid from the new rate minus the group’s allocated property tax relief.
Net change ($/year; negative means net savings) Net change (% of income) Taxes modeled per group (dollars and % of income) This table reflects what this simplified model actually computes: baseline sales tax paid, the change in sales tax from the scenario, and the allocated property tax relief.
It does not model total tax liability (income tax, payroll taxes, fees, corporate incidence, etc.).
Group Avg income Baseline sales tax Δ sales tax Property tax relief Net change Bottom 20% $18,000 $1,148 6.38% $1,072 5.96% $682,299,694 3790553.85% -$682,298,622 -3790547.90% 20–40% $35,000 $1,969 5.63% $1,839 5.26% $1,474,104,276 4211726.50% -$1,474,102,437 -4211721.25% 40–60% $55,000 $2,681 4.88% $2,505 4.55% $2,501,765,544 4548664.62% -$2,501,763,038 -4548660.07% 60–80% $85,000 $3,506 4.13% $3,276 3.85% $4,105,029,433 4829446.39% -$4,105,026,157 -4829442.54% Top 20% $160,000 $4,200 2.63% $3,924 2.45% $8,176,365,054 5110228.16% -$8,176,361,130 -5110225.71% What the model assumes (editable) - Sales tax paid ≈ income × taxable consumption share × rate - Property tax relief allocated by: population × (income^exponent) × incidence factor - Incidence factor = homeowner share + renter share × pass-through Edit group assumptions in data/ga-affordability/distribution.ts .
Scenario Property tax replacement → required sales tax change Because property tax is primarily local in Georgia, the key question is: “How much local revenue are we trying to replace?” This model expresses that replacement as a required increase to the combined sales tax rate.
Source Local revenue replaced (derived) $17B CY2023 baseline × 100% removal Other replacement revenue (derived) $0 Sum of enabled policy toggles (editable estimates).
Required sales tax increase 7.01% Percent points added to the combined rate.
Net sales tax revenue required: $17B /yr New combined sales tax rate (estimate) 14.51% State 4% + assumed average local + required increase.
Household Lens Wages and buying power (simple math) This is intentionally conservative: gross pay only (no federal tax credits, no payroll deductions).
It’s a baseline reality-check, not a promise of precision.
Source Annual gross pay $15,080 Monthly gross pay $1,257 Assumptions & Caveats Property tax is primarily local revenue in Georgia; eliminating it requires replacing local funding or cutting local services.
This page does not model behavioral effects (reduced consumption, cross-border shopping, price pass-through).
Distribution charts use a simplified incidence model (taxable consumption shares and a transparent property-tax weighting rule).
These are editable assumptions, not claims of exact burden by income group.
The household budget section is gross-income-only and uses user-entered estimates for expenses.
It does not include payroll taxes, federal income tax, or refundable credits.
Property tax replacement uses a calendar-year (CY2023) local collections baseline from U.S.
Census government finance; sales tax and other tax baselines are FY2024 (DOR).
This mismatch is why the removal slider is framed as a modeling assumption.
Source Controls Edit assumptions No persistence.
Refresh resets to defaults.
Edit defaults in the repo under data/ga-affordability.
Simple Advanced Scenario import/export Export Reset Import Only known editable input IDs are applied.
Assumed average local sales tax rate Local rates vary by jurisdiction; this is a single-number simplification.
Source 2% 4.5% Property tax removal (local) Models eliminating local property tax revenue statewide as a percentage of the CY2023 local property tax collections baseline (Census).
Source 0% 100% Adjust budget to base-year dollars (toggle) If on, the monthly budget lens shows values deflated from Current CPI to Base CPI using CPI-U (national).
This is a communication tool, not a GA-specific inflation estimate.
Source Off Use KFF benchmark worker premium contribution (toggle) If on, the budget uses KFF's national average covered-worker premium contribution (single vs family) instead of the manual Healthcare premiums input.
Source Off Healthcare coverage type: Family (toggle) If on, uses the family benchmark; if off, uses the single benchmark.
Source Off Protect groceries from sales tax (toggle) Modeled as excluding the FY2024 'Food & Grocery' business-group share from the taxable sales base.
This is a simplification; the business-group category is not identical to groceries as consumed by households.
Source Off Include marijuana tax revenue (toggle) Toggle on and set an estimated annual revenue below.
Source Off Marijuana tax revenue (annual, estimate) Used only when the marijuana toggle is on.
Default is a third-party estimate (not an official GA forecast); edit based on actual proposal design.
Source $0 $5B Include sports gambling tax revenue (toggle) Toggle on and set an estimated annual revenue below.
Source Off Sports gambling tax revenue (annual, estimate) Used only when the sports gambling toggle is on.
Default is an order-of-magnitude proxy based on another state's reported collections; edit based on actual GA proposal design.
Source $0 $2B Rent pass-through of property tax changes How much of a property tax cut eventually shows up in rent.
This is uncertain and context-dependent; treat as a sensitivity slider.
0% 100% Hourly wage Default is federal minimum wage.
Source $0 $60 Rent (monthly) Estimate input.
If you want this sourced, we can add HUD/ACS rent benchmarks into the repo and cite them. $0 $6K
