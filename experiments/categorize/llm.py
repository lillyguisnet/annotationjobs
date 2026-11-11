"""Routers for our three plans: ChatGPT (openai-codex), Claude (claude-code) and Muse Code (meta).

Every call goes to a plan, never to a pay-per-token key:
- openai-codex and claude-code use the plan logins lm15 finds (codex / claude sign-ins).
- meta uses the Muse Code plan's own key from ~/.config/muse/auth.json, in a router
  that sees no environment, so a META_API_KEY can never take over. The checks are
  the ones segbench/muse_plan.py makes (plan active, browser sign-in, meta.ai address).
"""

import json
import os
import urllib.parse
from pathlib import Path

from lm15 import LMRouter, Timeouts
from lm15.router import RouterConfig

# Anthropic refuses newer models to older Claude Code releases; lm15 1.5.0 claims
# an older one. Same pin as segbench (installed release on lambda, 2026-11-09).
CLAUDE_CODE_VERSION = "2.1.314"
MUSE_AUTH = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "muse" / "auth.json"

_plans = LMRouter(RouterConfig(timeouts=Timeouts(),
                               settings={"claude-code": {"client_version": CLAUDE_CODE_VERSION}}))


def _muse_router() -> LMRouter:
    meta = json.loads(MUSE_AUTH.read_text())["providers"]["meta"]
    key, base = meta.get("api_key"), (meta.get("api_base_url") or "https://api.meta.ai/v1").rstrip("/")
    if not key or meta.get("subs_active") is not True or meta.get("obtained_via") != "device_code":
        raise RuntimeError("Muse Code plan login missing or inactive; run `muse login` (never paying per token)")
    if key == os.environ.get("META_API_KEY"):
        raise RuntimeError("the Muse Code login holds the pay-per-token key")
    host = urllib.parse.urlsplit(base).hostname or ""
    if not (host == "meta.ai" or host.endswith(".meta.ai")):
        raise RuntimeError(f"Muse login names an address outside meta.ai: {base!r}")
    return LMRouter(RouterConfig(env={}, api_keys={"meta": key}, base_urls={"meta": base}, timeouts=Timeouts()))


def router_for(route: str) -> LMRouter:
    provider = route.split(":", 1)[0]
    if provider == "meta":
        return _muse_router()
    if provider not in ("openai-codex", "claude-code"):
        raise ValueError(f"{route}: not one of our plans")
    return _plans
