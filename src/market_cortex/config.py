"""Local configuration. Provider tokens and the database password are env-only."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    data_root: Path
    owner_timezone: str
    base_currency: str
    cloud_model_allowed: bool
    owner_configured: bool

    @classmethod
    def load(cls, root: Path | None = None) -> "Settings":
        project = root or Path(__file__).resolve().parents[2]
        owner_path = project / "config" / "owner.yaml"
        owner = yaml.safe_load(owner_path.read_text(encoding="utf-8")) if owner_path.exists() else {}
        if not isinstance(owner, dict):
            raise ValueError("owner.yaml must contain a mapping")
        timezone = owner.get("timezone", "Asia/Kolkata")
        ZoneInfo(timezone)
        currency = owner.get("base_currency", "INR")
        if not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha():
            raise ValueError("base_currency must be a three-letter code")
        privacy = owner.get("ai_privacy") or {}
        if not isinstance(privacy, dict):
            raise ValueError("ai_privacy must be a mapping")
        raw_data_root = os.environ.get("MARKET_CORTEX_DATA_ROOT")
        data_root = Path(raw_data_root).expanduser().resolve() if raw_data_root else (project / "data").resolve()
        return cls(
            database_url=os.environ.get("MARKET_CORTEX_DATABASE_URL"),
            data_root=data_root,
            owner_timezone=timezone,
            base_currency=currency.upper(),
            cloud_model_allowed=privacy.get("cloud_model_allowed") is True,
            owner_configured=owner_path.exists(),
        )

    def safe_summary(self) -> dict[str, object]:
        """Whitelist only; never serialize the dataclass because it contains a DSN."""
        return {"database_configured": bool(self.database_url), "owner_configured": self.owner_configured,
                "timezone": self.owner_timezone, "base_currency": self.base_currency,
                "cloud_model_allowed": self.cloud_model_allowed}
