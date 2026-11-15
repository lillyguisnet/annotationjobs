import json, sys, time
sys.path.insert(0, "/home/lilly/Projects/annotationjobs")
import annotationjobs.community as c
c.get.__defaults__  # noqa
def tryget(kind, sub, **kw):
    # one attempt only, so a refusal is visible instead of waited out
    import urllib.request, urllib.parse
    url = f"{c.API}/{kind}/search?" + urllib.parse.urlencode({"subreddit": sub, "after": "2026-05-01", "before": "2026-11-01", "limit": 100, **kw})
    time.sleep(6)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": c.UA}), timeout=90) as r: j = json.loads(r.read())
    except Exception as e: return f"error {str(e)[:40]}"
    return len(j["data"]) if j.get("data") is not None else j.get("error")
for sub in ["WorkOnline", "WFHJobs", "beermoney", "TranslationStudies", "remotework", "BeerMoneyPH", "freelance"]:
    for term in ["appen", "lionbridge", "scale ai", "cloudfactory", "centific"]:
        print(f"r/{sub:20} {term:13} posts: {tryget('posts', sub, query=term)}  comments: {tryget('comments', sub, body=term)}", flush=True)
