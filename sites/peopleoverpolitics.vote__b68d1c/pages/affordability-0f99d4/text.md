Interactive Infographic // No DB // Versioned Inputs
GEORGIA AFFORDABILITY SIMULATOR
A self-contained page that lets you change assumptions and see the mechanical tradeoffs.
Every default number is sourced; estimates are labeled as estimates.
Where state revenue comes from
Where it goes (education + healthcare)
A simple spending framing: two large agency totals (Education and Community Health) shown against the FY2026 revenue estimate.
Can wages cover the basics?
This lens is intentionally simple: gross monthly income minus your estimated monthly essentials.
Who pays more (by income group)
Net change is computed as: extra sales tax paid from the new rate minus the group’s allocated property tax relief.
| Group | Avg income | Baseline sales tax | Δ sales tax | Property tax relief | Net change |
|---|---|---|---|---|---|
| Bottom 20% | $18,000 | $1,148 6.38% | $1,072 5.96% | $682,299,694 3790553.85% | -$682,298,622 -3790547.90% |
| 20–40% | $35,000 | $1,969 5.63% | $1,839 5.26% | $1,474,104,276 4211726.50% | -$1,474,102,437 -4211721.25% |
| 40–60% | $55,000 | $2,681 4.88% | $2,505 4.55% | $2,501,765,544 4548664.62% | -$2,501,763,038 -4548660.07% |
| 60–80% | $85,000 | $3,506 4.13% | $3,276 3.85% | $4,105,029,433 4829446.39% | -$4,105,026,157 -4829442.54% |
| Top 20% | $160,000 | $4,200 2.63% | $3,924 2.45% | $8,176,365,054 5110228.16% | -$8,176,361,130 -5110225.71% |
- Property tax relief allocated by: population × (income^exponent) × incidence factor
- Incidence factor = homeowner share + renter share × pass-through
Property tax replacement → required sales tax change
Because property tax is primarily local in Georgia, the key question is: “How much local revenue are we trying to replace?” This model expresses that replacement as a required increase to the combined sales tax rate.
Wages and buying power (simple math)
This is intentionally conservative: gross pay only (no federal tax credits, no payroll deductions).
It’s a baseline reality-check, not a promise of precision.
- Property tax is primarily local revenue in Georgia; eliminating it requires replacing local funding or cutting local services.
- This page does not model behavioral effects (reduced consumption, cross-border shopping, price pass-through).
- Distribution charts use a simplified incidence model (taxable consumption shares and a transparent property-tax weighting rule).
These are editable assumptions, not claims of exact burden by income group.
- The household budget section is gross-income-only and uses user-entered estimates for expenses.
It does not include payroll taxes, federal income tax, or refundable credits.
- Property tax replacement uses a calendar-year (CY2023) local collections baseline from U.S.
Census government finance; sales tax and other tax baselines are FY2024 (DOR).
This mismatch is why the removal slider is framed as a modeling assumption.
