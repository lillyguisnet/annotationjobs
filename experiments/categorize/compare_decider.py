"""How the local decision model's choices compare with the five chat models (sample b, v2 categories).

    python3 experiments/categorize/compare_decider.py [--sample b]

No answer key: the yardstick is the chat models' majority (3 or more of 5 giving the
same answer); jobs where they split are listed but not counted. Languages: the decider
picks one, so it counts as agreeing when its pick is one of the languages the majority
listed (or "none" when the majority listed none).
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from report import MODELS, load, value  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--sample", default="b")
args = ap.parse_args()

rows, answers = load("v2", args.sample)
index = [json.loads(line) for line in (HERE / f"decider-{args.sample}-index.jsonl").open()]
replies = [json.loads(line) for line in (HERE / f"decider-{args.sample}-answers.jsonl").open()]
dec = {}
for i, r in zip(index, replies):
    a = r["answers"][i["question"]]
    dec[i["uid"], i["question"]] = (a["choice"], a["confidence"], max(a["probabilities"].values()))

tally = {d: Counter() for d in ("field", "task", "language")}
by_conf = Counter()
print(f"{'job':48s} {'dim':8s} {'chat models (n of 5)':34s} decider (prob.)")
for r in rows:
    if (r["uid"], "field") not in dec:
        continue
    for dim, key in (("field", "field"), ("task", "task"), ("language", "languages")):
        votes = Counter(value(answers[m, r["uid"]], key) for m in MODELS)
        top, n = votes.most_common(1)[0]
        pick, _, p = dec[r["uid"], dim]
        if dim == "language":
            listed = [] if top == "—" else [x.strip() for x in top.split(",")]
            same = (pick == "none" and not listed) or pick in listed or (pick == "English_variety" and "English" in listed)
        else:
            same = pick == top
        if n >= 3:
            tally[dim]["agree" if same else "differ"] += 1
            by_conf[("high" if p >= 0.8 else "low"), same] += 1
        else:
            tally[dim]["chat models split"] += 1
        if not same:
            print(f"{r['title'][:48]:48s} {dim:8s} {top + f' ({n})':34s} {pick} ({p:.2f})")

print()
for dim, c in tally.items():
    print(f"{dim:8s} agrees {c['agree']}/{c['agree'] + c['differ']}  (chat models split on {c['chat models split']})")
for level in ("high", "low"):
    ok, bad = by_conf[level, True], by_conf[level, False]
    print(f"decider {'sure (p >= 0.8)' if level == 'high' else 'unsure (p < 0.8)':18s}: agrees {ok}/{ok + bad}")
