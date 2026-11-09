"""The Phase 0/1 build must not be able to contact a target or submit a report."""

from __future__ import annotations

import re
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "src" / "bbguy"

FORBIDDEN_IMPORTS = (
    "socket",
    "ssl",
    "http.client",
    "urllib.request",
    "requests",
    "httpx",
    "aiohttp",
    "subprocess",
)
TOKEN_NAMES = (
    "H1_TOKEN",
    "HACKERONE_TOKEN",
    "HACKERONE_API_TOKEN",
    "X-HackerOne-API-Token",
)


def source_files() -> list[Path]:
    return sorted(SOURCE.rglob("*.py"))


def test_no_network_imports() -> None:
    for path in source_files():
        text = path.read_text(encoding="utf-8")
        for module in FORBIDDEN_IMPORTS:
            pattern = rf"^\s*(?:import|from)\s+{re.escape(module)}(?:\s|\.|$)"
            assert not re.search(pattern, text, re.MULTILINE), f"{path}: {module}"


def test_no_process_execution_or_dynamic_eval() -> None:
    for path in source_files():
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\bos\.system\s*\(", text), path
        assert not re.search(r"\bsubprocess\.", text), path
        assert not re.search(r"(?<![\w.])eval\s*\(", text), path
        assert not re.search(r"(?<![\w.])exec\s*\(", text), path


def test_no_hackerone_token_or_submit_path() -> None:
    for path in source_files():
        text = path.read_text(encoding="utf-8")
        for name in TOKEN_NAMES:
            assert name not in text, f"{path} contains {name}"
        assert not re.search(r"api\.hackerone\.com[^\n]*/(reports|submissions)", text), path
