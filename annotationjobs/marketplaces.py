"""Readers for contributor marketplaces with their own sites (every listing is contributor work)."""

import json
import re
from concurrent.futures import ThreadPoolExecutor

from .common import (fetch, fetch_json, flight_text_row, html_to_text, listing, next_data, next_flight,
                     page_lines, save_raw, short_hash)


def _pool(fn, items, n=4):
    def safe(x):
        try:
            return fn(x)
        except Exception as e:
            print(f"   skip {str(x)[:90]}: {e}")
            return None
    with ThreadPoolExecutor(n) as p:
        return [r for r in p.map(safe, items) if r]


def _num(x):
    try:
        return float(x) if x not in (None, "", "None") else None
    except (TypeError, ValueError):
        return None


# --- Mercor ---------------------------------------------------------------------------

def mercor(board):
    h = fetch("https://work.mercor.com/explore", raw=(board["source"], "explore.html"))
    props = next_data(h)["props"]["pageProps"]
    rows = props["dehydratedState"]["queries"][0]["state"]["data"]["listings"]
    urls = {u["url"].split("/jobs/")[1].split("/")[0]: u["url"]
            for u in props["structuredData"]["itemList"]["itemListElement"]}
    unit = {"hourly": "hour", "per-task": "task", "one-time": "one-time", "yearly": "year", "monthly": "month"}
    out = []
    for x in rows:
        out.append(listing(
            "Mercor", board["source"], x["listingId"], x["title"],
            urls.get(x["listingId"], f"https://work.mercor.com/jobs/{x['listingId']}"), x.get("description") or "",
            company=x.get("companyName") or "Mercor (client not named)",
            pay_min=x.get("rateMin"), pay_max=x.get("rateMax"),
            pay_unit=unit.get(x.get("payRateFrequency"), x.get("payRateFrequency")),
            hours_per_week=x.get("hoursPerWeek"), commitment=x.get("commitment") or "",
            arrangement=x.get("workArrangement") or "", location=x.get("location") or "",
            countries=", ".join(x.get("eligibleLocation") or []),
            posted=(x.get("postedAt") or x.get("createdAt") or "")[:10],
            extra={k: v for k, v in x.items() if k != "description"},
        ))
    return out


# --- Handshake AI ------------------------------------------------------------------------

def handshake(board):
    urls = []
    for i in range(10):
        try:
            xml = fetch(f"https://joinhandshake.com/sitemap-{i}.xml", tries=1)
        except Exception:
            break
        urls += re.findall(r"<loc>(https://joinhandshake.com/ai/opportunities/[^<]+/)</loc>", xml)

    def one(url):
        h = fetch(url)
        lines = page_lines(h)
        start = next((i for i, l in enumerate(lines) if l in ("Apply now", "Sign up now") and i > 5), None)
        if start is None:
            return None
        save_raw(board["source"], url.rstrip("/").rsplit("/", 1)[-1] + ".html", h)
        title = lines[start - 1]
        head = lines[start + 1:start + 25]
        pay_line = next((l for l in head if "$" in l), "")
        nums = [float(n.replace(",", "")) for n in re.findall(r"\$([\d,]+(?:\.\d+)?)", pay_line)]
        degs = [l.replace("Ph.D's", "PhD").replace("Ph.Ds", "PhD") for l in head
                if re.match(r"(Associate|Bachelor|Master|Ph\.?D|Postdoc)", l) and len(l) < 15]
        tags = [l for l in head if l in ("Remote", "Part-time", "Full-time", "Flexible hours", "Hybrid", "Onsite")]
        opt = any("OPT/CPT" in l for l in head)
        end = next((i for i, l in enumerate(lines) if l == "The application process"), len(lines))
        body = "\n".join(lines[start - 1:end]).replace("\n: ", ": ")
        return listing(
            "Handshake AI", board["source"], url.rstrip("/").rsplit("/", 1)[-1], title, url, body,
            pay_min=nums[0] if len(nums) > 1 else None, pay_max=nums[-1] if nums else None,
            pay_unit="hour" if "/hr" in pay_line else "", pay_text=pay_line,
            commitment=", ".join(t for t in tags if t != "Remote"), arrangement="remote" if "Remote" in tags else "",
            countries="USA" + (" (OPT/CPT students eligible)" if opt else ""),
            degrees=", ".join(degs), extra={"tags": head[:12]},
        )
    return _pool(one, sorted(set(urls)))


# --- micro1 -------------------------------------------------------------------------------

def micro1(board):
    api = "https://prod-api.micro1.ai/api/v1/job/portal"
    jobs, page = [], 1
    while True:
        d = fetch_json(f"{api}?page={page}&limit=100&keyword=",
                       data={"action": "get_all_jobs", "filters": {"type": ["EXPERT"]}})
        save_raw(board["source"], f"list-{page}.json", json.dumps(d))
        jobs += d.get("data") or []
        if not d.get("data") or len(jobs) >= int(d.get("total") or 0):
            break
        page += 1

    def one(j):
        url = f"https://jobs.micro1.ai/post/{j['job_id']}"
        h = fetch(url)
        save_raw(board["source"], j["job_id"] + ".html", h)
        fl = next_flight(h)
        data = {}
        m = re.search(r'[0-9a-f]+:(\["\$","\$L[0-9a-f]+",null,\{"id":"' + re.escape(j["job_id"]) + '","data")', fl)
        if m:
            try:
                data = json.JSONDecoder().raw_decode(fl[m.start(1):])[0][3].get("data", {})
            except Exception:
                data = {}
        desc = data.get("job_description") or ""
        if isinstance(desc, str) and desc.startswith("$"):
            desc = flight_text_row(fl, desc)
        text = html_to_text(desc)
        hr = _num(data.get("ideal_hourly_rate") or j.get("ideal_hourly_rate"))
        mo_lo, mo_hi = _num(j.get("ideal_monthly_salary_min")), _num(j.get("ideal_monthly_salary_max"))
        yr = _num(j.get("ideal_yearly_compensation"))
        pay = (None, hr, "hour") if hr else ((mo_lo, mo_hi, "month") if mo_hi else ((None, yr, "year") if yr else (None, None, None)))
        return listing(
            "micro1", board["source"], j["job_id"], j.get("job_name") or data.get("job_role_name"), url, text,
            company=j.get("company_name") or "micro1",
            pay_min=pay[0], pay_max=pay[1], pay_unit=pay[2],
            commitment=j.get("engagement_type") or data.get("engagement_type") or "",
            arrangement=(j.get("location_type") or data.get("location_type") or "").lower(),
            location=data.get("location_name") or "", posted=(j.get("date_posted") or "")[:10],
            department=j.get("role_type") or "",
            extra={"skills": j.get("skills"), "html": desc,
                   "detail": {k: v for k, v in data.items() if k != "job_description"}},
        )
    return _pool(one, jobs)


# --- Alignerr (Labelbox) ---------------------------------------------------------------------

def alignerr(board):
    jobs, off = [], 0
    while True:
        d = fetch_json(f"https://www.alignerr.com/api/jobs?limit=100&offset={off}")
        jobs += d["jobs"]
        off += 100
        if not d["jobs"] or off >= d["total"]:
            break
    save_raw(board["source"], "list.json", json.dumps(jobs))
    build = next_data(fetch("https://www.alignerr.com/jobs"))["buildId"]

    def one(j):
        raw = fetch(f"https://www.alignerr.com/_next/data/{build}/en/jobs/{j['id']}.json")
        save_raw(board["source"], j["id"] + ".json", raw)
        x = json.loads(raw)["pageProps"]["job"]
        unit = {"HOURLY": "hour", "YEARLY": "year", "MONTHLY": "month"}.get(x.get("salaryType"), (x.get("salaryType") or "").lower())
        place = ", ".join(v for v in (x.get("city"), x.get("state"), x.get("countryCode")) if v)
        return listing(
            "Alignerr", board["source"], x["id"], x.get("name") or j["title"], f"https://www.alignerr.com/jobs/{x['id']}",
            x.get("longDescription") or html_to_text(x.get("htmlLongDescription")),
            company="Alignerr (Labelbox)",
            pay_min=_num(x.get("lowerBoundHourlyRate")), pay_max=_num(x.get("upperBoundHourlyRate")), pay_unit=unit,
            pay_text=j.get("pay") or "", location=place or x.get("location") or "",
            countries=x.get("countryCode") or x.get("location") or "", arrangement="remote" if j.get("location") == "Remote" else "",
            employment_type=x.get("jobType") or "", posted=(x.get("firstPostDate") or x.get("createdAt") or "")[:10],
            department=x.get("category") or "", group=f"alignerr:{x.get('masterJobId') or x['id']}",
            extra={k: v for k, v in x.items() if k not in ("longDescription", "htmlLongDescription")},  # raw copy has the HTML
        )
    return _pool(one, jobs, n=4)


# --- Outlier (Scale AI) ------------------------------------------------------------------------

def outlier(board):
    jobs, page = [], 1
    while True:
        d = fetch_json("https://app.outlier.ai/internal/experts/job-board/jobs", data={"page": page})
        jobs += d["jobs"]
        if page >= (d.get("totalPages") or 1):
            break
        page += 1
    save_raw(board["source"], "jobs.json", json.dumps(jobs))
    out = []
    for j in jobs:
        out.append(listing(
            "Outlier", board["source"], j["id"], j["title"], j.get("absolute_url"), html_to_text(j.get("content")),
            company="Outlier (Scale AI)", pay_max=_num(j.get("maxHourlyRateUsd")), pay_unit="hour",
            pay_text=f"up to ${j.get('maxHourlyRateUsd')}/hr" if j.get("maxHourlyRateUsd") else "",
            location=(j.get("location") or {}).get("name", ""), countries=", ".join(j.get("allowedCountries") or []),
            arrangement="remote", posted=(j.get("createdAt") or "")[:10], department=j.get("pod_group") or "",
            extra={"html": j.get("content"), "skillNames": j.get("skillNames"), "hiredThisMonth": j.get("hiredThisMonth")},
        ))
    return out


# --- DataAnnotation (Surge AI) ------------------------------------------------------------------

def dataannotation(board):
    home = fetch("https://www.dataannotation.tech/")
    slugs = sorted(set(re.findall(r'href="/job-board/([a-z0-9-]+)"', home)))

    def one(slug):
        url = f"https://www.dataannotation.tech/job-board/{slug}"
        h = fetch(url)
        save_raw(board["source"], slug + ".html", h)
        lines = page_lines(h)
        a = next((i for i, l in enumerate(lines) if l == "Apply now"), 0)
        b = next((i for i, l in enumerate(lines) if l == "Similar roles"), len(lines))
        body = "\n".join(lines[a + 1:b])
        title = lines[a + 1] if a else slug
        m = re.search(r"Hourly rate up to\s*\n?\$?([\d,]+)(\+?)", body)
        return listing(
            "DataAnnotation", board["source"], slug, title, url, body, company="DataAnnotation (Surge AI)",
            pay_max=float(m.group(1).replace(",", "")) if m else None, pay_unit="hour" if m else None,
            pay_text=("up to $" + m.group(1) + m.group(2) + "/hr") if m else "",
            arrangement="remote", commitment="Flexible hours", employment_type="Independent contractor",
        )
    return _pool(one, slugs)


# --- OneForma (Centific) ---------------------------------------------------------------------------

def oneforma(board):
    urls, page = set(), 1
    while page < 30:
        try:
            h = fetch("https://www.oneforma.com/projects/" + (f"page/{page}/" if page > 1 else ""))
        except Exception:
            break
        found = set(re.findall(r'href="(https://www\.oneforma\.com/projects/[a-z0-9-]+/)"', h)) - {"https://www.oneforma.com/projects/page/"}
        if not found - urls:
            break
        urls |= found
        page += 1
    urls = sorted(urls)

    def one(url):
        h = fetch(url)
        save_raw(board["source"], url.rstrip("/").rsplit("/", 1)[-1] + ".html", h)
        lines = page_lines(h)
        t = re.search(r"<h1[^>]*>(.*?)</h1>", h, re.S)
        title = html_to_text(t.group(1)) if t else lines[0]
        a = next((i for i, l in enumerate(lines) if l == title), 0)
        b = next((i for i, l in enumerate(lines) if l.startswith("Similar projects") or l == "Related Projects"), len(lines))
        body = "\n".join(lines[a:b])
        m = re.search(r"Available in \d+ countr\w+\n(.*?)\n(?:Remote|On-?site|Hybrid)", body, re.S)
        countries = ", ".join(m.group(1).split("\n")) if m else ""
        return listing(
            "OneForma", board["source"], url.rstrip("/").rsplit("/", 1)[-1], title, url, body,
            company="OneForma (Centific)", countries=countries,
            arrangement="remote" if "\nRemote\n" in body else "",
        )
    return _pool(one, urls)
