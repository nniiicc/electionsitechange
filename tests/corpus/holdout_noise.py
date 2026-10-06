"""Second noise set (issue #5): 16 templates in markup and wording different from the evaluation's noise
(banner kits, flip clocks, fundraising widgets, feed dates, footer variants). Each template is injected
into every corpus page; a pair must NOT be flagged.

It is NOT an independent held-out set. It was written on 6 Oct after the first noise rules, by the same
person who wrote them. Its first run failed 7 of 16 templates (chipped_in, copyright_year_last,
countdown_no_units, election_in_n_days, flip_clock, hours_minutes_ago_feed, yesterday_rollover); the
rules were then generalised until all 16 passed. It now guards against regressions only.
See docs/parser_adoption_2026-10-06.md.
"""

from make_pairs import inject, pages, parse, ser

# (name, before, after, where)
HOLDOUT = [
    ("onetrust_banner",
     '<div id="onetrust-banner-sdk" class="otFlat"><div class="ot-sdk-container"><p id="onetrust-policy-text">We use cookies '
     'and similar technologies to personalize content and ads.</p><button id="onetrust-accept-btn-handler">Accept All Cookies'
     '</button></div></div>',
     '<div id="onetrust-banner-sdk" class="otFlat"><div class="ot-sdk-container"><p id="onetrust-policy-text">This site uses '
     'cookies to provide you with a great user experience.</p><button id="onetrust-accept-btn-handler">Allow All</button>'
     '</div></div>', "end"),
    ("squarespace_banner",
     '<div class="sqs-cookie-banner-v2"><div class="sqs-cookie-banner-v2-text">This website uses cookies.</div>'
     '<a class="sqs-cookie-banner-v2-cta" href="#">Accept</a></div>',
     '<div class="sqs-cookie-banner-v2"><div class="sqs-cookie-banner-v2-text">We use cookies to improve this site.</div>'
     '<a class="sqs-cookie-banner-v2-cta" href="#">Got it</a></div>', "end"),
    ("plain_banner_no_class",
     '<section><p>Our site uses cookies to understand how visitors use it. By clicking OK you agree.</p><button>OK</button></section>',
     '<section><p>We use cookies for analytics. Click OK to consent to their use.</p><button>OK</button></section>', "end"),
    ("flip_clock",
     '<div class="flipdown"><div><span>2</span><span>9</span></div><div>Days</div><div><span>1</span><span>4</span></div>'
     '<div>Hours</div><div><span>0</span><span>7</span></div><div>Minutes</div></div>',
     '<div class="flipdown"><div><span>2</span><span>8</span></div><div>Days</div><div><span>0</span><span>3</span></div>'
     '<div>Hours</div><div><span>5</span><span>2</span></div><div>Minutes</div></div>', "top"),
    ("countdown_no_units",
     '<div class="countdown-timer" data-end="2026-11-03"><span class="cd-days">29</span>:<span class="cd-hours">14</span>:'
     '<span class="cd-min">07</span></div>',
     '<div class="countdown-timer" data-end="2026-11-03"><span class="cd-days">28</span>:<span class="cd-hours">13</span>:'
     '<span class="cd-min">52</span></div>', "top"),
    ("election_in_n_days",
     '<p class="banner">Election Day is in 29 days! Make your plan to vote.</p>',
     '<p class="banner">Election Day is in 28 days! Make your plan to vote.</p>', "top"),
    ("thermometer_percent_goal",
     '<div class="progress-wrap"><div class="progress-bar" style="width:62%"></div></div><p class="progress-label">62% of our '
     '$50,000 goal</p>',
     '<div class="progress-wrap"><div class="progress-bar" style="width:71%"></div></div><p class="progress-label">71% of our '
     '$50,000 goal</p>', "top"),
    ("chipped_in",
     '<p>1,204 people have chipped in so far. Will you be next?</p>',
     '<p>1,233 people have chipped in so far. Will you be next?</p>', "top"),
    ("donor_count_heading",
     '<h3 class="stat">2,481 Donors</h3><p class="stat-label">and counting</p>',
     '<h3 class="stat">2,519 Donors</h3><p class="stat-label">and counting</p>', "top"),
    ("weeks_ago",
     '<div class="post"><a href="/news/town-hall">Town hall recap</a> <span class="entry-date">2 weeks ago</span></div>',
     '<div class="post"><a href="/news/town-hall">Town hall recap</a> <span class="entry-date">3 weeks ago</span></div>', "end"),
    ("yesterday_rollover",
     '<div class="post"><a href="/news/endorsement">New endorsement</a> <time>Yesterday</time></div>',
     '<div class="post"><a href="/news/endorsement">New endorsement</a> <time>2 days ago</time></div>', "end"),
    ("copyright_range",
     '<p class="site-info">Copyright 2024-2025 Smith for Senate</p>',
     '<p class="site-info">Copyright 2024-2026 Smith for Senate</p>', "end"),
    ("copyright_year_last",
     '<p class="footer-copy">© Smith for Senate 2025</p>',
     '<p class="footer-copy">© Smith for Senate 2026</p>', "end"),
    ("copyright_word_c",
     '<p>(c) 2025 Committee to Elect Jordan Lee. All rights reserved.</p>',
     '<p>(c) 2026 Committee to Elect Jordan Lee. All rights reserved.</p>', "end"),
    ("hours_minutes_ago_feed",
     '<ul class="news-feed"><li>Volunteer meetup <span class="ago">45 minutes ago</span></li></ul>',
     '<ul class="news-feed"><li>Volunteer meetup <span class="ago">1 hour ago</span></li></ul>', "end"),
    ("raised_toward",
     '<div class="fundraiser"><span class="amt">$8,140</span> <span>raised toward our end-of-quarter push</span></div>',
     '<div class="fundraiser"><span class="amt">$9,015</span> <span>raised toward our end-of-quarter push</span></div>', "top"),
]


def pairs(corpus_dir):
    for r, html in pages(corpus_dir):
        base = ser(parse(html))
        for name, ta, tb, where in HOLDOUT:
            a, b = parse(base), parse(base)
            inject(a, f"<div>{ta}</div>", where); inject(b, f"<div>{tb}</div>", where)
            yield {"pair_id": f"{r['page_id']}-holdout-{name}", "page_id": r["page_id"], "kind": "noise",
                   "type": "holdout_" + name, "a": ser(a), "b": ser(b)}
