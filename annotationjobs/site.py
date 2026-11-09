"""Data for the public page (docs/, served by GitHub Pages) -> docs/data/jobs.json.

    python3 -m annotationjobs.site

One record per distinct open job (copies of one job posted per city or country merged), with its
place in every grouping the page offers. The page plots the top of the hourly rate in US dollars,
the same number as the charts in data/plots ("up to $X" counts as X).
"""

import collections
import json
import re
from pathlib import Path

from .collect import all_listings
from .groups import FIELDS, KIND_NAME, RULES, degree_level, field, hourly_usd
from .places import COUNTRIES, ISO, STATE, normalize_places, places_in

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data" / "jobs.json"

YEARS = ["Not stated", "Preferred only", "1 year or less", "2 years", "3 years", "4–5 years", "6+ years"]
DEGREES = ["None mentioned", "Associate's", "Bachelor's", "Master's", "PhD", "MD / JD"]
MODES = {"remote": "Remote", "hybrid": "Hybrid", "onsite": "On site", "": "Not stated"}
CONTRACTS = {"contractor": "Contractor (stated)", "contractor?": "Contract (assumed)", "temporary": "Temporary / fixed-term",
             "internship": "Internship", "permanent": "Permanent employee", "": "Not stated"}
PAY = ["Hourly: fixed figure or range", "Hourly: varies or only \"up to\"", "Per project, task or session",
       "Yearly or monthly salary", "In another currency", "No figure, but says how", "Nothing about pay"]
# location rule -> short code the page uses for "open to people in <country>"
RULE_CODE = {"only listed places": "only", "anywhere": "any", "anywhere except excluded": "except", "must come on site": "onsite",
             "listed place, rule not stated": "listed", "": ""}
COUNTRY_NAMES = set(COUNTRIES) | set(ISO.values())
USD = ["Says US$", "\"$\" on a US-only job", "\"$\" assumed to be US$", "Not in the chart"]

# key, label, help, values (in their natural order), ordinal (natural order means something)
DIMS = [
    ("site", "Site", "Where the job is posted.", None, False),
    ("kind", "Type of site", "Contributor platforms (Mercor, Outlier...), data companies' own job boards, AI labs, big tech.",
     list(KIND_NAME.values()), False),
    ("field", "Field", "Guessed from the job title by keywords, so some jobs land in the wrong field.",
     [n for n, _ in FIELDS] + ["Other"], False),
    ("degree", "Degree mentioned", "Highest degree the listing mentions (mentioned, not necessarily required).", DEGREES, True),
    ("years", "Experience asked", "Smallest number of years of experience the listing asks for.", YEARS, True),
    ("mode", "Work mode", "Remote, hybrid or on site.", list(MODES.values()), False),
    ("who", "Who can apply", "Whether the listing limits where you must live or work.", [n for _, n, _ in RULES], False),
    ("contract", "Kind of job", "Contractor unless the listing says otherwise; permanent only when stated.",
     list(CONTRACTS.values()), False),
    ("pay", "How pay is stated", "Only hourly US$ figures are in the chart.", PAY, False),
    ("usd", "Why US$", "How we know the hourly figure is in US dollars.", USD, False),
]


def years_bucket(j):
    y = j.get("min_years_experience")
    if y is None:
        return YEARS[0]
    if (j.get("experience_text") or "").startswith("(preferred)"):
        return YEARS[1]
    return YEARS[2] if y <= 1 else YEARS[3] if y == 2 else YEARS[4] if y == 3 else YEARS[5] if y <= 5 else YEARS[6]


def pay_kind(j):
    if j["pay_max"] is None:
        return PAY[5] if j.get("pay_note") else PAY[6]
    if j.get("pay_currency") != "USD":
        return PAY[4]
    if j["pay_unit"] == "hour":
        return PAY[1] if j.get("pay_variable") else PAY[0]
    if j["pay_unit"] in ("year", "month"):
        return PAY[3]
    return PAY[2]


def usd_kind(j):
    if hourly_usd(j) is None:
        return USD[3]
    src = j.get("pay_currency_source") or ""
    return USD[1] if src.startswith("location") else USD[2] if src.startswith("assumed") else USD[0]


def places_of(j, locations):
    """Countries a job is open to (restricted jobs), closed to ("anywhere except"), or happens in (on site, place
    listed without a rule)."""
    if j.get("location_rule") == "only listed places":
        return normalize_places(j.get("allowed_places") or [])
    if j.get("location_rule") == "anywhere except excluded":
        return normalize_places(j.get("excluded_places") or [])
    out = []
    for loc in locations:
        # full names only: a two-letter ending ("Santa Clara, CA", "Munich, DE") can be a US state or a country
        ps = places_in(loc, strict=True)
        if not ps and (STATE.search(loc) or re.search(r"(?:^|, )(?:US|USA)$", loc)):
            ps = ["United States"]
        out += [p for p in ps if p in COUNTRY_NAMES and p not in out]
    return out


def clip(s, n=320):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def build():
    rows, _ = all_listings()
    groups = collections.defaultdict(list)
    for r in rows:
        if r["active"]:
            groups[r["group"]].append(r)
    jobs = []
    for copies in groups.values():
        j = copies[0]
        locations = list(dict.fromkeys(p for r in copies for p in (r.get("location") or "").split("; ") if p.strip()))
        if j.get("location_rule") == "only listed places":  # copies of one job can name different places
            j = j | {"allowed_places": list(dict.fromkeys(p for r in copies for p in r.get("allowed_places") or []))}
        cat = {
            "site": j["site"],
            "kind": KIND_NAME[j["kind"]],
            "field": field(j["title"]),
            "degree": {"none": DEGREES[0], "MD / JD": "MD / JD"}.get(degree_level(j.get("degrees")), degree_level(j.get("degrees"))),
            "years": years_bucket(j),
            "mode": MODES.get(j.get("work_mode") or "", "Not stated"),
            "who": next(n for k, n, _ in RULES if (j.get("location_rule") or "") == k),
            "contract": CONTRACTS.get(j.get("contract_type") or "", "Not stated"),
            "pay": pay_kind(j),
            "usd": usd_kind(j),
        }
        evidence = {
            "Pay as written": clip(j.get("pay_text")),
            "Pay read from": j.get("pay_source") or "",
            "Currency": clip(j.get("pay_currency_source")),
            "Why pay varies": clip(j.get("pay_variable_why")),
            "About pay": clip(j.get("pay_note")),
            "Earnings claim (not used)": clip(j.get("pay_earnings_claim")),
            "Who can apply": clip(j.get("location_evidence")),
            "Work mode": clip(j.get("work_mode_evidence")),
            "Kind of job": clip(j.get("contract_evidence")),
            "Experience": clip(j.get("experience_text")),
            "Degrees mentioned": j.get("degrees") or "",
            "Hours per week": str(j["hours_per_week"]) if j.get("hours_per_week") else "",
        }
        jobs.append({
            "id": j["uid"], "t": j["title"].strip(), "s": j["site"], "u": j["url"],
            "co": j["company"] if j.get("company") and j["company"] != j["site"] else "",
            "pmin": j["pay_min"], "pmax": j["pay_max"], "cur": j.get("pay_currency") or "", "unit": j.get("pay_unit") or "",
            "h": hourly_usd(j), "cat": cat, "w": RULE_CODE[j.get("location_rule") or ""],
            "pl": places_of(j, locations), "loc": locations[:12], "nloc": len(locations), "n": len(copies),
            "first": min(r["first_seen"] for r in copies), "posted": j.get("posted") or "",
            "ev": {k: v for k, v in evidence.items() if v},
        })
    # values of each grouping: natural order when it has one, else by number of jobs
    count = {k: collections.Counter(j["cat"][k] for j in jobs) for k, *_ in DIMS}
    dims = []
    for key, label, help_, values, ordinal in DIMS:
        vals = [v for v in values if count[key][v]] if values else [v for v, _ in count[key].most_common()]
        assert set(vals) == set(count[key]), (key, set(count[key]) - set(vals))
        dims.append({"key": key, "label": label, "help": help_, "values": vals, "ordinal": ordinal})
    index = {d["key"]: {v: i for i, v in enumerate(d["values"])} for d in dims}
    for j in jobs:
        j["c"] = [index[d["key"]][j["cat"][d["key"]]] for d in dims]
        del j["cat"]
    jobs.sort(key=lambda j: (-(j["h"] or 0), j["t"]))
    snapshot = max(r["last_seen"] for r in rows if r["active"])
    data = {"snapshot": snapshot, "dims": dims, "jobs": jobs, "postings": sum(j["n"] for j in jobs)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    n_h = sum(j["h"] is not None for j in jobs)
    print(f"site: {len(jobs)} jobs ({n_h} with an hourly US$ rate), snapshot {snapshot} -> {OUT.relative_to(ROOT)}"
          f" ({OUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    build()
