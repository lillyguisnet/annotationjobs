"""The same jobs, sorted by Perplexity's local decision model (pplx-decider-flash-v1.2, 4B).

    python3 experiments/categorize/decide.py --sample b            # writes decider-<sample>-requests.jsonl
    /home/maxime/Projects/deciders/deciders decide experiments/categorize/decider-b-requests.jsonl \
        --lines --device cpu > experiments/categorize/decider-b-answers.jsonl   (or as below)

A decision model does not write text: it gives a probability to each option of a
fixed list. So each job is three requests, one question each (the model's makers
say one question per request is more accurate for this small model):
- field: the 20 fields of taxonomy.py, with the same descriptions the chat models got;
- task: the 9 tasks of taxonomy.py;
- language: one choice among "none" and every language name (it can pick only one,
  where the chat models could list several).
No evidence sentences: the model cannot quote.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1])]
from taxonomy import FIELDS, TASKS  # noqa: E402

from annotationjobs.groups import LANGS  # noqa: E402

# One name per language, as the chat models were asked to write them
SAME = {"Mandarin": "Chinese", "Cantonese": "Chinese", "Flemish": "Dutch", "Farsi": "Persian", "Tagalog": "Filipino",
        "Dari": "Persian"}
LANGUAGES = sorted({SAME.get(x, x) for x in LANGS.split("|")})

FIELD_Q = ("Which specialist field of expertise must the worker bring? Choose the field of the knowledge the worker "
           "must bring, not the field of the client or of the company. A subject teacher or professor asked for "
           "subject knowledge takes the subject's field; education is for teaching skill itself. A doctor reviewing "
           "AI answers is medicine_health; a Dutch speaker rating search results is none.")
TASK_Q = "What is the main kind of work the person does in this job?"
LANG_Q = ("Which language other than English must the worker speak or write (native, fluent, bilingual)? "
          "Choose English_variety only when a specific variety or accent of English is required, and none when "
          "no language other than English is required.")


def requests(row: dict) -> list[dict]:
    state = f"Job listing for AI-training and data work.\nSite: {row['site']}\nTitle: {row['title']}\n\n{row['text']}"
    langs = {"none": "no language other than English is required",
             "English_variety": "a specific variety or accent of English (e.g. UK, Scottish, US)",
             **{x: None for x in LANGUAGES}}
    return [{"uid": row["uid"], "question": q, "request": {
                "state": state,
                "questions": {q: {"type": "choice", "instructions": words, "criteria": crit}}}}
            for q, words, crit in (("field", FIELD_Q, FIELDS), ("task", TASK_Q, TASKS), ("language", LANG_Q, langs))]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default="b")
    args = ap.parse_args()
    rows = [json.loads(line) for line in (HERE / f"sample-{args.sample}.jsonl").open()]
    items = [item for r in rows for item in requests(r)]
    (HERE / f"decider-{args.sample}-index.jsonl").write_text(
        "".join(json.dumps({"uid": i["uid"], "question": i["question"]}) + "\n" for i in items))
    (HERE / f"decider-{args.sample}-requests.jsonl").write_text(
        "".join(json.dumps(i["request"], ensure_ascii=False) + "\n" for i in items))
    print(f"{len(items)} requests for {len(rows)} jobs")
