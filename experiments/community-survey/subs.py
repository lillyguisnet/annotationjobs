import json, sys, datetime as dt
sys.path.insert(0, "/home/lilly/Projects/annotationjobs")
from annotationjobs.community import get
PREFIXES = {
 "Mindrift (Toloka)": ["mindrift", "toloka"], "Alignerr": ["alignerr", "labelbox"], "micro1": ["micro1"],
 "Welocalize": ["welocalize"], "Handshake AI": ["handshakeai", "handshake_ai", "handshake"], "RWS (TrainAI)": ["rws", "trainai"],
 "Lionbridge": ["lionbridge"], "Appen": ["appen"], "CloudFactory": ["cloudfactory"], "G2i": ["g2i"],
 "Scale AI": ["scaleai", "scale_ai", "remotasks"], "OneForma": ["oneforma"], "Centific": ["centific"], "Sama": ["sama"],
 "Surge AI": ["surgeai", "surge_ai"], "xAI": ["xai", "grok"], "TELUS Digital": ["telus", "raterlabs"],
 "Prolific": ["prolific"], "Invisible": ["invisible"], "Turing": ["turing"], "SuperAnnotate": ["superannotate"], "Innodata": ["innodata"],
}
out = {}
for site, prefixes in PREFIXES.items():
    subs = []
    for p in prefixes:
        for x in get("subreddits/search", subreddit_prefix=p, limit=15):
            m = x.get("_meta") or {}
            subs.append({"name": x["display_name"], "subscribers": x.get("subscribers"), "posts_total": m.get("num_posts"),
                         "comments_total": m.get("num_comments"), "desc": (x.get("public_description") or "")[:140].replace("\n", " ")})
    out[site] = subs
    print("==", site); [print(f"   {s['name']:28} subs {s['subscribers']!s:>8} posts {s['posts_total']!s:>7} | {s['desc'][:90]}") for s in subs]
json.dump(out, open("/mnt/bulk/lilly/annotationjobs/community/survey/subs.json", "w"), indent=1)
