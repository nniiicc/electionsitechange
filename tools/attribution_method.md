# Attribution check, 5 Oct 2026 (issue #3)

Does each monitored site belong to the candidate and race it is filed under? Results are in
`data/attribution_2026-10-05.csv`, one row per site. Its effects are in `monitor/excluded_sites.csv` (removed from
monitoring) and `monitor/site_flags.csv` (kept and flagged).

## Pipeline

1. **Input:** each site's homepage snapshot from commit `711a7afb` (5 Oct baseline): final URL, title, description,
   "Paid for by" text, years mentioned, and the first 1,500 characters of text. The candidate's name, office, party,
   district and state come from the candidate database. 282 sites had no snapshot, because they were unreachable on
   5 Oct; they are `not_checked`.
2. **Rule (6,711 sites):** `current` if one of the candidate's surnames (more than 2 letters) appears in the
   title, description, disclaimer or final URL, and the page mentions no year, or 2026, or its latest year is 2025 or
   later. On the 149 pilot sites the rule resolved, the reasoning model agreed on 143. None of the 6 disagreements
   was wrong_entity.
3. **Model, first pass (1,545 sites):** a Haiku-class model with the system prompt and tool in
   `tools/attribution_prompt.json`. Verdicts: current, earlier_cycle, wrong_entity, parked_or_empty, unclear.
4. **Model, confirmation (304 sites):** every first-pass `wrong_entity` or `earlier_cycle` was re-run with a
   Sonnet-class reasoning model; that verdict is the one used.
5. **Manual review of every wrong_entity (30):** each was checked by hand. 16 were overturned, mostly nicknames
   the models missed (Todd = James Todd Rutherford; Glenn "Chip" Curry; Alicia "Liish" Kozlowski), plus a
   vendor template and own sites for another race. 14 were confirmed and removed: 6 are domains now serving
   gambling sites, 6 are another person's or organisation's site, 1 is a PAC tool and 1 an unrelated music site.
   The `manual` column records each decision.

## Verdicts

`current`, `earlier_cycle`, `wrong_entity`, `parked_or_empty` and `unclear` come from the model (the enum in
`attribution_prompt.json`). `other_race` (the candidate's own site for a different race) and `personal_site` were
added only by manual review. Only `wrong_entity` removes a site; the others are kept and listed in
`monitor/site_flags.csv`. Totals are in `data/attribution_2026-10-05-summary.json`.

## Pilot (195 URLs, `attribution_pilot_input.csv`)

- Washington controls, known correct (40): no wrong_entity verdicts. 34 current, 2 parked (5xx error pages),
  2 unclear, 2 not fetched.
- Washington controls, known wrong entity (2): 1 detected. The other (votemarshall.com) fails TLS and couldn't be
  fetched, so it couldn't be classified.
- Washington controls labelled earlier cycle in September (13): both sites still showing dated earlier-cycle content
  were caught. Several others now show 2026 content, so their September labels are out of date rather than missed.

## Limits

- One homepage per site, on one day. Sites that change hands later are not caught until the check is re-run.
- The model classification ran in the research environment, not on the VM, because no model API key is configured
  there. The prompts are committed here so the check can be re-run anywhere with a key.
