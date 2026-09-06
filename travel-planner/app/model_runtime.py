"""运行期大模型配置(内存 + 可选持久化)。

页面填写的 Anthropic API Key / Base URL / 模型即时生效(无需重启)。
优先级:页面设置 > 持久化文件 > .env 环境变量 > 内置默认。
持久化文件默认 data/model_config.json(data/ 已被 .gitignore);可用 MODEL_CONFIG_PATH 覆盖。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_PARSE_MODEL = "claude-haiku-4-5"
DEFAULT_PLAN_MODEL = "claude-sonnet-5"
OPENAI_DEFAULT_MODEL = "deepseek-chat"

_state: dict = {
    "api_key": None,
    "base_url": None,
    "provider": None,
    "parse_model": None,
    "plan_model": None,
}
_loaded = False


def _path() -> Path:
    p = os.getenv("MODEL_CONFIG_PATH")
    if p:
        return Path(p)
    db = os.getenv("PLANNER_DB_PATH", "data/travel.db")
    return Path(db).parent / "model_config.json"


def _env_defaults() -> dict:
    return {
        "api_key": os.getenv("ANTHROPIC_API_KEY", "").strip() or None,
        "base_url": os.getenv("ANTHROPIC_BASE_URL", "").strip() or None,
        "provider": os.getenv("PLANNER_PROVIDER", "").strip() or None,
        "parse_model": os.getenv("PLANNER_PARSE_MODEL", "").strip() or None,
        "plan_model": os.getenv("PLANNER_PLAN_MODEL", "").strip() or None,
    }


def _load_file() -> dict:
    p = _path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _ensure_loaded() -> None:
    global _loaded
    if _loaded:
        return
    base = _env_defaults()
    for k, v in _load_file().items():
        if v:
            base[k] = v
    _state.update(base)
    _loaded = True


def reset() -> None:
    """回到 .env 环境变量默认,忽略持久化文件(供测试隔离)。"""
    global _loaded
    _state.update(_env_defaults())
    _loaded = True


def configured() -> bool:
    return bool(api_key())


def api_key() -> str | None:
    _ensure_loaded()
    return _state["api_key"]


def base_url() -> str | None:
    _ensure_loaded()
    return _state["base_url"]


def provider() -> str:
    _ensure_loaded()
    return _state["provider"] or "anthropic"


def parse_model() -> str:
    _ensure_loaded()
    if _state["parse_model"]:
        return _state["parse_model"]
    return OPENAI_DEFAULT_MODEL if provider() == "openai" else DEFAULT_PARSE_MODEL


def plan_model() -> str:
    _ensure_loaded()
    if _state["plan_model"]:
        return _state["plan_model"]
    return OPENAI_DEFAULT_MODEL if provider() == "openai" else DEFAULT_PLAN_MODEL


def set_config(
    api_key: str | None = None,
    base_url: str | None = None,
    provider: str | None = None,
    parse_model: str | None = None,
    plan_model: str | None = None,
    persist: bool = True,
) -> None:
    """写入配置;字段为 None 表示不清动,空字符串表示清除为默认。"""
    _ensure_loaded()
    for name, value in (
        ("api_key", api_key),
        ("base_url", base_url),
        ("provider", provider),
        ("parse_model", parse_model),
        ("plan_model", plan_model),
    ):
        if value is None:
            continue
        _state[name] = value.strip() or None
    if persist:
        _persist()


def _persist() -> None:
    p = _path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps({k: v for k, v in _state.items() if v}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass  # 持久化失败不阻塞本次会话使用


def public_info() -> dict:
    _ensure_loaded()
    key = _state["api_key"]
    return {
        "configured": bool(key),
        "api_key_masked": _mask(key),
        "base_url": _state["base_url"] or None,
        "provider": provider(),
        "parse_model": parse_model(),
        "plan_model": plan_model(),
    }


def _mask(key: str | None) -> str | None:
    if not key:
        return None
    if len(key) <= 8:
        return "•" * min(len(key), 8)
    return f"{key[:4]}…{key[-4:]}"
