"""What workers say about each platform on Reddit: a random sample of threads, sorted by topic.

    python3 -m annotationjobs.community list      # every post of the window in each forum (slow, polite)
    python3 -m annotationjobs.community sample    # draw the sample and fetch its threads with comments
    uv run --no-project --with lm15==1.5.0 python -m annotationjobs.community label   # sort them
    python3 -m annotationjobs.community report    # data/community/report.html

Reddit refuses scripts, so posts and comments come from the Arctic Shift archive of Reddit
(arctic-shift.photon-reddit.com), a free service run by one volunteer: one request at a
time, a pause between requests, longer pauses when it says it is busy.

Design (why, not only what):
- The forums are each platform's own subreddits. Keyword search in big general forums
  (r/WorkOnline, r/beermoney) times out on the archive, so they are not covered.
- Every post of the window is listed first: monthly activity is then a count, not a guess,
  and the sample is a true random draw (fixed seed, so it can be redrawn identically) of 5%
  of each month's threads, so busier months get more.
- Recurring threads (venting, weekly/daily threads, megathreads, moderator posts) are a separate stratum. r/outlier_ai removes stand-alone
  complaint posts and sends them to its weekly venting thread; mixing that thread into a
  uniform draw would hide most complaints, counting each of its comments as a thread would
  swamp everything else. Their numbers are shown on their own line.
- The archive often keeps the text of posts that moderators later removed; they stay in the
  sample, marked. Posts whose text was lost keep only their title.
- Votes are saved by the archive seconds after posting (sometimes refreshed a day later), so
  they are near zero and not used.

Thread texts stay on the bulk disk (not in git): they are other people's words. Only the
labels, short checked quotes and links are kept in data/community/.
"""

import argparse
import collections
import datetime as dt
import hashlib
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .common import UA

API = "https://arctic-shift.photon-reddit.com/api"
WINDOW = ("2026-05-01", "2026-11-01")  # [start, end) in UTC
PLATFORMS = {  # platform -> its own forums
    "Outlier": ["outlier_ai"],
    "DataAnnotation": ["DataAnnotationTech", "dataannotation"],
    "Mercor": ["mercor_ai", "mercorai_workers", "Mercor_contractors"],
}
SHARE = 0.05  # share of each month's ordinary threads read, per platform (more in busier months)
PILOT_PER_MONTH = 20  # the pilot's draw (2026-11-11), kept as the start of the sample: see draw()
MEGA_PER_MONTH = 1  # recurring / moderator threads read per platform per month
MEGA_COMMENTS = 80  # comments read from one megathread (a random subset)
MAX_CHARS = 30000  # thread text given to the model; longer threads lose their last comments
SEED = 20261111
MEGA = re.compile(r"mega ?thread|\bvent(ing)?\b.*\bthread\b|\b(daily|weekly|monthly)\b.*\b(thread|discussion)\b"
                  r"|\b(thread|discussion)\b.*\b(daily|weekly|monthly)\b", re.I)
BOTS = {"AutoModerator", "[deleted]"}

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "community"
BULK = Path("/mnt/bulk/lilly/annotationjobs/community")
POSTS = BULK / "posts"  # <subreddit>.jsonl: every post of the window
THREADS = BULK / "threads"  # <post id>.json: post + comments as read by the model
SAMPLE = OUT / "sample.jsonl"
LABELS = OUT / "labels.jsonl"


# --- the archive, politely ----------------------------------------------------------------

_last = [0.0]
GAP = 5.0  # seconds between two requests (shorter gaps get "slow down" answers)


def get(path, **params):
    """GET one archive endpoint; waits and retries while the archive says it is busy."""
    url = f"{API}/{path}?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    for attempt in range(8):
        wait = _last[0] + GAP - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA + " annotationjobs-research"})
            with urllib.request.urlopen(req, timeout=120) as r:
                body = r.read()
        except urllib.error.HTTPError as e:
            body = e.read()
            if e.code not in (422, 429, 500, 502, 503, 504):
                raise RuntimeError(f"{e.code} {body[:200]!r} for {url}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            body = json.dumps({"error": f"network: {e}"}).encode()
        try:
            j = json.loads(body)
        except json.JSONDecodeError:
            j = {"error": f"not JSON: {body[:100]!r}"}
        if j.get("data") is not None and not j.get("error"):
            return j["data"]
        pause = min(300, 30 * 2 ** attempt)
        print(f"    archive busy ({j.get('error')}); waiting {pause}s", file=sys.stderr)
        time.sleep(pause)
    raise RuntimeError(f"archive kept refusing {url}")


def epoch(day):
    return int(dt.datetime.fromisoformat(day).replace(tzinfo=dt.timezone.utc).timestamp())


def month_of(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m")


# --- 1. every post of the window ----------------------------------------------------------

POST_FIELDS = "id,created_utc,title,author,link_flair_text,distinguished"


def list_forum(sub):
    """All posts of the window in one subreddit, oldest first. Resumes a partial file."""
    path = POSTS / f"{sub}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    seen, after = set(), epoch(WINDOW[0])
    if path.exists():
        for line in path.read_text().splitlines():
            p = json.loads(line)
            seen.add(p["id"])
            after = max(after, p["created_utc"] - 1)
    end = epoch(WINDOW[1])
    with path.open("a") as f:
        while True:
            page = get("posts/search", subreddit=sub, after=after, before=end, sort="asc", limit=100,
                       fields=POST_FIELDS)
            new = [p for p in page if p["id"] not in seen]
            for p in new:
                seen.add(p["id"])
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
            f.flush()
            if not page or not new:
                break
            after = page[-1]["created_utc"] - 1  # -1: posts sharing the last second are not lost
            print(f"  r/{sub}: {len(seen)} posts, up to {dt.datetime.fromtimestamp(page[-1]['created_utc'], dt.timezone.utc).date()}")
    (POSTS / f"{sub}.done").write_text(dt.datetime.now(dt.timezone.utc).isoformat())
    return len(seen)


def load_posts(sub):
    path = POSTS / f"{sub}.jsonl"
    if not (POSTS / f"{sub}.done").exists():
        raise SystemExit(f"r/{sub} is not fully listed yet: run `community list`")
    return [json.loads(line) for line in path.read_text().splitlines()]


def is_mega(p):
    """Recurring and moderator threads (megathreads, daily/weekly threads, venting, mod notices)."""
    return (bool(MEGA.search(p.get("title") or "")) or p.get("author") == "AutoModerator"
            or p.get("distinguished") == "moderator")


# --- 2. sample and fetch the threads ------------------------------------------------------

def draw():
    """The sample: SHARE of each month's ordinary threads (at least one) and MEGA_PER_MONTH
    recurring threads, per platform and month.

    Each month's posts are put in a random order and the first ones are taken. That order starts
    with the pilot's draw (PILOT_PER_MONTH random threads, same seed and calls as then) and goes
    on with the other posts in a seeded random order. A random set followed by a random choice
    among the rest is still a uniformly random sample, and the pilot's threads, already fetched
    and sorted, are reused.
    """
    rng = random.Random(SEED)

    def rest_order(post):
        return hashlib.sha1(f"{SEED}:{post['id']}".encode()).hexdigest()

    rows, activity = [], {}
    for platform, subs in PLATFORMS.items():
        by_month = collections.defaultdict(lambda: {"ordinary": [], "mega": []})
        for sub in subs:
            for p in load_posts(sub):
                p["subreddit"] = sub
                by_month[month_of(p["created_utc"])]["mega" if is_mega(p) else "ordinary"].append(p)
        activity[platform] = {m: {k: len(v) for k, v in g.items()} for m, g in sorted(by_month.items())}
        for m, g in sorted(by_month.items()):
            for stratum, n_pilot in (("ordinary", PILOT_PER_MONTH), ("mega", MEGA_PER_MONTH)):
                pool = sorted(g[stratum], key=lambda p: p["id"])
                first = rng.sample(pool, min(n_pilot, len(pool)))
                ids = {p["id"] for p in first}
                order = first + sorted((p for p in pool if p["id"] not in ids), key=rest_order)
                n = max(1, round(SHARE * len(pool))) if stratum == "ordinary" else MEGA_PER_MONTH
                for p in order[:n]:
                    rows.append({"platform": platform, "month": m, "stratum": stratum, "pool": len(pool),
                                 "id": p["id"], "subreddit": p["subreddit"], "title": p["title"]})
    return rows, activity


def flatten(children, out, depth=0):
    for c in children or []:
        if c.get("kind") != "t1":
            continue
        d = c["data"]
        out.append({"id": d["id"], "author": d.get("author"), "body": d.get("body") or "",
                    "created_utc": d.get("created_utc"), "depth": depth})
        replies = d.get("replies")
        if isinstance(replies, dict):
            flatten(replies.get("data", {}).get("children"), out, depth + 1)
    return out


def fetch_thread(row, rng, post=None):
    path = THREADS / f"{row['id']}.json"
    if path.exists():
        return json.loads(path.read_text())
    post = post or get("posts/ids", ids=row["id"])[0]
    tree = get("comments/tree", link_id="t3_" + row["id"], limit=9999)
    comments = [c for c in flatten(tree, []) if c["author"] not in BOTS and c["body"] not in ("[deleted]", "[removed]")]
    total = len(comments)
    if row["stratum"] == "mega" and total > MEGA_COMMENTS:
        keep = set(rng.sample(range(total), MEGA_COMMENTS))
        comments = [c for i, c in enumerate(comments) if i in keep]
    t = {"id": post["id"], "subreddit": post["subreddit"], "title": post["title"],
         "selftext": post.get("selftext") or "", "author": post.get("author"),
         "created_utc": post["created_utc"], "permalink": post.get("permalink"),
         # removed by moderators or Reddit, or deleted by its author (the archive often saved it first)
         "removed": (post.get("_meta") or {}).get("removal_type") or post.get("removed_by_category")
                    or ({"[removed]": "removed", "[deleted]": "deleted"}.get(post.get("selftext"))),
         "text_lost": post.get("selftext") in ("[removed]", "[deleted]"),
         "comments_total": total, "comments": comments}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(t, ensure_ascii=False))
    return t


def thread_text(t):
    """Numbered text the model reads: [P] the post, [C1].. comments in reading order."""
    parts = [f"[P] {t['title']}\n{t['selftext']}".strip()]
    for i, c in enumerate(t["comments"], 1):
        parts.append(f"[C{i}]{'  ' * min(c['depth'], 4)} {c['body'].strip()}")
    out, size = [], 0
    for p in parts:
        if size + len(p) > MAX_CHARS and out:
            out.append(f"[... {len(parts) - len(out)} more comments not shown]")
            break
        out.append(p)
        size += len(p) + 2
    return "\n\n".join(out)


# --- 3. topics ----------------------------------------------------------------------------

LABEL_VERSION = "c2"  # c2: posts whose text was removed are judged from their title
LABEL_MODEL = "openai-codex:gpt-6.1-terra"  # on our ChatGPT plan, thinking off
TOPICS = {  # key: (name in the report, what the model is told it covers)
    "getting_paid": ("Getting paid", "whether money arrives: on time, late, missing, held, payment methods, fees"),
    "pay_rate": ("Pay rate", "how much the work pays: rate levels, cuts, raises, bonuses, rate differences between people or countries"),
    "work_available": ("Enough work", "whether there are tasks or projects to do: steady work, dry spells, empty queues, projects ending, waiting for the next one"),
    "getting_in": ("Getting in", "applying, tests and assessments, interviews, onboarding courses, waiting to hear back, being accepted or rejected"),
    "removed": ("Removed or banned", "accounts deactivated, banned or suspended, being dropped from a project, usually and especially without explanation"),
    "reviews": ("Reviews & scoring", "how work is checked: quality scores, reviewer feedback, fairness of grading, being flagged"),
    "support": ("Support & communication", "help from support or staff, answers to questions, announcements, how the company communicates"),
    "time_rules": ("Time rules & unpaid time", "time limits per task, hour caps, how time is tracked or approved, unpaid time or work"),
    "the_work": ("The work itself", "what the tasks are like: interesting or tedious, clear or unclear instructions, tools and site bugs, stress, workload"),
    "trust": ("Trust & privacy", "whether the company is legitimate or a scam, ID checks, privacy, contracts, being an independent contractor, taxes"),
}
STANCES = ("good", "bad", "mixed", "neutral")


def prompt(platform, text):
    topics = "\n".join(f"- {k}: {v[1]}" for k, v in TOPICS.items())
    return f"""You read one Reddit thread from a forum about the AI-training work platform {platform}.
Say what it tells a person deciding whether to work for {platform}. Judge only what is said
about {platform}; ignore what is said about other platforms.

Topics:
{topics}

Answer with one JSON object, nothing else:
{{
  "about_platform": false only if the thread is clearly about something else (another platform,
                    unrelated work, off-topic); a post in this forum with only a title left counts as about {platform},
  "promotional": true if the post mainly advertises (a referral link, a course, a service, a job ad),
  "post_kind": "question" | "experience" | "news" | "advice" | "other"  (what the opening post mainly is),
  "topics": [
    {{
      "topic": one key from the list above,
      "stance": "good" if what is said is good news for workers on this topic, "bad" if bad news,
                "mixed" if people clearly disagree or report both, "neutral" if it is only a question or a fact,
      "firsthand": true if at least one person reports their own experience on this topic,
      "where": the labels of the parts that say it, e.g. ["P", "C3"],
      "quote": the sentence that best shows the stance on its own, copied word for word from one of
               those parts (at most 40 words),
      "summary": one plain sentence saying what was said
    }}
  ]
}}
List only topics the thread really discusses, each at most once, most important first. A topic
that is only mentioned in passing is not listed. An empty list is fine.

Many posts were removed and only their title is left (the text reads [removed] or [deleted]).
Then judge from the title: list the topic it clearly asks or tells about ("Account under review",
"No tasks, anyone else?", "Payout time"), quote the title, firsthand true only if the title says it
happened to the poster, stance "neutral" unless the title itself gives good or bad news
("Account deactivated" is bad news on removed). A vague title ("Genuine question") gets no topic.

Thread (P = opening post, C1.. = comments in reading order, indented by reply depth):

{text}"""


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[‘’]", "'", re.sub(r"[“”]", '"', s or ""))).strip().lower()


def parse_answer(reply_text, text):
    found = re.search(r"\{.*\}", reply_text or "", re.S)
    if not found:
        raise ValueError(f"no JSON in the reply: {(reply_text or '')[:200]!r}")
    a = json.loads(found.group(0))
    topics, seen = [], set()
    for t in a.get("topics") or []:
        if t.get("topic") not in TOPICS or t.get("stance") not in STANCES:
            raise ValueError(f"answer outside the lists: {t.get('topic')!r} / {t.get('stance')!r}")
        if t["topic"] in seen:
            continue
        seen.add(t["topic"])
        q = str(t.get("quote") or "").strip()
        topics.append({"topic": t["topic"], "stance": t["stance"], "firsthand": bool(t.get("firsthand")),
                       "where": [str(x) for x in (t.get("where") or [])], "quote": q,
                       "quote_found": bool(q) and norm(q) in norm(text), "summary": str(t.get("summary") or "")})
    return {"about_platform": bool(a.get("about_platform")), "promotional": bool(a.get("promotional")),
            "post_kind": str(a.get("post_kind") or "other"), "topics": topics}


def label(limit=None, model=LABEL_MODEL, store=LABELS, ids=None):
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from lm15 import Config, LMRouter, Message, Reasoning, Request, Timeouts
    from lm15.router import RouterConfig

    sample = [json.loads(line) for line in SAMPLE.read_text().splitlines()]
    done = set()
    if store.exists():
        for line in store.read_text().splitlines():
            r = json.loads(line)
            if r["version"] == LABEL_VERSION and r["model"] == model:
                done.add(r["id"])
    todo = [r for r in sample if r["id"] not in done and (ids is None or r["id"] in ids)][:limit]
    print(f"label: {len(sample)} threads in the sample, {len(todo)} to sort with {model}")
    # Plans only, never a pay-per-token key. Anthropic refuses newer models to the older Claude
    # Code release lm15 claims: same pin as experiments/categorize/llm.py.
    router = LMRouter(RouterConfig(timeouts=Timeouts(), settings={"claude-code": {"client_version": "2.1.314"}}))
    if model.split(":")[0] not in ("openai-codex", "claude-code"):
        raise SystemExit(f"{model}: not one of our plans")

    def one(row):
        t = json.loads((THREADS / f"{row['id']}.json").read_text())
        text = thread_text(t)
        start = time.perf_counter()
        cfg = Config(reasoning=Reasoning(effort="off" if model.startswith("openai-codex") else "low"))
        reply = router.complete(Request(model=model, messages=(Message.user(prompt(row["platform"], text)),), config=cfg))
        a = parse_answer(reply.text, text)
        return {"id": row["id"], "platform": row["platform"], "version": LABEL_VERSION, "model": model,
                "date": dt.date.today().isoformat(), **a, "seconds": round(time.perf_counter() - start, 1),
                "tokens": [reply.usage.input_tokens, reply.usage.output_tokens]}

    ok = failed = 0
    with store.open("a") as out, ThreadPoolExecutor(4) as pool:
        futures = {pool.submit(one, r): r for r in todo}
        for f in as_completed(futures):
            try:
                rec = f.result()
            except Exception as e:  # noqa: BLE001 - reported, asked again on the next run
                failed += 1
                print(f"  failed {futures[f]['id']}: {type(e).__name__}: {str(e)[:200]}", file=sys.stderr)
                continue
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            ok += 1
            if ok % 50 == 0:
                print(f"  {ok}/{len(todo)}")
    print(f"label: {ok} sorted, {failed} failed (run again to retry)")
    return 1 if failed else 0


# --- commands -----------------------------------------------------------------------------

def cmd_list(_):
    for subs in PLATFORMS.values():
        for sub in subs:
            if (POSTS / f"{sub}.done").exists():
                print(f"r/{sub}: already listed")
                continue
            print(f"r/{sub}: {list_forum(sub)} posts in {WINDOW[0]} .. {WINDOW[1]}")


def cmd_sample(_):
    rows, activity = draw()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "activity.json").write_text(json.dumps(activity, indent=1))
    rng = random.Random(SEED + 1)
    posts = {}
    need = [r["id"] for r in rows if not (THREADS / f"{r['id']}.json").exists()]
    for i in range(0, len(need), 100):  # the posts themselves, 100 per request
        posts.update({p["id"]: p for p in get("posts/ids", ids=",".join(need[i:i + 100]))})
    with SAMPLE.open("w") as f:
        for i, row in enumerate(rows, 1):
            t = fetch_thread(row, rng, posts.get(row["id"]))
            row.update({"permalink": t["permalink"], "removed": t["removed"], "text_lost": t["text_lost"], "created_utc": t["created_utc"],
                        "comments_total": t["comments_total"], "comments_read": len(t["comments"]),
                        "chars": len(thread_text(t))})
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            if i % 25 == 0:
                print(f"  {i}/{len(rows)} threads fetched")
    print(f"sample: {len(rows)} threads -> {SAMPLE.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sub.add_parser("sample")
    lp = sub.add_parser("label")
    lp.add_argument("--limit", type=int)
    lp.add_argument("--model", default=LABEL_MODEL)
    lp.add_argument("--ids", help="file with one thread id per line (only these)")
    sub.add_parser("report")
    a = ap.parse_args()
    if a.cmd == "list":
        return cmd_list(a)
    if a.cmd == "sample":
        return cmd_sample(a)
    if a.cmd == "label":
        ids = set(Path(a.ids).read_text().split()) if a.ids else None
        store = LABELS if a.model == LABEL_MODEL else OUT / f"labels-{re.sub(r'[^A-Za-z0-9.-]+', '_', a.model)}.jsonl"
        return label(a.limit, a.model, store, ids)
    if a.cmd == "report":
        from .community_report import main as report
        return report()


if __name__ == "__main__":
    sys.exit(main())
