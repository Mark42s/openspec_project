"""两段式受控 LLM workflow(design D1/D3/D5)。

第一段「意图解析」:自然语言 → 结构化 TripRequest(structured output)。
第二段「逐日规划」:候选交通/酒店 + 交叉景点(POI) → day-by-day 行程;
费用由确定性 costing 计算后回填,不经模型心算。

未配置 ANTHROPIC_API_KEY 时走确定性演示模式,保证本地与 CI 无 key 可端到端跑通。
实时网页资讯默认关闭(WEB_RESEARCH_ENABLED=0);开启时用 Claude 网页搜索补充。
"""

from __future__ import annotations

import json
import os
import re
from typing import Literal, TypeVar

import anthropic
import httpx
from pydantic import BaseModel, Field

from app import model_runtime as rt
from app.models import (
    CostBreakdown,
    ItineraryDay,
    PlanRecommendation,
    PlanResponse,
    Poi,
    ResultBundle,
    TransportQuote,
    TripRequest,
)

DEFAULT_PARSE_MODEL = "claude-sonnet-5"
DEFAULT_PLAN_MODEL = "claude-sonnet-5"

# 规划步骤的模型中间输出:只含"需要模型生成"的部分;费用/来源/快照由上层确定性回填。
class ItineraryPlan(BaseModel):
    request_summary: str
    budget_status: Literal["ok", "over_budget"]
    note: str
    recommendations: list[PlanRecommendation] = Field(default_factory=list)
    days: list[ItineraryDay] = Field(default_factory=list)

_CITIES = [
    "北京", "上海", "广州", "深圳", "苏州", "杭州", "西安", "成都", "重庆", "天津",
    "南京", "武汉", "长沙", "郑州", "济南", "青岛", "大连", "沈阳", "哈尔滨", "长春",
    "厦门", "福州", "泉州", "南昌", "合肥", "太原", "石家庄", "兰州", "西宁", "银川",
    "乌鲁木齐", "拉萨", "贵阳", "昆明", "南宁", "海口", "三亚", "桂林", "珠海", "佛山",
    "东莞", "无锡", "常州", "扬州", "镇江", "南通", "宁波", "温州", "嘉兴", "湖州",
    "绍兴", "台州", "威海", "烟台", "秦皇岛", "洛阳", "开封", "大理", "丽江", "张家界",
]
_PREF_TRIGGERS = {
    "人文": ["人文", "古迹", "历史", "博物馆", "文化"],
    "美食": ["美食", "小吃", "吃"],
    "亲子": ["亲子", "小孩", "孩子", "带娃", "遛娃"],
    "自然": ["自然", "山水", "风景", "户外", "海岛"],
    "海滨": ["海滩", "滨海", "海边"],
    "购物": ["购物", "逛街"],
}
_LOCAL_HINTS = re.compile(r"周边|附近|自驾|周边游|省内|近郊|开车去")


def configured() -> bool:
    return rt.configured()


def provider() -> str:
    return rt.provider()


def _client() -> anthropic.Anthropic:
    kwargs: dict = {}
    key = rt.api_key()
    if key:
        kwargs["api_key"] = key
    base = rt.base_url()
    if base:
        kwargs["base_url"] = base
    return anthropic.Anthropic(**kwargs)


def parse_model() -> str:
    return rt.parse_model()


def plan_model() -> str:
    return rt.plan_model()


def web_research_enabled() -> bool:
    raw = os.getenv("WEB_RESEARCH_ENABLED", "0")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------- 第一段:意图解析

_ModelT = TypeVar("_ModelT", bound=BaseModel)


def _openai_parse(prompt: str, output_model: type[_ModelT], model: str) -> _ModelT:
    """OpenAI 兼容(DeepSeek)JSON 模式:POST /chat/completions → pydantic 校验。"""
    base = (rt.base_url() or "https://api.deepseek.com").rstrip("/")
    key = rt.api_key()
    schema = output_model.model_json_schema()
    full_prompt = (
        "请严格只输出一个 JSON 对象,不要输出任何 JSON 以外的文字或代码块标记。"
        f"JSON 的字段与类型必须符合以下 schema:\n{json.dumps(schema, ensure_ascii=False)}\n"
        f"任务:\n{prompt}"
    )
    try:
        resp = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": full_prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0,
            },
            timeout=60.0,
        )
    except httpx.HTTPError as exc:
        raise RuntimeError(f"OpenAI 兼容调用失败: {exc}") from exc
    if resp.status_code != 200:
        raise RuntimeError(f"OpenAI 兼容调用失败: {resp.status_code} {resp.text[:300]}")
    try:
        content = resp.json()["choices"][0]["message"]["content"]
        return output_model.model_validate(json.loads(content))
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError(f"OpenAI 兼容响应解析失败: {exc}") from exc


def parse_intent(text: str) -> TripRequest:
    """把自然语言解析为结构化约束。无 key 时退化为确定性规则解析。"""
    if not configured():
        return _heuristic_parse(text)
    prompt = (
        "把下面的中文旅行需求解析为结构化约束。\n"
        "规则:只能从文本推断,不要编造;无法确定的必填信息(出发地/目的地/出发日期/天数)置空,"
        "并把该字段名加入 missing_fields;目的地可有多个候选,按文本偏好排序。\n"
        "若用户未指明具体目的地但提到 周边/自驾/附近/省内 等,"
        "把 destinations 设为 [出发地] 并把 local_tour 置为 true,不要加入 missing_fields。\n"
        "文本:\n" + text
    )
    if provider() == "openai":
        return _openai_parse(prompt, TripRequest, parse_model())
    try:
        resp = _client().messages.parse(
            model=parse_model(),
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
            output_format=TripRequest,
        )
        return resp.parsed_output
    except anthropic.APIError as exc:
        raise RuntimeError(f"意图解析调用失败: {exc}") from exc


def _heuristic_parse(text: str) -> TripRequest:
    """无 key 演示解析:确定性子集,保证全链路在无模型下可跑。"""
    req = TripRequest()
    seen = [c for c in _CITIES if c in text]

    m = re.search(r"从\s*([一-龥]{2,4}?)\s*(?:出发|离开)", text) or re.search(
        r"([一-龥]{2,4}?)\s*出发", text
    )
    origin = m.group(1) if m else (seen[0] if seen else None)
    if origin in _CITIES:
        req.origin = origin

    m = re.search(r"(?:去|到|飞|游)\s*([一-龥]{2,4})", text)
    if m and m.group(1) in _CITIES:
        req.destinations = [m.group(1)]
    elif origin and seen:
        req.destinations = [c for c in seen if c != origin][:1]
    if not req.destinations and req.origin and _LOCAL_HINTS.search(text):
        req.destinations = [req.origin]
        req.local_tour = True

    m = re.search(r"(\d{1,2})\s*(?:天|日)", text)
    if m:
        req.days = int(m.group(1))

    m = re.search(r"人均\s*[:：]?\s*(\d+(?:\.\d+)?)\s*(?:元)?", text)
    if m:
        req.per_person_budget = float(m.group(1))

    elders = len(re.findall(r"老人", text))
    req.elders = elders
    if elders:
        req.adults = 0
    if re.search(r"亲子|小孩|孩子", text):
        req.children = max(req.children, 1)
    req.adults = max(req.adults, 1)

    for pref, keys in _PREF_TRIGGERS.items():
        if any(k in text for k in keys):
            req.preferences.append(pref)

    _mark_missing(req)
    return req


def _mark_missing(req: TripRequest) -> None:
    missing: list[str] = []
    if not req.origin:
        missing.append("出发地")
    if not req.destinations:
        missing.append("目的地")
    if not req.start_date:
        missing.append("出发日期")
    if req.days is None:
        missing.append("天数")
    req.missing_fields = missing


# ---------------------------------------------------------------- 第二段:汇总建议

def build_plan(
    request: TripRequest,
    bundle: ResultBundle,
    pois: list[Poi] | None = None,
    cost: CostBreakdown | None = None,
    live_info: str = "",
) -> PlanResponse:
    """读交通/酒店候选 + 交叉景点,输出 day-by-day 行程。费用用确定性 costing 回填。"""
    pois = pois or []
    cost = cost or CostBreakdown()
    if not configured():
        return _build_plan_demo(request, bundle, pois, cost)

    block = "\n".join(
        [_fmt_transport(q) for q in bundle.transport]
        + [_fmt_hotel(h) for h in bundle.hotels]
    )
    poi_lines = "\n".join(_poi_line(p) for p in pois)
    prompt = (
        "你是旅游规划师。依据用户约束、交通/住宿候选与景点,规划逐日行程(day-by-day)。\n"
        "规则:\n"
        "1) days 数组长度=行程天数;首日为抵达+入住(1-2 个就近点),末日宽松并留返程;\n"
        "2) 每日 2-3 个景点,按地理位置就近编排,含餐饮与大致时段;\n"
        "3) 带老人/慢节奏则每日最多 2 个点并安排午间休息;亲子则留亲子友好时段;\n"
        "4) 费用请勿自行估算(系统会确定性计算);note 写中文权衡与提醒。\n"
        f"用户约束:\n{request.model_dump(mode='json', exclude={'missing_fields'})}\n"
        f"交通/住宿候选:\n{block or '(无)'}\n"
        f"可安排景点:\n{poi_lines or '(无)'}\n"
        f"实时资讯(可选参考):\n{live_info or '(未启用网页检索)'}"
    )
    if provider() == "openai":
        p = _openai_parse(prompt, ItineraryPlan, plan_model())
    else:
        try:
            resp = _client().messages.parse(
                model=plan_model(),
                max_tokens=8000,
                messages=[{"role": "user", "content": prompt}],
                output_format=ItineraryPlan,
            )
            p = resp.parsed_output
        except anthropic.APIError as exc:
            raise RuntimeError(f"逐日规划调用失败: {exc}") from exc

    over = request.per_person_budget is not None and cost.per_person > request.per_person_budget
    return PlanResponse(
        request_summary=p.request_summary,
        budget_status="over_budget" if over else "ok",
        note=p.note,
        recommendations=p.recommendations,
        days=p.days,
        pois=pois,
        cost_breakdown=cost,
        per_person_estimate=cost.per_person,
        web_research_used=bool(live_info),
        is_mock=bundle.is_mock,
        sources=bundle.sources,
        recorded_snapshot=False,
    )


def gather_live_info(pois: list[Poi], enabled: bool | None = None) -> str:
    """可选:用 Claude 网页搜索补最新开放时间/票价/攻略/官网链接(有界 ≤3 次检索)。

    enabled 覆盖环境变量(缺省读 WEB_RESEARCH_ENABLED)。返回压缩文本段;
    未启用/无 key/无景点时返回空串(调用方据此设 web_research_used=False)。
    """
    on = enabled if enabled is not None else web_research_enabled()
    if not (configured() and on and pois):
        return ""
    if provider() != "anthropic":
        return ""  # OpenAI 兼容协议无 web_search 服务端工具
    names = "\n".join(f"- {p.name}: {p.description or '游览'}" for p in pois[:6])
    prompt = (
        "请对下列中文景点检索实时开放时间与门票价格等最新信息(近期公告/预约要求),"
        "汇总成简短中文要点;同时请附上每个景点的官网/百科链接(如有)。"
        "信息不确定请注明「以官方为准」。请勿编造。\n" + names
    )
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 3}]
    client = _client()
    messages: list[dict] = [{"role": "user", "content": prompt}]
    collected: list[str] = []
    for _ in range(4):  # 有界;处理 pause_turn 最多重启几次
        resp = client.messages.create(
            model=plan_model(), max_tokens=6000, tools=tools, messages=messages
        )
        for block in resp.content:
            if block.type == "text" and block.text:
                collected.append(block.text)
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "pause_turn":
            break
    return "\n".join(collected).strip()[:6000]


def _poi_line(p: Poi) -> str:
    tag = "多平台已确认" if p.verified else "单平台"
    ticket = f"门票约{p.ticket_price:.0f}元" if p.ticket_price is not None else "门票以现场为准"
    link = f"详情:{p.url}" if p.url else ""
    img = f"封面图:{p.image_url}" if p.image_url else ""
    return (
        f"- {p.name}({p.category}) {p.address} {ticket} "
        f"开放{p.open_hours or '?'} 来源{'、'.join(p.sources) or '?'} {tag} "
        f"{p.description or ''}{' '+link if link else ''}{' '+img if img else ''}"
    )


def _fmt_transport(q: TransportQuote) -> str:
    return (
        f"[交通 {q.supplier}] {q.mode}:{q.operator} {q.from_city}→{q.to_city} "
        f"{q.departure_time}-{q.arrival_time} {q.price:.0f}元 {q.travel_class}"
    )


def _fmt_hotel(h) -> str:
    refund = "可退" if h.is_refundable else "不可退"
    return (
        f"[酒店 {h.supplier}] {h.city} {h.name} {h.room_type} "
        f"{h.price_per_night:.0f}元/晚 {refund} 评分{h.rating or '-'}"
    )


def _build_plan_demo(
    request: TripRequest,
    bundle: ResultBundle,
    pois: list[Poi] | None = None,
    cost: CostBreakdown | None = None,
) -> PlanResponse:
    """确定性兜底:规则分日 + 确定性费用,保证无模型也能给出完整计划。"""
    pois = pois or []
    cost = cost or CostBreakdown()
    transport = min(bundle.transport, key=lambda q: q.price, default=None)
    hotel = bundle.hotels[len(bundle.hotels) // 2] if bundle.hotels else None

    recommendations: list[PlanRecommendation] = []
    if transport:
        recommendations.append(
            PlanRecommendation(
                kind="transport",
                label=(
                    f"{transport.mode} {transport.operator} "
                    f"{transport.from_city}→{transport.to_city} "
                    f"{transport.departure_time} 出发"
                ),
                supplier=transport.supplier,
                price=transport.price,
                reason=(
                    f"当前候选中最低的{'高铁二等座' if transport.mode == 'train' else '经济舱'}方案"
                ),
            )
        )
    if hotel:
        recommendations.append(
            PlanRecommendation(
                kind="hotel",
                label=f"{hotel.city} {hotel.name} · {hotel.room_type}",
                supplier=hotel.supplier,
                price=hotel.price_per_night,
                reason=(
                    "中档选择,评分 "
                    f"{hotel.rating or '-'},"
                    f"{'可免费取消' if hotel.is_refundable else '不可退'}"
                ),
            )
        )

    days = _demo_days(request, pois, transport)
    budget = request.per_person_budget
    over = budget is not None and cost.per_person > budget
    note_parts = []
    if over and budget is not None:
        note_parts.append(
            f"估算人均约 {cost.per_person:.0f} 元,已超出你 {budget:.0f} 元预算,"
            "建议下调酒店档位或缩短行程。"
        )
    else:
        note_parts.append(f"按当前候选估算人均约 {cost.per_person:.0f} 元,未超预算。")
    verified = sum(1 for p in pois if p.verified)
    if pois:
        note_parts.append(f"检索到 {len(pois)} 个候选景点,其中 {verified} 个经多平台交叉确认。")
    if request.local_tour:
        note_parts.append("周边游模式:按本地自驾理解,未计入长途交通费用。")
    note_parts.append("以上为演示数据(mock),价格与实时性不保证,请以实际下单页为准。")
    if request.preferences:
        note_parts.append("已考虑偏好:" + "、".join(request.preferences) + "。")

    return PlanResponse(
        request_summary=(
            f"{request.origin or '?'} → {'、'.join(request.destinations) or '?'},"
            f"{request.days or '?'} 天,{request.adults + request.elders + request.children} 人"
            f"{', 人均 ' + str(int(budget)) if budget else ''}"
        ),
        budget_status="over_budget" if over else "ok",
        note=" ".join(note_parts),
        recommendations=recommendations,
        days=days,
        pois=pois,
        cost_breakdown=cost,
        per_person_estimate=cost.per_person,
        is_mock=bundle.is_mock,
        sources=bundle.sources,
        recorded_snapshot=False,
    )


def _demo_days(
    request: TripRequest,
    pois: list[Poi],
    transport: TransportQuote | None,
) -> list[ItineraryDay]:
    """规则分日:首日到达、末日宽松返程、中间按类别就近轮转;带老人限 2 点加午休。"""
    days_n = request.days or 1
    city = request.destinations[0] if request.destinations else ""
    slow = request.elders > 0
    max_poi = 1 if slow else 2

    per_day_pois: list[list[Poi]] = [[] for _ in range(days_n)]
    pool = list(pois)
    for d in range(days_n):
        if d == 0 or d == days_n - 1:
            budget_pts = 1
        else:
            budget_pts = max_poi
        per_day_pois[d] = pool[:budget_pts]
        pool = pool[budget_pts:]
        if d != 0 and d != days_n - 1:
            per_day_pois[d].extend(pool[: max_poi - budget_pts])
            pool = pool[max_poi - budget_pts:]

    days: list[ItineraryDay] = []
    for d in range(1, days_n + 1):
        acts: list[str] = []
        if d == 1:
            if request.local_tour:
                acts.append(
                    f"{request.origin or '本地'} 自驾出发,入住 {city} 周边/市区酒店,不安排长途交通"
                )
            else:
                acts.append(
                    f"乘 {transport.operator if transport else '交通'} "
                    f"抵达 {city},入住酒店"
                )
        poi_list = per_day_pois[d - 1]
        for i, p in enumerate(poi_list):
            when = "上午" if i % 2 == 0 else "下午"
            price = f"{p.ticket_price:.0f}元" if p.ticket_price is not None else "门票以现场为准"
            tag = "[多平台]" if p.verified else "[单平台]"
            acts.append(f"{when} 游览 {p.name}{tag}({price},开放 {p.open_hours or '以官方为准'})")
        if slow and poi_list:
            acts.append("午后安排休息(带老人节奏放缓)")
        if d == days_n:
            acts.append("整理返程,预留机动时间")
        if d == 1 and not poi_list:
            acts.append("入住后附近轻松逛逛")
        if days_n == 1:
            title = "单日往返"
        elif d == 1:
            title = "抵达与安顿"
        elif d == days_n:
            title = "返程与收尾"
        else:
            title = f"第 {d} 天·{city} 深度游"
        days.append(
            ItineraryDay(
                day=d,
                title=title,
                activities=acts or ["自由活动"],
            )
        )
    return days
