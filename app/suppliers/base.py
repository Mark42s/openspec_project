"""供应商适配层抽象(design D2:统一接口 + mock 兜底)。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Protocol

from app.models import HotelQuote, TransportQuote


class QueryError(Exception):
    """供应商查询失败(超时/无凭证/未接入)。"""


class TransportQuery(Protocol):
    origin: str
    destination: str
    travel_date: date
    travelers: int


class HotelQuery(Protocol):
    city: str
    check_in: date
    nights: int
    travelers: int


class SupplierAdapter(ABC):
    """国内供应商适配器统一接口。真实源与 mock 都实现它。"""

    name: str = "base"

    @abstractmethod
    def search_transport(self, query: TransportQuery) -> list[TransportQuote]:
        """查询城市间交通。失败抛 QueryError,由上层回落 mock。"""

    @abstractmethod
    def search_hotel(self, query: HotelQuery) -> list[HotelQuote]:
        """查询城市酒店。失败抛 QueryError。"""
