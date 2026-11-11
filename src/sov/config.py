"""Settings. Everything that decides reads its numbers from config/platform.toml."""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]


@lru_cache
def platform() -> dict[str, Any]:
    with open(ROOT / "config" / "platform.toml", "rb") as f:
        return tomllib.load(f)


def tenants_dir() -> Path:
    return ROOT / "tenants"


def load_tenants() -> dict[str, dict[str, Any]]:
    """The authorities on the platform: one YAML file each in tenants/."""
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(tenants_dir().glob("*.yaml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        out[spec["name"]] = spec
    return out
