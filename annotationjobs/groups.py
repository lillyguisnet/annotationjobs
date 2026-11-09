"""How jobs are grouped, shared by the charts (plots.py) and the public page (site.py)."""

import re

KIND_NAME = {"marketplace": "Contributor platform", "vendor": "Data company's own board", "lab": "AI lab / AI company",
             "bigtech": "Big tech"}

LANGS = ("Spanish|French|German|Italian|Portuguese|Japanese|Korean|Chinese|Mandarin|Cantonese|Arabic|Hindi|Bengali|Urdu|Punjabi|"
         "Tamil|Telugu|Marathi|Gujarati|Kannada|Malayalam|Russian|Ukrainian|Polish|Czech|Slovak|Hungarian|Romanian|Bulgarian|"
         "Greek|Turkish|Hebrew|Persian|Farsi|Dutch|Flemish|Swedish|Norwegian|Danish|Finnish|Icelandic|Estonian|Latvian|"
         "Lithuanian|Serbian|Croatian|Bosnian|Slovenian|Albanian|Macedonian|Georgian|Armenian|Azerbaijani|Kazakh|Uzbek|"
         "Vietnamese|Thai|Indonesian|Malay|Filipino|Tagalog|Burmese|Khmer|Lao|Nepali|Sinhala|Swahili|Amharic|Yoruba|Igbo|"
         "Hausa|Zulu|Xhosa|Afrikaans|Somali|Catalan|Basque|Galician|Welsh|Irish|Maltese|Luxembourgish|Lingala|Siswati|"
         "Kyrgyz|Tajik|Mongolian|Pashto|Dari|Kurdish|Haitian|Quechua|Guarani|Maori|Samoan|Hawaiian|Cherokee|Navajo")
FIELDS = [  # first match wins, on the title
    ("Medicine & health", r"physician|doctor|\bmd\b|\bdo\b|nurse|\brn\b|medical|clinic|health|surgeon|radiolog|oncolog|cardiolog|"
                          r"neurolog|psychiatr|patholog|pharma|dentist|dental|therap|anesthes|pediatric|obstetric|gynec|"
                          r"dermatolog|veterinar|epidemiolog|inpatient coder|medical coder|vascular|technologist|hospital|internist|sonograph|ultrasound|optometr|ophthalm|nurs|intensivist|"
                          r"nephrolog|orthodont|urolog|gastro|endocrin|hematolog|pulmonolog|rheumatolog|immunolog|"
                          r"emergency med|paramedic|\bemt\b|midwi|dietitian|nutrition|surgery|clinician|biomedical|"
                          r"\bVA eligibility"),
    ("Law", r"legal|\blaw\b|lawyer|attorney|paralegal|counsel|compliance|litigat|contracts? (?:attorney|specialist)"),
    ("Finance & accounting", r"financ|accountant|accounting|\btax\b|audit|actuar|invest|banking|bank\b|\bcfa\b|equity|trader|"
                             r"trading|econom|insurance|underwrit|controller|fp&a|bookkeep"),
    ("Security, defense & AI safety", r"red team|military|intelligence|naval|navy|army|defen[cs]e|cbrn|incident respon|"
                                      r"threat|imagery analyst|cleared|safety trainer|\bihl\b|weapons|forensic|combat|targeting|nuclear"),
    ("Software & data", r"software|developer|coding|\bcode\b|programm|data scien|machine learning|\bml\b|devops|back[- ]?end|"
                        r"front[- ]?end|full[- ]?stack|python|javascript|typescript|java\b|rust\b|golang|\bc\+\+|sql|"
                        r"cyber|security|cloud|infrastructure|swe\b|ai engineer|data engineer|data analyst|lean 4|formal"),
    ("Other engineering", r"engineer|mechanical|civil|electrical|chemical|aerospace|\bcad\b|cfd|robotic|manufactur|architect|"
                          r"construction|energy|hvac|pcb|semiconductor|automotive"),
    ("Math & science", r"math|physic|chemist|biolog|scien|statistic|astronom|geolog|ecolog|neuro|genomic|materials|"
                       r"postdoc|phd|masters?\b|researcher"),
    ("Languages", rf"trainers network|1[ ,.]?200.{{0,4}}1[ ,.]?600|linguist|translat|transcri|native|bilingual|dialect|language|speaker|locali[sz]|{LANGS}"),
    ("Creative & media", r"design|music|video|audio|voice|artist|\bart\b|writer|writing|photo|film|animat|editor|creative|"
                         r"illustrat|game|actor|vo talent|sound|producer|journalis|cinemat"),
    ("Business, sales & operations", r"manag|analyst|marketing|sales|consult|retail|logistic|clerk|telemarket|credit|"
                                     r"treasury|\besg\b|venture|recruit|procurement|supply chain|operations|business|"
                                     r"human resources|\bhr\b|real estate|insurance|agent|planner|merchandis|buyer|styling"),
    ("Trades & technical", r"electrician|weld|inspector|inspection|\bndt\b|pilot|metallurg|plumb|mechanic|technician|"
                           r"carpent|machinist|driver|aircraft|maritime|aviation|agricultur|crop|farm"),
    ("App users & software testing", r"application users|\buser\b|\btester\b|testing|chatbot"),
    ("Education & humanities", r"teacher|tutor|instructor|professor|educat|history|philosoph|sociolog|psycholog|humanit|"
                               r"literature|anthropolog|politic"),
    ("Generalist, data collection & studies", r"generalist|rater|evaluat|annotat|label|data collect|record|participant|study|"
                                              r"studies|gig|capture|survey|photo contributor|operator|driver|search|focus group|get paid for your time|"
                                              r"reviewer|task author|ai trainer|data quality|talent pool|vlogger|bezahlte studie|"
                                              r"ビデオ|撮影"),
]
FIELDS = [(n, re.compile(rx, re.I)) for n, rx in FIELDS]


def field(title):
    for name, rx in FIELDS:
        if rx.search(title):
            return name
    return "Other"


def hourly_usd(r):
    return r["pay_max"] if r["pay_max"] is not None and r["pay_unit"] == "hour" and r["pay_currency"] == "USD" else None



def degree_level(degrees):
    """Highest degree mentioned in the listing (mentioned, not necessarily required)."""
    d = degrees or ""
    return ("MD / JD" if "MD/JD" in d else "PhD" if "PhD" in d else "Master's" if "Master" in d
            else "Bachelor's" if "Bachelor" in d else "Associate's" if "Associate" in d else "none")


PAY_CLASSES = [("Fixed figure or range", "#2a9d6f"), ("Varies / only \"up to\"", "#e9b44c"),
               ("No figure, but says how (per task, later...)", "#e07a5f"), ("Nothing about pay", "#bbbbbb")]


def pay_class(j):
    if j["pay_max"] is not None:
        return PAY_CLASSES[1][0] if j.get("pay_variable") else PAY_CLASSES[0][0]
    return PAY_CLASSES[2][0] if j.get("pay_note") else PAY_CLASSES[3][0]


RULES = [("only listed places", "Must live in listed places", "#d0662b"), ("anywhere", "Anywhere", "#2a9d6f"),
         ("anywhere except excluded", "Anywhere except some places", "#7fc8a9"),
         ("must come on site", "Must come on site", "#7a5cc0"),
         ("listed place, rule not stated", "Place listed, not said if required", "#e9d8a6"), ("", "Not stated", "#cccccc")]
