"""Every place listings are collected from.

kind:
  marketplace  contributor platform: every listing is AI-training / annotation work
  vendor       data / annotation company's own careers board: staff jobs filtered out by title
  lab          AI lab or AI company careers board: only annotation-type titles kept
  bigtech      keyword search of a big company's career site, then the same title filter
"""

from . import ats, bigtech, marketplaces as mp


def B(source, site, kind, reader, token=None, **kw):
    return {"source": source, "site": site, "kind": kind, "reader": reader, "token": token,
            "all_relevant": kind == "marketplace", **kw}


BOARDS = [
    # contributor marketplaces with their own sites
    B("mercor", "Mercor", "marketplace", mp.mercor),
    B("handshake", "Handshake AI", "marketplace", mp.handshake),
    B("micro1", "micro1", "marketplace", mp.micro1),
    B("alignerr", "Alignerr", "marketplace", mp.alignerr),
    B("outlier", "Outlier", "marketplace", mp.outlier),
    B("dataannotation", "DataAnnotation", "marketplace", mp.dataannotation),
    B("oneforma", "OneForma", "marketplace", mp.oneforma),
    B("mindrift", "Mindrift (Toloka)", "marketplace", ats.workable, "toloka-ai", detail_limit=0),
    # data / annotation companies' own careers boards
    B("gh-scaleai", "Scale AI", "vendor", ats.greenhouse, "scaleai"),
    B("gh-remotasks", "Remotasks", "vendor", ats.greenhouse, "remotasks"),
    B("gh-invisible", "Invisible Technologies", "vendor", ats.greenhouse, "invisible"),
    B("gh-invisibletech", "Invisible Technologies", "vendor", ats.greenhouse, "invisibletech"),
    B("gh-labelbox", "Labelbox", "vendor", ats.greenhouse, "labelbox"),
    B("gh-prolific", "Prolific", "vendor", ats.greenhouse, "prolific"),
    B("gh-snorkel", "Snorkel AI", "vendor", ats.greenhouse, "snorkelai"),
    B("gh-toloka", "Toloka", "vendor", ats.greenhouse, "toloka"),
    B("gh-turing", "Turing", "vendor", ats.greenhouse, "turing"),
    B("gh-sama", "Sama", "vendor", ats.greenhouse, "samainc"),
    B("ashby-surge", "Surge AI", "vendor", ats.ashby, "surge-ai"),
    B("ashby-abaka", "Abaka AI", "vendor", ats.ashby, "abaka.ai"),
    B("ashby-pareto", "Pareto.AI", "vendor", ats.ashby, "pareto-ai"),
    B("ashby-afterquery", "AfterQuery", "vendor", ats.ashby, "afterquery"),
    B("ashby-g2i", "G2i", "vendor", ats.ashby, "g2i"),
    B("ashby-braintrust", "Braintrust", "vendor", ats.ashby, "braintrust"),
    B("ashby-mercor", "Mercor (staff board)", "vendor", ats.ashby, "mercor"),
    B("ashby-handshake", "Handshake (staff board)", "vendor", ats.ashby, "handshake"),
    B("lever-appen", "Appen", "marketplace", ats.lever, "appen"),  # crowd board: all postings are contributor work
    B("lever-rws", "RWS (TrainAI)", "marketplace", ats.lever, "rws"),  # TrainAI crowd board
    B("lever-lionbridge", "Lionbridge", "marketplace", ats.lever, "lionbridge", host="api.eu.lever.co"),  # AI crowd board
    B("lever-welocalize", "Welocalize", "vendor", ats.lever, "weloglobal",
      also=r"\bAI\b|recording|audio|rater|evaluat|annotat|transcri|relevance|search|ad(vertisement)? reviewer|anzeigenpr|data"),
    B("lever-superannotate", "SuperAnnotate", "vendor", ats.lever, "superannotate"),
    B("lever-innodata", "Innodata", "vendor", ats.lever, "innodata"),
    B("workable-cloudfactory", "CloudFactory", "vendor", ats.workable, "cloudfactory",
      also=r"capture|technician|annotator|linguist|pedagogy"),
    B("workday-centific", "Centific", "vendor", ats.workday, host="centific.wd1.myworkdayjobs.com",
      tenant="centific", site_id="Centific_Global"),
    # AI labs and AI companies
    B("gh-anthropic", "Anthropic", "lab", ats.greenhouse, "anthropic"),
    B("gh-xai", "xAI", "lab", ats.greenhouse, "xai"),
    B("gh-together", "Together AI", "lab", ats.greenhouse, "togetherai"),
    B("gh-figure", "Figure AI", "lab", ats.greenhouse, "figure"),
    B("gh-stability", "Stability AI", "lab", ats.greenhouse, "stabilityai"),
    B("gh-ai2", "Allen Institute for AI", "lab", ats.greenhouse, "thealleninstitute"),
    B("ashby-openai", "OpenAI", "lab", ats.ashby, "openai"),
    B("ashby-cohere", "Cohere", "lab", ats.ashby, "cohere"),
    B("ashby-mistral", "Mistral AI", "lab", ats.ashby, "mistral.ai"),
    B("ashby-perplexity", "Perplexity", "lab", ats.ashby, "perplexity"),
    B("ashby-character", "Character.AI", "lab", ats.ashby, "character"),
    B("ashby-elevenlabs", "ElevenLabs", "lab", ats.ashby, "elevenlabs"),
    B("ashby-suno", "Suno", "lab", ats.ashby, "suno"),
    B("ashby-midjourney", "Midjourney", "lab", ats.ashby, "midjourney"),
    B("ashby-thinkingmachines", "Thinking Machines Lab", "lab", ats.ashby, "thinkingmachines"),
    B("ashby-reflection", "Reflection AI", "lab", ats.ashby, "reflectionai"),
    B("ashby-pi", "Physical Intelligence", "lab", ats.ashby, "physicalintelligence"),
    B("ashby-1x", "1X", "lab", ats.ashby, "1x"),
    B("ashby-reka", "Reka", "lab", ats.ashby, "reka"),
    B("ashby-magic", "Magic", "lab", ats.ashby, "magic"),
    B("ashby-poolside", "Poolside", "lab", ats.ashby, "poolside"),
    B("ashby-alephalpha", "Aleph Alpha", "lab", ats.ashby, "alephalpha"),
    B("ashby-worldlabs", "World Labs", "lab", ats.ashby, "worldlabs"),
    B("ashby-runway", "Runway", "lab", ats.ashby, "runway"),
    B("ashby-cognition", "Cognition", "lab", ats.ashby, "cognition"),
    B("ashby-harvey", "Harvey", "lab", ats.ashby, "harvey"),
    B("ashby-sierra", "Sierra", "lab", ats.ashby, "sierra"),
    B("ashby-decagon", "Decagon", "lab", ats.ashby, "decagon"),
    B("ashby-writer", "Writer", "lab", ats.ashby, "writer"),
    B("ashby-cursor", "Cursor", "lab", ats.ashby, "cursor"),
    B("workable-huggingface", "Hugging Face", "lab", ats.workable, "huggingface"),
    # big companies, keyword search
    B("google", "Google / DeepMind", "bigtech", bigtech.google),
    B("amazon", "Amazon", "bigtech", bigtech.amazon),
    B("apple", "Apple", "bigtech", bigtech.apple),
    B("workday-nvidia", "NVIDIA", "bigtech", ats.workday, host="nvidia.wd5.myworkdayjobs.com", tenant="nvidia",
      site_id="NVIDIAExternalCareerSite", search=bigtech.KEYWORDS),
]
