"""Collect every board, merge into the store, write the table and the page.

    python3 -m annotationjobs.collect                 # everything
    python3 -m annotationjobs.collect --only mercor,gh-xai
    python3 -m annotationjobs.collect --page-only     # rebuild page/CSV from the store
    python3 -m annotationjobs.collect --reparse       # re-read pay/type/years from stored text, no fetching

Store (in git):
  data/listings/<source>.jsonl   one listing per line, full text, kept after it closes
  data/seen.json                 uid -> [first_seen, last_seen]
  data/sources.json              per source: kind, counts, last run, last error
  data/dropped/<source>.tsv      titles on company boards judged not annotation work
Public page (GitHub Pages): docs/, its data docs/data/jobs.json rebuilt with the table.
Raw responses (not in git): /mnt/bulk/lilly/annotationjobs/raw/<date>/<source>/
"""

import argparse
import csv
import gzip
import json
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .boards import BOARDS
from .common import RAW_ROOT, TODAY
from .fields import derive, lever_salaries, site_pay_from_record

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LISTINGS = DATA / "listings"
DROPPED = DATA / "dropped"
SUMMARY = ["uid", "site", "company", "kind", "title", "url", "pay_min", "pay_max", "pay_currency", "pay_unit",
           "pay_text", "pay_source", "pay_currency_source", "pay_note", "contract_type", "contract_evidence",
           "pay_depends_on", "pay_earnings_claim",
           "work_mode", "work_mode_evidence", "location_rule", "allowed_places", "excluded_places", "location_evidence", "hours_per_week", "commitment", "employment_type", "arrangement", "location", "countries",
           "degrees", "min_years_experience", "experience_text", "department", "posted", "first_seen",
           "last_seen", "active", "group", "relevant_why"]


def load_jsonl(p):
    if not p.exists():
        return {}
    return {r["uid"]: r for r in (json.loads(l) for l in p.open() if l.strip())}


def merge_duplicates(rows):
    """Some boards list one posting once per location under the same id: keep one, join the places."""
    out = {}
    for r in rows:
        if r["uid"] not in out:
            out[r["uid"]] = r
            continue
        o = out[r["uid"]]
        for k in ("location", "countries"):
            parts = [p for p in (o[k] or "").split("; ") + (r[k] or "").split("; ") if p]
            o[k] = "; ".join(dict.fromkeys(parts))
    return list(out.values())


def run_board(b):
    t = time.time()
    try:
        rows = b["reader"](b)
        return b, rows, None, time.time() - t
    except Exception as e:
        return b, None, f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}", time.time() - t


def collect(only=None):
    LISTINGS.mkdir(parents=True, exist_ok=True)
    DROPPED.mkdir(parents=True, exist_ok=True)
    seen = json.loads((DATA / "seen.json").read_text()) if (DATA / "seen.json").exists() else {}
    sources = json.loads((DATA / "sources.json").read_text()) if (DATA / "sources.json").exists() else {}
    boards = [b for b in BOARDS if not only or b["source"] in only]
    with ThreadPoolExecutor(8) as pool:
        for b, rows, err, secs in pool.map(run_board, boards):
            src = b["source"]
            info = sources.setdefault(src, {})
            info.update(site=b["site"], kind=b["kind"], reader=b["reader"].__name__, token=b.get("token"))
            if err:
                info.update(last_error=err, last_error_date=TODAY)
                print(f"!! {src:24} FAILED in {secs:5.0f}s  {err.splitlines()[0][:120]}")
                continue
            for r in rows:
                derive(r, b)
            keep = merge_duplicates([r for r in rows if r["relevant"]])
            drop = [r for r in rows if not r["relevant"]]
            old = load_jsonl(LISTINGS / f"{src}.jsonl")
            for r in keep:
                r["kind"] = b["kind"]
                first = seen.get(r["uid"], [TODAY, TODAY])[0]
                seen[r["uid"]] = [first, TODAY]
                old[r["uid"]] = r
            with open(LISTINGS / f"{src}.jsonl", "w") as f:
                for uid in sorted(old):
                    f.write(json.dumps(old[uid], ensure_ascii=False, sort_keys=True) + "\n")
            with open(DROPPED / f"{src}.tsv", "w") as f:
                for r in sorted(drop, key=lambda r: r["title"]):
                    f.write(f"{r['title']}\t{r['relevant_why']}\t{r['url']}\n")
            info.update(last_run=TODAY, fetched=len(rows), kept=len(keep), dropped=len(drop),
                        active=len(keep), stored=len(old), seconds=round(secs))
            info.pop("last_error", None)
            print(f"   {src:24} {len(rows):5} fetched  {len(keep):5} kept  {len(old):5} stored  {secs:5.0f}s")
    (DATA / "seen.json").write_text(json.dumps(seen, indent=0, sort_keys=True))
    (DATA / "sources.json").write_text(json.dumps(sources, indent=1, sort_keys=True))


def _reread_dataannotation(src, rows):
    from .marketplaces import dataannotation_page
    n = 0
    for uid, r in list(rows.items()):
        raws = sorted(RAW_ROOT.glob(f"*/{src}/{r['id']}.html.gz"))
        if not raws:
            continue
        with gzip.open(raws[-1]) as f:
            new = dataannotation_page(src, r["id"], f.read().decode("utf-8", "replace"))
        new["kind"] = r.get("kind")
        rows[uid] = new
        n += 1
    return n


RAW_PAGES = {"dataannotation": _reread_dataannotation}


def reparse(only=None):
    """Re-derive pay, currency, engagement type, years and degrees from what is stored. No network."""
    boards = {b["source"]: b for b in BOARDS}
    for p in sorted(LISTINGS.glob("*.jsonl")):
        src = p.stem
        if only and src not in only:
            continue
        b = boards.get(src, {"source": src, "kind": ""})
        rows = load_jsonl(p)
        lever = lever_salaries(src) if src.startswith("lever-") else None
        if src in RAW_PAGES:  # parsing of these pages improved: rebuild the records from the saved raw pages
            rebuilt = RAW_PAGES[src](src, rows)
            print(f"   {src:24} rebuilt {rebuilt} records from raw pages")
        for r in rows.values():
            # stored before the site's own pay was kept apart; Alignerr's was once read with its pay frequency as the unit
            if "pay_site" not in r or src == "alignerr":
                r["pay_site"] = site_pay_from_record(r, lever)
                if src == "handshake":
                    r["degrees_from_site"] = bool(r.get("degrees"))
            if lever is not None and r["id"] in lever:
                r["extra"]["salaryRange"] = lever[r["id"]]
            r.setdefault("kind", b.get("kind", ""))
            r["title"] = r["title"].lstrip("# ").strip()  # headings once leaked into a few titles
            derive(r, b)
        with open(p, "w") as f:
            for uid in sorted(rows):
                f.write(json.dumps(rows[uid], ensure_ascii=False, sort_keys=True) + "\n")
        n = len(rows)
        pay = sum(r["pay_max"] is not None for r in rows.values())
        ct = sum(bool(r["contract_type"]) for r in rows.values())
        print(f"   {src:24} {n:5} listings  pay {pay:5}  type {ct:5}")


def all_listings():
    seen = json.loads((DATA / "seen.json").read_text())
    sources = json.loads((DATA / "sources.json").read_text())
    out = []
    for p in sorted(LISTINGS.glob("*.jsonl")):
        src = p.stem
        last_ok = sources.get(src, {}).get("last_run")
        for r in load_jsonl(p).values():
            f, l = seen.get(r["uid"], ["", ""])
            r["first_seen"], r["last_seen"] = f, l
            r["active"] = bool(last_ok) and l == last_ok  # still listed on the last good run of its board
            out.append(r)
    return out, sources


def write_outputs():
    rows, sources = all_listings()
    with open(DATA / "jobs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, SUMMARY, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["site"], r["title"])):
            w.writerow(r)
    page = (ROOT / "page.html").read_text()
    slim = [{k: r.get(k) for k in SUMMARY + ["source"]} | {"snippet": (r.get("text") or "")[:600]} for r in rows]
    data = json.dumps({"rows": slim, "sources": sources, "built": TODAY}, ensure_ascii=False, separators=(",", ":"))
    (DATA / "index.html").write_text(page.replace("/*DATA*/null", data.replace("</", "<\\/")))
    act = sum(r["active"] for r in rows)
    print(f"page: {len(rows)} listings ({act} open) from {len(sources)} sources -> {DATA / 'index.html'}")
    from .site import build  # the public page (docs/); imported here because site.py reads the store through this module

    build()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated sources")
    ap.add_argument("--page-only", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--reparse", action="store_true")
    a = ap.parse_args()
    if a.list:
        for b in BOARDS:
            print(f"{b['source']:24} {b['kind']:12} {b['site']}")
        return
    only = set(a.only.split(",")) if a.only else None
    if a.reparse:
        reparse(only)
    elif not a.page_only:
        collect(only)
    write_outputs()


if __name__ == "__main__":
    sys.exit(main())
