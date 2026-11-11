"""Data for the public page (docs/, served by GitHub Pages) -> docs/data/jobs.json.

    python3 -m annotationjobs.site

One record per distinct open job (copies of one job posted per city or country merged), with its
place in every grouping the page offers. The page plots the top of the stated pay range in US dollars
("up to $X" counts as X), either per hour or per task / project:

- per hour: hourly rates, and salaries where the listing gives no hourly rate, at 40 hours a week
  (a year = 2,080 hours, a month = 2,080 / 12 hours);
- other currencies are converted with the European Central Bank's rates of the day the page data was
  first built for a snapshot (data/fx.json, kept so a rebuild gives the same numbers).
"""

import collections
import json
import re
import sys
import urllib.request
from pathlib import Path

from . import categories as C
from .collect import all_listings
from .groups import KIND_NAME, RULES, degree_level
from .logos import logo_paths
from .places import COUNTRIES, ISO, STATE, normalize_places, places_in
from .terms import pay_factors

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data" / "jobs.json"
FX = ROOT / "data" / "fx.json"
FX_URL = "https://api.frankfurter.dev/v1/latest?base=USD"  # European Central Bank reference rates
HOURS = {"year": 52 * 40, "month": 52 * 40 / 12}  # 40 hours a week
PIECE_UNITS = ("task", "project", "session", "")  # "" = an amount with no unit ("$1,000 per successful placement")

YEARS = ["Not stated", "Preferred only", "1 year or less", "2 years", "3 years", "4–5 years", "6+ years"]
DEGREES = ["None mentioned", "Associate's", "Bachelor's", "Master's", "PhD", "MD / JD"]
MODES = {"remote": "Remote", "hybrid": "Hybrid", "onsite": "On site", "": "Not stated"}
CONTRACTS = {"contractor": "Contractor (stated)", "contractor?": "Contract (assumed)", "temporary": "Temporary / fixed-term",
             "internship": "Internship", "permanent": "Permanent employee", "": "Not stated"}
PAY = ["Fixed figure or range", "Only \"up to\"", "No figure, but says how", "Nothing about pay"]
DEP_NONE, DEP_UNNAMED = "Not said", "Several factors (not named)"
UNITS = {"hour": "Hour", "year": "Year (salary)", "month": "Month (salary)", "task": "Task", "session": "Session",
         "project": "Project", "": "Amount, unit not stated", None: "No pay figure"}
# location rule -> short code the page uses for "open to people in <country>"
RULE_CODE = {"only listed places": "only", "anywhere": "any", "anywhere except excluded": "except", "must come on site": "onsite",
             "listed place, rule not stated": "listed", "": ""}
COUNTRY_NAMES = set(COUNTRIES) | set(ISO.values())
CUR = ["US$ (stated)", "\"$\" on a US-only job", "\"$\" assumed to be US$", "Converted from another currency", "No pay figure"]

# key, label, help, values (in their natural order), ordinal (natural order means something)
DIMS = [
    ("site", "Site", "Where the job is posted.", None, False),
    ("kind", "Type of site", "Contributor platforms (Mercor, Outlier...), data companies' own job boards, AI labs, big tech.",
     list(KIND_NAME.values()), False),
    ("field", "Field", "The specialist knowledge the job asks for, read from the full listing by a language model "
     "(GPT-6.1 Terra). Open a job in the table to see the sentences it used.",
     [n for n, _ in C.FIELDS.values()] + [C.NOT_SORTED], False),
    ("task", "Kind of task", "What the work mainly is, read from the full listing by a language model (GPT-6.1 Terra).",
     [n for n, _ in C.TASKS.values()] + [C.NOT_SORTED], False),
    ("lang", "Language", "The language other than English the job requires. Jobs asking for two or more are under "
     "\u201cSeveral languages\u201d; the search box finds each language.", None, False),
    ("degree", "Degree mentioned", "Highest degree the listing mentions (mentioned, not necessarily required).", DEGREES, True),
    ("years", "Experience asked", "Smallest number of years of experience the listing asks for.", YEARS, True),
    ("mode", "Work mode", "Remote, hybrid or on site.", list(MODES.values()), False),
    ("who", "Who can apply", "Whether the listing limits where you must live or work.", [n for _, n, _ in RULES], False),
    ("contract", "Kind of job", "Contractor unless the listing says otherwise; permanent only when stated.",
     list(CONTRACTS.values()), False),
    ("unit", "Paid per", "What the pay figure is for. Salaries are shown per hour at 40 hours a week.",
     list(UNITS.values()), False),
    ("pay", "How pay is stated", "A fixed figure or range, or only an \"up to\" (the job likely pays less).", PAY, False),
    ("dep", "What sets the rate", "What the listing says the pay depends on, next to the figure. A range on its own does not say.",
     None, False),
    ("cur", "Currency", "\"$\" with no currency is taken as US$; other currencies are converted at the day's rate.", CUR, False),
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
        return PAY[2] if j.get("pay_note") else PAY[3]
    return PAY[1] if j["pay_min"] is None else PAY[0]


def depends_kind(j):
    """'Experience, skill level and location': the factors the listing names, in a fixed order."""
    quote = j.get("pay_depends_on")
    if not quote:
        return DEP_NONE
    names = pay_factors(quote)
    if not names:
        return DEP_UNNAMED
    names = [names[0]] + [n.lower() for n in names[1:]]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def cur_kind(j):
    if j["pay_max"] is None:
        return CUR[4]
    if j.get("pay_currency") != "USD":
        return CUR[3]
    src = j.get("pay_currency_source") or ""
    return CUR[1] if src.startswith("location") else CUR[2] if src.startswith("assumed") else CUR[0]


def exchange_rates(snapshot, needed):
    """Units of each currency per US dollar. Fetched once per snapshot and kept in data/fx.json."""
    old = json.loads(FX.read_text()) if FX.exists() else None
    if old and old.get("snapshot") == snapshot and needed <= set(old["per_usd"]) | {"USD"}:
        return old
    try:
        with urllib.request.urlopen(urllib.request.Request(FX_URL, headers={"User-Agent": "annotationjobs"}), timeout=30) as f:
            got = json.load(f)
        fx = {"snapshot": snapshot, "date": got["date"], "source": "European Central Bank reference rates (frankfurter.dev)",
              "per_usd": got["rates"]}
        FX.write_text(json.dumps(fx, indent=1, sort_keys=True) + "\n")
        return fx
    except (OSError, ValueError, KeyError) as e:
        if old:
            print(f"site: exchange rates not fetched ({e}); using those of {old['date']}", file=sys.stderr)
            return old
        print(f"site: exchange rates not fetched ({e}); jobs paid in other currencies stay out of the chart", file=sys.stderr)
        return {"snapshot": snapshot, "date": "", "source": "", "per_usd": {}}


def money(v, cur="USD"):
    sym = {"USD": "$", "EUR": "€", "GBP": "£", "CAD": "CA$", "AUD": "A$", "INR": "₹"}.get(cur, cur + " ")
    return sym + (f"{v:,.0f}" if v >= 1000 or v == int(v) else f"{v:,.2f}")


def pay_in_usd(j, fx):
    """(US$ per hour, US$ per piece, how it was worked out): the top of the stated range, converted."""
    unit, top, cur = j.get("pay_unit"), j.get("pay_max"), j.get("pay_currency") or "USD"
    if top is None:
        return None, None, ""
    steps = []
    if unit in HOURS:  # a salary: an hourly rate elsewhere in the listing wins
        hourly = [m for m in j.get("pay_all") or [] if m[3] == "hour" and m[1] and m[1] > 1]
        if hourly:
            top, cur, unit = hourly[0][1], hourly[0][2] or cur, "hour"
            steps.append(f"hourly rate {money(top, cur)}/hr also in the listing, used instead of the salary")
    if cur != "USD":
        rate = fx["per_usd"].get(cur)
        if not rate:
            return None, None, f"no exchange rate for {cur}"
        steps.append(f"{money(top, cur)} = {money(top / rate)} at the rate of {fx['date']} ({rate:g} {cur} per US$)")
        top = top / rate
    if unit in HOURS:
        steps.append(f"{money(top)} a {unit} ÷ {HOURS[unit]:,.0f} hours (40 hours a week) = {money(top / HOURS[unit])}/hr")
        return top / HOURS[unit], None, "; ".join(steps)
    if unit == "hour":
        return top, None, "; ".join(steps)
    if unit in PIECE_UNITS:
        return None, top, "; ".join(steps)
    return None, None, "; ".join(steps)  # per day / week: not shown


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


def _r(v):
    return None if v is None else round(v, 2)


def clip(s, n=320):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def quotes(pairs):
    """The model's evidence passages that are really in the listing."""
    return " … ".join(q for q, found in pairs or [] if found)


def build():
    labels = C.load()
    rows, _ = all_listings()
    groups = collections.defaultdict(list)
    for r in rows:
        if r["active"]:
            groups[r["group"]].append(r)
    snapshot = max(r["last_seen"] for r in rows if r["active"])
    fx = exchange_rates(snapshot, {c[0]["pay_currency"] for c in groups.values() if c[0]["pay_max"] is not None})
    jobs = []
    for copies in groups.values():
        j = copies[0]
        locations = list(dict.fromkeys(p for r in copies for p in (r.get("location") or "").split("; ") if p.strip()))
        if j.get("location_rule") == "only listed places":  # copies of one job can name different places
            j = j | {"allowed_places": list(dict.fromkeys(p for r in copies for p in r.get("allowed_places") or []))}
        lab = C.label_for(copies, labels) or {}
        cat = {
            "site": j["site"],
            "kind": KIND_NAME[j["kind"]],
            "field": C.FIELDS[lab["field"]][0] if lab else C.NOT_SORTED,
            "task": C.TASKS[lab["task"]][0] if lab else C.NOT_SORTED,
            "lang": C.language_group(lab["languages"]) if lab else C.NOT_SORTED,
            "degree": {"none": DEGREES[0], "MD / JD": "MD / JD"}.get(degree_level(j.get("degrees")), degree_level(j.get("degrees"))),
            "years": years_bucket(j),
            "mode": MODES.get(j.get("work_mode") or "", "Not stated"),
            "who": next(n for k, n, _ in RULES if (j.get("location_rule") or "") == k),
            "contract": CONTRACTS.get(j.get("contract_type") or "", "Not stated"),
            "unit": UNITS.get(j.get("pay_unit") if j["pay_max"] is not None else None, j.get("pay_unit")),
            "pay": pay_kind(j),
            "dep": depends_kind(j),
            "cur": cur_kind(j),
        }
        hourly, piece, how = pay_in_usd(j, fx)
        evidence = {
            "Pay as written": clip(j.get("pay_text")),
            "Pay read from": j.get("pay_source") or "",
            "Currency": clip(j.get("pay_currency_source")),
            "Pay depends on": clip(j.get("pay_depends_on")),
            "About pay": clip(j.get("pay_note")),
            "Earnings claim (not used)": clip(j.get("pay_earnings_claim")),
            "Who can apply": clip(j.get("location_evidence")),
            "Work mode": clip(j.get("work_mode_evidence")),
            "Kind of job": clip(j.get("contract_evidence")),
            "Experience": clip(j.get("experience_text")),
            "Degrees mentioned": j.get("degrees") or "",
            "Hours per week": str(j["hours_per_week"]) if j.get("hours_per_week") else "",
            "Field": clip(quotes(lab.get("field_evidence"))),
            "Kind of task": clip(quotes(lab.get("task_evidence"))),
            "Languages": ", ".join(lab.get("varieties") or C.languages(lab)),
            "Languages, as written": clip(quotes(lab.get("languages_evidence"))),
            "Converted": how,
        }
        jobs.append({
            "id": j["uid"], "t": j["title"].strip(), "s": j["site"], "u": j["url"],
            "co": j["company"] if j.get("company") and j["company"] != j["site"] else "",
            "pmin": j["pay_min"], "pmax": j["pay_max"], "cur": j.get("pay_currency") or "", "unit": j.get("pay_unit") or "",
            "h": _r(hourly), "pt": _r(piece), "cat": cat, "w": RULE_CODE[j.get("location_rule") or ""],
            "pl": places_of(j, locations), "loc": locations[:12], "nloc": len(locations), "n": len(copies),
            "lg": list(dict.fromkeys(C.languages(lab) + (lab.get("varieties") or []))),  # for the search box
            "first": min(r["first_seen"] for r in copies), "posted": j.get("posted") or "",
            "ev": {k: v for k, v in evidence.items() if v},
        })
    # values of each grouping: natural order when it has one, else by number of jobs
    count = {k: collections.Counter(j["cat"][k] for j in jobs) for k, *_ in DIMS}
    dims = []
    for key, label, help_, values, ordinal in DIMS:
        vals = list(dict.fromkeys(v for v in values if count[key][v])) if values else [v for v, _ in count[key].most_common()]
        assert set(vals) == set(count[key]), (key, set(count[key]) - set(vals))
        dims.append({"key": key, "label": label, "help": help_, "values": vals, "ordinal": ordinal})
    index = {d["key"]: {v: i for i, v in enumerate(d["values"])} for d in dims}
    for j in jobs:
        j["c"] = [index[d["key"]][j["cat"][d["key"]]] for d in dims]
        del j["cat"]
    jobs.sort(key=lambda j: (-(j["h"] or 0), j["t"]))
    data = {"snapshot": snapshot, "dims": dims, "jobs": jobs, "postings": sum(j["n"] for j in jobs),
            "fx": {"date": fx["date"], "source": fx["source"]},
            "logos": logo_paths(next(d["values"] for d in dims if d["key"] == "site"))}  # site -> its small logo (docs/logos/, python3 -m annotationjobs.logos)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    n_h, n_p = sum(j["h"] is not None for j in jobs), sum(j["pt"] is not None for j in jobs)
    print(f"site: {len(jobs)} jobs ({n_h} paid per hour, {n_p} per task or project), snapshot {snapshot} -> {OUT.relative_to(ROOT)}"
          f" ({OUT.stat().st_size / 1e6:.1f} MB)")
    missing = sum(not C.label_for(c, labels) for c in groups.values())
    if missing:
        print(f"site: {missing} jobs not sorted into field / task / language yet: "
              "uv run --no-project --with lm15==1.5.0 python -m annotationjobs.categorize", file=sys.stderr)


if __name__ == "__main__":
    build()
