import json, re, html, time, urllib.request, urllib.parse
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
SITES = {"Mindrift": "mindrift.ai", "Alignerr": "alignerr.com", "micro1": "micro1.ai", "Welocalize": "welocalize.com",
 "Handshake AI": "joinhandshake.com", "RWS": "rws.com", "Lionbridge": "lionbridge.com", "Appen": "appen.com",
 "CloudFactory": "cloudfactory.com", "G2i": "g2i.co", "Scale AI": "scale.com", "Remotasks": "remotasks.com", "OneForma": "oneforma.com",
 "Centific": "centific.com", "Sama": "sama.com", "Surge AI": "surgehq.ai", "TELUS Digital": "telusdigital.com",
 "Prolific": "prolific.com", "Turing": "turing.com", "Toloka": "toloka.ai", "Outlier": "outlier.ai", "DataAnnotation": "dataannotation.tech", "Mercor": "mercor.com"}
def fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        with urllib.request.urlopen(req, timeout=30) as r: return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e: return e.code, ""
    except Exception as e: return str(e)[:40], ""
out = {}
for name, dom in SITES.items():
    row = {}
    # Sitejabber: aggregate rating in structured data
    st, s = fetch(f"https://www.sitejabber.com/reviews/{dom}")
    m = re.search(r'"ratingValue":"?([\d.]+)"?,?[^}]*?"reviewCount":"?(\d+)', s) or re.search(r'"reviewCount":"?(\d+)"?[^}]*?"ratingValue":"?([\d.]+)', s)
    row["sitejabber"] = (st, m.group(0)[:80] if m else None)
    # PissedConsumer: review count in page text
    sub = dom.split(".")[0]
    st, s = fetch(f"https://{sub}.pissedconsumer.com/review.html")
    m = re.search(r"(\d[\d,]*)\s+(?:Reviews|reviews|Complaints)", html.unescape(re.sub(r"<[^>]+>", " ", s)))
    row["pissedconsumer"] = (st, m.group(0) if m else None)
    # Hacker News: stories + comments mentioning the name since 2026-05-01
    q = urllib.parse.quote(name if name not in ("RWS",) else "RWS TrainAI")
    st, s = fetch(f"https://hn.algolia.com/api/v1/search?query=%22{q}%22&numericFilters=created_at_i%3E1777593600&hitsPerPage=0")
    row["hackernews"] = (st, json.loads(s).get("nbHits") if s else None)
    out[name] = row
    print(f"{name:15} sitejabber {row['sitejabber']}  | pissedconsumer {row['pissedconsumer']} | HN since May {row['hackernews'][1]}")
    time.sleep(2)
json.dump(out, open("/mnt/bulk/lilly/annotationjobs/community/survey/review_sites.json", "w"), indent=1)
