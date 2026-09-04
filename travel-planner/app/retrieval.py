"""检索聚合:并发查源、按去重键合并多源、规则初筛 top-N(design D1/D4)。

比价是确定性并发代码,不经大模型——见 design.md D1。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from app.models import HotelQuote, ResultBundle, TransportQuote, TripRequest
from app.suppliers.base import QueryError, SupplierAdapter

MAX_TRANSPORT = 4
MAX_HOTELS = 4


class _TransportQuery:
    def __init__(self, origin: str, destination: str, travel_date: date, travelers: int) -> None:
        self.origin = origin
        self.destination = destination
        self.travel_date = travel_date
        self.travelers = travelers


class _HotelQuery:
    def __init__(self, city: str, check_in: date, nights: int, travelers: int) -> None:
        self.city = city
        self.check_in = check_in
        self.nights = nights
        self.travelers = travelers


def search_all(request: TripRequest, suppliers: list[SupplierAdapter]) -> ResultBundle:
    """对主目的地并发检索交通与酒店,去重并初筛。"""
    destination = request.destinations[0] if request.destinations else ""
    origin = request.origin or ""
    start = request.start_date or date.today()
    days = request.days or 1
    travelers = max(1, request.adults + request.elders + request.children)

    transport_q = _TransportQuery(origin, destination, start, travelers)
    hotel_q = _HotelQuery(destination, start, days, travelers)

    all_transport: list[TransportQuote] = []
    all_hotels: list[HotelQuote] = []
    errors: list[str] = []

    jobs: list[tuple[SupplierAdapter, str]] = [
        (s, "transport") for s in suppliers
    ] + [(s, "hotel") for s in suppliers]

    with ThreadPoolExecutor(max_workers=max(4, len(jobs))) as pool:
        futures = {
            pool.submit(_call, supplier, kind, transport_q, hotel_q): (supplier.name, kind)
            for supplier, kind in jobs
        }
        for fut in as_completed(futures):
            name, kind = futures[fut]
            try:
                result = fut.result()
            except QueryError as exc:
                errors.append(f"{name}.{kind}: {exc}")
                continue
            if kind == "transport":
                all_transport.extend(result)
            else:
                all_hotels.extend(result)

    transport = _dedup_transport(all_transport)
    hotels = _dedup_hotels(all_hotels)

    return ResultBundle(
        transport=transport[:MAX_TRANSPORT],
        hotels=hotels[:MAX_HOTELS],
        is_mock=all(s.name == "mock" for s in suppliers),
        sources=sorted({s.name for s in suppliers}),
        supplier_errors=errors,
    )


def _call(supplier, kind, transport_q, hotel_q):
    if kind == "transport":
        return supplier.search_transport(transport_q)
    return supplier.search_hotel(hotel_q)


def _dedup_transport(quotes: list[TransportQuote]) -> list[TransportQuote]:
    """同车次/航班保留最低价,并合并来源到 supplier 字段。"""
    best: dict[str, TransportQuote] = {}
    for q in sorted(quotes, key=lambda x: x.price):
        key = q.dedup_key
        if key not in best:
            best[key] = q
        else:
            best[key].supplier = f"{best[key].supplier}+{q.supplier}"
    return sorted(best.values(), key=lambda x: x.price)


def _dedup_hotels(quotes: list[HotelQuote]) -> list[HotelQuote]:
    """同酒店同房型保留最低价。"""
    best: dict[str, HotelQuote] = {}
    for q in sorted(quotes, key=lambda x: (x.price_per_night, -(x.rating or 0))):
        key = q.dedup_key
        if key not in best:
            best[key] = q
        else:
            best[key].supplier = f"{best[key].supplier}+{q.supplier}"
    return sorted(best.values(), key=lambda x: (x.price_per_night, -(x.rating or 0)))
