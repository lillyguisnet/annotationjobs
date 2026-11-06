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

Standard library only (Python 3.11+). Open `data/index.html` through a web server
(`python3 -m http.server -d data`) so "full listing" can load the text.

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
  the amount ("30 CAD/hour", "CAD $30", "€15", "US$35"). A bare "$" with no code is recorded as
  USD and marked "assumed" (shown as `USD?` on the page). "$/hr equiv." converts only USD,
  yearly pay at 2,080 h and monthly at 173 h.
- Kind of job (`contract_type`, `contract_evidence`): contractor (freelance, independent
  contractor, 1099, per task), temporary (temporary, fixed-term, an end date, W-2 through a
  staffing agency), permanent (an employee post on a company board with no contract or end date
  mentioned) or internship. Read from the title first, then the site's employment-type field,
  then the text; on platforms where all work is freelance, that is the fallback. Blank = not stated.
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
