"""Unit tests for monitor/detect.py (issue #5): noise is ignored, campaign content is never hidden.

The labelled-corpus test (test_parser_corpus.py) is the acceptance test; these pin down the rules
one by one, including the cases where a rule must NOT apply.
"""
import importlib.util, os, unittest

spec = importlib.util.spec_from_file_location(
    "detect", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "monitor", "detect.py"))
detect = importlib.util.module_from_spec(spec); spec.loader.exec_module(detect)


def doc(body):
    return f"<html><head><title>Jane Doe</title></head><body><main><p>Jane Doe is running for State House.</p>{body}</main></body></html>"


def fp(body):
    return detect.page(doc(body), "https://jane.test/")["meta"]["fingerprint"]


NOISE = [  # (before, after): must compare equal
    ('<div class="countdown"><span>12</span> Days <span>5</span> Hours</div>', '<div class="countdown"><span>11</span> Days <span>23</span> Hours</div>'),
    ("<p>Only 12 days until Election Day!</p>", "<p>Only 9 days until Election Day!</p>"),
    ('<div class="timer">29d : 14h : 7m</div>', '<div class="timer">28d : 13h : 52m</div>'),
    ("<div>$12,450 raised of $25,000 goal</div>", "<div>$14,980 raised of $25,000 goal</div>"),
    ("<div>49% funded - 183 donors</div>", "<div>59% funded - 211 donors</div>"),
    ("<span>Posted 3 days ago</span>", "<span>Posted 1 week ago</span>"),
    ("<time>Yesterday</time>", "<time>2 days ago</time>"),
    ("<footer>© 2025 Friends of Jane</footer>", "<footer>© 2026 Friends of Jane</footer>"),
    ("<footer>Copyright 2024-2025 Friends of Jane</footer>", "<footer>Copyright 2024-2026 Friends of Jane</footer>"),
    ('<div id="cookie-notice">We use cookies. <button>Accept</button></div>',
     '<div id="cookie-notice">This site uses cookies for analytics. <button>Accept all</button></div>'),
    ("<section><p>We use cookies to improve your experience.</p><button>OK</button></section>",
     "<section><p>By continuing you agree to our use of cookies.</p><button>Got it</button></section>"),
    ('<a href="/issues?utm_source=fb">Issues</a>', '<a href="/issues?utm_source=email">Issues</a>'),
    ('<img src="/wp-content/uploads/jane-300x200.jpg?ver=1" alt="Jane">', '<img src="/wp-content/uploads/jane-1024x683.jpg?ver=2" alt="Jane">'),
    ("<p>Jane   will\n  fight for schools.</p>", "<p>Jane will fight for schools.</p>"),
    ('<div class="countdown"><span>12</span><span>Days</span><span>05</span><span>Hours</span></div>',
     '<div class="countdown"><span>11</span><span>Days</span><span>22</span><span>Hours</span></div>'),
    ("<div>Goal: $50,000 - 72% funded</div>", "<div>Goal: $50,000 - 81% funded</div>"),
    ("<p>1,204 donors and counting</p>", "<p>1,288 donors and counting</p>"),
    # fundraising counts are treated as progress-widget noise even inside a sentence (the wording is still compared)
    ("<p>Thank you to our 500 donors who helped us reach this goal.</p>", "<p>Thank you to our 600 donors who helped us reach this goal.</p>"),
    # found on real pages, 5 vs 6 Oct: re-encoded on every load
    ('<a href="/cdn-cgi/l/email-protection#9bf3fef7f7f4dbf9feeff3f6faf8e2fdf4e9f8f4f5fce9fee8e8b5f8f4f6">[email&#160;protected]</a>',
     '<a href="/cdn-cgi/l/email-protection#355d5059595a755750415d5854564c535a47565a5b52475046461b565a58">[email&#160;protected]</a>'),
    ('<a href="mailto:%62eattyforc%6fng%72%65%73s@%67%6da%69%6c.c%6f%6d">Email</a>',
     '<a href="mailto:b%65attyforco%6egr%65ss@gma%69l.%63o%6d">Email</a>'),
    ('<div class="gform_validation_container"><label>LinkedIn</label><input name="input_9"><div>This field is for validation purposes and should be left unchanged.</div></div>',
     '<div class="gform_validation_container"><label>Company</label><input name="input_9"><div>This field is for validation purposes and should be left unchanged.</div></div>'),
    ('<a href="/Events?range=2026-10-05">This week</a>', '<a href="/Events?range=2026-10-06">This week</a>'),
    ('<img src="https://sites.google.com/sitesv-images-rt/AMxu72sFTz=w1280">', '<img src="https://sites.google.com/sitesv-images-rt/AMxu72sOwT=w16383">'),
]

CONTENT = [  # (before, after): must compare different
    ("<p>Pat will cap insulin at $35 a month.</p>", "<p>Pat will cap insulin at $25 a month.</p>"),
    ("<p>Call us at 202-555-0100.</p>", "<p>Call us at 202-555-0199.</p>"),
    ("<p>(202) 555-0100</p>", "<p>(202) 555-0111</p>"),
    ("<p>Early voting ends 11/01/2026</p>", "<p>Early voting ends 11/02/2026</p>"),
    ("<p>Vote by Nov. 3</p>", "<p>Vote by Nov. 4</p>"),
    ("<p>Jane has 3 children and 2 dogs.</p>", "<p>Jane has 3 children and 3 dogs.</p>"),
    ("<p>Thank you to our 500 donors who helped us reach this goal.</p>", "<p>Thank you to our 500 volunteers who helped us reach this goal.</p>"),
    ("<p>I have raised taxes on no one and will fight for schools.</p>", "<p>I have raised taxes on no one and will fight for clinics.</p>"),
    ("<p>Town hall on Nov. 3 at 6pm.</p>", "<p>Town hall on Nov. 5 at 6pm.</p>"),
    ("<p>In 2 years we will fix every road.</p>", "<p>In 4 years we will fix every road.</p>"),
    ("<p>We use cookies and local flour in every batch at our family bakery.</p>",
     "<p>We use cookies and local butter in every batch at our family bakery.</p>"),
    ('<label class="sms-consent">By providing your number you consent to texts from Jane Doe.</label>',
     '<label class="sms-consent">By providing your number you consent to calls from Jane Doe.</label>'),
    ("<p>Yesterday’s ruling was a win for voters.</p>", "<p>Yesterday’s ruling was a loss for voters.</p>"),
    ('<a href="/donate">Donate</a>', '<a href="https://secure.actblue.com/jane">Donate</a>'),
    ('<a href="/cdn-cgi/l/email-protection#9bf3fef7f7f4dbf9feeff3f6faf8e2fdf4e9f8f4f5fce9fee8e8b5f8f4f6">Email</a>',
     '<a href="mailto:press@janedoe.test">Email</a>'),
    ('<a href="/events?day=2026-10-06">Rally</a>', '<a href="/events/rally-in-dayton">Rally</a>'),
    ('<img src="/img/jane.jpg" alt="Jane">', '<img src="/img/jane.jpg" alt="Jane with nurses">'),
    ('<iframe src="https://www.youtube.com/embed/abc"></iframe>', '<iframe src="https://www.youtube.com/embed/xyz"></iframe>'),
    ('<div style="display:none"><p>Jane backs a public option.</p></div>', '<div style="display:none"><p>Jane opposes a public option.</p></div>'),
    ("<footer>Paid for by Friends of Jane.</footer>", "<footer>Paid for by Jane Doe for House.</footer>"),
    # other numbers sharing a block with a widget are still compared (code review, 6 Oct)
    ('<div class="sidebar">Election Day is in 29 days. Call 202-555-0100</div>',
     '<div class="sidebar">Election Day is in 29 days. Call 202-555-0199</div>'),
    ('<div class="countdown-wrap"><span>12</span> days to go. <p>Town hall on Nov. 3 at 6pm.</p></div>',
     '<div class="countdown-wrap"><span>12</span> days to go. <p>Town hall on Nov. 5 at 6pm.</p></div>'),
    ('<div class="countdown"><span>12</span> Days <span>202-555-0100</span></div>',
     '<div class="countdown"><span>12</span> Days <span>202-555-0199</span></div>'),
    ('<div class="timer"><span>29</span> days <span>11/03/2026</span></div>',
     '<div class="timer"><span>29</span> days <span>11/04/2026</span></div>'),
    ("<div><p>$12,450 raised of $25,000 goal</p><p>Pat will cap insulin at $35 a month.</p></div>",
     "<div><p>$12,450 raised of $25,000 goal</p><p>Pat will cap insulin at $25 a month.</p></div>"),
]


class Rules(unittest.TestCase):
    def test_noise_is_ignored(self):
        for a, b in NOISE:
            with self.subTest(a=a):
                self.assertEqual(fp(a), fp(b))

    def test_content_changes_are_detected(self):
        for a, b in CONTENT:
            with self.subTest(a=a):
                self.assertNotEqual(fp(a), fp(b))

    def test_cookie_banner_removal_keeps_large_blocks(self):
        big = "<p>" + "Jane will fight for schools. " * 40 + "</p>"
        p = detect.page(doc(f'<div class="cookies-accepted">{big}</div>'), "https://jane.test/")
        self.assertIn("Jane will fight for schools.", p["text"])

    def test_cloudflare_email_is_decoded(self):
        p = detect.page(doc('<a href="/cdn-cgi/l/email-protection#9bf3fef7f7f4dbf9feeff3f6faf8e2fdf4e9f8f4f5fce9fee8e8b5f8f4f6">x</a>'),
                        "https://jane.test/")
        self.assertEqual(p["links"][0]["href"], "mailto:hello@bethmacyforcongress.com")

    def test_paid_for_by_and_years(self):
        p = detect.page(doc("<p>Jane first ran in 2018.</p><footer>© 2025 Paid for by Friends of Jane Doe. All rights reserved.</footer>"),
                        "https://jane.test/")
        self.assertEqual(p["meta"]["paid_for_by"], "Paid for by Friends of Jane Doe")
        self.assertEqual(p["meta"]["years_mentioned"], ["2018"])

    def test_empty_document(self):
        with self.assertRaises(detect.EmptyDocument):
            detect.page("   ", "https://jane.test/")

    def test_snapshot_parts(self):
        p = detect.page(doc('<a href="/about?utm_medium=x&amp;id=2">About</a><img src="//cdn.test/a.png" alt="A">'),
                        "https://jane.test/")
        self.assertEqual(p["links"], [{"text": "About", "href": "https://jane.test/about?id=2"}])
        self.assertEqual(p["media"], ["alt://cdn.test/a.png|A", "img://cdn.test/a.png"])
        self.assertEqual(p["meta"]["title"], "Jane Doe")
        self.assertIn("https://jane.test/about?utm_medium=x&id=2", p["hrefs"])     # the crawler sees every link


if __name__ == "__main__":
    unittest.main(verbosity=2)
