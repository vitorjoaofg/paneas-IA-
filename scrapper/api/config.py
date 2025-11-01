from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    env: Literal["dev", "prod"] = Field(default="dev", description="Execution environment flag.")
    base_url: AnyHttpUrl = Field(
        default="https://esaj.tjsp.jus.br/cpopg/open.do",
        description="TJSP consulta pública URL.",
    )
    tools_manifest_path: Path = Field(
        default=Path(__file__).with_name("tools_manifest.json"),
        description="Path to the tools manifest file.",
    )
    playwright_browser: Literal["chromium", "firefox", "webkit"] = Field(
        default="chromium",
        description="Browser engine used by Playwright.",
    )
    headless: bool = Field(
        default=True,
        description="Run the Playwright browser in headless mode.",
    )
    navigation_timeout_ms: int = Field(
        default=30000,
        description="Default navigation timeout for Playwright operations.",
    )
    slow_mo_ms: int | None = Field(
        default=None,
        description="Optional Playwright slow motion delay (useful for debugging).",
    )

    class Config:
        env_prefix = "SCRAPPER_"
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()

