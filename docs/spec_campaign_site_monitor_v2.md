# Spec: 2026 Campaign Website Change Monitor

*Written with the `to-spec` engineering skill (mattpocock/skills), synthesising the project discussion up to 5 Oct 2026. Supersedes `spec_campaign_site_monitoring.md`.*

## Problem Statement

We hold a verified national database of 2026 midterm candidates and their campaign websites: US Senate, US House, governor and the other statewide offices, state legislatures, and state supreme and appellate courts across all 50 states plus DC and the territories. We have no record of what those sites say, or of how they change in the weeks before the 3 November general election. Campaign sites are edited quietly. Positions get softened, endorsements added or dropped, donation platforms switched, candidacies suspended. Once a page changes, the earlier version is gone unless someone captured it. Nobody can see how often a candidate updates their site, or what they changed.

A first homepage-only snapshot on 5 Oct showed that capturing homepages is not enough:

- Homepages link to a median of 5 other pages on the same site, 50,616 internal pages in total. None of these were captured.
- The text extractor kept a median of 63% of each page's visible text, and less than half on 31% of sampled pages.
- 597 pages returned almost no text because they are built with JavaScript.
- 775 linked PDFs were not captured.
- Nothing was submitted to the Wayback Machine.

Raw edit counts are also misleading. Most edits to a campaign page are noise (countdowns, donation progress bars, rotating banners). Counting edits measures widget churn, not campaign activity.

## Solution

1. **Capture.** Crawl every candidate's campaign site every day to a bounded depth. Store a normalised snapshot of each page in a Git repository, so its history is the change log. Keep the raw HTML of changed pages. Submit pages to the Wayback Machine so each recorded change has an independent, citable copy.
2. **Categorise.** Compare each page with the previous day's version and label each change against a fixed category list, using the cheapest method that settles it: noise rules first, then a fast classifier (Jev), then an LLM only for substantive or uncertain changes. A person approves every substantive change before it is published.
3. **Publish.** A public website shows, for every candidate and race, how often the campaign site changes in substance, what changed, the quoted before and after text, and a link to the archived copy. It is backed by a downloadable dataset and a methods page that states what is and isn't monitored and how accurate the labels are.

## User Stories

**Capture**

1. As a researcher, I want every reachable campaign site in the national database crawled daily, so that there is a daily record of each site through election day.
2. As a researcher, I want the crawl to follow internal links up to 3 clicks from the homepage, so that issue, biography, endorsement and event pages are tracked, not just homepages.
3. As a researcher, I want a per-site page cap, so that one very large site cannot dominate the daily run.
4. As a researcher, I want only pages on the candidate's own site crawled, so that the crawl doesn't wander into news sites, donation processors or social networks.
5. As a researcher, I want outbound links (donation platforms, endorsers, social accounts) recorded but not crawled, so that link changes are tracked without fetching third-party sites.
6. As a researcher, I want the full visible text of each page used for comparison, so that content in tabs, cards and accordions isn't lost.
7. As a reader, I want a cleaned main-text version alongside the full text, so that I can read a page without its menus and footers.
8. As a researcher, I want text stored one sentence per line, so that a reworded sentence appears as one changed line.
9. As a researcher, I want JavaScript-built pages rendered in a headless browser, so that they are tracked rather than recorded as empty.
10. As a researcher, I want linked PDFs on a candidate's site captured as text, so that policy documents are tracked.
11. As a researcher, I want each page's "Paid for by" disclaimer, title, description and the years it mentions recorded, so that committee changes and stale-cycle sites are visible.
12. As a researcher, I want a failed fetch never to overwrite the last good snapshot, so that an outage is not recorded as content disappearing.
13. As a researcher, I want every fetch logged with its status and error, so that an unchanged page can be told apart from one we failed to reach.
14. As a researcher, I want pages that appear or disappear recorded as added or removed, so that a deleted issue page is itself a visible change.
15. As a researcher, I want the raw HTML of every changed page kept, so that normalisation can be re-run later.
16. As a site operator, I want the crawler to obey robots.txt, make at most 1 request per second to my site, and identify itself honestly, so that the monitor never loads or deceives my server.
17. As a researcher, I want sites that refuse automated access listed as "not monitorable" with the reason, so that missing data is explained, not silent.
18. As a researcher, I want each day's results pushed to GitHub, so that the history is backed up and can be shared.
19. As a researcher, I want a daily run summary (sites reached, pages fetched, changed, failures by type, Wayback backlog), so that I can see whether the run was healthy.
20. As a researcher, I want a crashed run to be safe to re-run, so that one bad day doesn't corrupt the history.

**Archive**

21. As a researcher, I want every site's homepage submitted to the Wayback Machine with its outlinks on first capture, so that each site's linked pages are archived from one request.
22. As a researcher, I want each changed page submitted to the Wayback Machine the day it changes, so that each recorded change has an independent copy.
23. As a researcher, I want pages skipped if the Wayback Machine already captured them recently, so that submissions aren't wasted.
24. As a researcher, I want Wayback submissions that haven't gone through carried over to the next day, so that a temporary limit delays archiving rather than losing it.
25. As a researcher, I want the Wayback capture URL recorded against each page version, so that the website can link to the independent copy.

**Categorise**

26. As a researcher, I want noise-only changes discarded by rules before any model sees them, so that model cost and reviewer time go only to real edits.
27. As a researcher, I want each remaining change labelled as substantive, routine or cosmetic, with a category from a fixed list, so that the counts mean the same thing across candidates.
28. As a researcher, I want each label to carry a confidence score, so that uncertain labels are escalated rather than trusted.
29. As a researcher, I want a fast, cheap classifier for the first pass and a more capable model only for substantive or uncertain changes, so that cost scales with real change, not page count.
30. As a reader, I want every substantive change to have a one-line summary with quoted before and after text, so that the claim can be checked at a glance.
31. As a researcher, I want added or removed outbound links classified too (for example, a donation platform switched or an endorser's link removed), so that changes outside the page text are categorised.
32. As a researcher, I want classifier accuracy measured on hand-labelled real changes before it is trusted, so that Jev is adopted only if it beats the alternatives on our data.
33. As a researcher, I want accuracy rechecked weekly on newly labelled changes, so that drift is caught during the election window.
34. As a reviewer, I want every substantive change held for my approval before publication, so that a wrong claim about a candidate never goes public.
35. As a reviewer, I want each queue item to show the candidate, race, category, summary, quoted text, diff and Wayback links, so that I can decide without opening raw files.
36. As a reviewer, I want to approve, edit or reject a label with one action, so that daily review fits before the site rebuilds.
37. As a researcher, I want published claims to be correctable, with a visible correction note, so that mistakes are fixed openly.

**Web interface**

38. As a member of the public, I want to search for a candidate by name, state, office or district, so that I can find their page quickly.
39. As a member of the public, I want a candidate page with a timeline of substantive changes, the date of the last substantive change and a count by category, so that I can see how actively and how much a campaign changed its message.
40. As a member of the public, I want routine and cosmetic changes available as a lighter layer on the candidate page, so that I can see all activity without it drowning out substance.
41. As a member of the public, I want a change detail view showing the side-by-side diff, the summary and links to both archived versions, so that I can verify the change myself.
42. As a member of the public, I want a race page showing every candidate's changes side by side, so that I can compare opponents.
43. As a member of the public, I want explore pages listing the most and least active sites by office tier and state, plus recent substantive changes nationwide, so that I can find notable activity.
44. As a member of the public, I want sites that went offline or were taken down during the window flagged, so that disappearances are visible.
45. As a member of the public, I want a methods page explaining what is monitored, the category list, the review policy, measured accuracy and the list of non-monitorable sites, so that I can judge how far to trust the data.
46. As a data user, I want to download every approved change as CSV and SQLite, so that I can analyse the history myself.
47. As a researcher, I want the website rebuilt automatically each day after review, so that it stays current without manual publishing.

**Scope integrity**

48. As a researcher, I want sites the attribution check marks as belonging to someone else excluded, so that we never report changes to another person's website.
49. As a researcher, I want sites that show only an earlier election cycle flagged but still tracked, so that a switch to 2026 content is itself recorded.
50. As a researcher, I want a final snapshot after election day, so that post-election takedowns and concessions are captured.

## Implementation Decisions

### Hosting and operation
- Runs on one GCP VM (`electionsites`: Debian 13, 2 vCPU, 3.9 GB RAM, 49 GB disk) with open internet access. The research sandbox can't reach campaign domains or resolve DNS, so all fetching happens on the VM.
- The VM is attached to the project as an SSH compute target. The daily run is a cron job on the VM; classification and calibration may run from the project.
- Software: Python 3.13 with `requests` for fetching, `trafilatura` for main-text extraction, and `playwright` driving the system Chromium for rendering.

### Module: URL list
- Source: campaign-scoped website links in the national candidate database whose reachability is reachable, ambiguous or not tested. That is 8,538 unique URLs across every tier in the database. A URL shared by several candidates is tracked once and attributed to all of them.
- Each URL gets a stable site identifier (host plus a short hash of the URL). Sites the attribution pilot marks as the wrong entity are removed; earlier-cycle sites are kept and flagged.

### Module: Crawler and renderer
- Breadth-first from the homepage. Same-host links only, with `www.` treated as the same host. **Depth 3 clicks, 50 pages per site** (decided 5 Oct). The cap is applied in breadth-first order, so shallower pages always win over deeper ones.
- PDFs on the candidate's own site are fetched, their text extracted and stored like any page (counted against the cap). Scanned PDFs with no text layer are recorded as such.
- Skips images, stylesheets, scripts, fonts and media. Obeys robots.txt for the monitor's own user agent, keeps requests to any one host at least 1 second apart, crawls many sites in parallel, and identifies itself honestly. It never disguises itself as a browser.
- Any page whose full visible text is under 200 characters and that contains a script is re-fetched with headless Chromium (images off, the monitor's own user agent, at most 2 at once), and the snapshot records that it was rendered. If a page rendered yesterday fails to render today, yesterday's snapshot is kept. (Pages without scripts are not rendered: a browser would show the same text.)

### Module: Normaliser and store
- **The raw HTML of each recorded version is kept**: gzip-compressed on the VM, outside Git, written only when a page is new or changed (decided by the user, 8 Oct: never every page every day). Whether to store later versions as diffs is open.
- How text, links, images and embeds are extracted from that HTML, and how noise is ignored, is **decided by the parser evaluation below**. No parser is adopted until it passes. The parsers used up to 6 Oct (`trafilatura` main-text extraction, then a hand-written full-text normaliser with noise rules) are not adopted: on aaron4az.com the stored text missed 35 of the 42 lines visible on the page.
- Git repository: one directory per site, one sub-directory per page. A file is rewritten only when its content changes, and each day ends in one commit, so commits record only real changes. Volatile values (fetch time, size, timing) go in the daily run log, never in snapshot files.
- The repository is pushed to `github.com/nniiicc/electionsitechange` after each run, using a deploy key that can only write to that repository.

### Parser evaluation: text parsing and change measurement (agreed with the user, 6 Oct)
Chooses the parser and change detection, using fake sites built from real pages, so every answer is known in advance and the test runs in hours.

1. **Corpus:** about 100 real pages taken from the 5 Oct crawl's saved raw HTML. The sample spans the main site builders (Squarespace, Wix, WordPress, NationBuilder, custom-built), every office tier, homepages and inner pages, and includes aaron4az.com. A separate set of JavaScript-built sites is rendered once in Chromium, because their raw HTML has no content.
2. **Known edits,** applied by script to copies of each page, each labelled:
   - *Must be detected:* sentence reworded, added or removed; heading changed; text inside a collapsed accordion or tab changed; list item changed; image swapped or its alt text changed; link target changed; menu page added or removed; embedded video changed; "Paid for by" text changed.
   - *Noise, must be ignored:* security tokens and build IDs rotated; script and style contents changed; attributes reordered and whitespace changed; countdown and donation-total numbers changed; relative dates ("3 days ago") and copyright year changed; cookie-banner wording changed; image size and cache-busting parameters changed.
3. **Methods compared on the same pairs:** EDGI `web-monitoring-diff` (text and link diffs); changedetection.io's HTML-to-text conversion; the current `snapshot.py` parser as the baseline. Each is scored with and without an image-and-embed list, which is the one piece we write ourselves if EDGI's diffs don't report image changes.
4. **Scoring, by edit type:** detected or missed; whether the reported difference points at the edited text; noise-only pairs wrongly flagged. A method passes only if it detects every edit type and flags zero noise-only pairs. Every miss is listed with its page.
5. **Outcome:** the passing method becomes the parser in `snapshot.py` and the Change detector's method (#5, #9). The corpus and labels go into the automated tests, so every later code change is checked against them. Day-to-day noise on live sites is monitored after launch and does not gate this decision.

### Module: Archiver (Wayback Machine)
- We submit URLs; Internet Archive's own crawler fetches the pages. Submission uses the open-source `spn.sh`
  (overcast07/wayback-machine-spn-scripts, MIT), vendored unmodified in `tools/vendor/`; it handles Save Page Now
  authentication, parallel jobs and retries. `monitor/archive.py` only builds the queue and records results, and
  `monitor/archive.sh` runs them, started in the background by `daily.sh` after each snapshot.
- **Measured capacity (9 Oct):** this account has 3 concurrent captures and a 30,000/day limit (Save Page Now's status
  call). Two trials (50 and 30 changed pages) captured 2.3 and 2.9 pages a minute, so about **3,300–4,200 pages a
  day**; concurrency, not the daily limit, is the constraint. (The published 12 concurrent / 100,000 a day do not
  apply to this account.)
- **Daily queue, in priority order:** homepages of sites that changed (a site-wide change submits the homepage), new
  pages, pages whose text, links or metadata changed, pages where only images changed. On 8 Oct data that is about
  5,100 pages, more than a day's capacity: submission stops at 07:30 UTC the next day, so the lowest-priority end of
  the list may not be archived. **Unsent pages are not carried over** (a change from the earlier spec): with the queue
  already above capacity every day, carried-over pages would only push out the next day's changes; the change itself is
  still recorded in Git, and its record says it has no Wayback copy (`wayback.after` empty, status `not_captured` in
  `wayback/<day>.csv`). Changed pages are skipped only if captured in the last 3 hours.
- **First round:** after the day's changed pages, up to 2,000 homepages never archived by us are submitted (skipped if
  already captured in the last 30 days). At current capacity this queue is rarely reached. Outlink capture is not
  used: it would multiply captures far beyond capacity.
- Results go to `~/monitor/wayback/results/<day>.csv` (outside the repository, which daily.sh resets at the start of
  each run); the next morning's run copies them to `wayback/<day>.csv` and fills each change record's `wayback.before`
  (latest earlier capture we made) and `wayback.after` (that day's capture).
- Keys: archive.org S3-style access and secret key, in `~/.config/archiveorg/spn_keys` on the VM (mode 600), never in
  chat or Git. Without them nothing is submitted.

### Module: Change detector
- Runs after each day's commit. For every page added, removed or changed, it produces a change record with:
  - a sentence-level text diff, so reordered or reflowed text doesn't count as an edit;
  - a link diff (outbound links added and removed);
  - a metadata diff (title, description, "Paid for by", years);
  - the before and after Wayback links (empty until the Archiver, #8, records captures).
- An edit repeated identically on 3 or more changed pages of one site (a menu, footer or "recent posts" sidebar) is recorded once, in one site-wide change record per site that gives the pages each item changed on, not once per page (added 8 Oct, from the first day-over-day run, where such edits made up a large share of page records).
- Implemented in `monitor/changes.py`; records are written to `changes/<day>.jsonl` in the snapshot commit.
- Uses the method chosen by the parser evaluation. EDGI's open-source `web-monitoring-diff` library is the default candidate (installation needs `pkg-config`, `libxml2-dev` and lxml built from source). EDGI's tools reliably show *what* changed; deciding whether a change matters is the next module's job.

### Module: Categoriser (the labelling cascade)

**Category list** (fixed before collection begins, so labels stay comparable across candidates and days):

| Class | Category | Examples |
|---|---|---|
| **Substantive** | `issue_added` / `issue_removed` / `issue_reworded` | New healthcare plank; abortion language softened |
| | `endorsement_added` / `endorsement_removed` | Union or newspaper endorsement |
| | `party_affiliation_changed` | Party name or logo removed or added |
| | `opponent_content` | New contrast or attack copy |
| | `donation_platform_changed` | ActBlue → own processor; donate link removed |
| | `candidacy_status` | Withdrawal, concession, suspension notice |
| **Routine** | `event_added`, `news_post_added`, `volunteer_cta` | Rally listing; press release |
| **Cosmetic** | `typo`, `image_swap`, `layout`, `date_counter`, `other_cosmetic` | Comma fix; new hero image |

**The cascade, cheapest step first:**

| Step | Method | Input | Output | Runs on |
|---|---|---|---|---|
| 0 | Rules | Change record | Discard if only noise patterns or whitespace changed. Site-specific strip rules are added for any site producing more than 3 cosmetic-only changes a day | Every change |
| 1 | **Jev** (TypeSafe AI) | Change record plus candidate context (name, office, party, state) | Three typed answers, each with a confidence: *is this substantive?* (yes/no), *which category?* (choice from the list above), *how significant?* (score 1–5) | Changes that pass step 0 |
| 2 | LLM (small, fast class) | Change record plus candidate context | One-line summary, quoted before and after text, and a second-opinion category | Changes step 1 calls substantive, or labels below the confidence threshold |
| 3 | Human reviewer | Step 2 output | Approve, edit or reject | Every substantive change before publication |

- **Escalation rule:** a step-1 result goes to step 2 if it is substantive, or if any of its confidences is below the threshold set during calibration. Changes confidently labelled routine or cosmetic stop at step 1 and publish automatically as the lighter layer.
- **Why Jev:** it is built for fast, structured decisions over a fixed answer set, and its yes/no, choice and score questions map directly onto the category list. It can't write text, which is why step 2 is still needed for summaries.
- **Calibration before trust:** about 200 changes from days 1–5 are hand-labelled across tiers and change types. Keyword rules, Jev and the step-2 LLM are each scored on that set. Jev is adopted only if it beats the alternatives on our data; the vendor's published benchmark is not evidence for this task. Escalation thresholds are set from the same labelled set. Accuracy is rechecked weekly against 50 newly labelled changes.
- **Accuracy target:** at least 95% of changes labelled substantive after step 2 are actually substantive. Precision matters more than recall here, because a false public claim is costly.
- **Fallback:** if Jev isn't used, step 1 is the small LLM. A small open model fine-tuned on the labelled changes is a second-month option; it needs more labels than exist in October.
- **Access:** the Jev API key is stored as a Claude Science credential, which needs one network approval for `api.typesafe.ai`. The LLM is called through the platform's model access.
- **Cost:** model calls scale with the number of changes that survive step 0, not with the number of pages. That number is unknown until week one.

### Module: Review queue
- A private reviewer view (not public) listing changes awaiting approval, newest first. Each item shows the candidate, race, category, confidence, summary, quoted before and after text, the side-by-side diff and both Wayback links. Each item has approve, edit (category or summary) and reject actions.
- Decisions are written to a reviewed-changes record. That record is the only thing the public site reads for substantive changes, so nothing substantive can be published without approval.
- Review must finish before the daily rebuild. Turnaround and reviewer are an open decision.
- Corrections: a published change can be retracted or amended. The public page keeps a visible correction note.

### Module: Public website
- A static site generated each day from the snapshot repository, the change records and the reviewed-changes record. It has no live server-side code, which keeps it cheap and robust.
- Pages:
  - **Home and search:** find a candidate by name, state, office or district.
  - **Candidate:** a timeline of approved substantive changes; the date of the last substantive change; counts by category over the window; routine and cosmetic changes as a collapsible lighter layer; current site status (live, offline, not monitorable).
  - **Change detail:** the side-by-side diff, the summary, the category, and links to the archived before and after versions.
  - **Race:** every candidate in the contest side by side, with change counts and the latest substantive change for each.
  - **Explore:** most and least active sites by office tier and state; recent substantive changes nationwide; sites that went offline or were taken down.
  - **Methods:** what is monitored and what isn't, the crawl limits, the category list and cascade, measured accuracy, the review and corrections policy, and the list of non-monitorable sites with reasons.
  - **Data:** daily downloads of all approved changes as CSV and SQLite.
- The headline metric everywhere is **substantive changes**. Total edit counts are shown only as secondary context.
- Hosting is an open decision. Options are GitHub Pages from the existing repository, a static bucket, or the VM.

### Data contracts
- **Daily run.** Input: the URL list and a date. Output: one Git commit, a run log, a run summary, new Archiver queue items and change records. Running it again for the same date gives the same repository state, apart from anything that genuinely changed in between.
- **Run log row:** site, page URL, depth, HTTP status, error class, rendered flag, text length, changed/added/removed, timing.
- **Change record:** change id, site and page, date, candidate ids and race, text diff, link diff, metadata diff, before and after Wayback links, step-0 result, step-1 labels with confidences, step-2 summary and quotes, review status, reviewer and decision time, correction note.

### Measured capacity (5 Oct homepage baseline)
- 8,538 sites in 32 minutes at 8 workers; 8,069 reached. Not reached: 334 refused automated access (HTTP 403), 60 SSL errors, 45 disallowed by robots.txt, 30 other.
- Expected daily volume at full scope: at least 59,000 pages (8,069 homepages plus about 50,600 pages one click away); depth 3 adds more, bounded by the 50-page cap (at most about 400,000). The first depth-3 run will measure the real figure and runtime.
- Repository: 18 MB packed after the homepage baseline. Raw HTML: about 0.5 GB per full capture.

## Testing Decisions

- A good test checks behaviour you can observe from outside: given what fake sites serve, what ends up stored, committed, queued and labelled. It doesn't test internal functions.
- **Test boundary (agreed with the user, 5 Oct): the daily pipeline end to end.** It runs against a local fixture web server serving small fake campaign sites over two or more simulated days, and asserts on the repository, run log, archive queue and change records. Fixtures:
  - a page edited between days;
  - an unchanged page;
  - a noise-only change (countdown, donation counter);
  - a page removed and a page added;
  - a site that is unreachable on day 2;
  - a robots.txt rule disallowing a page;
  - a site with more pages than the cap;
  - links deeper than 3 clicks;
  - an off-site link;
  - a JavaScript-only page;
  - a PDF link (text stored and diffed), including one scanned PDF with no text layer;
  - a donation-platform link swap.
- **Parser and change detection** are tested against the parser-evaluation corpus: every labelled edit must be detected and every noise-only pair must be ignored.
- The Archiver is tested at the same boundary against a stub Wayback endpoint: first-capture outlink submission, changed-page submission order, skipping recent captures, carrying the queue over, and recording capture URLs.
- The Categoriser is tested against the hand-labelled set of real week-one changes. Pass condition: at least 95% precision on substantive after step 2.
- The website is tested by building it from a fixture set of approved and unapproved changes. Pass conditions: unapproved substantive changes never appear; candidate, race and change pages render for every fixture candidate; downloads match the approved records.
- Prior art: a 20-site smoke run, the 8,538-site homepage baseline (5 Oct) and the first full crawl (93,707 pages fetched, 5–6 Oct) on the VM. The automated tests are in `tests/`.

## Out of Scope

- Offices that aren't in the national candidate database (county, city and other local races). The separate Washington dataset includes local candidates, but they are not part of this monitor unless added later.
- Official office pages, legislature member pages and personal websites. Campaign-scoped sites only.
- Social media accounts.
- Crawling third-party pages linked from campaign sites. Their links are recorded only.
- Getting past bot protection. Sites that refuse the monitor's honest user agent are listed as not monitorable.
- Recovering changes made before the first snapshot (5 Oct), except by linking to existing Wayback captures.
- Real-time alerting. The cadence is daily.

## Further Notes

- **Open decisions:**
  1. archive.org keys.
  2. Jev credential and network approval.
  3. Reviewer and daily review turnaround.
  4. Website hosting, domain and branding.
  5. Whether to add Washington's local candidates.
- **Decided 5 Oct:** crawl depth 3 clicks; cap 50 pages per site; PDFs captured as text.
- **Schedule:** the planned 4 Oct baseline slipped to 5 Oct (homepages only). Each day without the full crawl is internal-page history that can't be recovered.
- **Cost:** a GCP e2-medium VM costs roughly $25–40 a month; price trackers disagree, so check the GCP calculator. Model calls for categorisation are the cost most likely to exceed the VM.
- **Built so far:** only the homepage snapshot script and the GitHub push. Still to build: the depth crawl, renderer, PDFs, Archiver, daily cron, change detector, categoriser, review queue and website.
- **Tracker:** `to-spec` normally files the spec as an issue labelled `ready-for-agent`. No tracker is configured; this can go on `nniiicc/electionsitechange` once GitHub API access exists, or be committed to the repository's documentation.
