# tests/helpers/redact.py
from __future__ import annotations
import re
from typing import Iterable

_TS = re.compile(r"\b20\d{2}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?\b")
_PATH = re.compile(r"[A-Za-z]:\\\\[^\\n\\r\\t]+")
_WS = re.compile(r"\s+")


def normalize_for_snapshot(text: str) -> str:
    text = _TS.sub("<TIMESTAMP>", text)
    text = _PATH.sub("<ABS_PATH>", text)
    # Collapse excessive whitespace lines that vary by terminal size
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return text


def contains_all(haystack: str, needles: Iterable[str]) -> bool:
    return all(n in haystack for n in needles)
