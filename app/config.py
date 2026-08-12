from __future__ import annotations

import os
from dataclasses import dataclass

_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "Team Notes API"
    database_url: str = "sqlite+pysqlite:///./team_notes.db"
    auto_create_db: bool = True

    @classmethod
    def from_env(cls) -> Settings:
        defaults = cls()
        return cls(
            app_name=os.getenv("APP_NAME", defaults.app_name),
            database_url=os.getenv("DATABASE_URL", defaults.database_url),
            auto_create_db=os.getenv("AUTO_CREATE_DB", "true").lower() in _TRUE_VALUES,
        )
