from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


class ConfigError(RuntimeError):
    pass


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_runtime_config(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path.name} must contain a JSON object")
    return data


def _get_value(name: str, default: object, runtime_config: dict[str, object]) -> object:
    if name in os.environ:
        return os.environ[name]
    if name in runtime_config:
        return runtime_config[name]
    return default


def _int_env(
    name: str,
    default: int,
    runtime_config: dict[str, object],
    min_value: int | None = None,
) -> int:
    value = int(_get_value(name, default, runtime_config))
    if min_value is not None and value < min_value:
        raise ConfigError(f"{name} must be >= {min_value}")
    return value


def _float_env(
    name: str,
    default: float,
    runtime_config: dict[str, object],
    min_value: float | None = None,
) -> float:
    value = float(_get_value(name, default, runtime_config))
    if min_value is not None and value < min_value:
        raise ConfigError(f"{name} must be >= {min_value}")
    return value


@dataclass(frozen=True)
class Settings:
    target_url: str
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_max_retries: int
    llm_retry_seconds: float
    initial_users: int
    min_users: int
    max_users: int
    step_users: int
    spawn_rate: float
    interval_seconds: int
    max_intervals: int
    report_every_seconds: int
    latency_threshold_ms: float
    error_rate_threshold: float
    cpu_threshold_percent: float
    stable_intervals: int
    knee_latency_multiplier: float
    report_dir: Path
    runtime_config_path: Path

    @classmethod
    def from_env(cls, root: Path) -> "Settings":
        load_dotenv(root / ".env")
        runtime_config_path = root / "alg.settings.json"
        runtime_config = load_runtime_config(runtime_config_path)

        llm_api_key = os.getenv("ALG_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        llm_model = os.getenv("ALG_LLM_MODEL", "").strip()
        llm_base_url = os.getenv("ALG_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")

        if not llm_api_key:
            raise ConfigError("ALG_LLM_API_KEY or OPENAI_API_KEY is required in .env")
        if not llm_model:
            raise ConfigError("ALG_LLM_MODEL is required in .env")

        min_users = _int_env("ALG_MIN_USERS", 1, runtime_config, min_value=1)
        max_users = _int_env("ALG_MAX_USERS", 1000, runtime_config, min_value=min_users)
        initial_users = _int_env("ALG_INITIAL_USERS", 50, runtime_config, min_value=min_users)
        if initial_users > max_users:
            raise ConfigError("ALG_INITIAL_USERS must be <= ALG_MAX_USERS")

        return cls(
            target_url=(os.getenv("ALG_TARGET_URL") or "http://127.0.0.1:8000").rstrip("/"),
            llm_api_key=llm_api_key,
            llm_base_url=llm_base_url,
            llm_model=llm_model,
            llm_max_retries=_int_env("ALG_LLM_MAX_RETRIES", 3, runtime_config, min_value=0),
            llm_retry_seconds=_float_env("ALG_LLM_RETRY_SECONDS", 10.0, runtime_config, min_value=0.1),
            initial_users=initial_users,
            min_users=min_users,
            max_users=max_users,
            step_users=_int_env("ALG_STEP_USERS", 50, runtime_config, min_value=1),
            spawn_rate=_float_env("ALG_SPAWN_RATE", 10.0, runtime_config, min_value=0.1),
            interval_seconds=_int_env("ALG_INTERVAL_SECONDS", 30, runtime_config, min_value=1),
            max_intervals=_int_env("ALG_MAX_INTERVALS", 20, runtime_config, min_value=1),
            report_every_seconds=_int_env("ALG_REPORT_EVERY_SECONDS", 60, runtime_config, min_value=1),
            latency_threshold_ms=_float_env("ALG_LATENCY_THRESHOLD_MS", 2000.0, runtime_config, min_value=1.0),
            error_rate_threshold=_float_env("ALG_ERROR_RATE_THRESHOLD", 0.02, runtime_config, min_value=0.0),
            cpu_threshold_percent=_float_env("ALG_CPU_THRESHOLD_PERCENT", 80.0, runtime_config, min_value=1.0),
            stable_intervals=_int_env("ALG_STABLE_INTERVALS", 2, runtime_config, min_value=1),
            knee_latency_multiplier=_float_env(
                "ALG_KNEE_LATENCY_MULTIPLIER", 2.5, runtime_config, min_value=1.0
            ),
            report_dir=root / "reports",
            runtime_config_path=runtime_config_path,
        )

    def thresholds(self) -> dict[str, float | int]:
        return {
            "latency_threshold_ms": self.latency_threshold_ms,
            "error_rate_threshold": self.error_rate_threshold,
            "cpu_threshold_percent": self.cpu_threshold_percent,
            "stable_intervals": self.stable_intervals,
            "knee_latency_multiplier": self.knee_latency_multiplier,
        }
