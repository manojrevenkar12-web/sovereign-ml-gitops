"""Python access to the generated Fluent Bit redactor, so training data is cleaned by the same code
that cleans the logs. Offsets come back as character positions in the Python string."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from sov.config import ROOT, platform


@dataclass(frozen=True)
class Found:
    kind: str
    start: int
    end: int


@lru_cache
def _lua() -> Any:
    try:
        from lupa.luajit21 import LuaRuntime  # the runtime Fluent Bit embeds
    except ImportError:  # pragma: no cover - lupa built without LuaJIT
        from lupa.lua51 import LuaRuntime
    rt = LuaRuntime(unpack_returned_tuples=True, encoding="utf-8")
    rt.execute((ROOT / platform()["pii"]["lua_engine"]).read_text(encoding="utf-8"))
    return rt


def redact(text: str) -> tuple[str, list[Found]]:
    rt = _lua()
    out, spans = rt.globals().REDACTOR.redact(text)
    raw = text.encode("utf-8")
    found = []
    for i in range(1, len(spans) + 1):
        sp = spans[i]
        start = len(raw[: sp[2] - 1].decode("utf-8", "ignore"))
        end = len(raw[: sp[3]].decode("utf-8", "ignore"))
        found.append(Found(sp[1], start, end))
    return out, found


def redact_record(record: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Run the Fluent Bit callback exactly as Fluent Bit would (for tests)."""
    rt = _lua()
    table = rt.table_from(record)
    code, _ts, out = rt.globals().redact_record("kube.test", 0, table)
    return int(code), {k: out[k] for k in out}
