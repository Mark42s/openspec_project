"""途牛 MCP 开放平台适配器:真实交通/酒店检索(JSON-RPC 2.0 over MCP)。

只做检索(火车/机票/酒店),不做下单(本期范围)。协议:
POST https://openapi.tuniu.cn/mcp/{server},认证头 apiKey,method tools/call,
结果在 result.content[0].text(JSON 字符串)。无 TUNIU_API_KEY 时实例化抛
QueryError,由 resolve_suppliers 回落 mock。
"""

from __future__ import annotations

import json
import os
from datetime import timedelta

import httpx

from app.models import HotelQuote, TransportQuote
from app.suppliers.base import QueryError, SupplierAdapter

_TUNIU_BASE = "https://openapi.tuniu.cn/mcp"
_ACCEPT = "application/json, text/event-stream"
_TIMEOUT = 30.0

# 火车座位类型 → 途牛 price 字段(取第一个可用的作为该车次参考报价)
_TRAIN_SEATS = [
    ("二等座", "edzPrice"),
    ("一等座", "ydzPrice"),
    ("商务座", "swzPrice"),
    ("无座", "wzPrice"),
]


def _key() -> str:
    return os.getenv("TUNIU_API_KEY", "").strip()


def _num(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _hhmm(value: str) -> str:
    """'2026-09-29 07:46' → '07:46'。"""
    return value.split(" ")[-1][:5] if value else ""


def _rpc(server: str, tool: str, arguments: dict) -> dict:
    """调用途牛 MCP 工具,返回解析后的业务数据(JSON 对象)。失败抛 QueryError。"""
    base = os.getenv("TUNIU_BASE_URL", _TUNIU_BASE).rstrip("/")
    try:
        resp = httpx.post(
            f"{base}/{server}",
            headers={"Content-Type": "application/json", "Accept": _ACCEPT, "apiKey": _key()},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": tool, "arguments": arguments},
            },
            timeout=_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        raise QueryError(f"途牛 {server} 网络错误: {exc}") from exc
    if resp.status_code != 200:
        raise QueryError(f"途牛 {server} HTTP {resp.status_code}: {resp.text[:200]}")
    text = resp.text.strip()
    if text.startswith("event:"):
        text = text.split("data:", 1)[1].strip()
    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise QueryError(f"途牛 {server} 返回非 JSON: {text[:200]}") from exc
    err = payload.get("error")
    if err:
        msg = err.get("message") if isinstance(err, dict) else err
        raise QueryError(f"途牛 {server} 错误: {msg}")
    result = payload.get("result") or {}
    content = result.get("content") or []
    if not content:
        return result
    raw = content[0].get("text", "")
    try:
        return json.loads(raw)
    except ValueError:
        return {"_raw": raw}


class TuniuAdapter(SupplierAdapter):
    name = "tuniu"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or _key()
        if not self.api_key:
            raise QueryError("TUNIU_API_KEY 未配置,回落 mock")

    def search_transport(self, query) -> list[TransportQuote]:
        date_s = query.travel_date.isoformat()
        quotes: list[TransportQuote] = []
        try:
            train = _rpc("train", "searchLowestPriceTrain", {
                "departureCityName": query.origin,
                "arrivalCityName": query.destination,
                "departureDate": date_s,
                "searchType": "5",
            })
            for t in train.get("data") or []:
                q = self._train_quote(query, t)
                if q:
                    quotes.append(q)
        except QueryError:
            pass  # 火车失败不阻塞机票
        try:
            flight = _rpc("flight", "searchLowestPriceFlight", {
                "departureCityName": query.origin,
                "arrivalCityName": query.destination,
                "departureDate": date_s,
            })
            for f in flight.get("data") or []:
                q = self._flight_quote(query, f)
                if q:
                    quotes.append(q)
        except QueryError:
            pass
        if not quotes:
            raise QueryError("途牛交通查询无结果")
        return quotes

    def search_hotel(self, query) -> list[HotelQuote]:
        check_in = query.check_in.isoformat()
        check_out = (query.check_in + timedelta(days=max(query.nights, 1))).isoformat()
        data = _rpc("hotel", "tuniuHotelSearch", {
            "cityName": query.city,
            "checkIn": check_in,
            "checkOut": check_out,
            "adultNum": max(1, query.travelers),
        })
        quotes: list[HotelQuote] = []
        for h in data.get("hotels") or []:
            refund = h.get("refund") or ""
            quotes.append(
                HotelQuote(
                    supplier="tuniu",
                    city=query.city,
                    name=h.get("hotelName") or "未命名酒店",
                    room_type=h.get("roomName") or "标准房",
                    price_per_night=_num(h.get("lowestPrice")) or 0.0,
                    is_refundable=refund not in ("", "不可取消"),
                    rating=_num(h.get("commentScore")),
                )
            )
        if not quotes:
            raise QueryError("途牛酒店查询无结果")
        return quotes

    def _train_quote(self, query, t: dict) -> TransportQuote | None:
        price_map = t.get("price") or {}
        travel_class = ""
        price: float | None = None
        for cls, field in _TRAIN_SEATS:
            p = _num(price_map.get(field))
            if p is not None:
                travel_class, price = cls, p
                break
        if price is None:
            return None
        return TransportQuote(
            supplier="tuniu",
            mode="train",
            from_city=query.origin,
            to_city=query.destination,
            operator=t.get("trainNum", ""),
            departure_station=t.get("departStationName", ""),
            arrival_station=t.get("destStationName", ""),
            departure_time=_hhmm(t.get("departureTime", "")),
            arrival_time=_hhmm(t.get("arrivalTime", "")),
            price=price,
            travel_class=travel_class,
        )

    def _flight_quote(self, query, f: dict) -> TransportQuote | None:
        base = _num(f.get("basePrice"))
        if base is None:
            return None
        dep = f"{f.get('departureAirport', '')}{f.get('departureTerminal', '')}".strip()
        arr = f"{f.get('arrivalAirport', '')}{f.get('arrivalTerminal', '')}".strip()
        return TransportQuote(
            supplier="tuniu",
            mode="flight",
            from_city=query.origin,
            to_city=query.destination,
            operator=f.get("flightNumber", ""),
            departure_station=dep,
            arrival_station=arr,
            departure_time=_hhmm(f.get("departureTime", "")),
            arrival_time=_hhmm(f.get("arrivalTime", "")),
            price=base + (_num(f.get("totalTax")) or 0.0),
            travel_class=f.get("cabinClass") or "经济舱",
        )
