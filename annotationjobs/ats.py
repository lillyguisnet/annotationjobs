"""Readers for the standard hiring systems: Greenhouse, Ashby, Lever, Workable, Workday."""

import json
import re
from concurrent.futures import ThreadPoolExecutor

from .common import classify, fetch, fetch_json, html_to_text, listing, save_raw, short_hash
import html as htmllib


def _rel(board, title, dept=""):
    """Marketplace boards: every posting is contributor work. Company boards: filter by title."""
    if board.get("all_relevant"):
        return True, "contributor board"
    return classify(title, dept, board.get("also"))


# --- Greenhouse -----------------------------------------------------------------

def greenhouse(board):
    t = board["token"]
    body = fetch(f"https://boards-api.greenhouse.io/v1/boards/{t}/jobs?content=true")
    save_raw(board["source"], "jobs.json", body)
    out = []
    for j in json.loads(body)["jobs"]:
        content = htmllib.unescape(j.get("content") or "")
        text = html_to_text(content)
        depts = ", ".join(d["name"] for d in j.get("departments") or [])
        rel, why = _rel(board, j["title"], depts)
        out.append(listing(
            board["site"], board["source"], j["id"], j["title"], j["absolute_url"], text,
            company=j.get("company_name") or board["site"],
            location=(j.get("location") or {}).get("name", ""),
            posted=(j.get("first_published") or j.get("updated_at") or "")[:10],
            department=depts, relevant=rel, relevant_why=why,
            extra={"html": content, "updated_at": j.get("updated_at"),
                   "offices": [o.get("name") for o in j.get("offices") or []],
                   "metadata": j.get("metadata")},
        ))
    return out


# --- Ashby --------------------------------------------------------------------------

INTERVAL = {"1 HOUR": "hour", "1 YEAR": "year", "1 MONTH": "month", "1 WEEK": "week", "1 DAY": "day"}


def ashby(board):
    t = board["token"]
    body = fetch(f"https://api.ashbyhq.com/posting-api/job-board/{t}?includeCompensation=true")
    save_raw(board["source"], "jobs.json", body)
    out = []
    for j in json.loads(body)["jobs"]:
        if j.get("isListed") is False:
            continue
        comp = j.get("compensation") or {}
        lo = hi = cur = unit = None
        for c in comp.get("summaryComponents") or []:
            if c.get("compensationType") in ("Salary", "Hourly", "Base"):
                lo, hi, cur = c.get("minValue"), c.get("maxValue"), c.get("currencyCode")
                unit = INTERVAL.get(c.get("interval"), (c.get("interval") or "").lower())
                break
        locs = [j.get("location") or ""] + [s.get("location", "") for s in j.get("secondaryLocations") or []]
        rel, why = _rel(board, j["title"], j.get("department", ""))
        text = j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml"))
        out.append(listing(
            board["site"], board["source"], j["id"], j["title"], j["jobUrl"], text,
            location="; ".join(l for l in locs if l),
            arrangement=(j.get("workplaceType") or ("Remote" if j.get("isRemote") else "")).lower(),
            employment_type=j.get("employmentType") or "",
            pay_min=lo, pay_max=hi, pay_currency=cur, pay_unit=unit,
            pay_text=comp.get("compensationTierSummary") or "",
            posted=(j.get("publishedAt") or "")[:10], department=" / ".join(x for x in (j.get("department"), j.get("team")) if x),
            relevant=rel, relevant_why=why,
            extra={"html": j.get("descriptionHtml"), "compensation": comp, "address": j.get("address"),
                   "applyUrl": j.get("applyUrl")},
        ))
    return out


# --- Lever ------------------------------------------------------------------------------

LEVER_UNIT = {"per-hour-wage": "hour", "per-year-salary": "year", "per-month-salary": "month",
              "per-week-salary": "week", "per-day-wage": "day", "one-time": "one-time"}


def lever(board):
    t, host = board["token"], board.get("host", "api.lever.co")
    body = fetch(f"https://{host}/v0/postings/{t}?mode=json")
    save_raw(board["source"], "postings.json", body)
    out = []
    for j in json.loads(body):
        cat = j.get("categories") or {}
        parts = [j.get("descriptionPlain") or ""]
        for l in j.get("lists") or []:
            parts.append(l.get("text", "") + "\n" + html_to_text(l.get("content", "")))
        parts.append(j.get("additionalPlain") or "")
        text = "\n\n".join(p.strip() for p in parts if p and p.strip())
        sr = j.get("salaryRange") or {}
        rel, why = _rel(board, j["text"], cat.get("team", ""))
        out.append(listing(
            board["site"], board["source"], j["id"], j["text"], j["hostedUrl"], text,
            location="; ".join(cat.get("allLocations") or [cat.get("location") or ""]),
            countries=j.get("country") or "", arrangement=j.get("workplaceType") or "",
            commitment=cat.get("commitment") or "",
            pay_min=sr.get("min"), pay_max=sr.get("max"), pay_currency=sr.get("currency"),
            pay_unit=LEVER_UNIT.get(sr.get("interval"), sr.get("interval")) if sr else None,
            pay_text=j.get("salaryDescriptionPlain") or "",
            posted=_ms(j.get("createdAt")), department=" / ".join(x for x in (cat.get("department"), cat.get("team")) if x),
            relevant=rel, relevant_why=why,
            extra={"description_html": j.get("description"), "lists": j.get("lists"), "additional_html": j.get("additional")},
        ))
    return out


def _ms(ms):
    if not ms:
        return ""
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ms / 1000, timezone.utc).date().isoformat()


# --- Workable ------------------------------------------------------------------------------

def workable(board):
    t = board["token"]
    body = fetch(f"https://apply.workable.com/api/v1/widget/accounts/{t}?details=true")
    save_raw(board["source"], "widget.json", body)
    jobs = json.loads(body)["jobs"]
    detail = len(jobs) <= board.get("detail_limit", 300)

    def one(j):
        d = {}
        if detail:  # requirements/benefits live in separate fields on some accounts
            try:
                raw = fetch(f"https://apply.workable.com/api/v2/accounts/{t}/jobs/{j['shortcode']}")
                save_raw(board["source"], j["shortcode"] + ".json", raw)
                d = json.loads(raw)
            except Exception:
                d = {}
        html_parts = [j.get("description") or d.get("description") or "", d.get("requirements") or "", d.get("benefits") or ""]
        text = "\n\n".join(html_to_text(p) for p in html_parts if p)
        locs = j.get("locations") or []
        countries = sorted({l.get("country") for l in locs if l.get("country")}) or ([j["country"]] if j.get("country") else [])
        rel, why = _rel(board, j["title"], j.get("department", ""))
        return listing(
            board["site"], board["source"], j["shortcode"], j["title"], j["url"], text,
            location="; ".join(", ".join(x for x in (l.get("city"), l.get("region"), l.get("country")) if x) for l in locs),
            countries=", ".join(countries), arrangement="remote" if j.get("telecommuting") else "",
            employment_type=j.get("employment_type") or "", posted=j.get("published_on") or "",
            department=j.get("department") or "", relevant=rel, relevant_why=why,
            group=f"{board['source']}:{short_hash(j['title'] + text)}",
            extra={"html": "\n".join(html_parts), "education": j.get("education"), "experience": j.get("experience"),
                   "function": j.get("function"), "industry": j.get("industry"), "locations": locs},
        )

    with ThreadPoolExecutor(3) as pool:
        return list(pool.map(one, jobs))


# --- Workday -----------------------------------------------------------------------------------

def workday(board):
    """board: host, tenant, site; optional 'search' list of keywords (else the whole board)."""
    base = f"https://{board['host']}/wday/cxs/{board['tenant']}/{board['site_id']}"
    seen, paths = set(), []
    for q in board.get("search") or [""]:
        off = 0
        while True:
            d = fetch_json(base + "/jobs", data={"appliedFacets": {}, "limit": 20, "offset": off, "searchText": q})
            for p in d.get("jobPostings", []):
                if p["externalPath"] not in seen:
                    seen.add(p["externalPath"])
                    paths.append(p)
            off += 20
            if off >= d.get("total", 0) or off > 2000:
                break

    def one(p):
        rel, why = _rel(board, p["title"])
        if not rel and not board.get("keep_all"):
            return None
        raw = fetch(base + p["externalPath"])
        save_raw(board["source"], p["externalPath"].rsplit("/", 1)[-1] + ".json", raw)
        info = json.loads(raw).get("jobPostingInfo", {})
        text = html_to_text(info.get("jobDescription"))
        return listing(
            board["site"], board["source"], info.get("jobReqId") or p["externalPath"], info.get("title") or p["title"],
            info.get("externalUrl") or f"https://{board['host']}/en-US/{board['site_id']}{p['externalPath']}", text,
            location="; ".join([info.get("location") or ""] + (info.get("additionalLocations") or [])),
            countries=(info.get("country") or {}).get("descriptor", ""), employment_type=info.get("timeType") or "",
            posted=info.get("startDate") or "", relevant=rel, relevant_why=why,
            extra={"html": info.get("jobDescription"), "postedOn": info.get("postedOn")},
        )

    with ThreadPoolExecutor(3) as pool:
        return [r for r in pool.map(one, paths) if r]
