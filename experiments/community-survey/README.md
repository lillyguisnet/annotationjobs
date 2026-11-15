# Where worker feedback can be read, per site (survey, 2026-11-14)

Before running the Reddit method (annotationjobs/community.py) on more sites: what exists for each.
Scripts here; raw outputs in /mnt/bulk/lilly/annotationjobs/community/survey/.

## Reddit forums of their own (posts May–Oct 2026; "~" = estimated from the latest 100 posts)

| Site | Forum(s) | Posts | Note |
|---|---|---|---|
| micro1 | r/micro1_ai | ~8,700 | genuine worker posts |
| RWS (TrainAI) | r/RWShelp, r/RWSPay, r/RWSCallistoRaters | ~980 + ~420 + ~330 | |
| Alignerr | r/alignerr (+2 small) | ~820 + 53 | |
| Welocalize | r/Welocalize | ~790 | |
| OneForma (Centific) | r/OneFormaOfficial | ~770 | says it is the official subreddit: company-moderated |
| Mindrift (Toloka) | r/Toloka, r/mindrift | ~340 + 61 | r/mindrift reads as company-run; r/Toloka mixes Toloka tasks and Mindrift |
| xAI | r/xAI_community | ~240 | AI tutors mixed with Grok customers |
| Handshake AI | r/HandshakeAi_jobs, r/HandshakeAiHate | ~3,700 + ~130 | the first is mostly job ads (2 accounts wrote 59 of the last 100 posts); the second is a complaints forum by name |
| TELUS Digital (not on the page) | r/TELUSinternational, r/TelusSafetyRaters | ~960 + 65 | raters; Lionbridge's AI rating business went to TELUS in 2020 |
| Prolific (no open jobs on the page) | r/ProlificAc | ~8,000 | |

## No forum of their own

Appen, Lionbridge, CloudFactory, G2i, Centific, Sama, Scale AI (own board), Surge AI, Remotasks, Turing,
Invisible: forums empty or absent. Surge AI = DataAnnotation and Scale AI = Outlier (already covered).

Mentions in the three pilot forums (26,668 titles; 1,337 full threads with 9,020 comments): Appen,
Lionbridge, CloudFactory, G2i, Centific, Sama, Invisible 0; Handshake 14 threads, micro1 21, Alignerr 7.
General forums, when the archive answers: Appen 9 posts + 28 comments in r/WorkOnline in 6 months,
Lionbridge 29 comments in r/TranslationStudies. The archive refuses keyword search in busy forums;
mentions there need the whole forum listed and searched locally.

## Other sites

- Blocked to scripts: Glassdoor, Indeed, Trustpilot, G2, Quora; search engines (DuckDuckGo blocks, Bing irrelevant).
- Readable but thin: Sitejabber (Turing 136 reviews, Remotasks 49, Appen 7, others none), PissedConsumer (Appen 5, Outlier 3).
- Blind: readable, reviews by staff employees (fits the AI labs' staff jobs, not contractors).
- Hacker News: almost nothing on worker experience; names collide (sama, outlier, turing).
- Discord (where Alignerr, Mindrift and others talk): closed.

## Job sites the page may be missing (2026-11-15)

Why TELUS and Prolific have no jobs on the page:
- TELUS Digital AI Community: its public pages are behind Cloudflare ("Just a moment..."), and the job
  list (telusinternational.ai/cmp) is a sign-in app; its API paths for jobs are not public.
- Prolific: work is paid studies shown only after signing up, not job listings. Its Greenhouse board
  (`gh-prolific`, 28-30 jobs) is staff roles (engineers, growth), all left out as not annotation work.

Names workers use (`missing_names.py` over the 26,668 titles and 1,337 full threads): Ethos AI 31,
Turing 7, TELUS 6, Prolific 5, CrowdGen (Appen) 5, Stellar AI 5, Meridial 3, Babel Audio 1,
Uber AI Solutions 1, DataForce 1.

Public job feeds found (ATS probes, page source):
- Meridial (Invisible Technologies' contributor marketplace): Greenhouse board `agency`, 827 open
  "Freelance AI Trainer Project" roles (200 worldwide, 130 US, 51 India...). Not covered: the page reads
  Invisible's staff boards only.
- HumanSignal (Label Studio): Greenhouse `humansignal`, 33 jobs, AI trainer roles among them.
No public feed found: TELUS, Uber AI Solutions, Deccan AI, LXT, DataForce, Stellar AI, Ethos AI
(its sites did not answer), Babel Audio, Soul AI, Datacurve, Revelo, OpenTrain (a board for hiring
annotators), CrowdGen (sign-up app; Appen's Lever board is already covered).
