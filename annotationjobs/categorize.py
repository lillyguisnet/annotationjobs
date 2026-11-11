"""Sort every open job into field, languages and kind of task with a language model.

    uv run --no-project --with lm15==1.5.0 python -m annotationjobs.categorize
    uv run --no-project --with lm15==1.5.0 python -m annotationjobs.categorize --limit 5   # a try

Asks GPT-6.1 Terra on our ChatGPT plan (the codex sign-in; never a pay-per-token key) about
each open job that has no answer for the current categories (annotationjobs/categories.py)
and appends the answers to data/categories.jsonl. Copies of one job with the same text are
asked once. A failed call or an answer outside the lists is not stored, so running again
asks only for what is missing. `collect` runs this after fetching.

Needs lm15, unlike the rest of the project (standard library only).
"""

import argparse
import collections
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from lm15 import Config, LMRouter, Message, Reasoning, Request

from .categories import FIELDS, MODEL, STORE, TASKS, VERSION, content_key, load, prompt
from .collect import all_listings

THREADS = 4  # calls at once on the plan
LIST_KEYS = ("languages", "varieties", "field_evidence", "languages_evidence", "task_evidence")


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()


def ask(router, listing):
    """One call; returns the record to store, or raises with the reason."""
    start = time.perf_counter()
    request = Request(model=MODEL, messages=(Message.user(prompt(listing)),),
                      config=Config(reasoning=Reasoning(effort="off")))
    reply = router.complete(request)
    found = re.search(r"\{.*\}", reply.text or "", re.S)
    if not found:
        raise ValueError(f"no JSON in the reply: {(reply.text or '')[:200]!r}")
    a = json.loads(found.group(0))
    if a.get("field") not in FIELDS or a.get("task") not in TASKS:
        raise ValueError(f"answer outside the lists: field {a.get('field')!r}, task {a.get('task')!r}")
    for k in LIST_KEYS:
        v = a.get(k) or []
        a[k] = [str(x) for x in (v if isinstance(v, list) else [v]) if str(x).strip()]
    text = norm(listing["title"] + " " + (listing.get("text") or ""))
    return {
        "key": content_key(listing), "uid": listing["uid"], "title": listing["title"].strip(),
        "version": VERSION, "model": MODEL, "date": date.today().isoformat(),
        "field": a["field"], "languages": a["languages"], "varieties": a["varieties"], "task": a["task"],
        # each evidence passage, and whether it is really in the listing (the page shows only those)
        **{k: [[q, norm(q) in text] for q in a[k]] for k in ("field_evidence", "languages_evidence", "task_evidence")},
        "seconds": round(time.perf_counter() - start, 2),
        "tokens": [reply.usage.input_tokens, reply.usage.output_tokens],
    }


def todo():
    """One listing per open job with no current answer, in the order the page picks them."""
    rows, _ = all_listings()
    groups = collections.defaultdict(list)
    for r in rows:
        if r["active"]:
            groups[r["group"]].append(r)
    labels = load()
    out, keys = [], set()
    for copies in groups.values():
        if any(content_key(c) in labels for c in copies):
            continue
        k = content_key(copies[0])
        if k not in keys:
            keys.add(k)
            out.append(copies[0])
    return out, len(groups)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="ask about at most this many jobs")
    a = ap.parse_args()
    jobs, total = todo()
    jobs = jobs[: a.limit] if a.limit else jobs
    print(f"categorize: {total} open jobs, {len(jobs)} to sort with {MODEL} (categories {VERSION})")
    if not jobs:
        return 0
    router = LMRouter()
    done = failed = 0
    with STORE.open("a") as out, ThreadPoolExecutor(THREADS) as pool:
        futures = {pool.submit(ask, router, j): j for j in jobs}
        for f in as_completed(futures):
            try:
                rec = f.result()
            except Exception as e:  # noqa: BLE001 - a failed job is reported and asked again next run
                failed += 1
                print(f"  failed: {futures[f]['uid']}: {type(e).__name__}: {str(e)[:200]}", file=sys.stderr)
                continue
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{len(jobs)} sorted")
    print(f"categorize: {done} sorted, {failed} failed (run again to retry) -> {STORE.relative_to(STORE.parent.parent)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
