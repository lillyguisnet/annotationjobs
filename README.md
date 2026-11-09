# annotationjobs

Open AI-training and data-annotation work, collected from the contributor platforms
(Mercor, Handshake AI, micro1, Alignerr, Outlier, DataAnnotation, Mindrift, OneForma,
Appen, RWS TrainAI, Lionbridge...), the data companies' own boards (Scale AI, Welocalize,
CloudFactory, Centific...) and the AI labs' careers boards (Cohere, Mistral, xAI,
Anthropic, OpenAI, Google DeepMind, ...), with pay, experience asked, degrees and the
full listing text.

```sh
python3 -m annotationjobs.collect                     # every source (about 40 minutes, mostly Alignerr)
python3 -m annotationjobs.collect --only mercor,gh-xai
python3 -m annotationjobs.collect --page-only         # rebuild the page and CSV from what is stored
python3 -m annotationjobs.collect --list              # all sources
```

Standard library only (Python 3.11+). Charts (`data/plots/`, with a short write-up in
`data/plots/README.md`): `uv run --no-project --with matplotlib python -m annotationjobs.plots`. Open `data/index.html` through a web server
(`python3 -m http.server -d data`) so "full listing" can load the text.

## Public page

`docs/` is the public page (GitHub Pages, served from `docs/` on `main`): a box plot of the top of each
job's hourly rate in US$ (same number as the charts), grouped and colored by any of site, type of site,
field, degree, experience, work mode, who can apply, kind of job, how pay is stated and why it is taken
as US$, with filters (including "open to people in <country>") shared by the chart and the table below it.
The view is kept in the address, so a link reopens it.

- `docs/data/jobs.json` is rebuilt by every `collect` run (or alone: `python3 -m annotationjobs.site`):
  one record per distinct open job, with the sentences behind each value. Commit and push it to update
  the page.
- Groupings shared with the charts live in `annotationjobs/groups.py`.
- Try it locally: `python3 -m http.server -d docs`.

## What is kept

- `data/listings/<source>.jsonl`: one listing per line with its **full text** (`text`), the
  fields read from it, and source-specific fields (`extra`, often the original HTML). A
  listing that disappears from its board stays here; the page shows it as closed.
- `data/seen.json`: first and last date each listing was seen.
- `data/sources.json`: per source, the last run, counts and the last error.
- `data/dropped/<source>.tsv`: postings on company boards left out as not annotation work
  (engineers, sales...), with the reason, so the filter can be checked.
- `data/jobs.csv`, `data/index.html`: the table, built from the above.
- Raw responses, byte for byte, of every run (all postings, kept or not):
  `/mnt/bulk/lilly/annotationjobs/raw/<date>/<source>/` (not in git).

## How fields are read

All of this is redone from the stored text, without fetching, by `--reparse`
(`annotationjobs/fields.py`, `annotationjobs/terms.py`).

- Pay: the site's own pay field when it has one (Mercor, Handshake, micro1, Alignerr, Outlier,
  DataAnnotation, Ashby, Lever: kept in `pay_site`), otherwise the amount in the text that sits
  near a pay word ("pay", "rate", "compensation"...) and has a unit; bonuses, referral rewards
  and funding amounts are skipped. When the site only gives a top figure ("up to $75") and the
  text gives the range ("$40–$75"), the range is used. `pay_source` says which; `pay_note`
  flags a text that disagrees with the site's field; `pay_all` lists every amount in the text.
  A single figure is stored as exact (min = max) unless the text says "up to".
- Currency (`pay_currency`, `pay_currency_source`): the site's field, or the code/symbol next to
  the amount in the text ("30 CAD/hour", "CAD $30", "$35–$60 USD", "€15"). When the site's pay
  field has no currency, the text is searched for one; if neither names it, a bare "$" is
  recorded as USD and marked "assumed" (shown as `USD?`). "$/hr equiv." converts only USD,
  yearly pay at 2,080 h and monthly at 173 h.
- Currency from location: a bare "$" on a job that must be done from the US (or on site in the
  US) is recorded as USD with the reason. For a job limited to another dollar country (Canada,
  Australia, Mexico...) it stays "assumed" with a note that "$" may be the local dollar.
- Variable pay (`pay_variable`, `pay_variable_why`): only a top figure ("up to"), or the text
  around the figure says it depends on task, project, level, country... (quoted).
- `pay_earnings_claim`: sentences such as "Many contributors add $100k–$200k a year". Kept as
  a note only: on DataAnnotation it is the same sentence on every role, including roles paying
  at most $40/hr (which would need 5,000 hours a year to reach $200k), so no per-role pay is
  derived from it.
- A site pay field of $1 or less per hour or per project is a placeholder (e.g. Appen's
  "$0.01 one-time") and is ignored, with a note.
- No figure: `pay_note` says what the listing says instead ("paid per task, amount not stated",
  "rate varies…", "compensation shared later", "competitive"), `pay_text` quotes it.
- Kind of job (`contract_type`, `contract_evidence`): contractor (freelance, independent
  contractor, 1099, per task), temporary (temporary, fixed-term, an end date, W-2 through a
  staffing agency), internship, or permanent only when the listing says so ("permanent",
  "full-time employee") or lists employee benefits (401(k), health/dental, paid time off,
  equity, pension...). Anything else is `contractor?` (shown "contract (assumed)").
- Where (`places.py`): `work_mode` (remote / hybrid / onsite), `location_rule`
  ("only listed places" = the listing or site says you must be there; "anywhere"; "must come on
  site"; "listed place, rule not stated" = a place is listed but not said to be required),
  `allowed_places`, `excluded_places`, and `location_evidence` (the sentence or site field).
  Site eligibility lists come first (Mercor, Outlier, Handshake = US only), then sentences such
  as "must be based in…", "available within Canada", "Location: Remote (US, UK…)",
  "authorized to work in…". Preferences ("we prefer people living in…") are not rules.
- Years of experience: the smallest "N years" in a sentence about experience; years that are
  only "preferred" / "nice to have" are marked so. The quoted sentence is shown next to it.
- Degrees: degrees *mentioned* in the text, required or not.
- Company boards (`vendor`, `lab`, `bigtech`): kept only when the title reads as annotation /
  AI-training work (`classify` in `annotationjobs/common.py`).

## Not covered

- TELUS Digital AI Community and Turing's own site block automated visits (Turing's Greenhouse
  board is covered).
- Meta, Microsoft and Tesla career sites (no readable public feed found).
- Rex.zone (page built in the browser only); Toloka's own task site (down).
- Platforms that only show tasks after you sign in (DataAnnotation's projects, Prolific
  studies, Remotasks tasks): only their public role pages are covered.
