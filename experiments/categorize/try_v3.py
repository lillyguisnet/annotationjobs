"""Ask the current categories (v3) about the talent-pool postings that v2 split, and a control set.

    uv run --no-project --with lm15==1.5.0 python experiments/categorize/try_v3.py
"""
import collections
import json
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from lm15 import LMRouter  # noqa: E402

from annotationjobs.categorize import ask  # noqa: E402
from annotationjobs.collect import all_listings  # noqa: E402

old = {}
for line in (ROOT / "data/categories.jsonl").open():
    r = json.loads(line)
    if r["version"] == "v2":
        old[r["uid"]] = r
rows = {r["uid"]: r for r in all_listings()[0] if r["uid"] in old}
pool = [u for u in rows if re.search(r"^(AI Trainers Network|Shape the Future of AI)", rows[u]["title"])]
rng = random.Random(1)
control = rng.sample(sorted(u for u in rows if u not in pool), 40)
router = LMRouter()
with ThreadPoolExecutor(4) as ex:
    new = dict(zip(pool + control, ex.map(lambda u: ask(router, rows[u]), pool + control)))
for name, uids in (("talent pools", pool), ("40 other jobs", control)):
    print(f"\n{name}: v2 {collections.Counter(old[u]['task'] for u in uids).most_common()}")
    print(f"{name}: v3 {collections.Counter(new[u]['task'] for u in uids).most_common()}")
for u in control:
    for k in ("task", "field"):
        if old[u][k] != new[u][k]:
            print(f"  changed {k}: {rows[u]['title'][:60]}: {old[u][k]} -> {new[u][k]}")
