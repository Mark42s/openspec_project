"""数据模型:行程约束、供应商归一化报价、规划响应(specs: travel-planner)。"""

from __future__ import annotations

# 必须在导入 BaseModel 之前加载,以确保 v2 API polyfill 已生效
import app.pydantic_compat  # noqa: F401, isort:skip

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class TripRequest(BaseModel):
    """意图解析产出的结构化行程约束(spec: 解析自然语言旅行需求)。"""

    origin: str | None = Field(default=None, description="出发地")
    destinations: list[str] = Field(default_factory=list, description="目的地候选,按偏好排序")
    start_date: date | None = Field(default=None, description="出发日期,未知则为 None")
    days: int | None = Field(default=None, description="行程天数,未知则为 None")
    adults: int = 1
    elders: int = 0
    children: int = 0
    per_person_budget: float | None = Field(default=None, description="人均预算(元),未知则为 None")
    preferences: list[str] = Field(default_factory=list, description="偏好,如 人文/美食/亲子/自然")
    local_tour: bool = Field(
        default=False,
        description="周边游:用户未指明具体目的地,以出发地为游览中心(不安排城际交通)",
    )
    missing_fields: list[str] = Field(default_factory=list, description="用户未提供、待确认的字段")


class TransportQuote(BaseModel):
    """归一化的跨城交通报价(spec: 多源并发检索与去重)。"""

    supplier: str
    mode: Literal["train", "flight"]
    from_city: str
    to_city: str
    operator: str = Field(description="车次或航班号")
    departure_station: str = Field(default="", description="出发站/机场(如 苏州北/硕放T2)")
    arrival_station: str = Field(default="", description="到达站/机场(如 贵阳北/龙洞堡T2)")
    departure_time: str
    arrival_time: str
    price: float
    currency: str = "CNY"
    travel_class: str = "标准"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def dedup_key(self) -> str:
        return f"{self.mode}:{self.operator}:{self.from_city}:{self.to_city}:{self.travel_class}"


class HotelQuote(BaseModel):
    """归一化的酒店报价(spec: 多源并发检索与去重)。"""

    supplier: str
    city: str
    name: str
    room_type: str
    price_per_night: float
    currency: str = "CNY"
    is_refundable: bool = False
    rating: float | None = Field(default=None, description="点评分,如 4.5")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def dedup_key(self) -> str:
        return f"{self.city}:{self.name}:{self.room_type}"


class ResultBundle(BaseModel):
    """检索聚合结果(spec: 多源并发检索与去重 / 无凭证兜底)。"""

    transport: list[TransportQuote] = Field(default_factory=list)
    hotels: list[HotelQuote] = Field(default_factory=list)
    is_mock: bool = True
    sources: list[str] = Field(default_factory=list)
    supplier_errors: list[str] = Field(default_factory=list)


class Poi(BaseModel):
    """归一化的景点(POI),含跨平台交叉来源标注(spec: 多平台交叉检索景点)。"""

    name: str
    address: str = ""
    category: str = ""
    sources: list[str] = Field(default_factory=list, description="命中的平台列表")
    verified: bool = Field(default=False, description="是否 ≥2 平台交叉命中")
    lng: float | None = None
    lat: float | None = None
    rating: float | None = None
    ticket_price: float | None = Field(default=None, description="估算门票(元),以现场为准")
    open_hours: str | None = None
    description: str = ""
    is_mock: bool = False
    url: str | None = Field(default=None, description="地图详情页链接(高德/百度)")
    image_url: str | None = Field(default=None, description="首张封面图 URL")
    website: str | None = Field(default=None, description="景点官网或百科链接")


class Activity(BaseModel):
    """逐日行程中的一段结构化活动(spec: 结构化逐日行程)。"""

    time: str = Field(default="", description="时段,如 09:00-11:30")
    title: str = Field(description="活动内容,如 游览甲秀楼")
    kind: Literal["transport", "meal", "sight", "hotel", "rest", "note"] = Field(default="sight", description="transport/meal/sight/hotel/rest/note")
    poi_name: str = Field(default="", description="关联景点名,用于前端富化")
    note: str = Field(default="", description="补充说明")


class ItineraryDay(BaseModel):
    """逐日行程的一天(spec: 逐日行程规划)。"""

    day: int
    date_label: str = ""
    title: str
    activities: list[Activity] = Field(default_factory=list, description="当日结构化安排")
    lodging_note: str = ""


class CostBreakdown(BaseModel):
    """确定性费用分解(spec: 确定性费用计算)。"""

    transport: float = 0.0
    hotels: float = 0.0
    tickets: float = 0.0
    meals: float = 0.0
    total: float = 0.0
    per_person: float = 0.0


class PlanRecommendation(BaseModel):
    """行程建议中的一段(交通或住宿)。"""

    kind: Literal["transport", "hotel"]
    label: str = Field(description="人类可读描述,如 高铁 G1234 上海→西安")
    supplier: str
    price: float
    currency: str = "CNY"
    reason: str = Field(description="为何推荐该项")


class PlanResponse(BaseModel):
    """最终响应(spec: 汇总生成行程建议 / 记录价格快照 / 不执行下单)。"""

    request_summary: str = Field(description="回显解析出的结构化约束")
    budget_status: Literal["ok", "over_budget"]
    note: str = Field(description="中文说明:推荐理由、预算提示、风险提示")
    recommendations: list[PlanRecommendation] = Field(default_factory=list)
    per_person_estimate: float = Field(description="人均估算总花费(元)")
    days: list[ItineraryDay] = Field(default_factory=list, description="逐日行程")
    pois: list[Poi] = Field(default_factory=list, description="交叉检索到的景点")
    cost_breakdown: CostBreakdown = Field(default_factory=CostBreakdown)
    web_research_used: bool = Field(default=False, description="是否使用了实时网页资讯")
    is_mock: bool = True
    sources: list[str] = Field(default_factory=list)
    recorded_snapshot: bool = False
    session_id: str | None = Field(default=None, description="会话 ID,用于多轮细化")
