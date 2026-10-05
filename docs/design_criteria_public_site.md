# Public site design criteria (issue #13)

**Status:** draft for the user's approval · 5 Oct 2026 · Applies to issues #14 (site v1) and #15 (site v2). Every page and component is reviewed against this document before release. Where this document and convenience conflict, this document wins; changing it needs the user's approval.

## 1. Audience and core tasks

| Audience | Comes to answer | Primary entry |
|---|---|---|
| **Journalists and researchers** | What did candidate X change, when, and what did it say before? Which candidates changed their position on topic Y this month? | Search → candidate page → change detail; explore pages; data download |
| **Voters** | What does my candidate's site say now, and has it shifted? How do the candidates in my race compare? | Search by name, state or district → race page |
| **Campaign staff and candidates** | What does the site record about *our* site, and is it accurate? How do we request a correction? | Candidate page → methods → corrections |
| **Fact-checkers and archivists** | Show me the evidence: exact before/after text and an independent archived copy. | Change detail → archive links |

Design for the journalist first: if a reporter can verify and cite a change within two clicks of finding it, every other audience is served.

## 2. Neutrality rules

1. **Equal treatment.** Every candidate in a race is shown with the same components, in the same order, at the same size. The ordering inside a race is alphabetical by surname, never by party, activity or incumbency.
2. **Party is a fact, not a design element.** Party appears as text (e.g. "Republican") with no party colours, logos or red/blue encoding anywhere on the site, including charts.
3. **Neutral change summaries.** Summaries describe *what the page says*, not what it means: "Removed the sentence 'I support a national abortion ban.'" — never "Backtracked on abortion." The approved summary templates are listed in the review queue (#12), and the reviewer checks every summary against them.
4. **No judgement by framing.** Lists are named descriptively — "Sites with the most substantive changes since 4 Oct" — never "Flip-floppers" or "Most evasive". No rankings appear on the home page. Every ranked list states the denominator and the period, and links to its method.
5. **Activity is not virtue or vice.** The site never implies that changing a site often (or rarely) is good or bad. A change count is always shown next to what kind of changes they were (§5).
6. **Symmetric scrutiny.** Any filter or view offered for one party is offered for all; no view highlights one party by default.

## 3. Accuracy and trust

1. **Every claim links to evidence.** Each change shown links to: the side-by-side diff, the Git commit, and the Internet Archive captures from before and after (when they exist). A change without evidence links is not published.
2. **Review status is always visible.** Substantive changes are published only after human review (#12) and carry "Reviewed by a person on <date>". Routine and cosmetic changes, which are automatic, are labelled "Automatically classified".
3. **Confidence is shown, not hidden.** Where the classifier's category was uncertain and a reviewer confirmed it, the page says so. No numeric confidence scores are shown to the public; the category plus review status is the public statement.
4. **Corrections.** Each candidate page has a "Report an error" link. Corrections are published in a public log with the date, what changed and why; nothing is silently edited. A retracted change remains visible as "Retracted on <date>: <reason>".
5. **Gaps are stated, not implied away.** Sites that could not be monitored (blocked automated access, down, JavaScript-only before #6, or wrong site removed by #3) appear on the candidate page as "Not monitored: <reason>, since <date>". A candidate with no detected changes is described as "No substantive changes detected since <start date>" — never "No changes".
6. **Dates are exact.** A change is dated by the day it was first detected ("Detected 14 Oct"), not presented as the day the campaign made it.
7. **Source of the candidate list** (Ballotpedia, FEC, state filings) is cited on every candidate page.

## 4. Information architecture

| Page | Purpose | Links to |
|---|---|---|
| **Home / search** | Search by candidate name, state, office or district; a plain explanation of what the site is; date range covered | Candidate, race, explore, methods |
| **Candidate** | Current site summary, timeline of substantive changes, counts by category, monitoring status, links to the live site and archive | Change detail, race, methods |
| **Change detail** | One change: before/after text side by side, category, review status, date detected, evidence links | Candidate, race |
| **Race** | All candidates in one contest with identical summary cards | Candidate pages |
| **Explore** (v2) | Lists by tier, state and category (e.g. "changes to health care pages"), with denominators | Candidate, change detail |
| **Methods** | How sites are collected, crawled, compared, classified and reviewed; known limits; the category definitions | Data, corrections |
| **Data** | CSV and SQLite downloads of all approved changes and the site list, with a data dictionary and licence | Methods |
| **Corrections** | Public correction and retraction log | Candidate, change detail |

Every page is reachable from search in at most two clicks. URLs are stable and human-readable (`/candidate/<state>/<office>/<name-slug>`, `/change/<id>`), so they can be cited.

## 5. Headline metric

- **The headline number is substantive changes**: changes in the content categories (positions, biography, endorsements, priorities, removals of content), counted after review.
- Routine changes (events, news posts, donation appeals) are shown as a secondary count, labelled as routine. Cosmetic and noise changes are not counted publicly; their totals appear only in Methods.
- Raw edit counts are never the headline, because they mostly measure page widgets.
- Every count states its period ("since 4 Oct 2026") and covers only the monitored pages.

## 6. Data display

1. **Timelines** are the default view of one candidate: one mark per substantive change, labelled by category, on a date axis covering the full monitoring period, so quiet periods are visible.
2. **Counts** are shown as integers. Percentages are shown only when the denominator is at least 20, and always with the denominator ("12 of 48 candidates").
3. **Comparisons across candidates** use the same scale, a shared axis and the alphabetical ordering from §2. No comparison chart sorts by party.
4. **Small numbers.** Counts of 0–2 are shown as words in prose ("one change"), and lists of top or bottom candidates require at least 3 substantive changes to appear, so a single edit doesn't make anyone a headline.
5. **Colour** encodes the change category only, using a colour-blind-safe palette that is never red/blue. Every colour has a text label as well.
6. **Tables** are sortable and every column has a plain-language header; every chart has an equivalent table.

## 7. Accessibility, mobile and performance

- **WCAG 2.2 AA** is the target for every page: contrast, keyboard navigation, visible focus, text alternatives for charts, no information conveyed by colour alone, reflow at 320 px width.
- **Diffs are accessible**: removed and added text are marked with words ("Removed:", "Added:") and semantic `<del>`/`<ins>`, not only colour or strike-through.
- **Mobile first**: the before/after view stacks vertically on small screens.
- **Performance budget**: the site is static (pre-built HTML). Each page under 200 KB transferred excluding downloads, Largest Contentful Paint under 2.5 s on a mid-range phone on 4G. No client-side framework is needed for core pages; search may use a small client-side index.

## 8. Legal and ethical

1. **Quoting.** Change pages quote only the changed sentences plus up to one sentence of context on each side. Full page copies are linked (Internet Archive), not republished.
2. **Candidate names** are shown as they appear on the ballot listing, with the source cited; names are never used in page titles or social cards in a way that implies an accusation.
3. **No visitor tracking.** No third-party analytics, cookies, advertising or embedded social widgets. Aggregate request counts from the web server logs are the only usage data.
4. **No candidate contact data** (filing emails, phone numbers, home addresses) appears on the site, even where it exists in the underlying database.
5. **Robots and takedown.** The methods page states that the crawler obeys robots.txt, how it identifies itself, and how a campaign can contact the project.

## 9. Branding, domain and hosting — open decisions

| Item | Status |
|---|---|
| Project name and logo | **Open.** Needs a neutral name with no party association. |
| Domain | **Open.** |
| Hosting | **Open.** Proposed: static hosting (GitHub Pages or Cloudflare Pages), rebuilt daily from approved changes. |
| Publisher / organisation named on the site | **Open.** Needed for the corrections contact and the methods page. |
| Licence for the data download | **Open.** Proposed: CC BY 4.0 for the change data. |
| Reviewer(s) for substantive changes | **Open** (also blocks #12). |

## 10. Review checklist (used for #14 and #15)

- [ ] Every candidate in a race renders identically and is ordered alphabetically.
- [ ] No party colours, logos or party-sorted views.
- [ ] Every published change has evidence links and a review status.
- [ ] Non-monitored sites and gaps are stated on the candidate page.
- [ ] Headline figure is substantive changes, with period and denominator.
- [ ] Small-number and percentage rules hold.
- [ ] WCAG 2.2 AA automated check passes, and keyboard-only walkthrough done.
- [ ] Page weight and LCP within budget.
- [ ] No tracking scripts or third-party requests.
- [ ] Quotes limited to changed sentences plus context.
