"""data/community/report.html: what the sampled Reddit threads say about each platform.

    python3 -m annotationjobs.community report

Standard library only. Shares are weighted back to all posts of each month (the sample takes
the same number of threads every month, while forums are busier some months than others),
with 95% intervals (Wilson, on the Kish effective sample size).
"""

import collections
import datetime as dt
import hashlib
import html
import json
import math
import re

from .community import (LABEL_MODEL, LABEL_VERSION, LABELS, MEGA_COMMENTS, OUT, PER_MONTH, PLATFORMS, SAMPLE,
                        TOPICS, WINDOW)

COLORS = {"bad": "#d0543f", "mixed": "#e2a93b", "good": "#3f9a5e", "neutral": "#9aa3ad"}
STANCE_WORD = {"bad": "bad news", "mixed": "mixed", "good": "good news", "neutral": "question / fact only"}


def load(path, model=LABEL_MODEL):
    out = {}
    if path.exists():
        for line in path.read_text().splitlines():
            r = json.loads(line)
            if r["version"] == LABEL_VERSION and r["model"] == model:
                out[r["id"]] = r
    return out


def wilson(p, n, z=1.96):
    if n <= 0:
        return 0.0, 1.0
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def weighted_share(rows, hit):
    """Share of rows where hit(row) is true, each row weighted; returns (share, low, high, n)."""
    w = [r["weight"] for r in rows]
    if not w:
        return None
    total = sum(w)
    p = sum(r["weight"] for r in rows if hit(r)) / total
    n_eff = total * total / sum(x * x for x in w)
    lo, hi = wilson(p, n_eff)
    return p, lo, hi, len(rows)


def esc(s):
    return html.escape(str(s), quote=True)


def stance_bar(counts, width=150):
    total = sum(counts.values())
    if not total:
        return ""
    segs, x = [], 0.0
    for s in ("bad", "mixed", "neutral", "good"):
        w = width * counts.get(s, 0) / total
        if w:
            segs.append(f'<rect x="{x:.1f}" y="0" width="{w:.1f}" height="12" fill="{COLORS[s]}"/>')
        x += w
    tip = ", ".join(f"{STANCE_WORD[s]} {counts[s]:.0f}%" for s in ("bad", "mixed", "neutral", "good") if counts.get(s))
    return f'<svg width="{width}" height="12" role="img" aria-label="{esc(tip)}"><title>{esc(tip)}</title>{"".join(segs)}</svg>'


def main():
    sample = [json.loads(line) for line in SAMPLE.read_text().splitlines()]
    labels = load(LABELS)
    activity = json.loads((OUT / "activity.json").read_text())
    # weight: posts of that month and stratum represented by each sampled thread
    drawn = collections.Counter((r["platform"], r["month"], r["stratum"]) for r in sample)
    rows = []
    for r in sample:
        lab = labels.get(r["id"])
        if not lab:
            continue
        rows.append({**r, **lab, "weight": r["pool"] / drawn[(r["platform"], r["month"], r["stratum"])]})
    missing = len(sample) - len(rows)

    def kept(platform, stratum):
        return [r for r in rows if r["platform"] == platform and r["stratum"] == stratum
                and r["about_platform"] and not r["promotional"]]

    plats = list(PLATFORMS)
    parts = []
    months = sorted({m for p in plats for m in activity[p]})
    # --- activity
    act_rows = "".join(
        f"<tr><th>{esc(p)}</th>" + "".join(
            f"<td>{activity[p].get(m, {}).get('ordinary', 0) + activity[p].get(m, {}).get('mega', 0):,}</td>" for m in months)
        + f"<td class=sub>{', '.join('r/' + s for s in PLATFORMS[p])}</td></tr>" for p in plats)
    parts.append(f"""<h2>How busy each forum was</h2>
<p>New posts per month, all of each platform's forums together (every post was counted).</p>
<table class=act><tr><th></th>{''.join(f'<th>{dt.date.fromisoformat(m + "-01"):%b}</th>' for m in months)}<th>Forums</th></tr>{act_rows}</table>""")

    # --- removals: what the forums take down shapes what can be read
    rem_rows = []
    for p in plats:
        ss = [r for r in sample if r["platform"] == p and r["stratum"] == "ordinary"]
        weighted = [{**r, "weight": r["pool"] / drawn[(p, r["month"], "ordinary")]} for r in ss]

        def pct(hit, weighted=weighted):
            s = weighted_share(weighted, hit)
            return f"{100 * s[0]:.0f}%<div class=ci>{100 * s[1]:.0f}–{100 * s[2]:.0f}</div>"
        rem_rows.append(f"<tr><th>{esc(p)}</th><td>{pct(lambda r: r['removed'] == 'moderator')}</td>"
                        f"<td>{pct(lambda r: r['removed'] in ('reddit', 'automod_filtered', 'content_takedown'))}</td>"
                        f"<td>{pct(lambda r: r['removed'] == 'deleted')}</td><td>{pct(lambda r: r.get('text_lost'))}</td></tr>")
    parts.append(f"""<h2>How much the forums remove</h2>
<p>Share of posts later taken down, from the sample. A removed post usually disappears from Reddit; the
archive often saved it first. When its text was lost, the title is still read (it often says enough:
“No tasks, anyone in the same boat?”). A forum that removes many posts of one kind shows less of it.</p>
<table class=act><tr><th></th><th>Removed by moderators</th><th>Removed by Reddit's or the forum's filters</th>
<th>Deleted by the author</th><th>Text lost, title only</th></tr>{''.join(rem_rows)}</table>""")

    # --- main table
    head = "".join(f"<th colspan=2>{esc(p)}<div class=sub>n = {len(kept(p, 'ordinary'))} threads</div></th>" for p in plats)
    body = []
    for key, (name, desc) in TOPICS.items():
        cells = []
        for p in plats:
            ks = kept(p, "ordinary")
            s = weighted_share(ks, lambda r, key=key: any(t["topic"] == key for t in r["topics"]))
            if not s:
                cells.append("<td></td><td></td>")
                continue
            share, lo, hi, _ = s
            hits = [r for r in ks if any(t["topic"] == key for t in r["topics"])]
            tw = sum(r["weight"] for r in hits) or 1
            counts = {st: 100 * sum(r["weight"] for r in hits for t in r["topics"] if t["topic"] == key and t["stance"] == st) / tw
                      for st in COLORS}
            cells.append(f'<td class=num><b>{100 * share:.0f}%</b><div class=ci>{100 * lo:.0f}–{100 * hi:.0f}</div></td>'
                         f'<td>{stance_bar(counts)}<div class=ci>{len(hits)} threads</div></td>')
        body.append(f"<tr><th>{esc(name)}<div class=sub>{esc(desc)}</div></th>{''.join(cells)}</tr>")
    parts.append(f"""<h2>What people talk about, and whether it is good or bad news</h2>
<p>For each topic: the share of threads that discuss it (with its 95% range), and how what is said
splits: <span class=k style="background:{COLORS['bad']}"></span>bad news for workers,
<span class=k style="background:{COLORS['mixed']}"></span>mixed,
<span class=k style="background:{COLORS['neutral']}"></span>only a question or a fact,
<span class=k style="background:{COLORS['good']}"></span>good news. Hover a bar for the numbers.
Ordinary threads only; threads not about the platform and adverts are left out.</p>
<table class=main><tr><th></th>{head}</tr>{''.join(body)}</table>""")

    # --- megathreads
    mega_cells = []
    for p in plats:
        ms = kept(p, "mega")
        if not ms:
            mega_cells.append(f"<tr><th>{esc(p)}</th><td>none found in the window</td></tr>")
            continue
        c = collections.Counter((t["topic"], t["stance"]) for r in ms for t in r["topics"])
        top = collections.Counter(t["topic"] for r in ms for t in r["topics"]).most_common(5)
        desc = "; ".join(f"{TOPICS[k][0]} ({n} of {len(ms)}, {c[(k, 'bad')]} bad news)" for k, n in top)
        pool = sum(activity[p][m]["mega"] for m in activity[p])
        mega_cells.append(f"<tr><th>{esc(p)}</th><td>{len(ms)} read of {pool} in the window. Topics: {esc(desc) or 'none'}</td></tr>")
    parts.append(f"""<h2>Recurring and moderator threads</h2>
<p>Megathreads, daily or weekly threads and moderator posts, where a forum gathers one subject in one place
(on r/outlier_ai: a weekly “Aether Removal” thread, a weekly Aether task thread, daily threads in June and July).
One per month was read (up to {MEGA_COMMENTS} random comments of it), and they are kept out of the table above
because one such thread is many people at once.</p><table class=mega>{''.join(mega_cells)}</table>""")

    # --- quotes per platform
    for p in plats:
        ks = kept(p, "ordinary") + kept(p, "mega")
        blocks = []
        for key, (name, _) in TOPICS.items():
            items = [(r, t) for r in ks for t in r["topics"] if t["topic"] == key and t["quote_found"] and t["stance"] != "neutral"]
            if not items:
                continue
            # first-hand reports first; otherwise a fixed random order, so quotes spread over the months
            items.sort(key=lambda rt: (not rt[1]["firsthand"], hashlib.sha1((rt[0]["id"] + key).encode()).hexdigest()))
            pick, seen = [], set()
            for want in ("bad", "good", "mixed", "bad", "good"):
                for r, t in items:
                    if t["stance"] == want and r["id"] not in seen:
                        pick.append((r, t))
                        seen.add(r["id"])
                        break
            lis = "".join(
                f'<li><span class=dot style="background:{COLORS[t["stance"]]}"></span>“{esc(t["quote"])}” '
                f'<a href="https://www.reddit.com{esc(r["permalink"])}" target=_blank rel=noopener>r/{esc(r["subreddit"])}, '
                f'{dt.datetime.fromtimestamp(r["created_utc"], dt.timezone.utc):%b %Y}</a></li>' for r, t in pick[:4])
            nb = collections.Counter(t["stance"] for _, t in items)
            blocks.append(f"<h4>{esc(name)} <span class=sub>{nb['bad']} bad, {nb['mixed']} mixed, {nb['good']} good</span></h4><ul>{lis}</ul>")
        parts.append(f"<details><summary><h2 style='display:inline'>{esc(p)}: what people say</h2></summary>{''.join(blocks)}</details>")

    # --- agreement with a second model
    agree = agreement(rows)
    if agree:
        parts.append(agree)

    # --- method and limits
    n_quotes = sum(1 for r in rows for t in r["topics"])
    n_found = sum(1 for r in rows for t in r["topics"] if t["quote_found"])
    n_removed = sum(1 for r in rows if r.get("removed"))
    n_off = sum(1 for r in rows if not r["about_platform"])
    n_promo = sum(1 for r in rows if r["promotional"])
    parts.append(f"""<h2>How this was made, and its limits</h2><ul>
<li><b>Source.</b> Each platform's own Reddit forums, {WINDOW[0]} to {WINDOW[1]}, read through the Arctic Shift archive
of Reddit (Reddit itself blocks scripts). Glassdoor, Indeed and Trustpilot block automated reading and are not included.
General forums such as r/WorkOnline could not be searched reliably and are not included either.</li>
<li><b>Sample.</b> Every post of the window was listed, then {PER_MONTH} ordinary threads per platform per month were drawn at
random, with all their comments. Shares are weighted back to how busy each month was.</li>
<li><b>Reading.</b> A language model ({esc(LABEL_MODEL.split(':')[-1])}) read each thread and listed the topics it discusses, whether
what is said is good or bad news for workers, and a quote. {n_found} of {n_quotes} quotes were found word for word in the
thread; only those are shown. {n_off} threads were not about the platform and {n_promo} were adverts; both are left out.
{missing} sampled threads are not sorted yet.</li>
<li><b>Who posts.</b> People write when something goes wrong far more than when things are fine, so “bad news” shares
are high everywhere. Compare platforms with each other and over time, not against zero.</li>
<li><b>Forum rules shape what is said.</b> r/outlier_ai's rules remove complaints that do not ask anything and repeated
questions (no venting thread was posted in these months). r/dataannotation forbids sharing pay and project names.
Removed posts stay in the sample: {n_removed} of {len(sample)} sampled threads were later removed, most often by
moderators on DataAnnotation and Outlier and by Reddit's automatic spam filter on Mercor (it catches ordinary posts from
new accounts too). See “How much the forums remove”.</li>
<li><b>Referral spam.</b> Mercor and micro1 pay people for sign-ups, so some praise is advertising; posts that mainly advertise
are left out, but referral-motivated comments can remain.</li>
<li><b>Votes are not used:</b> the archive saved them seconds after posting (sometimes again a day later), so they are
near zero.</li>
<li>The thread texts are kept off git (other people's words): <code>/mnt/bulk/lilly/annotationjobs/community/</code>.</li>
</ul>""")

    page = f"""<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>What workers say on Reddit — pilot</title>
<style>
body{{font:15px/1.5 system-ui,sans-serif;max-width:1150px;margin:2em auto;padding:0 1em;color:#222}}
h1{{margin-bottom:.2em}} h2{{margin-top:1.6em}} h4{{margin:1em 0 .3em}}
table{{border-collapse:collapse;width:100%}} th,td{{padding:6px 8px;border-bottom:1px solid #e4e4e4;text-align:left;vertical-align:top}}
.main th[colspan]{{text-align:center;border-left:1px solid #ddd}} .num{{text-align:right;border-left:1px solid #ddd;white-space:nowrap}}
.sub{{font-weight:normal;color:#777;font-size:12px}} .ci{{color:#888;font-size:11px}} .act td{{text-align:right}} .act td.sub{{text-align:left}}
.k,.dot{{display:inline-block;width:10px;height:10px;border-radius:2px;margin:0 3px 0 6px}} .dot{{border-radius:50%;margin-left:0}}
ul{{padding-left:1.2em}} li{{margin:.3em 0}} details{{margin:1em 0;border-top:1px solid #ddd;padding-top:.5em}} summary{{cursor:pointer}}
a{{color:#2a62b8}} .lead{{color:#555}}
@media (prefers-color-scheme:dark){{body{{background:#161718;color:#ddd}} th,td{{border-color:#333}} a{{color:#7aa7ef}}}}
</style>
<h1>What workers say on Reddit</h1>
<p class=lead>Pilot on three platforms. A random sample of threads from each platform's own Reddit forums,
{dt.date.fromisoformat(WINDOW[0]):%B %Y} to {dt.date.fromisoformat(WINDOW[1]) - dt.timedelta(days=1):%B %Y}, read and sorted by topic. Built {dt.date.today():%Y-%m-%d}.</p>
{''.join(parts)}
</html>"""
    (OUT / "report.html").write_text(page)
    print(f"report: {len(rows)} sorted threads -> {(OUT / 'report.html')}")
    return 0


def agreement(rows):
    """How often a second model, reading the same threads, finds the same topics and stances."""
    import glob
    from pathlib import Path

    out = []
    for f in sorted(glob.glob(str(OUT / "labels-*.jsonl"))):
        model = re.sub(r"^labels-|\.jsonl$", "", Path(f).name)
        other = {}
        for line in Path(f).read_text().splitlines():
            r = json.loads(line)
            if r["version"] == LABEL_VERSION:
                other[r["id"]] = r
        both = [r for r in rows if r["id"] in other]
        if not both:
            continue
        a_pairs = b_pairs = same_topic = 0
        for r in both:
            a = {t["topic"]: t["stance"] for t in r["topics"]}
            b = {t["topic"]: t["stance"] for t in other[r["id"]]["topics"]}
            a_pairs += len(a)
            b_pairs += len(b)
            common = set(a) & set(b)
            same_topic += len(common)
        exact = sum(1 for r in both for t in r["topics"] if t["topic"] in {x["topic"] for x in other[r["id"]]["topics"]}
                    and {x["topic"]: x["stance"] for x in other[r["id"]]["topics"]}[t["topic"]] == t["stance"])
        badness = [(t["stance"] == "bad", {x["topic"]: x["stance"] for x in other[r["id"]]["topics"]}[t["topic"]] == "bad")
                   for r in both for t in r["topics"] if t["topic"] in {x["topic"] for x in other[r["id"]]["topics"]}]
        bad_agree = sum(1 for x, y in badness if x == y)
        out.append(f"<li><b>{esc(model)}</b> read {len(both)} of the same threads. Of the topics the main model listed, "
                   f"it also listed {same_topic} of {a_pairs} ({100 * same_topic / max(1, a_pairs):.0f}%); it listed "
                   f"{b_pairs - same_topic} the main model did not. On topics both listed, they gave the same stance "
                   f"{exact} times of {same_topic} ({100 * exact / max(1, same_topic):.0f}%), and agreed on “bad news or not” "
                   f"{bad_agree} of {len(badness)} ({100 * bad_agree / max(1, len(badness)):.0f}%).</li>")
    if not out:
        return ""
    return ("<h2>Check: a second model reading the same threads</h2><p>No answers were written by hand, so this is "
            "agreement between two readers, not measured accuracy. Most disagreements are calls between “only a question” "
            "and “bad news”.</p><ul>" + "".join(out) + "</ul>")


if __name__ == "__main__":
    raise SystemExit(main())
