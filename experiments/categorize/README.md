# Sorting jobs into field, languages and task with a language model (test, 2026-11-10)

Replaces the single keyword "Field" (`annotationjobs/groups.py`, title only) with three
filters read from the full listing by a model: **field of expertise** (SOC-based list),
**languages** (non-English, plain names, plus the variety asked for), **kind of task**.
Categories and prompt: `taxonomy.py` (v2); the first version is `taxonomy_v1.py`.

```sh
uv run experiments/categorize/probe.py            # which model names the plans accept today
uv run experiments/categorize/run.py --sample a   # 30 jobs (2 per old keyword field), every model
uv run experiments/categorize/run.py --sample b   # 30 other jobs
python3 experiments/categorize/report.py          # summary + report.html (one table per job)
```

Models (latest each plan accepted on 2026-11-10), each at its lowest thinking setting:
Muse Ember 1.0 (Muse Code plan), Claude Haiku 5.5 and Opus 5.5 (Claude plan),
GPT-6 Luna and GPT-6.1 Terra (ChatGPT plan). Calls go only to plans (`llm.py`).

v2 was written after reading v1's disagreements on sample a, so sample b is the fair test.
There is no answer key: agreement between models is measured, not correctness.

Files: `sample-*.jsonl` (the listings sent), `answers-v*.jsonl` (one line per model and
job: the reply, the parsed answer, whether each evidence passage is really in the listing,
tokens, seconds). Re-running skips answered jobs.

## Local decision model (2026-11-11)

Perplexity's pplx-decider-flash-v1.2 (4B, `/home/maxime/Projects/deciders`) on sample b:
three one-question requests per job (field, task, one language), same lists and
descriptions. Run on the CPU (GPU 1 had ~8 GB free, the model needs ~9 GB): ~23 s per
question, 35 min for the 30 jobs. It gives probabilities, no evidence sentences, and
only one language.

```sh
python3 experiments/categorize/decide.py --sample b
/home/maxime/Projects/deciders/deciders decide experiments/categorize/decider-b-requests.jsonl \
    --lines --device cpu > experiments/categorize/decider-b-answers.jsonl
python3 experiments/categorize/compare_decider.py --sample b
```

Agreement with the chat models' majority (3+ of 5): field 24/29, task 26/30,
language 29/30; when it gives its pick 0.8 or more, 36/37 agree.
