"""The three filters a job is sorted by: field of expertise, languages, kind of task.

Fields follow the major groups of the US Standard Occupational Classification
(SOC 2018, the list O*NET uses), merged or split where AI-training work needs it:
science is split the way SOC splits it (life / physical / social), maths is
separated from software, and "none" holds work that needs no specialist field.
"""

VERSION = "v1"

FIELDS = {
    "medicine_health": "physicians, nurses, pharmacists, dentists, veterinarians, therapists, medical coders, clinical research (SOC 29, 31)",
    "life_sciences": "biology, genetics, biotech, ecology, neuroscience research, agricultural and food science (SOC 19-1000)",
    "physical_sciences": "physics, chemistry, materials science, earth, climate and space science (SOC 19-2000)",
    "mathematics_statistics": "mathematics, statistics, actuarial science, operations research (SOC 15-2000)",
    "computing_software": "software engineering, data science, machine learning, IT, cybersecurity (SOC 15-1200)",
    "engineering_architecture": "every engineering discipline except software, architecture, CAD and drafting (SOC 17)",
    "law": "lawyers, paralegals, legal compliance, judges (SOC 23)",
    "finance_accounting": "accounting, auditing, tax, banking, investing, trading, insurance, financial analysis (SOC 13-2000)",
    "business_management": "management, operations, consulting, HR, recruiting, marketing strategy, supply chain, real estate (SOC 11, 13-1000)",
    "social_sciences": "economics, psychology, sociology, political science, anthropology, geography, public policy (SOC 19-3000)",
    "humanities": "history, philosophy, religion, literature, classics, art history",
    "languages_linguistics": "linguistics, translation, interpreting, professional transcription and localization as a trade",
    "education": "teaching, tutoring, instructional design, academic advising (SOC 25)",
    "arts_design_media": "visual art, graphic/UX design, music, film, video, photography, writing, journalism, acting, voice acting, games (SOC 27)",
    "military_security_safety": "military, intelligence, law enforcement, firefighting, emergency management, defense (SOC 33, 55)",
    "trades_transport_manufacturing": "construction trades, electricians, mechanics, technicians, pilots, drivers, manufacturing, farming (SOC 45-53)",
    "sales_service_admin": "sales, retail, customer support, office and administrative work (SOC 41, 43)",
    "personal_services_hospitality": "cooking, hospitality, personal care, fitness, beauty, childcare (SOC 35-39)",
    "other_specialty": "a specialist field that none of the above covers",
    "none": "no specialist field: open to the general public, generalists, or anyone who speaks a language",
}

TASKS = {
    "ai_answer_training": "write prompts and model answers, solve or check problems, judge or rank chatbot answers, write rubrics, red-team AI (expert or generalist)",
    "search_ads_content_rating": "rate search results, ads, maps, recommendations or content against guidelines; content moderation",
    "data_labeling": "label or annotate images, video, text, audio or sensor data (tags, boxes, outlines, categories)",
    "translation_transcription": "translate, transcribe, localize, or review language quality",
    "recording_data": "record your voice, speech, video, photos, or sensor/driving data for a dataset",
    "research_study": "take part as a subject in a paid study, focus group, interview or experiment",
    "software_use_testing": "use or test software applications while being recorded, or quality-test apps",
    "staff_role": "an employee role running the company or its projects (building the product, managing annotators or projects, recruiting, sales), not doing the data tasks yourself",
    "other": "none of the above",
}


def describe(choices: dict) -> str:
    return "\n".join(f"- {key}: {words}" for key, words in choices.items())


PROMPT = """You sort job listings for AI-training and data work into three independent filters.

1. field: the specialist field of expertise the work draws on. One of:
{fields}
Choose the field of the knowledge the worker must bring, not the field of the client
or of the company. A doctor reviewing AI answers is medicine_health; a Dutch speaker
rating search results is none; a legal translator is law only if legal expertise is
asked for, otherwise languages_linguistics.

2. languages: every language other than English that the worker must speak or write
(native, fluent, bilingual), named in English. Add the variety in parentheses when the
listing names one, e.g. "Spanish (Mexico)", "Chinese (Mandarin)", "Arabic (Egyptian)".
Include English only when a specific variety or accent is required, e.g. "English (UK)".
An empty list when no other language is required.

3. task: the main kind of work the person does. One of:
{tasks}

Reply with one JSON object and nothing else, keys in this order:
{{"field_evidence": "<words copied exactly from the listing that show the field>",
  "field": "<one field key>",
  "languages_evidence": "<words copied exactly from the listing, or empty>",
  "languages": ["..."],
  "task_evidence": "<words copied exactly from the listing that show the task>",
  "task": "<one task key>"}}

The listing:
Site: {site}
Title: {title}

{text}"""


def prompt(site: str, title: str, text: str) -> str:
    return PROMPT.format(fields=describe(FIELDS), tasks=describe(TASKS), site=site, title=title, text=text)
