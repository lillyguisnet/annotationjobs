"""Reading pay and the kind of engagement (contract, temporary, permanent) from listing text."""

import re

# --- pay ----------------------------------------------------------------------------------

# currency written before the number ("CA$45", "CAD $30", "USD 12", "€30")
PRE = {
    "US$": "USD", "USD$": "USD", "USD": "USD", "U$": "USD", "U$S": "USD",
    "CA$": "CAD", "C$": "CAD", "CAD$": "CAD", "CAD": "CAD",
    "A$": "AUD", "AU$": "AUD", "AUD$": "AUD", "AUD": "AUD",
    "NZ$": "NZD", "NZD": "NZD", "S$": "SGD", "SGD": "SGD", "HK$": "HKD", "HKD": "HKD",
    "R$": "BRL", "BRL": "BRL", "MX$": "MXN", "MXN": "MXN",
    "£": "GBP", "GBP": "GBP", "€": "EUR", "EUR": "EUR", "₹": "INR", "INR": "INR", "RS.": "INR",
    "CHF": "CHF", "¥": "JPY", "JPY": "JPY", "₱": "PHP", "PHP": "PHP", "ZAR": "ZAR", "R": "ZAR",
    "PLN": "PLN", "$": "USD",
}
# currency written after the number ("30 CAD", "35 €", "50 zł")
POST = {"USD": "USD", "CAD": "CAD", "AUD": "AUD", "NZD": "NZD", "SGD": "SGD", "HKD": "HKD", "EUR": "EUR",
        "GBP": "GBP", "INR": "INR", "CHF": "CHF", "JPY": "JPY", "BRL": "BRL", "MXN": "MXN", "PHP": "PHP",
        "ZAR": "ZAR", "PLN": "PLN", "ZŁ": "PLN", "SEK": "SEK", "NOK": "NOK", "DKK": "DKK", "€": "EUR",
        "£": "GBP", "EUROS": "EUR", "EURO": "EUR", "DOLLARS": "USD"}
_pre = "|".join(sorted((re.escape(k) for k in PRE if k not in ("R",)), key=len, reverse=True))
_post = "|".join(sorted((re.escape(k) for k in POST), key=len, reverse=True))
NUM = r"\d{1,3}(?:[,\u202f ]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
MONEY = re.compile(
    rf"(?P<pre>(?<![A-Za-z])(?:{_pre})(?:\s?\$)?)?\s?(?P<n>{NUM})\s?(?P<k>[kKmM]\b)?(?:\s?(?P<post>(?:{_post}))(?![A-Za-z]))?",
    re.I,
)
UNIT_WORDS = [
    ("hour", r"hour|hr|h\b|hora|heure|stunde|std\b|ora\b|uur|godz"),
    ("day", r"day|día|dia\b|jour|tag\b"),
    ("week", r"week|semana|semaine|woche"),
    ("month", r"month|mo\b|mes\b|mois|monat"),
    ("year", r"year|yr|annum|annual|año|an\b|jahr"),
    ("task", r"(?:approved |completed |accepted |submitted |valid )?(?:task|unit|submission|item|image|video|clip|recording|"
             r"audio|minute of audio|file|question|prompt|conversation|annotation|label|entry|response|sample|page|word)s?"),
    ("session", r"(?:\d+[- ]?(?:minutes?|mins?|hours?)\b(?: (?:session|of \w+))?)|(?:\d+[- ]minutes? )?(?:session|interview|participation)"),
    ("project", r"project|assignment|campaign|study|program(?:me)?"),
]
UNIT = re.compile(r"\s*(?:/|per|an|a|par|pro|por|each|for (?:each|every|a|one|the)?)\s*(?:(?:full|entire|whole|complete|total) )?(?:" +
                  "|".join(f"(?P<{n}>{rx})" for n, rx in UNIT_WORDS) + r")", re.I)
RANGE_SEP = re.compile(r"^\s*(?:-|–|—|to|and|à|a|bis|hasta|~)\s*$", re.I)
NEAR = re.compile(r"compensat|\bpay|paid|\brate|salary|wage|earn|remunerat|fee\b|stipend|incentive|honorari|"
                  r"tarif|vergütung|gehalt|sueldo|salario|pago", re.I)
UPTO = re.compile(r"(up to|as much as|max(?:imum)?|hasta|jusqu'?à|bis zu)\s*$", re.I)
FROM = re.compile(r"(from|starting at|starts at|at least|minimum|min\.?|desde|à partir de|ab)\s*$", re.I)
NOT_PAY = re.compile(r"bonus|referral|refer a friend|gift card|raised|funding|secured|revenue|budget|valuation|"
                     r"billion|million|assets|\bfund|insurance|credit|equipment|reimburs|travel|fee to apply|deposit", re.I)
CONTEXT_UNIT = [("hour", r"hourly|per hour|an hour|/hr\b|/h\b|par heure|por hora|pro stunde"),
                ("year", r"annual|per year|a year|yearly|salary|per annum|/yr"),
                ("month", r"monthly|per month|a month"), ("task", r"per task|per item|per unit")]


def _num(s, k):
    v = float(re.sub(r"[,\u202f ]", "", s))
    if k and k.lower() == "k":
        v *= 1000
    elif k and k.lower() == "m":
        v *= 1_000_000
    return v


def _unit_after(text, pos):
    m = UNIT.match(text, pos)
    if not m:
        return None, pos
    return next(n for n, _ in UNIT_WORDS if m.group(n)), m.end()


def pay_mentions(text):
    """Every amount of money in the text, ranges joined: dicts with min, max, currency, unit, quote."""
    text = text or ""
    toks = []
    for m in MONEY.finditer(text):
        pre, post = (m.group("pre") or "").strip(), (m.group("post") or "").strip()
        if not pre and not post:
            continue
        pkey = pre.replace(" ", "").upper()
        code = POST.get(post.upper()) if post else PRE.get(pkey) or PRE.get(pkey.rstrip("$")) or "USD"
        unit, end = _unit_after(text, m.end())
        toks.append({"v": _num(m.group("n"), m.group("k")), "cur": code, "unit": unit, "s": m.start(), "e": end,
                     "explicit": bool(post) or pkey not in ("$",)})
    out, i = [], 0
    while i < len(toks):
        a = toks[i]
        b = toks[i + 1] if i + 1 < len(toks) else None
        # "$40/hour - $75/hour", "$40 - $75 per hour", "40 to 75 USD/hour"
        if b and RANGE_SEP.match(text[a["e"]:b["s"]]) and (a["unit"] in (None, b["unit"])):
            lo, hi, unit, s, e, cur = a["v"], b["v"], b["unit"] or a["unit"], a["s"], b["e"], b["cur"] if b["explicit"] else a["cur"]
            i += 2
            explicit = a["explicit"] or b["explicit"]
        else:
            # bare second number of a range: "$40-75/hr", "€30 – 45 per hour"
            m = re.match(rf"\s*(?:-|–|—|to|and)\s*(?P<n>{NUM})\s?(?P<k>[kK]\b)?(?:\s?(?P<post>{_post})(?![A-Za-z]))?", text[a["e"]:])
            if m and a["unit"] is None:
                lo, hi = a["v"], _num(m.group("n"), m.group("k") or ("k" if a["v"] >= 1000 and _num(m.group("n"), None) < 1000 else None))
                e = a["e"] + m.end()
                unit, e = _unit_after(text, e) if _unit_after(text, e)[0] else (None, e)
                cur = POST.get((m.group("post") or "").upper()) or a["cur"]
                s = a["s"]
                explicit = a["explicit"] or bool(m.group("post"))
            else:
                lo = hi = a["v"]
                unit, s, e, cur = a["unit"], a["s"], a["e"], a["cur"]
                explicit = a["explicit"]
                before = text[max(0, s - 25):s]
                if UPTO.search(before):
                    lo = None
                elif FROM.search(before):
                    pass
            i += 1
        window = text[max(0, s - 160):e + 60].lower()
        nxt = toks[i]["s"] if i < len(toks) else len(text)  # look for a unit only up to the next amount
        if not unit:
            for u, rx in CONTEXT_UNIT:
                if re.search(rx, text[e:min(e + 40, nxt)], re.I) or re.search(rx, text[max(0, s - 60):s], re.I):
                    unit = u
                    break
        if not unit and hi >= 15000:
            unit = "year"
        quote = re.sub(r"\s+", " ", text[max(0, s - 90):e + 40]).strip()
        # a bonus / referral / funding amount: the word is right next to the number
        after, before = text[e:e + 40], text[max(0, s - 40):s]
        not_pay = bool(re.match(r"[ \t]*(?:\([A-Z]{3}\)[ \t]*)?(?:[\w-]+[ \t]){0,2}?(?:" + NOT_PAY.pattern + ")", after, re.I)
                       or re.search(r"(?:" + NOT_PAY.pattern + r")[^\w.;!?\n]{0,3}(?:\w+[^\w.;!?\n]{1,3}){0,2}(?:of|up to|worth)?\s*$", before, re.I))
        out.append({"min": lo, "max": hi, "currency": cur, "unit": unit or "", "quote": quote,
                    "near_pay_word": bool(NEAR.search(window)), "pos": s, "explicit_currency": explicit,
                    "not_pay": not_pay})
    return out


def best_pay(mentions):
    """The mention most likely to be this job's pay (or None)."""
    def score(p):
        sc = 0
        if p["near_pay_word"]:
            sc += 3
        if p["unit"]:
            sc += 3
        if p["min"] is not None and p["min"] != p["max"]:
            sc += 1
        if not p["unit"] and p["max"] < 1000:
            sc -= 6  # "$500 bonus", "$1M secured" ...
        if p["not_pay"]:
            sc -= 8
        return sc
    good = [p for p in mentions if score(p) > 0]
    if not good:
        return None
    top = max(score(p) for p in good)
    return min((p for p in good if score(p) == top), key=lambda p: p["pos"])  # first of the best


# --- kind of engagement -------------------------------------------------------------------

CONTRACTOR = re.compile(r"independent contractor|\bcontractors?\b|freelance|freelancer|\b1099\b|contract (role|position|basis|"
                        r"work|rate|opportunity|engagement|job|assignment)|(?<!employment )(?<!permanent )(?<!indefinite )(?<!open-ended )"
                        r"\bcontract\b(?!\s*(manager|management|negotiat|law|review|drafting|lifecycle|analy))|"
                        r"gig\b|pay-by-task|per task|task-based|project-based|self-employed|"
                        r"not an employee|no employment relationship|auftragnehmer|autónomo|prestataire|indépendant",
                        re.I)
TEMPORARY = re.compile(r"\btemporary\b|\btemp\b|fixed[- ]term|seasonal|\d+[- ]?(month|week)s? (contract|assignment|project|engagement)|"
                       r"contract (length|duration|of \d+)|duration: ?\d|\bw-?2\b|limited[- ]term|short[- ]term|befristet|"
                       r"\bcdd\b|interim\b", re.I)
# Said outright, or employee benefits that contractors do not get.
PERMANENT = re.compile(r"\bpermanent (?:role|position|contract|employee|employment|job|hire|full[- ]time)|\bpermanent\b(?! residen)|"
                       r"full[- ]time employee|regular (?:full[- ]time )?(?:employee|employment|position)|"
                       r"\bunbefristet|contrat (?:en )?CDI|\bCDI contract|contrato indefinido|"
                       r"401\(?k\)?|health(?:,| and) dental|medical, dental|dental(?:,| and) vision|"
                       r"(?:offer|provide|benefits?\W|including|eligible for)[^.\n]{0,40}(?:health|medical) (?:insurance|coverage|benefits)|"
                       r"paid time off|\bPTO\b|parental leave|pension (?:plan|scheme|contribution)|retirement (?:plan|savings)|"
                       r"stock options|\bRSUs?\b|equity (?:grant|package|compensation|award)|offers equity|employee benefits|"
                       r"benefits package|comprehensive benefits", re.I)
INTERN = re.compile(r"\bintern(ship)?\b|\bco-?op\b|working student|werkstudent|stagiaire|apprentice", re.I)

STRUCTURED = {  # what the site's own "employment type" fields say
    "contract": "contractor", "contractor": "contractor", "freelance": "contractor", "independent contractor": "contractor",
    "temporary": "temporary", "temp": "temporary", "fixed term": "temporary", "fixed-term": "temporary", "seasonal": "temporary",
    "intern": "internship", "internship": "internship",
    "fulltime": "employee", "full-time": "employee", "full time": "employee", "regular": "employee",
    "parttime": "employee", "part-time": "employee", "part time": "employee", "standard": "employee",
}


def engagement(title, text, structured="", kind="", site_default=""):
    """(type, evidence). type: contractor | temporary | permanent | internship | ''.

    Order: the title, then the site's own employment-type field, then the listing text,
    then what the platform says about all its work (site_default)."""
    t = title or ""
    if INTERN.search(t):
        return "internship", "title: " + t
    if TEMPORARY.search(t):
        return "temporary", "title: " + t
    if re.search(r"contract|freelance|contractor", t, re.I):
        return "contractor", "title: " + t
    s = re.sub(r"[_\s]+", " ", (structured or "").strip().lower())
    st = STRUCTURED.get(s.replace(" ", "")) or STRUCTURED.get(s)
    if st in ("contractor", "temporary", "internship"):
        return st, f"site field: {structured}"
    body = (text or "")[:20000]
    hits = {}
    for name, rx in (("contractor", CONTRACTOR), ("temporary", TEMPORARY), ("permanent", PERMANENT)):
        m = rx.search(body)
        if m:
            hits[name] = (m.start(), re.sub(r"\s+", " ", body[max(0, m.start() - 70):m.end() + 70]).strip())
    if "contractor" in hits and "temporary" in hits:
        # "W-2 contract", "6-month contract": a temporary job; "independent contractor ... short-term project": contractor
        name = "temporary" if re.search(r"\bw-?2\b|fixed[- ]term|temporary employ", body, re.I) else "contractor"
        return name, "text: …" + hits[name][1] + "…"
    for name in ("contractor", "temporary"):
        if name in hits:
            return name, "text: …" + hits[name][1] + "…"
    if "permanent" in hits and not re.search(r"no (?:employee )?benefits|not (?:eligible|entitled) (?:for|to) (?:employee )?benefits",
                                             body, re.I):
        return "permanent", "text: …" + hits["permanent"][1] + "…"
    if site_default:
        return site_default, "platform: all its work is " + site_default + " work"
    return "contractor?", ("assumed: nothing in the listing says it is permanent" +
                           (f" (site field: {structured})" if structured else ""))


# --- pay without a figure ------------------------------------------------------------------

UNSTATED = [
    ("paid per task, amount not stated",
     r"paid (?:per|by the|for each) (?:approved |completed |accepted )?(?:task|unit|item|submission|asset|recording|clip|image|video)|per[- ]task (?:pay|basis|rate|compensation)|"
     r"task[- ]based (?:pay|compensation|rate|payment)|pay[- ]by[- ]task|pay[- ]per[- ]task|output[- ]based|piece[- ]?rate|"
     r"(?:earnings|compensation|pay(?:ment)?) per (?:approved |completed )?task|fixed rate for each task|paid for each (?:approved |completed )?task"),
    ("rate varies (by country, level or project), not stated",
     r"(?:pay|rates?|compensation|earnings?|paid|remuneration)[^.\n]{0,60}(?:vary|varies|depend(?:s|ing)? on|based on (?:your )?"
     r"(?:location|country|level|tier|experience))|median at your tier|rates? (?:may )?vary"),
    ("compensation shared later",
     r"(?:compensation|pay|rate|details)[^.\n]{0,60}(?:shared|provided|discussed|communicated|disclosed|confirmed) (?:later|upon|during|after|at|when|once|in)|"
     r"reach out with[^.\n]{0,60}compensation|information will be provided"),
    ("described as competitive, no figure", r"competitive (?:pay|rates?|compensation|hourly|salary|remuneration)"),
    ("paid hourly, amount not stated", r"paid (?:per|by the) hour|hourly (?:pay|rate|compensation|contract)|\(hourly\)"),
]
UNSTATED = [(n, re.compile(rx, re.I)) for n, rx in UNSTATED]


def pay_unstated(text):
    """When a listing gives no figure: what it says about pay instead, and the quote."""
    for name, rx in UNSTATED:
        m = rx.search(text or "")
        if m:
            return name, re.sub(r"\s+", " ", text[max(0, m.start() - 70):m.end() + 70]).strip()
    return "", ""


# --- pay that varies ------------------------------------------------------------------------

VARY = [re.compile(x, re.I) for x in (  # strongest first
    r"depend(?:s|ing)? (?:up)?on (?:[^.\n;]|\.(?=\d)){3,80}",
    r"var(?:y|ies) (?:by|with|based on|depending on|according to|across|per)(?:[^.\n;]|\.(?=\d)){3,80}",
    r"rates? (?:may )?vary(?:[^.\n;]|\.(?=\d)){0,80}",
    r"based on (?:the |your )?(?:task|project|level|tier|experience|location|country)(?:[^.\n;]|\.(?=\d)){0,60}",
    r"commensurate with (?:[^.\n;]|\.(?=\d)){3,60}", r"determined by (?:[^.\n;]|\.(?=\d)){3,60}",
    r"according to (?:your )?(?:level|tier|experience)(?:[^.\n;]|\.(?=\d)){0,50}", r"median at your tier", r"per hour equivalent")]
# "Many contributors add $100k–$200k a year": a claim about some contributors, not this role's pay
EARN_CLAIM = re.compile(r"[^.\n]{0,80}(?:contributors|experts|members|people|users|freelancers|taskers)[^.\n]{0,40}"
                        r"(?:earn|make|add|take home)[^.\n]{0,80}(?:a year|per year|annually|a month|per month)[^.\n]{0,40}", re.I)


def pay_varies(text, positions):
    """Why the pay is variable, from the sentences around the pay figures (or '')."""
    text = text or ""
    windows = [text[max(0, p - 80):p + 260] for p in positions if p is not None and p >= 0]
    for rx in VARY:
        for w in windows:
            m = rx.search(w)
            if m:
                return re.sub(r"\s+", " ", m.group(0)).strip(" .,;")
    return ""


def earnings_claim(text):
    m = EARN_CLAIM.search(text or "")
    return re.sub(r"\s+", " ", m.group(0)).strip() if m else ""
