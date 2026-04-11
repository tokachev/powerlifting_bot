from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from pwrbot.config import Settings, load_yaml_config


def test_load_yaml_config_from_repo(tmp_path: Path) -> None:
    yaml_path = tmp_path / "settings.yaml"
    yaml_path.write_text(
        dedent(
            """
            windows: {short_days: 7, long_days: 28}
            thresholds:
              hard_set: {min_rpe: 7.5, intensity_fraction: 0.8}
              balance:
                push_pull_target: 1.0
                squat_hinge_target: 1.0
                tolerance: 0.3
                min_hard_sets_for_flag: 5
              recovery:
                max_hard_sets_7d: {squat: 12, hinge: 10, push: 16, pull: 18}
                tonnage_spike_ratio: 1.5
              warmup:
                max_fraction_of_working_weight: 0.6
            llm:
              model: gemma3:4b
              base_url: http://localhost:11434
              timeout_s: 60
              max_retries: 1
            """
        ).strip(),
        encoding="utf-8",
    )
    cfg = load_yaml_config(yaml_path)
    assert cfg.windows.short_days == 7
    assert cfg.thresholds.hard_set.min_rpe == 7.5
    assert cfg.thresholds.recovery.max_hard_sets_7d["squat"] == 12
    assert cfg.llm.model == "gemma3:4b"
    # frozen
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        cfg.windows.short_days = 9  # type: ignore[misc]


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_TOKEN", "test-token")
    monkeypatch.setenv("OLLAMA_MODEL", "gemma3:12b")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.telegram_token == "test-token"
    assert s.ollama_model == "gemma3:12b"
