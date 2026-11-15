import json, re, glob, collections
from pathlib import Path
TERMS = {"Appen": r"\bappen\b", "CloudFactory": r"cloud ?factory", "G2i": r"\bg2i\b", "Scale AI": r"\bscale ?ai\b",
 "Remotasks": r"remotasks?", "Centific": r"centific", "Sama": r"\bsama(source)?\b", "Lionbridge": r"lionbridge", "Turing": r"\bturing\b(?! test)",
 "Invisible": r"\binvisible (tech|technologies|ai)\b", "Mindrift": r"mindrift", "Toloka": r"toloka", "Handshake AI": r"\bhandshake\b",
 "xAI": r"\bxai\b", "Alignerr": r"alignerr", "micro1": r"micro ?1\b", "Welocalize": r"welocali[sz]e|\bwelo\b",
 "RWS": r"\brws\b", "OneForma": r"one ?forma", "TELUS": r"\btelus\b", "Prolific": r"\bprolific\b", "Surge AI": r"\bsurge ?(ai|hq)\b",
 "Mercor": r"mercor", "Outlier": r"\boutlier\b", "DataAnnotation": r"data ?annotation"}
P = Path("/mnt/bulk/lilly/annotationjobs/community")
titles = collections.Counter(); ntitles = 0
for f in glob.glob(str(P / "posts/*.jsonl")):
    for l in open(f):
        t = json.loads(l)["title"]; ntitles += 1
        for k, rx in TERMS.items():
            if re.search(rx, t, re.I): titles[k] += 1
sample = [json.loads(l) for l in open("data/community/sample.jsonl")]
threads = collections.Counter(); comments = collections.Counter(); ex = collections.defaultdict(list); ncom = 0
for r in sample:
    t = json.loads((P / "threads" / f"{r['id']}.json").read_text())
    parts = [t["title"] + " " + t["selftext"]] + [c["body"] for c in t["comments"]]
    ncom += len(t["comments"])
    for k, rx in TERMS.items():
        if k == r["platform"]: continue
        hits = [p for p in parts if re.search(rx, p, re.I)]
        if hits:
            threads[k] += 1; comments[k] += len(hits)
            if len(ex[k]) < 4:
                m = re.search(rx, hits[0], re.I); ex[k].append(hits[0][max(0, m.start()-100): m.end()+140].replace("\n", " "))
print(f"{ntitles} titles, {len(sample)} sampled threads with {ncom} comments")
print(f"{'company':15} {'in titles':>9} {'sampled threads':>16} {'comments':>9}  -> est. threads mentioning it, 6 months")
w = ntitles / len(sample)
for k in TERMS:
    print(f"{k:15} {titles[k]:>9} {threads[k]:>16} {comments[k]:>9}  ~{round(threads[k]*w):,}")
json.dump({k: ex[k] for k in TERMS}, open(P / "survey/local_mentions_examples.json", "w"), indent=1, ensure_ascii=False)
