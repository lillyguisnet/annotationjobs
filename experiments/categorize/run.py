# /// script
# requires-python = ">=3.11"
# dependencies = ["lm15==1.5.0"]
# ///
"""Sort a sample of open jobs into field / languages / task with several models.

    uv run experiments/categorize/run.py --sample a     # the 30 jobs the categories were tuned on
    uv run experiments/categorize/run.py --sample b     # 30 fresh jobs, none of sample a

A sample is drawn once into sample-<x>.jsonl (2 jobs per old keyword field, seeded;
sample b leaves out sample a's jobs), so every model sees the same jobs. Each answer is
one line of answers-<version>.jsonl (version from taxonomy.py); a job
already answered by a model is skipped, so running again resumes and costs nothing.
Calls go to our ChatGPT, Claude and Muse Code plans only (llm.py).
"""

import argparse
import json
import random
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from lm15 import Config, Message, Reasoning, Request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT)]
from llm import router_for  # noqa: E402
from taxonomy import FIELDS, TASKS, VERSION, prompt  # noqa: E402

from annotationjobs.groups import field as keyword_field  # noqa: E402

SEEDS = {"a": 2026, "b": 2027}

# Latest name each plan answered to on 2026-11-10 (probe.py), at each model's lowest
# thinking setting (the levels segbench measured: models/THINKING there).
MODELS = {
    "muse-ember": ("meta:muse-ember-1.0", {"reasoning": Reasoning(effort="minimal")}),
    "haiku": ("claude-code:claude-haiku-5-5", {"extensions": {"thinking": {"type": "disabled"}}}),
    "opus": ("claude-code:claude-opus-5-5", {"reasoning": Reasoning(effort="low")}),
    "luna": ("openai-codex:gpt-6-luna", {"reasoning": Reasoning(effort="off")}),
    "terra": ("openai-codex:gpt-6.1-terra", {"reasoning": Reasoning(effort="off")}),
}
NO_TOKEN_CEILING = {"openai-codex"}  # the Codex backend refuses a reply ceiling
THREADS_PER_PLAN = 4


def draw_sample(per_field: int, seed: int, leave_out: set) -> list[dict]:
    jobs = json.loads((ROOT / "docs/data/jobs.json").read_text())["jobs"]
    listings = {}
    for f in sorted((ROOT / "data/listings").glob("*.jsonl")):
        for line in f.open():
            r = json.loads(line)
            listings[r["uid"]] = r
    by_field = defaultdict(list)
    for j in sorted(jobs, key=lambda j: j["id"]):
        if j["id"] in listings and j["id"] not in leave_out and (listings[j["id"]].get("text") or "").strip():
            by_field[keyword_field(j["t"])].append(j["id"])
    rng = random.Random(seed)
    rows = []
    for name in sorted(by_field):
        for uid in rng.sample(by_field[name], min(per_field, len(by_field[name]))):
            r = listings[uid]
            rows.append({"uid": uid, "site": r["site"], "title": r["title"].strip(), "url": r["url"],
                         "keyword_field": name, "text": r["text"]})
    return rows


def parse(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise ValueError("no JSON object in the reply")
    a = json.loads(m.group(0))
    problems = []
    if a.get("field") not in FIELDS:
        problems.append(f"field {a.get('field')!r} not in the list")
    if a.get("task") not in TASKS:
        problems.append(f"task {a.get('task')!r} not in the list")
    for key in ("languages", "varieties", "field_evidence", "languages_evidence", "task_evidence"):
        if not isinstance(a.get(key), list):
            problems.append(f"{key} is not a list")
    a["problems"] = problems
    return a


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def quotes_found(quotes, row: dict) -> list[bool]:
    """Each evidence passage: is it really in the listing (title + text)?"""
    quotes = quotes if isinstance(quotes, list) else [quotes]
    listing = norm(row["title"] + " " + row["text"])
    return [norm(q) in listing for q in quotes if norm(q)]


def ask(model: str, row: dict) -> dict:
    route, settings = MODELS[model]
    if route.split(":")[0] not in NO_TOKEN_CEILING:
        settings = {"max_tokens": 4000, **settings}
    rec = {"model": model, "route": route, "uid": row["uid"], "version": VERSION}
    start = time.perf_counter()
    try:
        request = Request(model=route, messages=(Message.user(prompt(row["site"], row["title"], row["text"])),),
                          config=Config(**settings))
        response = router_for(route).complete(request)
        rec["reply"] = response.text
        rec["usage"] = {"input": response.usage.input_tokens, "output": response.usage.output_tokens}
        rec["answer"] = parse(response.text)
        rec["quotes_found"] = {k: quotes_found(rec["answer"].get(k + "_evidence"), row)
                               for k in ("field", "languages", "task")}
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
    rec["seconds"] = round(time.perf_counter() - start, 2)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2, help="jobs per old keyword field")
    ap.add_argument("--sample", choices=sorted(SEEDS), default="a")
    ap.add_argument("--models", default=",".join(MODELS))
    args = ap.parse_args()
    sample = HERE / f"sample-{args.sample}.jsonl"
    if not sample.exists():
        leave_out = {json.loads(l)["uid"] for x in SEEDS if x < args.sample for l in (HERE / f"sample-{x}.jsonl").open()}
        rows = draw_sample(args.n, SEEDS[args.sample], leave_out)
        sample.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    rows = [json.loads(line) for line in sample.open()]
    ANSWERS = HERE / f"answers-{VERSION}.jsonl"
    done = set()
    if ANSWERS.exists():
        for line in ANSWERS.open():
            r = json.loads(line)
            if "error" not in r:
                done.add((r["model"], r["uid"]))
        # failed calls are dropped so they are asked again
        ANSWERS.write_text("".join(l for l in ANSWERS.open() if "error" not in json.loads(l)))
    todo = [(m, r) for m in args.models.split(",") for r in rows if (m, r["uid"]) not in done]
    print(f"{len(rows)} jobs, {len(todo)} calls to make")
    pools = defaultdict(list)
    for m, r in todo:
        pools[MODELS[m][0].split(":")[0]].append((m, r))
    executors = {plan: ThreadPoolExecutor(THREADS_PER_PLAN) for plan in pools}  # at most 4 calls per plan at once
    with ANSWERS.open("a") as out:
        futures = [executors[plan].submit(ask, m, r) for plan, jobs in pools.items() for m, r in jobs]
        for f in futures:
            rec = f.result()
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            print(rec["model"], rec["uid"][:40], rec.get("error") or rec["answer"].get("field"), rec["seconds"])


if __name__ == "__main__":
    main()
