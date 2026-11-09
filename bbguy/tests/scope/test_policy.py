from __future__ import annotations

import pytest

from bbguy.scope.models import AutomationVerdict
from bbguy.scope.policy import classify_policy, classify_third_party_ai


@pytest.mark.parametrize(
    "text",
    [
        "Automated scanning is allowed.",
        "Automated testing is permitted.",
        "Scanners are welcome.",
        "You may use automated tools.",
        "Automation is permitted on production.",
        "Automated scanning is not prohibited.",
        "We do not prohibit automated scanning.",
        "<p>Automated scanning is <b>allowed</b>.</p>",
    ],
)
def test_allowed_policies(text: str) -> None:
    verdict = classify_policy(text)
    assert verdict.verdict is AutomationVerdict.ALLOWED
    assert verdict.evidence


@pytest.mark.parametrize(
    "text",
    [
        "Automated scanning is not allowed.",
        "Automated scanning is prohibited.",
        "Automated testing is forbidden.",
        "Do not use automated scanners.",
        "No automated scanning.",
        "Manual testing only.",
        "Manual testing only on staging.",
    ],
)
def test_forbidden_policies(text: str) -> None:
    verdict = classify_policy(text)
    assert verdict.verdict is AutomationVerdict.FORBIDDEN


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   \n",
        "Please follow responsible disclosure.",
        "Use the report form for vulnerabilities.",
    ],
)
def test_silent_policy_is_unknown(text: str) -> None:
    verdict = classify_policy(text)
    assert verdict.verdict is AutomationVerdict.UNKNOWN
    assert verdict.evidence == ()


def test_prohibition_wins_over_permission() -> None:
    verdict = classify_policy(
        "Automated scanning is allowed on production, but manual testing only on staging."
    )
    assert verdict.verdict is AutomationVerdict.FORBIDDEN
    assert any("manual testing only" in item.lower() for item in verdict.evidence)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Third-party AI tools are not permitted.", "forbidden"),
        ("AI processing is prohibited.", "forbidden"),
        ("Use of AI is allowed.", "allowed"),
        ("Nothing about models here.", "unknown"),
        (None, "unknown"),
    ],
)
def test_third_party_ai_policy(text: str | None, expected: str) -> None:
    assert classify_third_party_ai(text) == expected
