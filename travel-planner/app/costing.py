"""确定性费用计算(spec: 确定性费用计算 / design D3)。

规则常量计算,不经模型心算;金额为估算,非结算依据。
"""

from __future__ import annotations

from app.models import CostBreakdown, HotelQuote, Poi, ResultBundle, TransportQuote, TripRequest

MEAL_RATE = 80.0  # 每日餐饮估算(元/人/日)


def _min_price(quotes: list[TransportQuote | HotelQuote], key) -> float:
    return min((getattr(q, key) for q in quotes), default=0.0)


def estimate_cost(
    request: TripRequest,
    bundle: ResultBundle,
    pois: list[Poi],
    nights: int | None = None,
) -> CostBreakdown:
    """返回交通往返+住宿+门票+餐饮的分解与人均。"""
    days = request.days or 1
    nights = max(days - 1, 0) if nights is None else nights
    travelers = max(1, request.adults + request.elders + request.children)

    if request.transport_fixed:
        # 交通已自行安排:用用户告知的固定总价(如「两个人机票4400」),未告知则不计
        transport = float(request.fixed_transport_cost or 0.0)
    else:
        transport = _min_price(bundle.transport, "price") * 2  # 最低往返
    hotel_nightly = _min_price(bundle.hotels, "price_per_night")
    hotels = hotel_nightly * nights
    tickets = sum(p.ticket_price for p in pois if p.ticket_price is not None)
    meals = days * travelers * MEAL_RATE
    total = transport + hotels + tickets + meals
    return CostBreakdown(
        transport=round(transport, 1),
        hotels=round(hotels, 1),
        tickets=round(tickets, 1),
        meals=round(meals, 1),
        total=round(total, 1),
        per_person=round(total / travelers, 1) if travelers else 0.0,
    )
