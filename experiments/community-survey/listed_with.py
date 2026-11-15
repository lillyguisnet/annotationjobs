"""Names that workers list next to known platforms ("I'm on Outlier, Mercor and X"): finds platforms we did not think of."""
import collections, glob, json, re
from pathlib import Path
P = Path("/mnt/bulk/lilly/annotationjobs/community")
KNOWN = r"outlier|mercor|data ?annotation|\bDA\b|alignerr|micro ?1|handshake|mindrift|welocali[sz]e|rws|oneforma|appen|telus|prolific|turing|toloka|remotasks|scale"
STOP = set("I I'm Im The A An And But Or So If It It's Its This That They We You He She My Your Our Their Also Just Not No Yes Any All Some Most More Same Other Others Then Now Even Still Only Both Each Every Many Much Very Really Maybe Lol LOL AI US USA UK EU OK Okay Hi Hey Thanks Thank Edit Update Please PayPal Reddit Discord Google LinkedIn Indeed Glassdoor ChatGPT Claude Gemini Grok OpenAI Anthropic Meta Microsoft Amazon Apple India Canada Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July August September October November December Aether Oracle Multimango Stripe Payoneer Wise Mercor's Outlier's DA's EQ MM HR ID CV PhD Python SQL English Spanish French German USD What Why How When Where Who Is Are Was Were Do Does Did Have Has Had Can Could Would Should Will Don't Didn't I've I'd I'll There Here Well Yeah After Before Since With Without For From Into About Like Once Got Get Be".split())
docs = [json.loads(l)["title"] for f in glob.glob(str(P / "posts/*.jsonl")) for l in open(f)]
for f in glob.glob(str(P / "threads/*.json")):
    t = json.loads(Path(f).read_text()); docs.append(t["selftext"]); docs += [c["body"] for c in t["comments"]]
names = collections.Counter(); ex = {}
for d in docs:
    for sent in re.split(r"(?<=[.!?\n])\s+", d or ""):
        if len(re.findall(KNOWN, sent, re.I)) < 2:  # a sentence naming two known platforms is a list of platforms
            continue
        for m in re.finditer(r"\b([A-Z][A-Za-z0-9]+(?:[ .][A-Z][A-Za-z0-9]+)?(?:\.ai|\.com|\.io)?)\b", sent):
            w = m.group(1)
            if w.split()[0] in STOP or re.fullmatch(KNOWN, w, re.I) or re.search(KNOWN, w, re.I):
                continue
            names[w] += 1; ex.setdefault(w, sent[:200].replace("\n", " "))
for w, n in names.most_common(45):
    if n >= 2: print(f"{n:4}  {w:22} {ex[w]!r}")
