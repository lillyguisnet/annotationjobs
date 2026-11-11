# /// script
# requires-python = ">=3.11"
# dependencies = ["lm15==1.5.0"]
# ///
"""Which model names each plan answers to today (one tiny call per name).

uv run experiments/categorize/probe.py
"""

import sys

from lm15 import Config, Message, Request

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from llm import router_for  # noqa: E402

CANDIDATES = [
    "openai-codex:gpt-6-luna", "openai-codex:gpt-6.1-luna", "openai-codex:gpt-6.2-luna",
    "openai-codex:gpt-6.1-terra", "openai-codex:gpt-6.2-terra",
    "claude-code:claude-haiku-5-5", "claude-code:claude-haiku-5-6", "claude-code:claude-haiku-6",
    "claude-code:claude-opus-5-5", "claude-code:claude-opus-5-6", "claude-code:claude-opus-6",
    "meta:muse-ember-1.0", "meta:muse-ember-1.1",
]

for route in CANDIDATES:
    router = router_for(route)
    try:
        r = router.complete(Request(model=route, messages=(Message.user("Reply with the single word: ok"),),
                                    config=Config()))
        print(f"OK    {route:40s} -> {r.model!r}: {(r.text or '').strip()[:30]!r}")
    except Exception as e:
        print(f"FAIL  {route:40s} {type(e).__name__}: {str(e)[:120]}")
