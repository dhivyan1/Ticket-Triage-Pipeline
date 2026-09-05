"""Loader for app/config/prompts.yaml.

Prompts live in YAML so they can be diffed and reviewed like code; this
module is just the thin accessor.
"""

import os
from functools import lru_cache

import yaml

from app.config import CONFIG_DIR

PROMPTS_PATH = os.path.join(CONFIG_DIR, "prompts.yaml")


@lru_cache(maxsize=1)
def _load() -> dict:
    with open(PROMPTS_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def render(name: str, **kwargs) -> str:
    """Return prompt `name` with {placeholders} filled in."""
    prompts = _load()
    if name not in prompts:
        raise KeyError(f"No prompt named {name!r} in {PROMPTS_PATH}")
    return prompts[name]["template"].format(**kwargs)


def version(name: str) -> str:
    return _load()[name].get("version", "unversioned")
