"""Which work platforms do workers name in the Reddit corpus that the job page does not cover?"""
import collections, glob, json, re
from pathlib import Path
P = Path("/mnt/bulk/lilly/annotationjobs/community")
CANDIDATES = {  # name -> pattern (case-insensitive)
 "TELUS Digital": r"\btelus\b", "Prolific": r"\bprolific\b", "Clickworker": r"clickworker", "UHRS": r"\buhrs\b",
 "Amazon MTurk": r"\bm ?turk\b|mechanical turk", "Toloka": r"\btoloka\b", "Uber AI Solutions": r"uber ai|scaled solutions",
 "DataForce (TransPerfect)": r"data ?force\b|transperfect", "LXT": r"\blxt\b", "Sigma AI": r"\bsigma ai\b",
 "iMerit": r"\bimerit\b", "TaskUs": r"\btaskus\b", "Defined.ai / Neevo": r"defined\.?ai|\bneevo\b", "Shaip": r"\bshaip\b",
 "Summa Linguae": r"summa linguae", "Gengo": r"\bgengo\b", "Upwork": r"\bupwork\b", "Toptal": r"\btoptal\b",
 "Soul AI (Deccan)": r"\bsoul ?ai\b|deccan", "Datacurve": r"datacurve", "Revelo": r"\brevelo\b", "Andela": r"\bandela\b",
 "Snorkel": r"\bsnorkel\b", "Pareto": r"\bpareto\b", "Invisible": r"\binvisible\b", "Turing": r"\bturing\b",
 "Rex.zone": r"rex\.?zone", "OpenTrain": r"opentrain", "Stellar": r"\bstellar ?ai\b", "SME Careers": r"sme ?careers",
 "Ethos": r"\bethos\b", "Abaka": r"\babaka\b", "Braintrust": r"\bbraintrust\b", "Wirestock": r"wirestock",
 "Kled": r"\bkled\b", "Respondent": r"respondent\.io|\brespondent\b", "UserTesting": r"usertesting|user testing",
 "User Interviews": r"user ?interviews", "Appen / CrowdGen": r"\bappen\b|crowd ?gen\b", "Lionbridge": r"lionbridge",
 "Scale / Remotasks": r"remotasks|\bscale ?ai\b", "Sepal": r"\bsepal\b", "Aligned": r"\baligned ai\b", "Hive": r"\bhive ?(micro|work)\b",
 "Taskverse / Mindrift": r"mindrift", "Labelbox": r"labelbox", "Encord": r"\bencord\b", "Cogito": r"\bcogito\b",
 "Rapidata": r"rapidata", "Botpool": r"botpool", "Crossing Hurdles": r"crossing hurdles", "Afterquery": r"afterquery",
 "G2i": r"\bg2i\b", "Surge (as Surge)": r"\bsurge ?(ai|hq)\b", "Meta (in-house)": r"\bmeta ai trainer|\bmeta\b.{0,20}\btrainer",
 "Babel Audio": r"babel audio", "Lexi / Lexicon": r"\blexicon ai\b", "Datatang": r"datatang", "Magicdata": r"magic ?data\b",
 "Twine": r"\btwine\b", "Fiverr": r"\bfiverr\b", "Remote.com": r"remote\.com", "Flexjobs": r"flexjobs",
}
docs = []  # (kind, text)
for f in glob.glob(str(P / "posts/*.jsonl")):
    docs += [("title", json.loads(l)["title"]) for l in open(f)]
for f in glob.glob(str(P / "threads/*.json")):
    t = json.loads(Path(f).read_text())
    docs.append(("post", t["selftext"])); docs += [("comment", c["body"]) for c in t["comments"]]
cnt = collections.Counter(); ex = collections.defaultdict(list)
for kind, text in docs:
    for name, rx in CANDIDATES.items():
        m = re.search(rx, text or "", re.I)
        if m:
            cnt[name] += 1
            if len(ex[name]) < 3: ex[name].append(text[max(0, m.start() - 90): m.end() + 110].replace("\n", " "))
print(f"{len(docs)} texts (titles of every post, full text of the 1,337 sampled threads)")
for name, n in cnt.most_common():
    print(f"{n:5}  {name:28} e.g. {ex[name][0][:170]!r}")
print("never named:", ", ".join(k for k in CANDIDATES if not cnt[k]))
