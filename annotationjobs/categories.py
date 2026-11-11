"""The three ways a job is sorted: field of expertise, languages, kind of task.

A language model reads each listing and picks from these lists (annotationjobs/categorize.py);
its answers are kept in data/categories.jsonl and read here, standard library only, by the page
and the charts.

Fields follow the major groups of the US Standard Occupational Classification (SOC 2018, the
list O*NET uses), merged or split where AI-training work needs it. Chosen and tested on
2026-11-10 (experiments/categorize/: five models on 60 listings).
"""

import hashlib
import json
from pathlib import Path

VERSION = "v2"  # change it when the lists or the prompt change: every job is then sorted again
MODEL = "openai-codex:gpt-6.1-terra"  # on our ChatGPT plan, thinking off
STORE = Path(__file__).resolve().parent.parent / "data" / "categories.jsonl"

# key: (name on the page, what the model is told it covers)
FIELDS = {
    "medicine_health": ("Medicine & health", "physicians, nurses, pharmacists, dentists, veterinarians, therapists, medical coders, clinical research (SOC 29, 31)"),
    "life_sciences": ("Life sciences", "biology, genetics, biotech, ecology, neuroscience research, agricultural and food science (SOC 19-1000)"),
    "physical_sciences": ("Physical sciences", "physics, chemistry, materials science, earth, climate and space science (SOC 19-2000)"),
    "mathematics_statistics": ("Maths & statistics", "mathematics, statistics, actuarial science, operations research (SOC 15-2000)"),
    "computing_software": ("Computing & software", "software engineering, data science, machine learning, IT, cybersecurity (SOC 15-1200)"),
    "engineering_architecture": ("Engineering & architecture", "every engineering discipline except software, architecture, CAD and drafting (SOC 17)"),
    "law": ("Law", "lawyers, paralegals, legal compliance, judges (SOC 23)"),
    "finance_accounting": ("Finance & accounting", "accounting, auditing, tax, banking, investing, trading, insurance, financial analysis (SOC 13-2000)"),
    "business_management": ("Business & management", "management, operations, consulting, HR, recruiting, marketing strategy, supply chain, real estate (SOC 11, 13-1000)"),
    "social_sciences": ("Social sciences", "economics, psychology, sociology, political science, anthropology, geography, public policy (SOC 19-3000)"),
    "humanities": ("Humanities", "history, philosophy, religion, literature, classics, art history"),
    "languages_linguistics": ("Languages & linguistics", "linguistics, translation, interpreting, professional transcription and localization as a trade"),
    "education": ("Education", "teaching itself as the expertise: pedagogy, lesson planning, tutoring, teaching a language, instructional design (SOC 25)"),
    "arts_design_media": ("Arts, design & media", "visual art, graphic/UX design, music, film, video, photography, writing, journalism, acting, voice acting, games (SOC 27)"),
    "military_security_safety": ("Military, security & safety", "military, intelligence, law enforcement, firefighting, emergency management, defense (SOC 33, 55)"),
    "trades_transport_manufacturing": ("Trades, transport & manufacturing", "construction trades, electricians, mechanics, technicians, pilots, air traffic control, drivers, manufacturing and quality inspection, farming (SOC 45-53)"),
    "sales_service_admin": ("Sales, service & admin", "sales, retail, customer support, office and administrative work (SOC 41, 43)"),
    "personal_services_hospitality": ("Personal services & hospitality", "cooking, hospitality, personal care, fitness, beauty, childcare (SOC 35-39)"),
    "other_specialty": ("Other specialty", "a specialist field that none of the above covers"),
    "none": ("No specialist field", "no specialist field: open to the general public, generalists, or anyone who speaks a language"),
}

TASKS = {
    "ai_answer_training": ("Training AI with answers", "write prompts and model answers, solve or check problems, judge or rank chatbot answers, write rubrics, red-team AI (expert or generalist)"),
    "search_ads_content_rating": ("Rating search, ads & content", "rate search results, ads, maps, recommendations or content against guidelines; content moderation"),
    "data_labeling": ("Labeling data", "label or annotate images, video, text, audio or sensor data (tags, boxes, outlines, categories)"),
    "translation_transcription": ("Translation & transcription", "translate, transcribe (including specialist audio such as medical or radio), localize, or review language quality"),
    "recording_data": ("Recording data", "produce recordings that are the dataset: your voice, speech, video, photos, head-camera or sensor/driving data, even when it is called a study"),
    "research_study": ("Paid study", "take part as a subject in a paid study, focus group, interview or user research where your answers, opinions or behaviour are what is studied, not recordings for a dataset"),
    "software_use_testing": ("Using or testing software", "do real tasks in a software application on your own computer while screenshots or screen recordings are captured (computer-use data), or quality-test apps"),
    "staff_role": ("Company staff role", "an employee role running the company or its projects (building the product, managing annotators or projects, recruiting, sales), not doing the data tasks yourself"),
    "other": ("Other", "none of the above"),
}

NOT_SORTED = "Not sorted yet"
NO_LANGUAGE = "English only"
ENGLISH_VARIETY = "English (a specific accent)"
SEVERAL = "Several languages"

PROMPT = """You sort job listings for AI-training and data work into three independent filters.

1. field: the specialist field of expertise the work draws on. One of:
{fields}
Choose the field of the knowledge the worker must bring, not the field of the client
or of the company. A subject teacher or professor asked for subject knowledge (a physics
professor writing physics problems) takes the subject's field; education is for teaching
skill itself. A doctor reviewing AI answers is medicine_health; a Dutch speaker
rating search results is none; a legal translator is law only if legal expertise is
asked for, otherwise languages_linguistics.

2. languages: every language other than English that the worker must speak or write
(native, fluent, bilingual), as its plain English name only: "Spanish", "Dutch",
"German", "Chinese", "Arabic" (Flemish is Dutch; Mandarin and Cantonese are Chinese).
Include "English" only when a specific variety or accent of English is required.
An empty list when no other language is required.
   varieties: the variety, region or accent the listing requires, as "Language (place
   or variety)" with the place named in English: "Dutch (Belgium)", "German (Switzerland)",
   "Chinese (Cantonese)", "English (Scotland)". An empty list when none is named.

3. task: the main kind of work the person does. One of:
{tasks}

Evidence: one to three short passages copied word for word from the listing below
(never from these instructions), each a separate string, never joined or shortened
with "...".

Reply with one JSON object and nothing else, keys in this order:
{{"field_evidence": ["<exact passage>"],
  "field": "<one field key>",
  "languages_evidence": ["<exact passage>"],
  "languages": ["..."],
  "varieties": ["..."],
  "task_evidence": ["<exact passage>"],
  "task": "<one task key>"}}

The listing:
Site: {site}
Title: {title}

{text}"""


def prompt(listing: dict) -> str:
    describe = lambda d: "\n".join(f"- {k}: {words}" for k, (_, words) in d.items())  # noqa: E731
    return PROMPT.format(fields=describe(FIELDS), tasks=describe(TASKS), site=listing["site"],
                         title=listing["title"].strip(), text=listing.get("text") or "")


def content_key(listing: dict) -> str:
    """Same site, title and text -> same answer: copies of a job posted per city are sorted once,
    and a listing whose text changes is sorted again."""
    s = "\n".join([listing["site"], listing["title"].strip(), listing.get("text") or ""])
    return hashlib.sha256(s.encode()).hexdigest()[:20]


def load() -> dict:
    """content key -> the current answer (this VERSION only; the last line wins)."""
    out = {}
    if STORE.exists():
        for line in STORE.open():
            r = json.loads(line)
            if r.get("version") == VERSION:
                out[r["key"]] = r
    return out


def label_for(copies: list, labels: dict) -> dict | None:
    """The answer for a job, from any of its copies."""
    return next((labels[k] for k in (content_key(c) for c in copies) if k in labels), None)


# One name per language: the model wrote both names of these (all 2,653 open jobs, 2026-11-11)
SAME_LANGUAGE = {"Farsi": "Persian", "Filipino": "Tagalog", "Oriya": "Odia", "Mandarin": "Chinese",
                 "Cantonese": "Chinese", "Flemish": "Dutch"}


def languages(label: dict) -> list:
    return list(dict.fromkeys(SAME_LANGUAGE.get(x, x) for x in label.get("languages") or []))


def language_group(languages: list) -> str:
    """One value per job for grouping and filtering: English is dropped when another language is
    asked for (a Hungarian-English translator is grouped under Hungarian)."""
    other = sorted({SAME_LANGUAGE.get(x, x) for x in languages if x != "English"})
    if len(other) > 1:
        return SEVERAL
    if other:
        return other[0]
    return ENGLISH_VARIETY if "English" in languages else NO_LANGUAGE
