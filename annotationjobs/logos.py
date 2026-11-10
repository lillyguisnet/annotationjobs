"""Small logos of the sites, shown on the public page next to their names.

    python3 -m annotationjobs.logos            # download the logos still missing into docs/logos/
    python3 -m annotationjobs.logos --again    # download them all again

Each logo is the site's own icon (favicon) at 64 px, as Google's favicon service serves it, saved once into
docs/logos/ and committed with the page, so visitors' browsers never call Google or the sites themselves.
A site with no entry in DOMAINS, or whose icon could not be fetched, is shown without a logo.
"""

import argparse
import re
import struct
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "docs" / "logos"
URL = "https://www.google.com/s2/favicons?domain={}&sz=64"

# site name as stored (boards.py, bigtech.py) -> the company's own website
DOMAINS = {
    "1X": "1x.tech", "Abaka AI": "abaka.ai", "AfterQuery": "afterquery.com", "Aleph Alpha": "aleph-alpha.com",
    "Alignerr": "alignerr.com", "Allen Institute for AI": "allenai.org", "Amazon": "amazon.com",
    "Anthropic": "anthropic.com", "Appen": "appen.com", "Apple": "apple.com", "Braintrust": "usebraintrust.com",
    "Centific": "centific.com", "Character.AI": "character.ai", "CloudFactory": "cloudfactory.com",
    "Cognition": "cognition.ai", "Cohere": "cohere.com", "Cursor": "cursor.com", "DataAnnotation": "dataannotation.tech",
    "Decagon": "decagon.ai", "ElevenLabs": "elevenlabs.io", "Figure AI": "figure.ai", "G2i": "g2i.co",
    "Google": "google.com", "Google DeepMind": "deepmind.google", "Google / DeepMind": "deepmind.google",
    "Handshake AI": "joinhandshake.com", "Handshake (staff board)": "joinhandshake.com", "Harvey": "harvey.ai",
    "Hugging Face": "huggingface.co", "Innodata": "innodata.com", "Invisible Technologies": "invisible.co",
    "Labelbox": "labelbox.com", "Lionbridge": "lionbridge.com", "Magic": "magic.dev", "Mercor": "mercor.com",
    "Mercor (staff board)": "mercor.com", "Midjourney": "midjourney.com", "Mindrift (Toloka)": "mindrift.ai",
    "Mistral AI": "mistral.ai", "NVIDIA": "nvidia.com", "OneForma": "oneforma.com", "OpenAI": "openai.com",
    "Outlier": "outlier.ai", "Pareto.AI": "pareto.ai", "Perplexity": "perplexity.ai",
    "Physical Intelligence": "physicalintelligence.company", "Poolside": "poolside.ai", "Prolific": "prolific.com",
    "RWS (TrainAI)": "rws.com", "Reflection AI": "reflection.ai", "Reka": "reka.ai", "Remotasks": "remotasks.com",
    "Runway": "runwayml.com", "Sama": "sama.com", "Scale AI": "scale.com", "Sierra": "sierra.ai",
    "Snorkel AI": "snorkel.ai", "Stability AI": "stability.ai", "Suno": "suno.com", "SuperAnnotate": "superannotate.com",
    "Surge AI": "surgehq.ai", "Thinking Machines Lab": "thinkingmachines.ai", "Together AI": "together.ai",
    "Toloka": "toloka.ai", "Turing": "turing.com", "Welocalize": "welocalize.com", "World Labs": "worldlabs.ai",
    "Writer": "writer.com", "micro1": "micro1.ai", "xAI": "x.ai",
}


def slug(domain):
    return re.sub(r"[^a-z0-9]+", "-", domain.lower())


def image_kind(data):
    """("png" | "jpg", width, height), or None for anything else."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ("png", *struct.unpack(">II", data[16:24]))
    if data[:3] == b"\xff\xd8\xff":  # JPEG: size from the first start-of-frame marker
        i = 2
        while i + 9 < len(data):
            marker, length = data[i + 1], struct.unpack(">H", data[i + 2:i + 4])[0]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return ("jpg", w, h)
            i += 2 + length
        return ("jpg", 0, 0)
    return None


def on_disk(domain):
    return next((p for ext in ("png", "jpg") if (p := DIR / f"{slug(domain)}.{ext}").exists()), None)


def fetch(domain):
    """The icon's bytes, or None (Google answers 404 with a generic globe when it knows no icon)."""
    req = urllib.request.Request(URL.format(domain), headers={"User-Agent": "annotationjobs"})
    for attempt in range(3):  # the service sometimes answers 404 for a domain it knows, then not
        try:
            with urllib.request.urlopen(req, timeout=30) as f:
                data = f.read()
            return data if image_kind(data) else None
        except urllib.error.HTTPError:
            time.sleep(2 * (attempt + 1))
    return None


def download(again=False):
    DIR.mkdir(parents=True, exist_ok=True)
    for domain in sorted(set(DOMAINS.values())):
        if on_disk(domain) and not again:
            continue
        data = fetch(domain)
        if data is None:
            print(f"logos: no icon for {domain}", file=sys.stderr)
            continue
        ext, w, h = image_kind(data)
        for old in DIR.glob(slug(domain) + ".*"):
            old.unlink()
        (DIR / f"{slug(domain)}.{ext}").write_bytes(data)
        print(f"logos: {domain} {w}x{h} {ext}" + ("  (small: may look blurry)" if w < 32 else ""))


def logo_paths(sites):
    """{site name: path of its logo, relative to docs/} for the sites that have one on disk."""
    out = {}
    for s in sites:
        if s in DOMAINS and (p := on_disk(DOMAINS[s])):
            out[s] = p.relative_to(DIR.parent).as_posix()
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--again", action="store_true", help="download every logo again")
    download(ap.parse_args().again)
