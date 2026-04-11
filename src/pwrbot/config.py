"""Loads YAML thresholds + env settings into a frozen pydantic Settings model."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class HardSetThresholds(BaseModel):
    model_config = ConfigDict(frozen=True)
    min_rpe: float
    intensity_fraction: float


class BalanceThresholds(BaseModel):
    model_config = ConfigDict(frozen=True)
    push_pull_target: float
    squat_hinge_target: float
    tolerance: float
    min_hard_sets_for_flag: int


class RecoveryThresholds(BaseModel):
    model_config = ConfigDict(frozen=True)
    max_hard_sets_7d: dict[str, int]
    tonnage_spike_ratio: float


class WarmupThresholds(BaseModel):
    model_config = ConfigDict(frozen=True)
    max_fraction_of_working_weight: float


class Thresholds(BaseModel):
    model_config = ConfigDict(frozen=True)
    hard_set: HardSetThresholds
    balance: BalanceThresholds
    recovery: RecoveryThresholds
    warmup: WarmupThresholds


class Windows(BaseModel):
    model_config = ConfigDict(frozen=True)
    short_days: int = 7
    long_days: int = 28


class LLMConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    model: str = "gemma4:e4b"
    base_url: str = "http://localhost:11434"
    timeout_s: int = 60
    max_retries: int = 1


class YamlConfig(BaseModel):
    """Typed view over config/settings.yaml."""

    model_config = ConfigDict(frozen=True)
    windows: Windows
    thresholds: Thresholds
    llm: LLMConfig


class Settings(BaseSettings):
    """Env-driven settings (token, paths) + loaded YAML config."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    telegram_token: str = Field(..., alias="TELEGRAM_TOKEN")
    ollama_url: str = Field("http://localhost:11434", alias="OLLAMA_URL")
    ollama_model: str = Field("gemma4:e4b", alias="OLLAMA_MODEL")
    ollama_timeout_s: int = Field(60, alias="OLLAMA_TIMEOUT_S")
    db_path: Path = Field(Path("./data/pwrbot.db"), alias="DB_PATH")
    config_path: Path = Field(Path("./config/settings.yaml"), alias="CONFIG_PATH")
    exercises_path: Path = Field(Path("./config/exercises.yaml"), alias="EXERCISES_PATH")
    prompts_dir: Path = Field(Path("./prompts"), alias="PROMPTS_DIR")
    log_level: str = Field("INFO", alias="LOG_LEVEL")


def load_yaml_config(path: Path) -> YamlConfig:
    """Load and validate settings.yaml. Raises on malformed config."""
    with path.open("r", encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}
    return YamlConfig.model_validate(data)


def load_settings(env_file: str | None = ".env") -> tuple[Settings, YamlConfig]:
    """One-shot loader used by __main__ and tests."""
    settings = Settings(_env_file=env_file) if env_file else Settings()  # type: ignore[call-arg]
    yaml_cfg = load_yaml_config(settings.config_path)
    return settings, yaml_cfg
