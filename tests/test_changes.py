"""Change records (issue #9) and step-0 noise rules (issue #10), on hand-made snapshots.

The end-to-end checks (records written by the daily run) are in test_daily_run.py; the labelled-corpus
check is in test_parser_corpus.py.
"""
import importlib.util, os, unittest

M = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "monitor")


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(M, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod


changes, step0 = load("changes"), load("step0")
URL = "https://janedoe.test/"


def snap(lines=(), links=(), media=(), url=URL, fmt=3, **meta):
    return {"lines": list(lines), "links": [tuple(l) for l in links], "media": list(media),
            "meta": {"format": fmt, "final_url": url, "title": "Jane Doe", "description": "", "paid_for_by": "",
                     "years_mentioned": [], **meta}}


def rec(old, new, url=URL):
    c = changes.diff_pages(old, new)
    return None if c is None else changes.record("2026-10-09", "jane", "/", c, {})


class ChangeRecords(unittest.TestCase):
    def test_reworded_sentence(self):
        r = rec(snap(["A.", "B.", "C."]), snap(["A.", "B two.", "C."]))
        self.assertEqual(r["text"], {"removed": ["B."], "added": ["B two."]})
        self.assertEqual(r["kind"], "changed")

    def test_reordered_sentences_are_not_a_change(self):
        self.assertIsNone(rec(snap(["A.", "B."]), snap(["B.", "A."])))

    def test_donation_platform_switch_is_flagged(self):
        r = rec(snap(links=[("Donate", "https://secure.actblue.com/donate/jane")]),
                snap(links=[("Donate", "https://secure.winred.com/jane")]))
        self.assertEqual(r["links"]["removed"], [{"text": "Donate", "href": "https://secure.actblue.com/donate/jane"}])
        self.assertEqual(r["links"]["donation_links_changed"],
                         ["https://secure.actblue.com/donate/jane", "https://secure.winred.com/jane"])

    def test_metadata_changes(self):
        r = rec(snap(["A."], paid_for_by="Paid for by Friends of Jane"),
                snap(["A."], paid_for_by="Paid for by Jane Doe for House"))
        self.assertEqual(r["meta"], {"paid_for_by": {"before": "Paid for by Friends of Jane",
                                                     "after": "Paid for by Jane Doe for House"}})

    def test_added_and_removed_pages(self):
        self.assertEqual(rec(None, snap(["New."]))["kind"], "added")
        r = rec(snap(["Old."]), None)
        self.assertEqual((r["kind"], r["text"]["removed"]), ("removed", ["Old."]))

    def test_format_rewrite_is_not_a_change(self):
        self.assertIsNone(rec(snap(["A."], fmt=2), snap(["A. B."])))

    def test_record_has_the_spec_fields(self):
        r = rec(snap(["A."]), snap(["B."]))
        for k in ("change_id", "date", "site_id", "page", "candidate_uids", "office_tier", "state", "text", "links",
                  "media", "meta", "wayback", "step0", "step1", "step2", "review"):
            self.assertIn(k, r)
        self.assertEqual(r["wayback"], {"before": None, "after": None})


class SiteWide(unittest.TestCase):
    def test_edit_on_three_pages_becomes_one_sitewide_record(self):
        footer_old, footer_new = "Paid for by Friends of Jane.", "Paid for by Jane Doe for House."
        cs = {("jane", p): changes.diff_pages(snap([f"{p} text.", footer_old]), snap([f"{p} text.", footer_new]))
              for p in ("/", "about-1", "issues-2")}
        cs[("jane", "news-3")] = changes.diff_pages(snap(["Old news.", footer_old]), snap(["New news.", footer_new]))
        g = changes.group_sitewide(cs)
        self.assertEqual(set(g), {("jane", "*"), ("jane", "news-3")})
        sw = g[("jane", "*")]
        self.assertEqual((sw["kind"], sw["pages"]), ("sitewide", ["/", "about-1", "issues-2", "news-3"]))
        self.assertEqual(sw["text"], {"removed": [footer_old], "added": [footer_new]})
        self.assertEqual(g[("jane", "news-3")]["text"], {"removed": ["Old news."], "added": ["New news."]})

    def test_unrelated_sitewide_edits_keep_their_own_pages(self):
        cs = {("jane", p): changes.diff_pages(snap(["Menu A.", "x."]), snap(["Menu B.", "x."])) for p in ("a-1", "b-2", "c-3")}
        cs.update({("jane", p): changes.diff_pages(snap(["Footer A."]), snap(["Footer B."])) for p in ("d-4", "e-5", "f-6")})
        g = changes.group_sitewide(cs)
        self.assertEqual(set(g), {("jane", "*")})
        sw = g[("jane", "*")]
        self.assertEqual(sw["pages"], ["a-1", "b-2", "c-3", "d-4", "e-5", "f-6"])
        where = {(i["side"], i["value"]): i["pages"] for i in sw["item_pages"]}
        self.assertEqual(where[("added", "Menu B.")], ["a-1", "b-2", "c-3"])
        self.assertEqual(where[("added", "Footer B.")], ["d-4", "e-5", "f-6"])

    def test_edit_on_two_pages_stays_per_page(self):
        cs = {("jane", p): changes.diff_pages(snap(["A."]), snap(["B."])) for p in ("/", "about-1")}
        self.assertEqual(set(changes.group_sitewide(cs)), {("jane", "/"), ("jane", "about-1")})

    def test_added_pages_are_not_folded(self):
        cs = {("jane", p): changes.diff_pages(None, snap(["Same footer."])) for p in ("a-1", "b-2", "c-3")}
        self.assertEqual(set(changes.group_sitewide(cs)), set(cs))


class StepZero(unittest.TestCase):
    def check(self, old, new, discard, reason=None, rules=None):
        r = step0.apply(rec(old, new), rules)
        self.assertEqual(r["step0"]["discard"], discard, r["step0"])
        if reason:
            self.assertIn(reason, r["step0"]["reasons"])
        return r

    def test_like_and_cart_counters(self):
        self.check(snap(["124 likes", "Cart (2)"]), snap(["131 likes", "Cart (3)"]), True, "counters")

    def test_counter_rule_keeps_content(self):
        self.check(snap(["Vote Nov 3"]), snap(["Vote Nov 4"]), False)
        self.check(snap(["Jane has 3 children and 2 dogs."]), snap(["Jane has 3 children and 3 dogs."]), False)
        self.check(snap(["124 likes", "Jane supports schools."]), snap(["131 likes", "Jane supports clinics."]), False)

    def test_calendar_dates_only_on_calendar_pages(self):
        cal = "https://janedoe.test/events/today/"
        self.check(snap(["Events for Thursday, October 8"], url=cal), snap(["Events for Friday, October 9"], url=cal),
                   True, "calendar_dates")
        self.check(snap(["Early voting ends November 1"]), snap(["Early voting ends November 2"]), False)

    def test_social_feed_posts(self):
        self.check(snap(links=[("", "https://www.instagram.com/p/AAA111/")], media=["img://scontent.cdninstagram.com/a.jpg"]),
                   snap(links=[("", "https://www.instagram.com/p/BBB222/")], media=["img://scontent.cdninstagram.com/b.jpg"]),
                   True, "social_feed")

    def test_new_posts_in_a_list_are_kept(self):
        old = [("Fall festival recap", "https://janedoe.test/news/fall-festival"), ("Town hall", "https://janedoe.test/news/town-hall")]
        new = [("Debate night", "https://janedoe.test/news/debate"), ("Endorsed by teachers", "https://janedoe.test/news/teachers")]
        self.check(snap([t for t, _ in old], old), snap([t for t, _ in new], new), False)

    def test_menu_change_is_kept(self):
        self.check(snap(links=[("Issues", "https://janedoe.test/issues")]),
                   snap(links=[("Issues", "https://janedoe.test/issues"), ("Jobs", "https://janedoe.test/jobs")]), False)
        self.check(snap(links=[("Issues", "https://janedoe.test/issues")]),
                   snap(links=[("Priorities", "https://janedoe.test/issues")]), False)

    def test_signed_image_urls(self):
        self.check(snap(media=["img://lh3.googleusercontent.com/abc"]), snap(media=["img://lh3.googleusercontent.com/def"]),
                   True, "signed_media")

    def test_one_time_url_tokens(self):
        old = "Join today https://jane.test/wp-login.php?action=logout&_wpnonce=1a2b3c4d5e"
        self.check(snap([old], [("Log out", "https://jane.test/wp-login.php?action=logout&_wpnonce=1a2b3c4d5e")]),
                   snap([old.replace("1a2b3c4d5e", "9f8e7d6c5b")], [("Log out", "https://jane.test/wp-login.php?action=logout&_wpnonce=9f8e7d6c5b")]),
                   True, "url_tokens")
        self.check(snap(links=[("Donate", "https://secure.actblue.com/donate/jane?refcode=a")]),
                   snap(links=[("Donate", "https://secure.winred.com/jane?refcode=a")]), False)

    def test_site_rule(self):
        import re
        rules = {"jane": [("text", re.compile(r"^Weather in Dayton"), "weather widget")]}
        self.check(snap(["Weather in Dayton: 61F"]), snap(["Weather in Dayton: 58F"]), True, "site_rule: weather widget", rules)

    def test_added_and_removed_pages_are_never_discarded(self):
        r = step0.apply(rec(None, snap(["124 likes"])))
        self.assertFalse(r["step0"]["discard"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
