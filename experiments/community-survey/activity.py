import json, sys, datetime as dt
sys.path.insert(0, "/home/lilly/Projects/annotationjobs")
from annotationjobs.community import get, epoch
SUBS = {
 "Mindrift (Toloka)": ["mindrift", "Toloka", "TolokaPH"], "Alignerr": ["alignerr", "AlignerrAI", "alignerrunofficial"],
 "micro1": ["micro1_ai"], "Welocalize": ["Welocalize"], "Handshake AI": ["HandshakeAi_jobs", "HandshakeAiHate"],
 "RWS (TrainAI)": ["RWShelp", "RWSPay", "RWSCallisto", "RWSCallistoRaters"], "Lionbridge": ["LionbridgeRaters", "LionbridgeWorkers"],
 "Appen": ["Appen", "AppenCommunity", "AppenInternational"], "CloudFactory": ["CloudFactoryNepal"], "G2i": ["G2i"],
 "Scale AI": ["Remotasks", "remotasksworkfromhome", "scaleAI", "Scale_AI"], "OneForma": ["OneFormaOfficial", "OneFormabyCentific"],
 "Centific": ["Centific"], "Sama": ["Sama", "SamaSource"], "Surge AI": ["SurgeAI"], "xAI": ["xAI_community", "xai"],
 "TELUS Digital": ["TELUSinternational", "TelusSafetyRaters", "TELUSreality"], "Prolific": ["ProlificAc"],
 "Turing": ["turingcom"], "Invisible": ["InvisibleTech"], "SuperAnnotate": ["SuperAnnotate"], "Innodata": ["innodata"],
}
A, B = "2026-05-01", "2026-11-01"
days = (dt.date.fromisoformat(B) - dt.date.fromisoformat(A)).days
out = {}
for site, subs in SUBS.items():
    out[site] = {}
    for s in subs:
        try:
            page = get("posts/search", subreddit=s, after=A, before=B, sort="desc", limit=100, fields="id,created_utc,title")
        except RuntimeError as e:
            out[site][s] = {"error": str(e)[:100]}; print(site, s, "ERR", str(e)[:80]); continue
        if len(page) < 100:
            est, how = len(page), "exact"
        else:
            span = (epoch(B) - page[-1]["created_utc"]) / 86400
            est, how = round(100 / span * days), f"estimated from the last {span:.0f} days"
        out[site][s] = {"posts_6mo": est, "how": how, "titles": [p["title"] for p in page[:6]]}
        print(f"{site:20} r/{s:24} {est:>6} posts May-Oct ({how}) | {' / '.join(p['title'][:40] for p in page[:3])}")
json.dump(out, open("/mnt/bulk/lilly/annotationjobs/community/survey/activity.json", "w"), indent=1, ensure_ascii=False)
