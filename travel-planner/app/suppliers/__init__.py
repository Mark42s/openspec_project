"""供应商注册工厂:有真实凭证时用真实源,无凭证时仅 mock 兜底。"""

from __future__ import annotations

import os

from app.suppliers.base import QueryError, SupplierAdapter
from app.suppliers.mock import MockAdapter
from app.suppliers.tuniu import TuniuAdapter


def resolve_suppliers(enable_tuniu: bool | None = None) -> list[SupplierAdapter]:
    """返回启用的适配器列表。

    enable_tuniu 未指定时按是否有 TUNIU_API_KEY 自动决定。真实源可用时
    不混入 mock(避免假车次污染真实结果);只有全部真实源不可用时才回落 mock。
    """
    if enable_tuniu is None:
        enable_tuniu = bool(os.getenv("TUNIU_API_KEY", "").strip())
    if enable_tuniu:
        try:
            return [TuniuAdapter()]
        except QueryError:
            pass
    return [MockAdapter()]
