"""供应商注册工厂:按环境变量决定启用哪些源(无凭证时仅 mock)。"""

from __future__ import annotations

import os

from app.suppliers.base import QueryError, SupplierAdapter
from app.suppliers.mock import MockAdapter
from app.suppliers.tuniu import TuniuAdapter


def resolve_suppliers(enable_tuniu: bool | None = None) -> list[SupplierAdapter]:
    """返回启用的适配器列表。

    enable_tuniu 未指定时读环境变量 `TUNIU_ENABLED`(1/true 开启)。
    途牛实例化失败(缺凭证)不影响 mock 兜底。
    """
    suppliers: list[SupplierAdapter] = [MockAdapter()]
    if enable_tuniu is None:
        enable_tuniu = os_env_flag("TUNIU_ENABLED", False)
    if enable_tuniu:
        try:
            suppliers.append(TuniuAdapter())
        except QueryError:
            pass
    return suppliers


def os_env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
