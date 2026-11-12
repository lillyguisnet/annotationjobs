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

Standard library only (Python 3.11+), except the step that sorts jobs by field, task and language
with a language model (it needs `lm15` and runs through `uv`, see below). Charts (`data/plots/`, with a short write-up in
`data/plots/README.md`): `uv run --no-project --with matplotlib python -m annotationjobs.plots`. Open `data/index.html` through a web server
(`python3 -m http.server -d data`) so "full listing" can load the text.

## Public page

`docs/` is the public page (GitHub Pages, served from `docs/` on `main`): a box plot of the top of each
job's pay range in US$, grouped and colored by any of site, type of site, field, kind of task, language, degree, experience, work
mode, who can apply, kind of job, what the pay is per, how it is stated (a figure or range, or only "up to"),
what the listing says it depends on, and its currency, with filters
(including "open to people in <country>") shared by the chart and the table below it. A switch shows one
pay basis at a time: per hour, per task or project (task, project, session), or jobs with no pay figure.
The view is kept in the address, so a link reopens it.

- Per hour includes salaries when the listing gives no hourly rate, at 40 hours a week (year ÷ 2,080 h,
  month ÷ 173.3 h).
- Other currencies are converted to US$ with the European Central Bank rates (frankfurter.dev), fetched
  once per snapshot into `data/fx.json` so rebuilding gives the same numbers; delete it to refetch.
- `docs/data/jobs.json` is rebuilt by every `collect` run (or alone: `python3 -m annotationjobs.site`):
  one record per distinct open job, with the sentences behind each value. Commit and push it to update
  the page.
- Groupings shared with the charts live in `annotationjobs/groups.py` and `annotationjobs/categories.py`.
- Site logos (chart labels, legend, table, site filter) are the sites' own icons, downloaded once into
  `docs/logos/` and served with the page: `python3 -m annotationjobs.logos` fetches the missing ones
  (a new site needs its website added to `DOMAINS` in `annotationjobs/logos.py`); a site without one is
  shown by name only.
- Try it locally: `python3 -m http.server -d docs`.

## What is kept

- `data/listings/<source>.jsonl`: one listing per line with its **full text** (`text`), the
  fields read from it, and source-specific fields (`extra`, often the original HTML). A
  listing that disappears from its board stays here; the page shows it as closed.
- `data/seen.json`: first and last date each listing was seen.
- `data/sources.json`: per source, the last run, counts and the last error.
- `data/dropped/<source>.tsv`: postings on company boards left out as not annotation work
  (engineers, sales...), with the reason, so the filter can be checked.
- `data/categories.jsonl`: each job's field, languages and kind of task, with the passages the
  model quoted as evidence and whether each is really in the listing (one line per distinct
  site + title + text; a later line for the same text wins).
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
- What pay depends on (`pay_depends_on`): the words next to the pay figure (or, with no figure, next to
  what the listing says instead) that say what the rate depends on: "depending on experience and
  location", "rates vary by country", "based on tasks completed" (quoted). A range on its own says
  nothing about it, so most ranges have none. The page groups the quote by the factors it names
  (`FACTORS` in `annotationjobs/terms.py`): experience, skill level, location, kind of work, amount of
  work. "Up to" pay is a pay figure with no `pay_min`.
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

## Field, kind of task and language (language model)

A language model, GPT-6.1 Terra on our ChatGPT plan (thinking off), reads each open job's full
listing and picks from fixed lists (`annotationjobs/categories.py`):

- **Field**: the specialist knowledge the worker must bring, from 20 groups based on the US
  Standard Occupational Classification, including "No specialist field" (generalists, anyone
  who speaks a language). The worker's knowledge, not the client's industry.
- **Kind of task**: what the work mainly is, one of 9 (training AI with answers, rating search /
  ads / content, labeling data, translation and transcription, recording data, paid study, using
  or testing software, company staff role, other).
- **Languages**: every language other than English the job requires, plus the variety asked for
  ("Dutch (Belgium)"). English only when a specific accent is required. The page groups a job
  under its one non-English language, or "Several languages"; its search box finds each one.

It also quotes the passages behind each answer; the page shows only quotes found word for word
in the listing. Chosen after testing five models on 60 listings (`experiments/categorize/`):
Terra agreed with the other models' majority on 26 of 27 fields and 26 of 30 tasks, with every
quote real. No answer key was made by hand, so this is agreement, not measured accuracy.

```sh
uv run --no-project --with lm15==1.5.0 python -m annotationjobs.categorize   # sort open jobs not sorted yet
```

`collect` runs it after fetching (`--no-categorize` to skip). Each distinct listing text is
asked once (~1 s each with 4 at a time; about an hour for all ~2,650 open jobs, ~$2.50 per
1,000 jobs at API prices, nothing extra on the plan). Changing `VERSION` in `categories.py`
sorts every job again. Jobs not sorted yet show as "Not sorted yet".

## What workers say (Reddit, pilot)

`annotationjobs/community.py` reads a random sample of threads from each platform's own subreddits
(pilot: Outlier, DataAnnotation, Mercor, May–October 2026) through the Arctic Shift archive of Reddit
(Reddit refuses scripts; Glassdoor, Indeed and Trustpilot block automated reading), sorts each thread
into 10 topics with good/bad news for workers and a checked quote, and writes `data/community/report.html`.
Design choices and limits are in the module's docstring and at the end of the report.

```sh
python3 -m annotationjobs.community list     # every post of the window (hours: the archive is a volunteer service)
python3 -m annotationjobs.community sample   # draw 20 threads per platform per month, fetch them
uv run --no-project --with lm15==1.5.0 python -m annotationjobs.community label
uv run --no-project --with lm15==1.5.0 python -m annotationjobs.community label --model claude-code:claude-opus-5-5 --ids data/community/check-ids.txt
python3 -m annotationjobs.community report
```

Thread texts stay on `/mnt/bulk/lilly/annotationjobs/community/` (other people's words, not in git);
`data/community/` keeps the sample, the labels with short quotes and links, and the report.

## Not covered

- TELUS Digital AI Community and Turing's own site block automated visits (Turing's Greenhouse
  board is covered).
- Meta, Microsoft and Tesla career sites (no readable public feed found).
- Rex.zone (page built in the browser only); Toloka's own task site (down).
- Platforms that only show tasks after you sign in (DataAnnotation's projects, Prolific
  studies, Remotasks tasks): only their public role pages are covered.
