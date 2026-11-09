"""Charts of the stored listings -> data/plots/*.png (+ numbers printed for the write-up).

    uv run --no-project --with matplotlib python -m annotationjobs.plots

Counts are distinct jobs (copies of one job posted per city or country merged), open listings only.
Hourly comparisons use jobs paid per hour in US dollars (confirmed or "$" assumed USD), top of
the stated range ("up to $X" counts as X).
"""

import collections
import json
import re
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "plots"
KIND_COLOR = {"marketplace": "#2a9d6f", "vendor": "#7a5cc0", "lab": "#d0662b", "bigtech": "#2f6fed"}
KIND_NAME = {"marketplace": "Contributor platform", "vendor": "Data company's own board", "lab": "AI lab / AI company",
             "bigtech": "Big tech"}

plt.rcParams.update({
    "figure.dpi": 130, "savefig.dpi": 130, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlelocation": "left", "axes.grid": True,
    "grid.color": "#e6e6e6", "grid.linewidth": 0.7, "axes.axisbelow": True, "text.parse_math": False,
})

LANGS = ("Spanish|French|German|Italian|Portuguese|Japanese|Korean|Chinese|Mandarin|Cantonese|Arabic|Hindi|Bengali|Urdu|Punjabi|"
         "Tamil|Telugu|Marathi|Gujarati|Kannada|Malayalam|Russian|Ukrainian|Polish|Czech|Slovak|Hungarian|Romanian|Bulgarian|"
         "Greek|Turkish|Hebrew|Persian|Farsi|Dutch|Flemish|Swedish|Norwegian|Danish|Finnish|Icelandic|Estonian|Latvian|"
         "Lithuanian|Serbian|Croatian|Bosnian|Slovenian|Albanian|Macedonian|Georgian|Armenian|Azerbaijani|Kazakh|Uzbek|"
         "Vietnamese|Thai|Indonesian|Malay|Filipino|Tagalog|Burmese|Khmer|Lao|Nepali|Sinhala|Swahili|Amharic|Yoruba|Igbo|"
         "Hausa|Zulu|Xhosa|Afrikaans|Somali|Catalan|Basque|Galician|Welsh|Irish|Maltese|Luxembourgish|Lingala|Siswati|"
         "Kyrgyz|Tajik|Mongolian|Pashto|Dari|Kurdish|Haitian|Quechua|Guarani|Maori|Samoan|Hawaiian|Cherokee|Navajo")
FIELDS = [  # first match wins, on the title
    ("Medicine & health", r"physician|doctor|\bmd\b|\bdo\b|nurse|\brn\b|medical|clinic|health|surgeon|radiolog|oncolog|cardiolog|"
                          r"neurolog|psychiatr|patholog|pharma|dentist|dental|therap|anesthes|pediatric|obstetric|gynec|"
                          r"dermatolog|veterinar|epidemiolog|inpatient coder|medical coder|vascular|technologist|hospital|internist|sonograph|ultrasound|optometr|ophthalm|nurs|intensivist|"
                          r"nephrolog|orthodont|urolog|gastro|endocrin|hematolog|pulmonolog|rheumatolog|immunolog|"
                          r"emergency med|paramedic|\bemt\b|midwi|dietitian|nutrition|surgery|clinician|biomedical|"
                          r"\bVA eligibility"),
    ("Law", r"legal|\blaw\b|lawyer|attorney|paralegal|counsel|compliance|litigat|contracts? (?:attorney|specialist)"),
    ("Finance & accounting", r"financ|accountant|accounting|\btax\b|audit|actuar|invest|banking|bank\b|\bcfa\b|equity|trader|"
                             r"trading|econom|insurance|underwrit|controller|fp&a|bookkeep"),
    ("Security, defense & AI safety", r"red team|military|intelligence|naval|navy|army|defen[cs]e|cbrn|incident respon|"
                                      r"threat|imagery analyst|cleared|safety trainer|\bihl\b|weapons|forensic|combat|targeting|nuclear"),
    ("Software & data", r"software|developer|coding|\bcode\b|programm|data scien|machine learning|\bml\b|devops|back[- ]?end|"
                        r"front[- ]?end|full[- ]?stack|python|javascript|typescript|java\b|rust\b|golang|\bc\+\+|sql|"
                        r"cyber|security|cloud|infrastructure|swe\b|ai engineer|data engineer|data analyst|lean 4|formal"),
    ("Other engineering", r"engineer|mechanical|civil|electrical|chemical|aerospace|\bcad\b|cfd|robotic|manufactur|architect|"
                          r"construction|energy|hvac|pcb|semiconductor|automotive"),
    ("Math & science", r"math|physic|chemist|biolog|scien|statistic|astronom|geolog|ecolog|neuro|genomic|materials|"
                       r"postdoc|phd|masters?\b|researcher"),
    ("Languages", rf"trainers network|1[ ,.]?200.{{0,4}}1[ ,.]?600|linguist|translat|transcri|native|bilingual|dialect|language|speaker|locali[sz]|{LANGS}"),
    ("Creative & media", r"design|music|video|audio|voice|artist|\bart\b|writer|writing|photo|film|animat|editor|creative|"
                         r"illustrat|game|actor|vo talent|sound|producer|journalis|cinemat"),
    ("Business, sales & operations", r"manag|analyst|marketing|sales|consult|retail|logistic|clerk|telemarket|credit|"
                                     r"treasury|\besg\b|venture|recruit|procurement|supply chain|operations|business|"
                                     r"human resources|\bhr\b|real estate|insurance|agent|planner|merchandis|buyer|styling"),
    ("Trades & technical", r"electrician|weld|inspector|inspection|\bndt\b|pilot|metallurg|plumb|mechanic|technician|"
                           r"carpent|machinist|driver|aircraft|maritime|aviation|agricultur|crop|farm"),
    ("App users & software testing", r"application users|\buser\b|\btester\b|testing|chatbot"),
    ("Education & humanities", r"teacher|tutor|instructor|professor|educat|history|philosoph|sociolog|psycholog|humanit|"
                               r"literature|anthropolog|politic"),
    ("Generalist, data collection & studies", r"generalist|rater|evaluat|annotat|label|data collect|record|participant|study|"
                                              r"studies|gig|capture|survey|photo contributor|operator|driver|search|focus group|get paid for your time|"
                                              r"reviewer|task author|ai trainer|data quality|talent pool|vlogger|bezahlte studie|"
                                              r"ビデオ|撮影"),
]
FIELDS = [(n, re.compile(rx, re.I)) for n, rx in FIELDS]


def field(title):
    for name, rx in FIELDS:
        if rx.search(title):
            return name
    return "Other"


def load():
    rows = []
    for p in sorted((DATA / "listings").glob("*.jsonl")):
        rows += [json.loads(l) for l in p.open() if l.strip()]
    seen = json.loads((DATA / "seen.json").read_text())
    last = max(v[1] for v in seen.values())
    rows = [r for r in rows if seen.get(r["uid"], ["", ""])[1] == last]  # open on the last run
    jobs = {}
    for r in rows:
        jobs.setdefault(r["group"], r)
    return rows, list(jobs.values())


def hourly_usd(r):
    return r["pay_max"] if r["pay_max"] is not None and r["pay_unit"] == "hour" and r["pay_currency"] == "USD" else None


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", OUT / name)


# --- 1. where the jobs are ------------------------------------------------------------------

def jobs_by_site(rows, jobs):
    c = collections.Counter(j["site"] for j in jobs)
    p = collections.Counter(r["site"] for r in rows)
    kind = {j["site"]: j["kind"] for j in jobs}
    sites = [s for s, _ in c.most_common()]
    fig, ax = plt.subplots(figsize=(9, 8))
    y = range(len(sites))[::-1]
    ax.barh(list(y), [c[s] for s in sites], color=[KIND_COLOR[kind[s]] for s in sites])
    for yi, s in zip(y, sites):
        extra = f"  ({p[s]:,} postings)" if p[s] != c[s] else ""
        ax.text(c[s] + 4, yi, f"{c[s]}{extra}", va="center", fontsize=8.5, color="#333")
    ax.set_yticks(list(y), sites, fontsize=9)
    ax.set_xlabel("distinct jobs open")
    ax.set_xlim(0, max(c.values()) * 1.35)
    ax.grid(axis="y", visible=False)
    ax.set_title(f"Where the {len(jobs):,} jobs are ({len(rows):,} postings once each city's copy is counted)")
    for k, col in KIND_COLOR.items():
        ax.bar(0, 0, color=col, label=KIND_NAME[k])
    ax.legend(loc="lower right", frameon=False)
    save(fig, "1-jobs-by-site.png")
    by_kind = collections.Counter(j["kind"] for j in jobs)
    print("jobs by kind:", dict(by_kind))


# --- 2. hourly pay by site ----------------------------------------------------------------------

def box(ax, groups, labels, color="#4a7bd1"):
    data = [groups[l] for l in labels]
    ax.boxplot(data, orientation="horizontal", widths=0.6, showfliers=False, patch_artist=True,
               boxprops=dict(facecolor=color + "33", edgecolor=color), medianprops=dict(color=color, linewidth=2),
               whiskerprops=dict(color="#999"), capprops=dict(color="#999"))
    import random
    rnd = random.Random(0)
    for i, d in enumerate(data, 1):
        ax.scatter(d, [i + rnd.uniform(-0.22, 0.22) for _ in d], s=6, alpha=0.35, color=color, linewidths=0)
    ax.set_yticks(range(1, len(labels) + 1), [f"{l}  (n={len(groups[l])})" for l in labels])
    ax.grid(axis="y", visible=False)


def pay_by_site(jobs):
    g = collections.defaultdict(list)
    for j in jobs:
        h = hourly_usd(j)
        if h is not None:
            g[j["site"]].append(h)
    labels = sorted((s for s in g if len(g[s]) >= 5), key=lambda s: statistics.median(g[s]))
    fig, ax = plt.subplots(figsize=(9, 6))
    box(ax, g, labels)
    ax.set_xlabel("top of the hourly rate, US$ (\"up to $X\" counts as X)")
    ax.set_title("Hourly pay by site (jobs paid per hour in US$, sites with 5+ such jobs)")
    ax.set_xscale("log")
    ticks = [2, 5, 10, 20, 40, 75, 150, 300]
    ax.set_xticks(ticks, [f"${t}" for t in ticks])
    ax.set_xlim(1.6, 600)
    ax.minorticks_off()
    save(fig, "2-hourly-pay-by-site.png")
    for s in labels:
        print(f"  {s:22} n={len(g[s]):4} median ${statistics.median(g[s]):.0f}")


# --- 3. hourly pay by field ------------------------------------------------------------------------

def pay_by_field(jobs):
    g = collections.defaultdict(list)
    allf = collections.Counter()
    for j in jobs:
        f = field(j["title"])
        allf[f] += 1
        h = hourly_usd(j)
        if h is not None:
            g[f].append(h)
    labels = sorted((f for f in g if len(g[f]) >= 8), key=lambda f: statistics.median(g[f]))
    fig, ax = plt.subplots(figsize=(9, 5.5))
    box(ax, g, labels, color="#c2410c")
    ax.set_xscale("log")
    ticks = [2, 5, 10, 20, 40, 75, 150, 300]
    ax.set_xticks(ticks, [f"${t}" for t in ticks])
    ax.set_xlim(1.6, 600)
    ax.minorticks_off()
    ax.set_xlabel("top of the hourly rate, US$")
    ax.set_title("Hourly pay by field (field guessed from the job title)")
    save(fig, "3-hourly-pay-by-field.png")
    print("jobs per field:", dict(allf.most_common()))
    for f in labels:
        print(f"  {f:38} n={len(g[f]):4} median ${statistics.median(g[f]):.0f}")


# --- 4. pay vs experience and degree -------------------------------------------------------------

def pay_vs_requirements(jobs):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)
    yrs = collections.defaultdict(list)
    for j in jobs:
        h = hourly_usd(j)
        if h is None:
            continue
        y = j["min_years_experience"]
        if y is not None and (j.get("experience_text") or "").startswith("(preferred)"):
            y = None
        key = "not stated" if y is None else ("1" if y <= 1 else "2" if y == 2 else "3" if y == 3 else "4–5" if y <= 5 else "6+")
        yrs[key].append(h)
    order = [k for k in ["not stated", "1", "2", "3", "4–5", "6+"] if len(yrs[k]) >= 5]
    _vbox(a1, yrs, order, "#2a9d6f")
    a1.set_xlabel("years of experience asked")
    a1.set_title("Hourly pay vs years of experience asked")
    deg = collections.defaultdict(list)
    for j in jobs:
        h = hourly_usd(j)
        if h is None:
            continue
        d = j.get("degrees") or ""
        key = ("MD / JD" if "MD/JD" in d else "PhD" if "PhD" in d else "Master's" if "Master" in d
               else "Bachelor's" if "Bachelor" in d else "Associate's" if "Associate" in d else "none")
        deg[key].append(h)
    order2 = [k for k in ["none", "Associate's", "Bachelor's", "Master's", "PhD", "MD / JD"] if len(deg[k]) >= 5]
    _vbox(a2, deg, order2, "#7a5cc0")
    a2.set_xlabel("highest degree mentioned in the listing")
    a2.set_title("Hourly pay vs degree mentioned")
    a1.set_ylabel("top of the hourly rate, US$")
    save(fig, "4-pay-vs-experience-and-degree.png")
    for k in order:
        print(f"  years {k:10} n={len(yrs[k]):4} median ${statistics.median(yrs[k]):.0f}")
    for k in order2:
        print(f"  degree {k:15} n={len(deg[k]):4} median ${statistics.median(deg[k]):.0f}")


def _vbox(ax, g, labels, color):
    data = [g[l] for l in labels]
    ax.boxplot(data, widths=0.55, showfliers=False, patch_artist=True,
               boxprops=dict(facecolor=color + "33", edgecolor=color), medianprops=dict(color=color, linewidth=2),
               whiskerprops=dict(color="#999"), capprops=dict(color="#999"))
    import random
    rnd = random.Random(1)
    for i, d in enumerate(data, 1):
        ax.scatter([i + rnd.uniform(-0.2, 0.2) for _ in d], d, s=6, alpha=0.3, color=color, linewidths=0)
    ax.set_xticks(range(1, len(labels) + 1), [f"{l}\n(n={len(g[l])})" for l in labels], fontsize=9)
    ax.set_yscale("log")
    ticks = [2, 5, 10, 20, 40, 75, 150, 300]
    ax.set_yticks(ticks, [f"${t}" for t in ticks])
    ax.set_ylim(1.6, 600)
    ax.minorticks_off()
    ax.grid(axis="x", visible=False)


# --- 5. how clear the pay is ----------------------------------------------------------------------

PAY_CLASSES = [("Fixed figure or range", "#2a9d6f"), ("Varies / only \"up to\"", "#e9b44c"),
               ("No figure, but says how (per task, later...)", "#e07a5f"), ("Nothing about pay", "#bbbbbb")]


def pay_class(j):
    if j["pay_max"] is not None:
        return PAY_CLASSES[1][0] if j.get("pay_variable") else PAY_CLASSES[0][0]
    return PAY_CLASSES[2][0] if j.get("pay_note") else PAY_CLASSES[3][0]


def stacked(ax, jobs, key, classes, min_n=5):
    by = collections.defaultdict(collections.Counter)
    for j in jobs:
        by[j["site"]][key(j)] += 1
    sites = sorted((s for s in by if sum(by[s].values()) >= min_n), key=lambda s: -sum(by[s].values()))[::-1]
    left = [0.0] * len(sites)
    for name, col in classes:
        vals = [by[s][name] / sum(by[s].values()) * 100 for s in sites]
        ax.barh(range(len(sites)), vals, left=left, color=col, label=name, height=0.7)
        left = [a + b for a, b in zip(left, vals)]
    ax.set_yticks(range(len(sites)), [f"{s} ({sum(by[s].values())})" for s in sites], fontsize=9)
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of the site's jobs")
    ax.grid(axis="y", visible=False)
    return by


def pay_clarity(jobs):
    fig, ax = plt.subplots(figsize=(9, 6.5))
    stacked(ax, jobs, pay_class, PAY_CLASSES)
    ax.set_title("How clearly each site states pay (sites with 5+ jobs)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.09), ncol=2, frameon=False, fontsize=9)
    save(fig, "5-pay-clarity-by-site.png")
    print("pay clarity overall:", dict(collections.Counter(pay_class(j) for j in jobs)))


# --- 6. who can apply ------------------------------------------------------------------------------

RULES = [("only listed places", "Must live in listed places", "#d0662b"), ("anywhere", "Anywhere", "#2a9d6f"),
         ("anywhere except excluded", "Anywhere except some places", "#7fc8a9"),
         ("must come on site", "Must come on site", "#7a5cc0"),
         ("listed place, rule not stated", "Place listed, not said if required", "#e9d8a6"), ("", "Not stated", "#cccccc")]


def who_can_apply(jobs):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 6.5), gridspec_kw={"width_ratios": [1.5, 1], "wspace": 0.45})
    stacked(a1, jobs, lambda j: next(n for k, n, _ in RULES if (j.get("location_rule") or "") == k),
            [(n, c) for k, n, c in RULES if any((j.get("location_rule") or "") == k for j in jobs)])
    a1.set_title("Who can apply, by site")
    a1.legend(loc="upper center", bbox_to_anchor=(0.45, -0.09), ncol=2, frameon=False, fontsize=9)
    c = collections.Counter()
    for j in jobs:
        if j.get("location_rule") == "only listed places":
            for p in j.get("allowed_places") or []:
                c[p] += 1
    top = c.most_common(15)[::-1]
    a2.barh([p for p, _ in top], [n for _, n in top], color="#d0662b")
    for i, (_, n) in enumerate(top):
        a2.text(n + 2, i, str(n), va="center", fontsize=8.5)
    a2.grid(axis="y", visible=False)
    n_only = sum(1 for j in jobs if j.get("location_rule") == "only listed places")
    a2.set_title(f"Places allowed, among the {n_only} restricted jobs")
    a2.set_xlabel("jobs that accept people living there")
    save(fig, "6-who-can-apply.png")
    print("rules:", dict(collections.Counter(j.get("location_rule") or "" for j in jobs)))
    print("top allowed:", c.most_common(12))


# --- 7. kind of job and work mode -------------------------------------------------------------------

def kind_and_mode(jobs):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 3.8))
    names = {"contractor": "Contractor (stated)", "contractor?": "Contract (assumed)", "temporary": "Temporary / fixed-term",
             "permanent": "Permanent employee", "internship": "Internship"}
    c = collections.Counter(names.get(j.get("contract_type"), "Not stated") for j in jobs)
    labels = [n for n in names.values() if c[n]][::-1]
    a1.barh(labels, [c[l] for l in labels], color=["#2a9d6f", "#7fc8a9", "#e9b44c", "#2f6fed", "#7a5cc0"][:len(labels)][::-1])
    for i, l in enumerate(labels):
        a1.text(c[l] + 15, i, f"{c[l]:,}", va="center", fontsize=9)
    a1.set_xlim(0, max(c.values()) * 1.18)
    a1.set_title("Kind of job")
    a1.grid(axis="y", visible=False)
    m = collections.Counter({"remote": "Remote", "hybrid": "Hybrid", "onsite": "On site"}.get(j.get("work_mode"), "Not stated")
                            for j in jobs)
    labels = [l for l in ["Remote", "On site", "Hybrid", "Not stated"] if m[l]][::-1]
    a2.barh(labels, [m[l] for l in labels], color="#4a7bd1")
    for i, l in enumerate(labels):
        a2.text(m[l] + 15, i, f"{m[l]:,}", va="center", fontsize=9)
    a2.set_xlim(0, max(m.values()) * 1.18)
    a2.set_title("Work mode")
    a2.grid(axis="y", visible=False)
    fig.suptitle(f"All {len(jobs):,} jobs", x=0.01, ha="left", fontsize=10, color="#555")
    fig.tight_layout()
    save(fig, "7-kind-of-job-and-work-mode.png")
    print("kind:", dict(c), "mode:", dict(m))


def main():
    rows, jobs = load()
    jobs_by_site(rows, jobs)
    pay_by_site(jobs)
    pay_by_field(jobs)
    pay_vs_requirements(jobs)
    pay_clarity(jobs)
    who_can_apply(jobs)
    kind_and_mode(jobs)


if __name__ == "__main__":
    main()
