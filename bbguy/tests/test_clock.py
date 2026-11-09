from __future__ import annotations

import time

from bbguy.clock import Clock, boot_id, monotonic_ns, safe_env


def test_monotonic_advances_across_sleep() -> None:
    before = monotonic_ns()
    time.sleep(0.02)
    after = monotonic_ns()
    assert after > before
    assert after - before >= 10_000_000


def test_boot_id_is_stable_within_a_boot() -> None:
    first = boot_id()
    second = boot_id()
    assert first
    assert first == second


def test_clock_read() -> None:
    clock = Clock.read()
    assert clock.now_ns > 0
    assert clock.boot_id
    assert clock.elapsed_ns(clock.now_ns - 10) == 10
    assert clock.lease_deadline_ns(45) == clock.now_ns + 45_000_000_000


def test_safe_env_drops_secrets(monkeypatch) -> None:
    monkeypatch.setenv("BBGUY_SECRET_TOKEN", "do-not-leak")
    monkeypatch.setenv("OPENAI_API_KEY", "do-not-leak")
    env = safe_env()
    assert "BBGUY_SECRET_TOKEN" not in env
    assert "OPENAI_API_KEY" not in env
    assert "PATH" in env
