"""Fields read from a stored listing: pay (site field vs text), currency, engagement type, years, degrees.

Everything here works from the stored record alone (text + extra), so it can be re-run on the
whole store after an improvement without fetching anything (`collect --reparse`)."""

import gzip
import json
from pathlib import Path

from .common import RAW_ROOT, degrees_in, experience
from .terms import best_pay, engagement, pay_mentions

# What each platform says about all its work, used only when a listing itself says nothing.
SITE_DEFAULT = {
    "mercor": "contractor", "handshake": "contractor", "micro1": "contractor", "alignerr": "contractor",
    "outlier": "contractor", "dataannotation": "contractor", "mindrift": "contractor", "oneforma": "contractor",
    "lever-appen": "contractor", "lever-rws": "contractor", "lever-lionbridge": "contractor",
}
UNIT_ALIASES = {"hourly": "hour", "per-task": "task", "one-time": "project", "yearly": "year", "monthly": "month",
                "HOURLY": "hour", "YEARLY": "year", "MONTHLY": "month"}


def _f(x):
    try:
        return float(x) if x not in (None, "", "None") else None
    except (TypeError, ValueError):
        return None


def site_pay_from_record(r, lever_raw=None):
    """Rebuild the site's own pay field for records stored before `pay_site` existed."""
    src, x = r["source"], r.get("extra") or {}
    if src == "mercor":
        return _site(x.get("rateMin"), x.get("rateMax"), None, UNIT_ALIASES.get(x.get("payRateFrequency"), x.get("payRateFrequency")))
    if src == "alignerr":
        return _site(x.get("lowerBoundHourlyRate"), x.get("upperBoundHourlyRate"), None, UNIT_ALIASES.get(x.get("salaryType"), "hour"))
    if src == "micro1":
        d = x.get("detail") or {}
        if _f(d.get("ideal_hourly_rate")):
            return _site(None, d["ideal_hourly_rate"], None, "hour")
        if _f(d.get("ideal_monthly_salary_max")):
            return _site(d.get("ideal_monthly_salary_min"), d["ideal_monthly_salary_max"], None, "month")
        if _f(d.get("ideal_yearly_compensation")):
            return _site(None, d["ideal_yearly_compensation"], None, "year")
        return None
    if src in ("handshake", "outlier", "dataannotation"):
        m = best_pay(pay_mentions(r.get("pay_text") or ""))  # the pay badge shown on the site, e.g. "Up to $62.50/hr"
        if m:
            return _site(m["min"], m["max"], None, m["unit"] or "hour")
        return None
    if src.startswith("ashby-"):
        for c in (x.get("compensation") or {}).get("summaryComponents") or []:
            if c.get("compensationType") in ("Salary", "Hourly", "Base"):
                unit = {"1 HOUR": "hour", "1 YEAR": "year", "1 MONTH": "month", "1 WEEK": "week", "1 DAY": "day"}.get(c.get("interval"), "")
                return _site(c.get("minValue"), c.get("maxValue"), c.get("currencyCode"), unit)
        return None
    if src.startswith("lever-"):
        sr = x.get("salaryRange") or (lever_raw or {}).get(r["id"])
        if sr:
            unit = {"per-hour-wage": "hour", "per-year-salary": "year", "per-month-salary": "month", "per-week-salary": "week",
                    "per-day-wage": "day", "one-time": "project"}.get(sr.get("interval"), sr.get("interval") or "")
            return _site(sr.get("min"), sr.get("max"), sr.get("currency"), unit)
        return None
    return None


def _site(lo, hi, cur, unit):
    lo, hi = _f(lo), _f(hi)
    if hi is None and lo is None:
        return None
    if hi is None:
        hi = lo
    return {"min": lo, "max": hi, "currency": cur, "unit": unit or ""}


def lever_salaries(source):
    """id -> salaryRange from the newest raw copy of a Lever board."""
    days = sorted(RAW_ROOT.glob(f"*/{source}/postings.json.gz"))
    if not days:
        return {}
    with gzip.open(days[-1]) as f:
        return {p["id"]: p["salaryRange"] for p in json.load(f) if p.get("salaryRange")}


STRUCTURED_TYPE_KEYS = ("employmentType", "jobType", "employment_type", "timeType")


def derive(r, board):
    """Fill pay_*, contract_type, years and degrees on one record, in place."""
    text = r.get("text") or ""
    mentions = pay_mentions(text)
    best = best_pay(mentions)
    site = r.get("pay_site")
    r["pay_all"] = [[m["min"], m["max"], m["currency"], m["unit"], m["quote"][:220]] for m in mentions[:12]]
    note = ""
    if site:
        lo, hi, unit = site["min"], site["max"], site["unit"]
        cur, cur_src = site["currency"], "site field"
        if not cur:  # site shows "$" with no code
            if best and best["currency"] != "USD" and best["unit"] == unit:
                cur, cur_src = best["currency"], "text (site shows no currency)"
            else:
                cur, cur_src = "USD", "assumed: site shows $ with no currency code"
        src = "site field"
        if best and best["unit"] == unit and best["currency"] == cur:
            wider = best["min"] is not None and (lo is None or best["min"] < lo) and best["max"] >= hi
            if wider and best["max"] == hi:  # site badge says "up to $75", text says "$40 - $75"
                lo, src = best["min"], "site field + range from text"
            elif abs(best["max"] - hi) > 0.01 or (best["min"] is not None and lo is not None and abs(best["min"] - lo) > 0.01):
                note = f"text says {_fmt(best)}"
        elif best and best["unit"] and unit and best["unit"] != unit and best["near_pay_word"]:
            note = f"text also says {_fmt(best)}"
    elif best:
        lo, hi, cur, unit = best["min"], best["max"], best["currency"], best["unit"]
        src, cur_src = "text", "text"
        others = {_fmt(m) for m in mentions if m["near_pay_word"] and m["unit"] and best_pay([m])} - {_fmt(best)}
        if others:
            note = "other amounts in the text: " + "; ".join(sorted(others)[:4])
    else:
        lo = hi = cur = unit = None
        src = cur_src = ""
    r.update(pay_min=lo, pay_max=hi, pay_currency=cur or "", pay_unit=unit or "", pay_source=src,
             pay_currency_source=cur_src, pay_note=note)
    if src == "text" or (best and not r.get("pay_text")):
        r["pay_text"] = best["quote"] if best else ""
    # engagement type
    x = r.get("extra") or {}
    structured = r.get("employment_type") or next((x.get(k) for k in STRUCTURED_TYPE_KEYS if x.get(k)), "")
    if not structured and r["source"].startswith("lever-"):
        structured = r.get("commitment") or ""
    r["contract_type"], r["contract_evidence"] = engagement(
        r["title"], text, structured, board.get("kind", ""), SITE_DEFAULT.get(r["source"], ""))
    # years and degrees (degrees from a site badge, e.g. Handshake, are kept)
    r["min_years_experience"], r["experience_text"] = experience(text)
    if not r.get("degrees_from_site"):
        r["degrees"] = ", ".join(degrees_in(text))
    return r


def _fmt(m):
    sym = {"USD": "$", "EUR": "€", "GBP": "£", "CAD": "CA$", "AUD": "A$"}.get(m["currency"], (m["currency"] or "") + " ")
    a = f"{sym}{m['min']:g}–" if m["min"] is not None and m["min"] != m["max"] else ("up to " if m["min"] is None else "")
    return f"{a}{sym}{m['max']:g}" + (f"/{m['unit']}" if m["unit"] else "")
