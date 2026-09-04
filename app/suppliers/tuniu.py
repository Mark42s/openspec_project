"""途牛适配器占位(design D2 / open question:真实接入方式待定)。

本期未接入真实途牛。凭证缺失或调用一律抛 QueryError,由上层回落 mock;
真实接入(官方 MCP 开放平台或分销 API)作为后续独立 OpenSpec change 实现。
"""

from __future__ import annotations

import os

from app.suppliers.base import QueryError, SupplierAdapter


class TuniuAdapter(SupplierAdapter):
    name = "tuniu"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("TUNIU_API_KEY")
        if not self.api_key:
            raise QueryError("TUNIU_API_KEY 未配置,回落 mock")

    def search_transport(self, query) -> list:
        raise QueryError("途牛交通查询尚未接入(占位),回落 mock")

    def search_hotel(self, query) -> list:
        raise QueryError("途牛酒店查询尚未接入(占位),回落 mock")
