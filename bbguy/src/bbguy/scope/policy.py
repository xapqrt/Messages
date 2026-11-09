"""Policy prose to an automation verdict.

This is deliberately conservative and explainable. It is not an authority: a
human confirms the verdict per program. A policy that is silent yields UNKNOWN,
which turns every active verb off.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from .models import AutomationVerdict

_TAG = re.compile(r"<[^>]+>")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?;])\s+|\n+")

_FORBID_PATTERNS = (
    re.compile(
        r"\b(?:automated\s+(?:scanning|testing|tools?|scanners?)|scanners?)\b"
        r"[^.]{0,80}\b(?:not\s+(?:permitted|allowed|authori[sz]ed)|prohibited|forbidden)\b"
    ),
    re.compile(r"\b(?:do\s+not|don't|must\s+not|may\s+not|cannot|can't)\b[^.]{0,60}\bautomated\b"),
    re.compile(r"\bno\s+automated\s+(?:scanning|testing|tools?|scanners?)\b"),
    re.compile(r"\bmanual\s+testing\s+only\b"),
    re.compile(r"\bautomated\s+(?:scanning|testing)\b[^.]{0,40}\bonly\s+by\s+hand\b"),
)

_ALLOW_PATTERNS = (
    re.compile(
        r"\b(?:automated\s+(?:scanning|testing|tools?|scanners?)|scanners?)\b"
        r"[^.]{0,80}\b(?:permitted|allowed|welcome|authori[sz]ed|acceptable|encouraged)\b"
    ),
    re.compile(r"\b(?:may|can|allowed\s+to|permitted\s+to)\s+(?:use|run)\s+automated\b"),
    re.compile(r"\bautomation\b[^.]{0,60}\b(?:permitted|allowed|welcome)\b"),
    re.compile(r"\b(?:automated\s+(?:scanning|testing))\b[^.]{0,40}\bnot\s+prohibited\b"),
    re.compile(r"\bnot\s+(?:prohibited|forbidden)\b[^.]{0,40}\bautomated\b"),
)


@dataclass(frozen=True)
class PolicyVerdict:
    verdict: AutomationVerdict
    evidence: tuple[str, ...]

    @property
    def explanation(self) -> str:
        if not self.evidence:
            return "no automation language found; active verbs stay off"
        return " | ".join(self.evidence)


def _sentences(text: str) -> list[str]:
    plain = html.unescape(_TAG.sub(" ", text))
    return [part.strip() for part in _SENTENCE_SPLIT.split(plain) if part.strip()]


def classify_policy(text: str | None) -> PolicyVerdict:
    if not text or not text.strip():
        return PolicyVerdict(AutomationVerdict.UNKNOWN, ())
    sentences = _sentences(text)
    forbidden: list[str] = []
    allowed: list[str] = []

    for sentence in sentences:
        lowered = sentence.lower()
        if any(
            phrase in lowered
            for phrase in (
                "not prohibited",
                "not forbidden",
                "do not prohibit",
                "does not prohibit",
                "do not forbid",
            )
        ):
            allowed.append(f"permission: {sentence}")
            continue
        if any(pattern.search(lowered) for pattern in _FORBID_PATTERNS):
            forbidden.append(f"prohibition: {sentence}")
            continue
        if any(pattern.search(lowered) for pattern in _ALLOW_PATTERNS):
            allowed.append(f"permission: {sentence}")

    if forbidden:
        return PolicyVerdict(AutomationVerdict.FORBIDDEN, tuple(forbidden + allowed))
    if allowed:
        return PolicyVerdict(AutomationVerdict.ALLOWED, tuple(allowed))
    return PolicyVerdict(AutomationVerdict.UNKNOWN, ())


def classify_third_party_ai(text: str | None) -> str:
    if not text:
        return "unknown"
    lowered = html.unescape(_TAG.sub(" ", text)).lower()
    if re.search(
        r"\b(?:no|not\s+permitted|prohibited|forbidden)\b[^.]{0,60}\b(?:ai|llm|third[- ]party)\b",
        lowered,
    ) or re.search(
        r"\b(?:ai|llm|third[- ]party)\b[^.]{0,60}\b(?:not\s+permitted|prohibited|forbidden)\b",
        lowered,
    ):
        return "forbidden"
    if re.search(r"\b(?:ai|llm)\b[^.]{0,60}\b(?:permitted|allowed)\b", lowered):
        return "allowed"
    return "unknown"
