"""Compare the models' answers: agreement, evidence checks, speed; and a page per job.

    python3 experiments/categorize/report.py      -> prints the summary, writes report.html

There is no answer key: "agrees with the others" means the model gave the answer
most of the other four gave (leave-one-out majority, 3 or 4 of 4); jobs where the
other four split 2-2 or worse are not counted for that model.
"""

import html
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODELS = ["muse-ember", "haiku", "opus", "luna", "terra"]
NAMES = {"muse-ember": "Muse Ember 1.0", "haiku": "Claude Haiku 5.5", "opus": "Claude Opus 5.5",
         "luna": "GPT-6 Luna", "terra": "GPT-6.1 Terra"}
RUNS = [("v1", "a", "v1 categories, 30 jobs used to tune them"),
        ("v2", "a", "v2 categories, the same 30 jobs (tuned on these)"),
        ("v2", "b", "v2 categories, 30 fresh jobs (the honest test)")]


def load(version, sample):
    rows = [json.loads(line) for line in (HERE / f"sample-{sample}.jsonl").open()]
    answers, uids = {}, {r["uid"] for r in rows}
    for line in (HERE / f"answers-{version}.jsonl").open():
        a = json.loads(line)
        if "error" not in a and a["uid"] in uids:
            answers[a["model"], a["uid"]] = a
    return rows, answers


def value(a, dim):
    ans = a["answer"]
    if dim == "languages":  # compare base names only (v1 had varieties mixed in)
        return ", ".join(sorted({x.split("(")[0].strip() for x in ans.get("languages") or []})) or "—"
    return ans.get(dim)


def summary(version, sample):
    rows, answers = load(version, sample)
    out = {"n": len(rows), "unanimous": {}, "agree": defaultdict(dict), "quotes": {}, "seconds": {}, "tokens": {}}
    for dim in ("field", "task", "languages"):
        unanimous = 0
        hits, counted = Counter(), Counter()
        for r in rows:
            vals = {m: value(answers[m, r["uid"]], dim) for m in MODELS if (m, r["uid"]) in answers}
            unanimous += len(set(vals.values())) == 1
            for m in vals:
                others = Counter(v for k, v in vals.items() if k != m)
                top, count = others.most_common(1)[0]
                if count >= 3:
                    counted[m] += 1
                    hits[m] += vals[m] == top
        out["unanimous"][dim] = unanimous
        for m in MODELS:
            out["agree"][m][dim] = (hits[m], counted[m])
    for m in MODELS:
        mine = [a for (k, _), a in answers.items() if k == m]
        found = [q for a in mine for qs in a["quotes_found"].values() for q in (qs if isinstance(qs, list) else [qs])
                 if q is not None]
        out["quotes"][m] = (sum(found), len(found))
        out["seconds"][m] = sum(a["seconds"] for a in mine) / max(len(mine), 1)
        out["tokens"][m] = sum(a["usage"]["output"] or 0 for a in mine) / max(len(mine), 1)
    return out


def print_summary():
    for version, sample, label in RUNS:
        s = summary(version, sample)
        print(f"\n## {label}  (n={s['n']})")
        print("all five agree:", {d: f"{v}/{s['n']}" for d, v in s["unanimous"].items()})
        print(f"{'model':18s} {'field':>8s} {'task':>8s} {'langs':>8s} {'quotes ok':>10s} {'s/job':>6s} {'out tok':>8s}")
        for m in MODELS:
            ag = s["agree"][m]
            cell = lambda d: f"{ag[d][0]}/{ag[d][1]}"  # noqa: E731
            q = s["quotes"][m]
            print(f"{NAMES[m]:18s} {cell('field'):>8s} {cell('task'):>8s} {cell('languages'):>8s} "
                  f"{q[0]:>4d}/{q[1]:<4d} {s['seconds'][m]:6.1f} {s['tokens'][m]:8.0f}")


def page():
    parts = ["<!doctype html><meta charset=utf-8><title>Categorizing jobs: five models</title><style>",
             "body{font:14px/1.45 system-ui,sans-serif;max-width:1100px;margin:2em auto;padding:0 1em;color:#222}",
             "table{border-collapse:collapse;margin:.4em 0 1.4em}td,th{border:1px solid #ddd;padding:3px 7px;text-align:left;vertical-align:top}",
             "th{background:#f4f4f4}.odd{background:#ffe3c2}.job{margin:1.6em 0}.old{color:#777}.ev{color:#666;font-size:12px}",
             "h3{margin:.2em 0}details{margin:.3em 0}</style>",
             "<h1>Sorting jobs into field, language and task: five models compared</h1>",
             "<p>Each model read the full listing and chose a field of expertise, the languages required, "
             "and the kind of task. There is no answer key: an <span class=odd>orange</span> cell is an answer "
             "that differs from what most of the five models chose. The old keyword guess from the title is in grey.</p>"]
    for version, sample, label in RUNS[1:]:
        rows, answers = load(version, sample)
        parts.append(f"<h2>{html.escape(label)}</h2>")
        for r in rows:
            parts.append(f"<div class=job><h3><a href='{html.escape(r['url'])}'>{html.escape(r['title'])}</a> "
                         f"<small>({html.escape(r['site'])})</small></h3><div class=old>old keyword field: "
                         f"{html.escape(r['keyword_field'])}</div><table><tr><th>model<th>field<th>task<th>languages<th>varieties")
            majority = {}
            for dim in ("field", "task", "languages"):
                majority[dim] = Counter(value(answers[m, r["uid"]], dim) for m in MODELS).most_common(1)[0][0]
            for m in MODELS:
                a = answers[m, r["uid"]]
                cells = []
                for dim in ("field", "task", "languages"):
                    v = value(a, dim)
                    ev = a["answer"].get(f"{dim}_evidence") or []
                    ev = " | ".join(ev) if isinstance(ev, list) else ev
                    cls = " class=odd" if v != majority[dim] else ""
                    cells.append(f"<td{cls}>{html.escape(str(v))}<div class=ev>{html.escape(ev[:220])}</div>")
                var = ", ".join(a["answer"].get("varieties") or [])
                parts.append(f"<tr><td>{NAMES[m]}{''.join(cells)}<td>{html.escape(var)}")
            parts.append("</table><details><summary>listing text</summary><pre style='white-space:pre-wrap'>"
                         f"{html.escape(r['text'][:6000])}</pre></details></div>")
    (HERE / "report.html").write_text("\n".join(parts))


if __name__ == "__main__":
    print_summary()
    page()
