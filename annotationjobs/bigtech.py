"""Big companies whose career sites are searched by keyword (Google incl. DeepMind, Amazon)."""

import json
import re
import urllib.parse

from .common import classify, fetch, fetch_json, html_to_text, listing, save_raw

KEYWORDS = ["annotation", "annotator", "data labeling", "rater", "AI tutor", "AI trainer", "human data",
            "data associate", "data specialist", "linguist", "language data", "transcription", "evaluator",
            "data collection", "RLHF"]


# --- Google careers (Google DeepMind and Google) ---------------------------------------------------

def _google_page(params):
    url = "https://www.google.com/about/careers/applications/jobs/results?" + urllib.parse.urlencode(params)
    h = fetch(url)
    m = re.search(r"AF_initDataCallback\(\{key: 'ds:1'.*?data:(.*?), sideChannel", h, re.S)
    if not m:
        return [], 0
    d = json.loads(m.group(1))
    return d[0] or [], (d[2] if len(d) > 2 and isinstance(d[2], int) else 0)


def google(board):
    """Every DeepMind posting, plus Google postings that match the keywords."""
    found = {}
    searches = [({"company": "DeepMind"}, True)] + [({"q": k}, False) for k in KEYWORDS]
    for params, take_all in searches:
        page = 1
        while True:
            jobs, total = _google_page({**params, "page": page})
            for j in jobs:
                found.setdefault(j[0], (j, take_all))
            if not jobs or page * 20 >= total or page > 30:
                break
            page += 1
    save_raw(board["source"], "results.json", json.dumps([v[0] for v in found.values()]))
    out = []
    for jid, (j, _) in found.items():
        title, company = j[1], j[7] or "Google"
        rel, why = classify(title, also=r"\bexpert\b" if company == "DeepMind" else None)
        if not rel and company != "DeepMind":
            continue  # keyword hits on unrelated Google jobs are dropped
        about, resp, quals = (j[10] or [None, ""])[1], (j[3] or [None, ""])[1], (j[4] or [None, ""])[1]
        html = "\n".join(x for x in (about, "<h3>Responsibilities</h3>" + resp if resp else "", quals) if x)
        locs = [l[0] for l in j[9] or []]
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        out.append(listing(
            "Google DeepMind" if company == "DeepMind" else "Google", board["source"], jid, title,
            f"https://www.google.com/about/careers/applications/jobs/results/{jid}-{slug}", html_to_text(html),
            company=company, location="; ".join(locs),
            countries=", ".join(sorted({l[5] for l in j[9] or [] if len(l) > 5 and l[5]})),
            relevant=rel, relevant_why=why, extra={"html": html},
        ))
    return out


# --- Amazon -----------------------------------------------------------------------------------------

def amazon(board):
    found = {}
    for k in KEYWORDS:
        off = 0
        while True:
            q = urllib.parse.urlencode({"base_query": k, "result_limit": 100, "offset": off, "sort": "recent"})
            d = fetch_json("https://www.amazon.jobs/en/search.json?" + q)
            for j in d.get("jobs", []):
                found.setdefault(j["id_icims"], j)
            off += 100
            if off >= d.get("hits", 0) or off >= 1000:
                break
    save_raw(board["source"], "results.json", json.dumps(list(found.values())))
    out = []
    for jid, j in found.items():
        rel, why = classify(j["title"])
        if not rel:
            continue
        html = "\n".join([j.get("description") or "",
                          "<h3>Basic qualifications</h3>" + (j.get("basic_qualifications") or ""),
                          "<h3>Preferred qualifications</h3>" + (j.get("preferred_qualifications") or "")])
        out.append(listing(
            "Amazon", board["source"], jid, j["title"], "https://www.amazon.jobs" + j["job_path"], html_to_text(html),
            company=j.get("company_name") or "Amazon", location=j.get("normalized_location") or j.get("location") or "",
            countries=j.get("country_code") or "", employment_type=j.get("job_schedule_type") or "",
            posted=j.get("posted_date") or "", department=j.get("job_category") or "",
            relevant=rel, relevant_why=why, extra={"html": html, "team": j.get("team"), "business_category": j.get("business_category")},
        ))
    return out


# --- Apple ------------------------------------------------------------------------------------------

def _apple_data(h):
    m = re.search(r'window.__staticRouterHydrationData = JSON.parse\("(.*?)"\);', h, re.S)
    return json.loads(json.loads('"' + m.group(1) + '"'))["loaderData"] if m else {}


def apple(board):
    found = {}
    for k in KEYWORDS:
        for page in range(1, 6):
            q = urllib.parse.urlencode({"search": k, "page": page})
            s = _apple_data(fetch("https://jobs.apple.com/en-us/search?" + q)).get("search") or {}
            res = s.get("searchResults") or []
            for r in res:
                found.setdefault(r["positionId"], r)
            if len(res) < 20:
                break
    out = []
    for pid, r in found.items():
        rel, why = classify(r["postingTitle"])
        if not rel:
            continue
        url = f"https://jobs.apple.com/en-us/details/{pid}/{r['transformedPostingTitle']}"
        h = fetch(url)
        save_raw(board["source"], pid + ".html", h)
        j = (_apple_data(h).get("jobDetails") or {}).get("jobsData") or {}
        foot = []
        for f in j.get("postingFooters") or []:
            for items in (f.get("localizations") or {}).values():
                foot += [i.get("name", "") + "\n" + (i.get("content") or "") for i in items]
        parts = [("Summary", j.get("jobSummary") or r.get("jobSummary")), ("Description", j.get("description")),
                 ("Responsibilities", j.get("responsibilities")), ("Minimum qualifications", j.get("minimumQualifications")),
                 ("Preferred qualifications", j.get("preferredQualifications"))]
        text = "\n\n".join(f"## {a}\n{html_to_text(b)}" for a, b in parts if b) + "\n\n" + "\n\n".join(html_to_text(f) for f in foot)
        locs = [", ".join(x for x in (l.get("city"), l.get("countryName")) if x) for l in r.get("locations") or []]
        out.append(listing(
            "Apple", board["source"], pid, r["postingTitle"], url, text, location="; ".join(locs),
            countries=", ".join(sorted({l.get("countryName") for l in r.get("locations") or [] if l.get("countryName")})),
            employment_type=j.get("employmentType") or "", posted=(r.get("postDateInGMT") or "")[:10],
            department=(r.get("team") or {}).get("teamName", ""), relevant=rel, relevant_why=why,
            hours_per_week=float(r["standardWeeklyHours"]) if r.get("standardWeeklyHours") else None,
            extra={"job": {k2: v for k2, v in j.items() if k2 not in ("translations", "localizations")}},
        ))
    return out
