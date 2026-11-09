"""Where the work happens and who may do it: work mode, location rule, allowed / excluded places."""

import re

# name -> aliases (matched as whole words, case-insensitive unless all caps)
COUNTRIES = {
    "United States": ["United States of America", "United States", "USA", "U.S.A.", "U.S.", "US", "America"],
    "Canada": ["Canada"], "Mexico": ["Mexico", "México"],
    "United Kingdom": ["United Kingdom", "UK", "U.K.", "Great Britain", "Britain", "England", "Scotland", "Wales", "Northern Ireland"],
    "Ireland": ["Ireland"], "France": ["France"], "Germany": ["Germany", "Deutschland"],
    "Spain": ["Spain", "España"], "Portugal": ["Portugal"], "Italy": ["Italy", "Italia"], "Netherlands": ["Netherlands", "Holland"],
    "Belgium": ["Belgium"], "Luxembourg": ["Luxembourg"], "Switzerland": ["Switzerland"], "Austria": ["Austria"],
    "Denmark": ["Denmark"], "Sweden": ["Sweden"], "Norway": ["Norway"], "Finland": ["Finland"], "Iceland": ["Iceland"],
    "Poland": ["Poland"], "Czechia": ["Czech Republic", "Czechia"], "Slovakia": ["Slovakia"], "Hungary": ["Hungary"],
    "Romania": ["Romania"], "Bulgaria": ["Bulgaria"], "Greece": ["Greece"], "Croatia": ["Croatia"], "Serbia": ["Serbia"],
    "Slovenia": ["Slovenia"], "Bosnia and Herzegovina": ["Bosnia"], "North Macedonia": ["North Macedonia", "Macedonia"],
    "Albania": ["Albania"], "Montenegro": ["Montenegro"], "Kosovo": ["Kosovo"], "Moldova": ["Moldova"],
    "Estonia": ["Estonia"], "Latvia": ["Latvia"], "Lithuania": ["Lithuania"], "Ukraine": ["Ukraine"], "Belarus": ["Belarus"],
    "Russia": ["Russia", "Russian Federation"], "Georgia (country)": ["Republic of Georgia"], "Armenia": ["Armenia"],
    "Azerbaijan": ["Azerbaijan"], "Turkey": ["Turkey", "Türkiye", "Turkiye"], "Cyprus": ["Cyprus"], "Malta": ["Malta"],
    "Israel": ["Israel"], "Egypt": ["Egypt"], "Morocco": ["Morocco"], "Algeria": ["Algeria"], "Tunisia": ["Tunisia"],
    "Saudi Arabia": ["Saudi Arabia", "KSA"], "United Arab Emirates": ["United Arab Emirates", "UAE", "U.A.E."],
    "Qatar": ["Qatar"], "Kuwait": ["Kuwait"], "Bahrain": ["Bahrain"], "Oman": ["Oman"], "Jordan": ["Jordan"],
    "Lebanon": ["Lebanon"], "Iraq": ["Iraq"], "Iran": ["Iran"], "Pakistan": ["Pakistan"], "India": ["India"],
    "Bangladesh": ["Bangladesh"], "Sri Lanka": ["Sri Lanka"], "Nepal": ["Nepal"], "China": ["China", "PRC", "Mainland China"],
    "Hong Kong": ["Hong Kong"], "Taiwan": ["Taiwan"], "Japan": ["Japan"], "South Korea": ["South Korea", "Korea"],
    "Singapore": ["Singapore"], "Malaysia": ["Malaysia"], "Indonesia": ["Indonesia"], "Philippines": ["Philippines"],
    "Thailand": ["Thailand"], "Vietnam": ["Vietnam", "Viet Nam"], "Cambodia": ["Cambodia"], "Myanmar": ["Myanmar", "Burma"],
    "Australia": ["Australia"], "New Zealand": ["New Zealand"], "South Africa": ["South Africa"],
    "Nigeria": ["Nigeria"], "Kenya": ["Kenya"], "Ghana": ["Ghana"], "Ethiopia": ["Ethiopia"], "Uganda": ["Uganda"],
    "Tanzania": ["Tanzania"], "Rwanda": ["Rwanda"], "Senegal": ["Senegal"], "Cameroon": ["Cameroon"],
    "Côte d'Ivoire": ["Côte d'Ivoire", "Ivory Coast"], "DR Congo": ["Democratic Republic of the Congo", "DR Congo", "DRC"],
    "Zimbabwe": ["Zimbabwe"], "Zambia": ["Zambia"], "Brazil": ["Brazil", "Brasil"], "Argentina": ["Argentina"],
    "Chile": ["Chile"], "Colombia": ["Colombia"], "Peru": ["Peru"], "Venezuela": ["Venezuela"], "Ecuador": ["Ecuador"],
    "Uruguay": ["Uruguay"], "Paraguay": ["Paraguay"], "Bolivia": ["Bolivia"], "Costa Rica": ["Costa Rica"],
    "Panama": ["Panama"], "Guatemala": ["Guatemala"], "Dominican Republic": ["Dominican Republic"],
    "Puerto Rico": ["Puerto Rico"], "Jamaica": ["Jamaica"], "Kazakhstan": ["Kazakhstan"], "Uzbekistan": ["Uzbekistan"],
    "Mongolia": ["Mongolia"],
}
REGIONS = {
    "EU": ["European Union", "EU", "EEA", "European Economic Area"], "Europe": ["Europe", "European"],
    "Latin America": ["Latin America", "LATAM", "LatAm", "South America", "Central America"],
    "North America": ["North America", "NAMER", "NA region"], "EMEA": ["EMEA"], "APAC": ["APAC", "Asia-Pacific", "Asia Pacific"],
    "Middle East": ["Middle East", "MENA", "GCC"], "Africa": ["Africa", "Sub-Saharan Africa"], "Asia": ["Asia", "Southeast Asia"],
}
# ambiguous words that only count as places inside a location clause
AMBIGUOUS = {"US", "America", "Korea", "Jordan", "Georgia",
             "Chile", "Turkey", "NA region"}

_alias = []
for name, al in list(COUNTRIES.items()) + list(REGIONS.items()):
    for a in al:
        _alias.append((a, name))
_alias.sort(key=lambda x: -len(x[0]))
PLACE = re.compile(r"(?<![A-Za-z])(" + "|".join(re.escape(a) for a, _ in _alias) + r")(?![A-Za-z])")
ALIAS = {a: n for a, n in _alias}
US_STATES = ("Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Hawaii|Idaho|Illinois|Indiana|"
             "Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|"
             "Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|"
             "Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|"
             "West Virginia|Wisconsin|Wyoming|Bay Area|San Francisco|Los Angeles|New York City|NYC|Seattle|Boston|Austin|Chicago")
STATE = re.compile(r"(?<![A-Za-z])(" + US_STATES + r")(?![A-Za-z])")


def places_in(s, strict=False):
    """Countries / regions named in a short clause, in order, without repeats."""
    out = []
    for m in PLACE.finditer(s):
        a = m.group(1)
        if a in AMBIGUOUS and strict:
            continue
        if a == "US" and not re.search(r"\bUS\b", s):  # 'us' the pronoun is lowercase; the regex is case-sensitive anyway
            continue
        n = ALIAS[a]
        if n not in out:
            out.append(n)
    return out


# --- rules in the text ---------------------------------------------------------------------

_P = r"([^.\n;]{2,160})"  # the clause holding the places
RESTRICT = [
    rf"\bmust (?:currently )?(?:be |reside |live |be physically )?(?:based|located|residing|living|resident|present)? ?(?:in|within) {_P}",
    rf"\b(?:only )?(?:open|available) (?:only )?(?:to|for) (?:[\w-]+ ){{0,4}}(?:in|from|of|based in|located in|residing in|within|living in) {_P}",
    rf"\bavailable (?:only )?(?:within|in) {_P}",
    rf"\b(?:remote|work) (?:work )?within {_P}",
    rf"\b(?:candidates|applicants|contributors|experts|participants|people|individuals|professionals|physicians|speakers) (?:who are |currently )?(?:based|located|residing|living) in {_P}",
    rf"\bbased in:\s*{_P}",
    rf"(?m)^[-*•\s]*based in {_P}",
    rf"\bresidents? of {_P}",
    rf"\b(?:legally )?(?:authori[sz]ed|eligible|permitted) to work in {_P}",
    rf"\bwork authori[sz]ation (?:in|for) {_P}",
    rf"\b(?:eligible|allowed|supported) (?:countries|locations|regions|states)\s*(?:include|are|:)\s*{_P}",
    rf"\bremote\s*[(\[–—-]\s*{_P}",
    rf"\blocation(?:s)?\s*(?:requirement)?\s*:\s*{_P}",
    r"\b([^.\n;(]{2,60}?)\)? only\b",
    rf"\b(?:hiring|recruiting) (?:only )?(?:in|from) {_P}",
]
RESTRICT = [re.compile(x, re.I) for x in RESTRICT]
EXCLUDE = re.compile(
    r"\b(?:not (?:available|open|accepting|eligible|able to (?:hire|accept|consider))|unable to (?:hire|accept|consider|engage|work with)|"
    r"cannot (?:hire|accept|consider|engage)|excluding|except(?: for)?|with the exception of)\b([^.\n;]{2,200})", re.I)
ANYWHERE = re.compile(
    r"\b(?:work(?:ing)? (?:remotely )?from anywhere|from anywhere|anywhere in the world|wherever you are|"
    r"(?:open|available) to (?:candidates|applicants|contributors|experts|people|everyone|talent)[^.\n]{0,20}(?:worldwide|globally|from any country|anywhere)|"
    r"(?:worldwide|global) (?:applicants|candidates|contributors|remote)|remote[,(\s–-]{1,3}(?:worldwide|global|international|anywhere)|"
    r"location\W{1,4}(?:anywhere|worldwide|global|international)|any country|all countries|no location (?:restriction|requirement)s?|"
    r"location[- ]independent|open to all locations|based anywhere)\b", re.I)
ANYWHERE_FALSE = re.compile(r"customers|users|clients|teams|offices|people|millions|companies|labs|leading|community|network of|"
                            r"contributors in|experts in \d|countries\b.*\d|\d+\+? countries", re.I)
ONSITE = re.compile(r"\b(on-?site|in[- ]person|in[- ]office|at (?:our|the|a) (?:office|lab|facility|studio|site|location)|"
                    r"this is not a remote|not remote|office[- ]based|on location|at the client'?s? (?:site|office))\b", re.I)
HYBRID = re.compile(r"\bhybrid\b|\b\d (?:days?|times) (?:a|per) week (?:in|at) (?:the )?(?:office|site)\b", re.I)
REMOTE = re.compile(r"\b(fully remote|100% remote|remote|work from home|work-from-home|wfh|telecommut|home[- ]based|from home)\b", re.I)
NEG = re.compile(r"(?:\bno|\bnot|\bnon|without|never)[\s-]{1,3}(?:\w+[\s-]){0,2}$", re.I)


def _real_place(s):
    s = re.sub(r"\b(remote|hybrid|on-?site|flexible|multiple locations|\d+ locations?|tbd|n/a)\b", "", s or "", flags=re.I)
    return bool(re.search(r"[A-Za-z]{2,}", s))


def _clause(m, text):
    s, e = max(0, m.start() - 40), min(len(text), m.end() + 30)
    return re.sub(r"\s+", " ", text[s:e]).strip()


def location_info(r):
    """Work mode and location rule for one record (fields read from site fields first, then text)."""
    text = (r.get("text") or "")[:25000]
    x = r.get("extra") or {}
    src = r.get("source", "")
    out = {"work_mode": "", "work_mode_evidence": "", "location_rule": "", "allowed_places": [],
           "excluded_places": [], "location_evidence": ""}

    # work mode: an explicit "Location: ..." line, then hybrid / on-site words, then the site's field, then "remote" words
    loc_line = re.search(r"(?im)^[-*•\s]*(?:\*\*)?(?:location|work location|work arrangement|workplace|where)(?:\*\*)?\s*:\s*(?:\*\*)?([^\n]{2,160})", text)
    site_mode = (r.get("arrangement") or x.get("workArrangement") or x.get("workplaceType") or "").lower()
    site_mode = {"on-site": "onsite", "on site": "onsite", "in-person": "onsite", "in person": "onsite", "office": "onsite"}.get(site_mode, site_mode)
    mode, ev = "", ""
    if loc_line:
        l = loc_line.group(1)
        if HYBRID.search(l):
            mode, ev = "hybrid", loc_line.group(0).strip()
        elif ONSITE.search(l) and not REMOTE.search(l):
            mode, ev = "onsite", loc_line.group(0).strip()
        elif REMOTE.search(l):
            mode, ev = "remote", loc_line.group(0).strip()
    if not mode:
        hy = next((m for m in HYBRID.finditer(text) if not NEG.search(text[max(0, m.start() - 20):m.start()])), None)
        on = next((m for m in ONSITE.finditer(text) if not NEG.search(text[max(0, m.start() - 20):m.start()])), None)
        rem = next((m for m in REMOTE.finditer(text) if not NEG.search(text[max(0, m.start() - 20):m.start()])), None)
        if hy and site_mode != "remote":
            mode, ev = "hybrid", "text: …" + _clause(hy, text) + "…"
        elif site_mode in ("remote", "hybrid", "onsite"):
            mode, ev = site_mode, f"site field: {site_mode}"
            if site_mode == "remote" and on and not rem:
                mode, ev = "onsite", "text: …" + _clause(on, text) + "… (site field says remote)"
        elif on and not rem:
            mode, ev = "onsite", "text: …" + _clause(on, text) + "…"
        elif rem:
            mode, ev = "remote", "text: …" + _clause(rem, text) + "…"
            if on:
                ev += " (also mentions: …" + _clause(on, text) + "…)"
    out["work_mode"], out["work_mode_evidence"] = mode, ev

    # who may do it: the site's own eligibility lists first
    allowed, excluded, lev = [], [], ""
    if src == "mercor":
        allowed = [p for p in (x.get("eligibleLocation") or []) + (x.get("eligibleResidenceLocation") or []) if p]
        excluded = [p for p in (x.get("ineligibleLocation") or []) + (x.get("ineligibleResidenceLocation") or []) if p]
        if allowed or excluded:
            lev = "site field: eligible " + ", ".join(allowed) + ("; not eligible " + ", ".join(excluded) if excluded else "")
    elif src == "outlier" and (x.get("allowedCountries") or r.get("countries")):
        allowed = list(x.get("allowedCountries") or [c.strip() for c in r["countries"].split(",") if c.strip()])
        lev = "site field: allowed countries"
    elif src == "handshake":
        allowed, lev = ["United States"], "site: Handshake AI work requires being based in the US with US work authorization"
    # then the text
    if not allowed:
        for rx in RESTRICT:
            for m in rx.finditer(text):
                clause = m.group(1)
                if NEG.search(text[max(0, m.start() - 15):m.start()]):
                    continue
                sent = text[max(0, text.rfind(".", 0, m.start()) + 1, m.start() - 160):m.end()]
                if re.search(r"prefer|preferred|ideally|nice to have|a plus|bonus|anywhere", sent, re.I):
                    continue  # "based anywhere, though we prefer people living in ..."
                ps = places_in(clause)
                st = STATE.findall(clause)
                if not ps and st:
                    ps = ["United States"]
                if ps:
                    allowed = ps
                    lev = "text: …" + _clause(m, text) + "…"
                    if st:
                        lev += f" (US places named: {', '.join(dict.fromkeys(st))})"
                    break
            if allowed:
                break
    if not excluded:
        for m in EXCLUDE.finditer(text):
            ps = places_in(m.group(1), strict=True)
            if ps and re.search(r"hire|accept|available|open|eligible|consider|engage|resid|based|locat|countr|state", m.group(0), re.I):
                excluded = ps
                lev = (lev + " | " if lev else "") + "excluded: …" + _clause(m, text) + "…"
                break
    anywhere = next((m for m in ANYWHERE.finditer(text) if not ANYWHERE_FALSE.search(_clause(m, text))
                     and not NEG.search(text[max(0, m.start() - 15):m.start()])), None)
    if allowed:
        rule = "only listed places"
    elif mode in ("onsite", "hybrid"):
        rule, lev = "must come on site", ev
    elif anywhere:
        rule, lev = "anywhere", "text: …" + _clause(anywhere, text) + "…"
    elif re.search(r"\b(international|worldwide|anywhere|global)\b", " ".join([r.get("location") or "", r.get("countries") or ""]), re.I):
        rule, lev = "anywhere", "listed: " + "; ".join(x for x in (r.get("countries"), r.get("location")) if x)[:200]
    elif _real_place(r.get("location")) or _real_place(r.get("countries")):
        rule, lev = "listed place, rule not stated", "listed: " + "; ".join(x for x in (r.get("countries"), r.get("location")) if x)[:200]
    else:
        rule = ""
    if excluded and rule in ("", "anywhere", "listed place, rule not stated"):
        rule = "anywhere except excluded" if rule == "anywhere" else (rule or "excluded places only")
    out.update(location_rule=rule, allowed_places=normalize_places(allowed), excluded_places=normalize_places(excluded),
               location_evidence=lev)
    return out


# ISO country codes some sites use (Mercor: 3 letters, Alignerr / Lever: 2 letters)
ISO = {
    "USA": "United States", "US": "United States", "CAN": "Canada", "CA": "Canada", "MEX": "Mexico", "MX": "Mexico",
    "GBR": "United Kingdom", "GB": "United Kingdom", "UK": "United Kingdom", "IRL": "Ireland", "IE": "Ireland",
    "FRA": "France", "FR": "France", "DEU": "Germany", "DE": "Germany", "ESP": "Spain", "ES": "Spain", "PRT": "Portugal",
    "PT": "Portugal", "ITA": "Italy", "IT": "Italy", "NLD": "Netherlands", "NL": "Netherlands", "BEL": "Belgium", "BE": "Belgium",
    "CHE": "Switzerland", "CH": "Switzerland", "AUT": "Austria", "AT": "Austria", "DNK": "Denmark", "DK": "Denmark",
    "SWE": "Sweden", "SE": "Sweden", "NOR": "Norway", "NO": "Norway", "FIN": "Finland", "FI": "Finland", "POL": "Poland",
    "PL": "Poland", "CZE": "Czechia", "CZ": "Czechia", "SVK": "Slovakia", "SK": "Slovakia", "HUN": "Hungary", "HU": "Hungary",
    "ROU": "Romania", "RO": "Romania", "BGR": "Bulgaria", "BG": "Bulgaria", "GRC": "Greece", "GR": "Greece", "HRV": "Croatia",
    "HR": "Croatia", "SRB": "Serbia", "RS": "Serbia", "SVN": "Slovenia", "SI": "Slovenia", "EST": "Estonia", "EE": "Estonia",
    "LVA": "Latvia", "LV": "Latvia", "LTU": "Lithuania", "LT": "Lithuania", "UKR": "Ukraine", "UA": "Ukraine", "TUR": "Turkey",
    "TR": "Turkey", "ISR": "Israel", "IL": "Israel", "EGY": "Egypt", "EG": "Egypt", "MAR": "Morocco", "MA": "Morocco",
    "SAU": "Saudi Arabia", "SA": "Saudi Arabia", "ARE": "United Arab Emirates", "AE": "United Arab Emirates", "QAT": "Qatar",
    "QA": "Qatar", "JOR": "Jordan", "JO": "Jordan", "IND": "India", "IN": "India", "PAK": "Pakistan", "PK": "Pakistan",
    "BGD": "Bangladesh", "BD": "Bangladesh", "LKA": "Sri Lanka", "LK": "Sri Lanka", "CHN": "China", "CN": "China",
    "HKG": "Hong Kong", "HK": "Hong Kong", "TWN": "Taiwan", "TW": "Taiwan", "JPN": "Japan", "JP": "Japan",
    "KOR": "South Korea", "KR": "South Korea", "SGP": "Singapore", "SG": "Singapore", "MYS": "Malaysia", "MY": "Malaysia",
    "IDN": "Indonesia", "ID": "Indonesia", "PHL": "Philippines", "PH": "Philippines", "THA": "Thailand", "TH": "Thailand",
    "VNM": "Vietnam", "VN": "Vietnam", "AUS": "Australia", "AU": "Australia", "NZL": "New Zealand", "NZ": "New Zealand",
    "ZAF": "South Africa", "ZA": "South Africa", "NGA": "Nigeria", "NG": "Nigeria", "KEN": "Kenya", "KE": "Kenya",
    "GHA": "Ghana", "GH": "Ghana", "BRA": "Brazil", "BR": "Brazil", "ARG": "Argentina", "AR": "Argentina", "CHL": "Chile",
    "CL": "Chile", "COL": "Colombia", "CO": "Colombia", "PER": "Peru", "PE": "Peru", "URY": "Uruguay", "UY": "Uruguay",
    "CRI": "Costa Rica", "CR": "Costa Rica", "PRI": "Puerto Rico", "PR": "Puerto Rico", "VEN": "Venezuela", "VE": "Venezuela",
    "ECU": "Ecuador", "EC": "Ecuador", "LUX": "Luxembourg", "LU": "Luxembourg", "ISL": "Iceland", "IS": "Iceland",
    "CYP": "Cyprus", "CY": "Cyprus", "MLT": "Malta", "MT": "Malta",
    "LIE": "Liechtenstein", "MCO": "Monaco", "SMR": "San Marino", "ALB": "Albania", "BIH": "Bosnia and Herzegovina",
    "XKX": "Kosovo", "MKD": "North Macedonia", "MDA": "Moldova", "SLV": "El Salvador", "GTM": "Guatemala",
    "PAN": "Panama", "HND": "Honduras", "NIC": "Nicaragua", "CUB": "Cuba", "DOM": "Dominican Republic",
    "BOL": "Bolivia", "PRY": "Paraguay", "GUY": "Guyana",
}


def normalize_places(ps):
    out = []
    for p in ps:
        p = (p or "").strip()
        n = ISO.get(p.upper()) if len(p) <= 3 else None
        n = n or (places_in(p)[0] if places_in(p) else p)
        if n and n not in out:
            out.append(n)
    return out
