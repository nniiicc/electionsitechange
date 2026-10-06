# Parser evaluation, 6 Oct 2026 (issue #5; spec: Parser evaluation)

**Corpus:** 97 real pages from the 5 Oct crawl. 82 are raw HTML: Squarespace 21, Wix 20, WordPress 20, custom-built 20, NationBuilder 1 (only one turned up in the sample). 15 are JavaScript-built homepages rendered once in Chromium. They cover all ten office tiers and include aaron4az.com.

**Pairs:** 2,008 in total. Each copies one page and applies **one** labelled change; both sides are serialised the same way.

- **1,040 edit pairs** in 14 types. An edit counts only if it is **detected and located**: the reported difference contains the edit's token, or the removed text.
- **871 noise pairs** in 9 types; these must not be flagged.
- **97 identity controls,** where the two copies are the same.

Some edit types apply only where the page has the element: video on 8 pages, a list item on 38. Real collapsible content was on just 3 pages. So each page also got an injected collapsed block in one of four common markups (details, display:none accordion, hidden tab panel, aria-hidden FAQ), with only its hidden text changed.

Every method below includes the image-and-embed list. Without it, no method detects an image swap or video change, and EDGI finds 43 of 95 alt-text changes, the others 0.

## Edits: located / applicable

| Edit | EDGI text + links | changedetection.io text | snapshot.py (current) |
|---|---|---|---|
| collapsed text injected | 97/97 | 74/97 | 97/97 |
| heading changed | 93/93 | 93/93 | 93/93 |
| hidden text changed | 3/3 | 3/3 | 3/3 |
| image alt changed | 95/95 | 95/95 | 95/95 |
| image swapped | 95/95 | 95/95 | 95/95 |
| link target changed | 85/85 | 0/85 | 85/85 |
| list item changed | 38/38 | 38/38 | 38/38 |
| menu page added | 92/92 | 92/92 | 92/92 |
| menu page removed | 92/92 | 92/92 | 92/92 |
| paid for by changed | 80/80 | 80/80 | 80/80 |
| sentence added | 87/87 | 87/87 | 87/87 |
| sentence removed | 88/88 | 87/88 | 87/88 |
| sentence reworded | 87/87 | 87/87 | 86/87 |
| video changed | 8/8 | 8/8 | 8/8 |

## Noise and controls: wrongly flagged / pairs

| Noise | EDGI text + links | changedetection.io text | snapshot.py (current) |
|---|---|---|---|
| identity | 0/97 | 0/97 | 0/97 |
| attr whitespace | 41/97 | 0/97 | 0/97 |
| cookie banner | 97/97 | 97/97 | 49/97 |
| copyright year | 97/97 | 97/97 | 0/97 |
| countdown | 97/97 | 97/97 | 33/97 |
| donation | 97/97 | 97/97 | 0/97 |
| image params | 0/95 | 0/95 | 0/95 |
| relative date | 97/97 | 97/97 | 62/97 |
| script style | 0/97 | 0/97 | 0/97 |
| tokens build ids | 0/97 | 0/97 | 0/97 |

## Findings
- **EDGI text + links + the media list located all 1,040 edits,** and every one of the 14 types.
- **changedetection.io's text misses two kinds of edit:**
  - every link-target change (0 of 85), because its text has no links;
  - text inside display:none accordions (0 of 23); it reads the other three collapsed markups.
  - Its one sentence-removal miss is a scoring artefact: it prefixes list items with `* `, so the removed-text check didn't match.
- **snapshot.py located 1,038 of 1,040.** Of its 2 misses, 1 is real: its cookie-banner rule dropped an edited sentence. The other is a scoring artefact: it replaces the year with `YEAR`, so the removed-text check didn't match.
- **No method passes, because all three flag the visible-text noise:** countdown, donation total, relative date, copyright year and cookie banner. Those are real text changes on the page, so separating them from content takes rules. snapshot.py flags fewer (144 noise pairs in total) only because of rules I wrote for patterns like these, so that figure is biased in its favour. Its rules have already been shown to drop real content.
- **EDGI also flags 41 of 97 re-indented pages.** I checked all 41: the reported text is identical once whitespace is removed, so a whitespace-insensitive comparison fixes it. changedetection.io ignores whitespace by default.
- **All three ignored the invisible noise.** Tokens and build IDs, script and style changes and image-size parameters flagged 0 pairs; the media list's URL normalisation handled image sizes. The identity controls flagged 0 pairs.
- **EDGI's rendered diff (`html_diff_render`) is unsuitable,** tested on a subset. It caught image swaps (95 of 95), but missed every alt and video change. It also flagged 76 of 95 image-parameter pairs and 77 of 97 whitespace pairs.

## How the test was corrected while running (all methods rescored)
- **Image swap:** it first kept the Wix media ID, so the swapped image was the same image; rebuilt as a new image URL.
- **Hidden text:** the first version picked display:none utility text, such as screen-reader hints and form success messages. It was restricted to collapsible content, and the injected collapsed type was added.
- **Re-indentation:** whitespace is now widened only between block-level tags. It had been splitting letter-by-letter spans on one page.
- **Line diffs:** changedetection.io and snapshot.py are now diffed in sequence order rather than as sets, so a removed line that repeats elsewhere on the page still shows.
- **Token match:** EDGI's character-level diff can share one letter of the token with the old word, so the token's prefix or its suffix now counts.
- **Harness error:** the rendered-diff runner read the wrong result key, and was rerun.

## Limits
- **Coverage:** one NationBuilder page; 8 video pages; 3 pages with real collapsible content.
- **Noise:** the noise text was written by me from templates.
- **Pages:** JavaScript-built pages were rendered only once.
