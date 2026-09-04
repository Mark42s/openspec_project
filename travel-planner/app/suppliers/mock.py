"""确定性 mock 数据源(spec: 无凭证时以确定性数据源兜底)。

同输入必返回相同结果(去程价随旅行日期做确定性波动,但同一天两次查询结果一致),
便于测试与演示。真实凭证就位后可整体替换。
"""

from __future__ import annotations

import hashlib
from typing import Protocol

from app.models import HotelQuote, TransportQuote
from app.suppliers.base import SupplierAdapter


class _Q(Protocol):
    origin: str
    destination: str
    travel_date: object
    check_in: object
    city: str
    nights: int
    travelers: int


def _seed(*parts: object) -> int:
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:8], 16)


# 目的地 → 常见高铁运营商的稳定映射表(仅演示用)
_TRAIN_OPERATORS = {
    "西安": ["G1920", "G360", "G872"],
    "北京": ["G8", "G6", "G24"],
    "杭州": ["G7303", "G7501", "G7351"],
    "成都": ["G3286", "G2193", "G2831"],
    "广州": ["G1301", "G817", "G1007"],
}


def _ops(dest: str) -> list[str]:
    return _TRAIN_OPERATORS.get(dest, ["G1000", "G1001", "G1002"])


class MockAdapter(SupplierAdapter):
    name = "mock"

    def search_transport(self, query) -> list[TransportQuote]:
        dest = query.destination
        ops = _ops(dest)
        base = _seed(query.origin, dest, query.travel_date)
        day = _seed("day", query.travel_date)  # 随出发日波动,同一天稳定
        quotes = [
            TransportQuote(
                supplier="mock",
                mode="train",
                from_city=query.origin,
                to_city=dest,
                operator=ops[base % len(ops)],
                departure_time=f"{7 + (base % 9):02d}:0{base % 9}",
                arrival_time=f"{12 + (base % 8):02d}:{10 + day % 40:02d}",
                price=300.0 + (day % 300),  # 二等座,随日波动
                travel_class="二等座",
            ),
            TransportQuote(
                supplier="mock",
                mode="flight",
                from_city=query.origin,
                to_city=dest,
                operator=f"MU{(1000 + base % 9000)}",
                departure_time=f"{8 + (base % 11):02d}:15",
                arrival_time=f"{10 + (base % 10):02d}:50",
                price=480.0 + (base % 600),  # 经济舱
                travel_class="经济舱",
            ),
        ]
        return quotes

    def search_hotel(self, query) -> list[HotelQuote]:
        s = _seed(query.city, query.check_in, query.nights)
        tiers = [
            ("如家酒店·西安钟楼店", "标准大床房", 220.0, 4.2),
            ("全季酒店·西安北大街店", "高级双床房", 380.0, 4.6),
            ("西安威斯汀大酒店", "豪华双床房", 880.0, 4.8),
        ]
        quotes = []
        for name, room, price, rating in tiers:
            p = price + (s % 60)
            quotes.append(
                HotelQuote(
                    supplier="mock",
                    city=query.city,
                    name=name.replace("西安", query.city),
                    room_type=room,
                    price_per_night=p,
                    is_refundable=(s % 2 == 0),
                    rating=rating,
                )
            )
        return quotes
