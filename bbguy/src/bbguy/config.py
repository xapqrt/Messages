"""Filesystem layout and limits.

BBGUY_HOME overrides the root so tests and the job runner never touch the
owner's real state. One owner, one home: there is no multi-tenant mode.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    home: Path
    db_path: Path
    scope_dir: Path
    evidence_dir: Path
    bundles_dir: Path
    log_dir: Path
    max_evidence_gb: float = 14.0
    disk_floor_gb: float = 2.5

    def ensure_dirs(self) -> Settings:
        for path in (self.home, self.scope_dir, self.evidence_dir, self.bundles_dir, self.log_dir):
            path.mkdir(parents=True, exist_ok=True)
            try:
                path.chmod(0o700)
            except OSError:
                pass
        return self


def load_settings(home: str | os.PathLike[str] | None = None) -> Settings:
    root = Path(home or os.environ.get("BBGUY_HOME") or Path.home() / ".bbguy").expanduser()
    root = root.resolve()
    return Settings(
        home=root,
        db_path=root / "state.db",
        scope_dir=root / "scope",
        evidence_dir=root / "evidence",
        bundles_dir=root / "bundles",
        log_dir=root / "logs",
    )


def disk_free_gb(path: str | os.PathLike[str]) -> float:
    probe = Path(path)
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return shutil.disk_usage(probe).free / (1024**3)


def assert_disk_floor(settings: Settings) -> None:
    free = disk_free_gb(settings.home)
    if free < settings.disk_floor_gb:
        raise ConfigError(
            f"free disk {free:.2f} GiB is below the {settings.disk_floor_gb:.2f} GiB floor"
        )
