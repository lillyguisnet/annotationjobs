"""Collect open AI-training / annotation listings from Mercor and Handshake AI.

Writes data/jobs.json (everything, with full descriptions), data/jobs.csv
(one row per listing, the columns a person compares) and data/index.html
(a searchable, sortable table built from page.html). Standard library only:

    python3 scrape.py
"""

import csv
import html
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) annotationjobs-survey"
OUT = Path(__file__).parent / "data"


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def page_text(h):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", "\n", t))
    return [ln.strip() for ln in t.split("\n") if ln.strip()]


# --- shared extraction from free text -------------------------------------

WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
         "eight": 8, "nine": 9, "ten": 10, "twelve": 12, "fifteen": 15, "twenty": 20}
YEARS = re.compile(
    r"\b(\d{1,2}|" + "|".join(WORDS) + r")\s*(?:\(\d+\))?\s*\+?\s*(?:(?:[-–]|to)\s*\d{1,2}\s*\+?\s*)?(?:full[- ]time\s+)?(?:years?|yrs)\b",
    re.I,
)
DEGREES = [
    ("PhD", r"\bph\.?\s?d\b|doctora|\bdphil\b|\bmd\b|\bjd\b|\bpostdoc"),
    ("Master's", r"master'?s|\bm\.?s\.?c?\b|\bmba\b|\bm\.?a\.?\b(?= in)"),
    ("Bachelor's", r"bachelor'?s|\bb\.?s\.?c?\b(?= in)|\bb\.?a\.?\b(?= in)|undergraduate degree|college degree"),
    ("Associate's", r"associate'?s degree"),
]


def experience(text):
    """Smallest 'N years' figure in a sentence about experience, plus that sentence.

    Required figures win over ones in a 'nice to have' / 'preferred' part; when
    only the latter exist the quote is prefixed with '(preferred)'."""
    req, pref = experience_in(text, nice=False), experience_in(text, nice=True)
    if req[0] is not None:
        return req
    if pref[0] is not None:
        return pref[0], "(preferred) " + pref[1]
    return None, ""


NICE = re.compile(r"nice to have|preferred|bonus|plus\b|strengthen your application|ideal", re.I)


def experience_in(text, nice):
    best, sentence, in_nice = None, "", False
    for s in re.split(r"(?<=[.;])\s+|\n|\s-\s", text.replace("**", "")):
        if re.match(r"\s*#*\s*(nice to have|preferred|bonus|additional qualifications)", s, re.I):
            in_nice = True
        elif re.match(r"\s*#+\s|\s*(required|requirements|qualifications|what you)", s, re.I):
            in_nice = False
        if (in_nice or bool(NICE.search(s))) != nice:
            continue
        if not re.search(r"experien|practic|working|professional|career|in the field|industry", s, re.I):
            continue
        for m in YEARS.finditer(s):
            g = m.group(1).lower()
            n = WORDS.get(g) or int(g)
            if 0 < n <= 40 and (best is None or n < best):
                s = re.sub(r"\s+", " ", s).strip(" -*#")
                s = re.sub(r"^Qualifications\s*", "", s)
                best, sentence = n, s[:300]
    return best, sentence


def degrees_in(text):
    return [name for name, rx in DEGREES if re.search(rx, text, re.I)]


# --- Mercor ----------------------------------------------------------------

def mercor():
    h = get("https://work.mercor.com/explore")
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>', h, re.S)
    props = json.loads(m.group(1))["props"]["pageProps"]
    listings = props["dehydratedState"]["queries"][0]["state"]["data"]["listings"]
    urls = {u["url"].split("/jobs/")[1].split("/")[0]: u["url"]
            for u in props["structuredData"]["itemList"]["itemListElement"]}
    rows = []
    for x in listings:
        desc = x.get("description") or ""
        yrs, yrs_text = experience(desc)
        freq = x.get("payRateFrequency") or ""
        rows.append({
            "site": "Mercor",
            "title": x["title"].strip(),
            "pay_min": x.get("rateMin"),
            "pay_max": x.get("rateMax"),
            "pay_unit": {"hourly": "hour", "per-task": "task", "one-time": "one-time", "yearly": "year"}.get(freq, freq),
            "hours_per_week": x.get("hoursPerWeek"),
            "commitment": x.get("commitment") or "",
            "arrangement": x.get("workArrangement") or "",
            "location": x.get("location") or "",
            "eligible_countries": ", ".join(x.get("eligibleLocation") or []),
            "degrees_mentioned": ", ".join(degrees_in(desc)),
            "min_years_experience": yrs,
            "experience_text": yrs_text,
            "posted": (x.get("postedAt") or x.get("createdAt") or "")[:10],
            "url": urls.get(x["listingId"], f"https://work.mercor.com/jobs/{x['listingId']}"),
            "description": desc,
        })
    return rows


# --- Handshake AI ----------------------------------------------------------

def handshake_urls():
    urls = []
    for i in range(10):
        try:
            xml = get(f"https://joinhandshake.com/sitemap-{i}.xml", tries=1)
        except Exception:
            break
        urls += re.findall(r"<loc>(https://joinhandshake.com/ai/opportunities/[^<]+/)</loc>", xml)
    return sorted(set(urls))


def handshake_one(url):
    lines = page_text(get(url))
    # Header block: title, "Sign up now", "Up to $X/hr", "Depending on the project", degrees..., Remote, Part-time
    start = next((i for i, l in enumerate(lines) if l in ("Apply now", "Sign up now") and i > 5), None)
    if start is None:
        print("no header", url)
        return None
    title = lines[start - 1]
    head = lines[start + 1:start + 25]
    pay_line = next((l for l in head if "$" in l), "")
    nums = [float(n.replace(",", "")) for n in re.findall(r"\$([\d,]+(?:\.\d+)?)", pay_line)]
    unit = "hour" if re.search(r"/\s*h(ou)?r", pay_line) else ("task" if "task" in pay_line.lower() else "")
    degs = [l.replace("Ph.D's", "PhD").replace("Ph.Ds", "PhD") for l in head
            if re.match(r"(Associate|Bachelor|Master|Ph\.?D|Postdoc)", l) and len(l) < 15]
    tags = [l for l in head if l in ("Remote", "Part-time", "Full-time", "Flexible hours", "Hybrid", "Onsite")]
    opt_cpt = any("OPT/CPT" in l for l in head)
    try:
        body_start = lines.index("Opportunity Overview")
    except ValueError:
        body_start = start + 1
    try:
        body_end = lines.index("The application process")
    except ValueError:
        body_end = len(lines)
    # "Degree" / ": Completed ..." arrive as two lines; glue them back together
    desc = "\n".join(lines[body_start:body_end]).replace("\n: ", ": ")
    yrs, yrs_text = experience(desc)
    return {
        "site": "Handshake AI",
        "title": title,
        "pay_min": nums[0] if len(nums) > 1 else None,
        "pay_max": nums[-1] if nums else None,
        "pay_unit": unit,
        "hours_per_week": None,
        "commitment": ", ".join(t for t in tags if t != "Remote"),
        "arrangement": "remote" if "Remote" in tags else "",
        "location": "United States" if "United States" in desc else "",
        "eligible_countries": "USA" + (" (OPT/CPT students eligible)" if opt_cpt else ""),
        "degrees_mentioned": ", ".join(degs),
        "min_years_experience": yrs,
        "experience_text": yrs_text,
        "posted": "",
        "url": url,
        "description": desc,
    }


def handshake():
    urls = handshake_urls()
    with ThreadPoolExecutor(4) as pool:  # gentle: 4 pages at a time
        rows = list(pool.map(lambda u: _safe(handshake_one, u), urls))
    return [r for r in rows if r]


def _safe(f, u):
    try:
        return f(u)
    except Exception as e:
        print("skip", u, e)
        return None


def main():
    OUT.mkdir(exist_ok=True)
    rows = mercor() + handshake()
    for r in rows:
        r["collected"] = date.today().isoformat()
    json.dump(rows, open(OUT / "jobs.json", "w"), indent=1, ensure_ascii=False)
    cols = [k for k in rows[0] if k != "description"]
    with open(OUT / "jobs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    page = (Path(__file__).parent / "page.html").read_text()
    data = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    (OUT / "index.html").write_text(page.replace("/*DATA*/[]", data))
    by = {}
    for r in rows:
        by[r["site"]] = by.get(r["site"], 0) + 1
    print(by, "->", OUT)


if __name__ == "__main__":
    main()
