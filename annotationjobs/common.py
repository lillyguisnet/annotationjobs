"""Shared plumbing: polite HTTP, raw snapshots, HTML to text, field extraction."""

import gzip
import hashlib
import html as htmllib
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
TODAY = date.today().isoformat()
# Exact bytes of every response, so nothing has to be fetched again to re-read it.
RAW_ROOT = Path("/mnt/bulk/lilly/annotationjobs/raw")

# --- HTTP ---------------------------------------------------------------------

_host_locks = {}
_host_last = {}
_glock = threading.Lock()
MIN_GAP = 0.25  # seconds between two requests to the same host (per thread slot)
HOST_SLOTS = 4  # at most this many requests in flight per host


def _slot(host):
    with _glock:
        if host not in _host_locks:
            _host_locks[host] = threading.BoundedSemaphore(HOST_SLOTS)
            _host_last[host] = 0.0
        return _host_locks[host]


def fetch(url, data=None, headers=None, tries=4, raw=None, method=None):
    """GET (or POST when data is given) and return text. raw=(source, name) saves a gz copy."""
    host = urllib.parse.urlsplit(url).netloc
    h = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
    if data is not None and not isinstance(data, (bytes, str)):
        data = json.dumps(data)
        h["Content-Type"] = "application/json"
    if isinstance(data, str):
        data = data.encode()
    h.update(headers or {})
    sem = _slot(host)
    for i in range(tries):
        with sem:
            with _glock:
                wait = _host_last[host] + MIN_GAP - time.time()
                _host_last[host] = max(time.time(), _host_last[host] + MIN_GAP)
            if wait > 0:
                time.sleep(wait)
            try:
                req = urllib.request.Request(url, data=data, headers=h, method=method)
                with urllib.request.urlopen(req, timeout=60) as r:
                    body = r.read()
                break
            except urllib.error.HTTPError as e:
                if e.code in (404, 410, 401, 403) or i == tries - 1:
                    raise
                retry = e.headers.get("Retry-After")
                time.sleep(float(retry) if retry and retry.isdigit() else 3 * 2 ** i)
            except Exception:
                if i == tries - 1:
                    raise
                time.sleep(3 * 2 ** i)
    text = body.decode("utf-8", "replace")
    if raw:
        save_raw(raw[0], raw[1], body)
    return text


def fetch_json(url, data=None, **kw):
    return json.loads(fetch(url, data=data, **kw))


def save_raw(source, name, body):
    if isinstance(body, str):
        body = body.encode()
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:150]
    p = RAW_ROOT / TODAY / source / (safe + ".gz")
    p.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, "wb") as f:
        f.write(body)


def next_data(page_html):
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>', page_html, re.S)
    return json.loads(m.group(1)) if m else None


def next_flight(page_html):
    """Concatenated React Server Components payload of a Next.js app-router page."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', page_html, re.S)
    return "".join(json.loads('"' + c + '"') for c in chunks)


def flight_text_row(flight, ref):
    """Resolve a "$1f" reference to its text row ("1f:T<hex bytes>,<text>")."""
    m = re.search(r"(?<![0-9a-f])" + re.escape(ref.lstrip("$")) + r":T([0-9a-f]+),", flight)
    if not m:
        return ""
    n = int(m.group(1), 16)
    return flight[m.end():].encode("utf-8")[:n].decode("utf-8", "ignore")


# --- HTML -> readable text ------------------------------------------------------

class _ToText(HTMLParser):
    BLOCK = {"p", "div", "section", "article", "br", "tr", "table", "ul", "ol", "header", "footer", "blockquote", "pre"}
    HEAD = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1
        elif tag == "li":
            self.out.append("\n- ")
        elif tag in self.HEAD:
            self.out.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag in self.BLOCK:
            self.out.append("\n")
        elif tag in ("td", "th"):
            self.out.append(" | ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK or tag in self.HEAD or tag == "li":
            self.out.append("\n")

    def handle_data(self, d):
        if not self.skip:
            self.out.append(d)


def html_to_text(h):
    if not h:
        return ""
    if "<" not in h:
        return htmllib.unescape(h).strip()
    p = _ToText()
    p.feed(h)
    t = "".join(p.out).replace("\xa0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    t = re.sub(r"\n- \n", "\n- ", t)
    t = re.sub(r"(?m)^-\s*$\n?", "", t)  # empty bullets
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def page_lines(page_html):
    t = html_to_text(page_html)
    return [ln.strip() for ln in t.split("\n") if ln.strip()]


# --- extraction from free text ----------------------------------------------------

WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
         "eight": 8, "nine": 9, "ten": 10, "twelve": 12, "fifteen": 15, "twenty": 20}
YEARS = re.compile(
    r"\b(\d{1,2}|" + "|".join(WORDS) + r")\s*(?:\(\d+\))?\s*\+?\s*(?:(?:[-–]|to)\s*\d{1,2}\s*\+?\s*)?(?:full[- ]time\s+)?(?:years?|yrs)\b",
    re.I,
)
NICE = re.compile(r"nice to have|preferred|bonus|plus\b|strengthen your application|ideal", re.I)
DEGREES = [
    ("PhD", r"\bph\.?\s?d\b|doctora|\bdphil\b|\bpostdoc"),
    ("MD/JD", r"\bm\.?d\.?\b(?! ?\d)|\bj\.?d\.?\b|\bdo\b(?= degree)|medical degree|law degree"),
    ("Master's", r"master'?s|\bm\.?sc?\b\.?(?= in)|\bmba\b|\bm\.?a\.?\b(?= in)"),
    ("Bachelor's", r"bachelor'?s|\bb\.?sc?\b\.?(?= in)|\bb\.?a\.?\b(?= in)|undergraduate degree|college degree|university degree"),
    ("Associate's", r"associate'?s degree"),
]


def experience(text):
    """Smallest 'N years' in a sentence about experience, plus that sentence.

    Required figures win over ones in a 'nice to have' / 'preferred' part; when
    only those exist the quote is prefixed with '(preferred)'."""
    req, pref = _exp(text, False), _exp(text, True)
    if req[0] is not None:
        return req
    if pref[0] is not None:
        return pref[0], "(preferred) " + pref[1]
    return None, ""


def _exp(text, nice):
    best, sentence, in_nice = None, "", False
    for s in re.split(r"(?<=[.;])\s+|\n|\s-\s", (text or "").replace("**", "")):
        if re.match(r"\s*#*\s*(nice to have|preferred|bonus|additional qualifications)", s, re.I):
            in_nice = True
        elif re.match(r"\s*#+\s|\s*(required|requirements|minimum qualifications|qualifications|what you)", s, re.I):
            in_nice = False
        if (in_nice or bool(NICE.search(s))) != nice:
            continue
        if not re.search(r"experien|practic|working|professional|career|in the field|industry", s, re.I):
            continue
        for m in YEARS.finditer(s):
            g = m.group(1).lower()
            n = WORDS.get(g) or int(g)
            if 0 < n <= 40 and (best is None or n < best):
                s2 = re.sub(r"\s+", " ", s).strip(" -*#")
                best, sentence = n, re.sub(r"^Qualifications\s*", "", s2)[:300]
    return best, sentence


def degrees_in(text):
    return [name for name, rx in DEGREES if re.search(rx, text or "", re.I)]


# --- listing records -------------------------------------------------------------

FIELDS = [
    "uid", "site", "company", "source", "id", "title", "url", "location", "countries", "arrangement",
    "commitment", "employment_type", "hours_per_week", "pay_min", "pay_max", "pay_currency", "pay_unit",
    "pay_text", "posted", "department", "degrees", "min_years_experience", "experience_text",
    "relevant", "relevant_why", "group", "text", "extra", "pay_site", "pay_source", "pay_currency_source",
    "pay_note", "pay_all", "contract_type", "contract_evidence", "degrees_from_site",
    "work_mode", "work_mode_evidence", "location_rule", "allowed_places", "excluded_places", "location_evidence",
]


def listing(site, source, id, title, url, text, **kw):
    """Build one record. Pay given here is the site's own pay field (kept in pay_site);
    fields.derive() later combines it with what the text says."""
    r = {k: None for k in FIELDS}
    r.update(site=site, source=source, id=str(id), title=(title or "").strip(), url=url, text=(text or "").strip())
    r.update(kw)
    r["uid"] = f"{source}:{id}"
    r["company"] = r["company"] or site
    if r["pay_max"] is not None or r["pay_min"] is not None:
        r["pay_site"] = {"min": r["pay_min"], "max": r["pay_max"] if r["pay_max"] is not None else r["pay_min"],
                         "currency": r["pay_currency"] or None, "unit": r["pay_unit"] or ""}
    if r["relevant"] is None:
        r["relevant"], r["relevant_why"] = True, "contributor marketplace"
    r["group"] = r["group"] or r["uid"]
    r["extra"] = r["extra"] or {}
    for k in ("location", "countries", "arrangement", "commitment", "employment_type", "pay_text",
              "posted", "department", "experience_text", "relevant_why"):
        r[k] = r[k] or ""
    return r


# Titles that mean "people who make or judge AI training data".
STRONG = re.compile(
    r"annotat|label(l)?er\b|label(l)?ing\b|\braters?\b|evaluator|\btutor\b|(ai|llm|model|safety|data) trainers?\b|trainers network|"
    r"rlhf|human data (specialist|associate|contractor|expert|annotator|writer|operator)|"
    r"data (specialist|associate|contributor|collector|collection|operator|curator|annotator|labeler)|"
    r"linguist|language (specialist|expert|consultant|evaluator|reviewer)|transcri|"
    r"subject[- ]matter expert|domain expert|\bsme\b|red[- ]?teamer|prompt (writer|creator|author)|"
    r"content (reviewer|moderator|evaluator|writer.*ai)|search (quality )?(rater|evaluator)|quality (rater|evaluator)|"
    r"teleoperat|robot operator|data capture|ai (writing|data|training|quality|safety) (specialist|analyst|associate|evaluator|reviewer)|"
    r"model (behavior|evaluation) (specialist|associate|analyst)|human frontier collective|"
    r"voice recording|recording (specialist|contributor|project)|speech (collection|data)|audio evaluation|"
    r"\bai training\b|for ai\b|train(ing)? ai\b|\bgen(erative)? ?a[il]\b.{0,15}generalist|"
    r"(ai|llm|model|gen ?ai)\b.{0,20}\b(trainer|tutor|evaluator|reviewer|writer|contributor|freelancer|data (associate|specialist|annotator|contributor))\b",
    re.I,
)
# Staff roles at these companies (building the platform, selling it, running teams).
NOT = re.compile(
    r"engineer|developer|manager|director|head of|\blead\b|recruit|sourcer|sales|account exec|marketing|scientist|"
    r"researcher|designer|counsel|\bvp\b|chief|architect|business partner|product|solutions|customer success|"
    r"growth|partner|controller|technical staff|strategist|portfolio|\bgtm\b|go-to-market|leader|"
    r"worldwide|\bintern\b|technical trainer|enablement|public affairs|coordinator",
    re.I,
)
ALWAYS_STAFF = re.compile(r"\bsecurity\b|recruit|sourcer|\bsales\b|\bgtm\b|go-to-market|marketing|\bintern\b|enablement", re.I)
# ...unless the title says the engineering is itself the contract training work.
CONTRACT = re.compile(r"\bai training\b|ai tutor|(ai|llm|safety) trainer\b|"
                      r"^(data )?annotat\w* (specialist|analyst|expert)|annotator|labell?er\b|\braters?\b|evaluator\b", re.I)


def classify(title, department="", also=None):
    """(relevant, reason) for a posting on a company's general careers board.

    also: an extra regex that counts as annotation work on this one board."""
    t = title or ""
    m = STRONG.search(t) or (re.search(also, t, re.I) if also else None)
    if not m:
        return False, ""
    word = m.group(0).lower()
    if ALWAYS_STAFF.search(t):
        return False, f"title has '{word}' but reads as a staff role"
    if NOT.search(t) and not CONTRACT.search(t):
        return False, f"title has '{word}' but reads as a staff role"
    return True, f"title: '{word}'"


def short_hash(s):
    return hashlib.sha1(s.encode()).hexdigest()[:10]
