"""出行韧性:确定性健康提示、倒排时刻计算、行前行动日历(spec: trip-resilience)。

全部为纯规则实现,不依赖模型——健康提示在计划组装时确定性追加,
倒排计算供赶车/末班场景推理,行前日历供 /api/prep 端点。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from app.models import TripRequest

_LONG_ROAD = re.compile(r"拼车|包车|大巴|班车|直通车")


# ---------------------------------------------------------------- 韧性附言

def summary(request: TripRequest, corpus: str = "") -> str:
    """按场景字段返回确定性韧性提示(空串=无需追加)。

    corpus: 计划文本(活动标题/推荐/说明拼串),用于判断是否含长途地面交通。
    """
    parts: list[str] = []
    if request.motion_sickness and _LONG_ROAD.search(corpus):
        parts.append("途中含长途地面交通(拼车/包车/大巴):晕车建议坐前部靠窗、上车前半小时服晕车药、乘车时勿低头看手机。")
    if request.pack_light and (request.days or 1) > 1:
        parts.append("全程轻装:景区日可将背包寄存酒店/民宿前台,随身只带小包。")
    if request.travel_pace == "intensive" and (request.days or 0) > 4:
        parts.append("行程较紧凑且超过 4 天:建议在中段留半天恢复窗口。")
    return " ".join(parts)


# ---------------------------------------------------------------- 倒排计算

@dataclass
class BackchainResult:
    """倒排结果:各步最晚开始、附加项取舍与可行性。"""

    latest: list[tuple[str, str]]  # [(label, "HH:MM")] 按执行顺序
    kept_optional: list[str] = field(default_factory=list)
    dropped_optional: list[str] = field(default_factory=list)
    feasible: bool = True
    buffer_min: int = 0
    must_shorten_hint: str = ""


def backchain(
    deadline: datetime,
    chain_start: datetime,
    must_steps: list[tuple[str, int]],
    optional_steps: list[tuple[str, int]] | None = None,
) -> BackchainResult:
    """从 deadline 逆推必须链各步最晚开始;窗口放不下附加项时按"最可舍在前"依次舍弃。

    must_steps 按执行顺序;optional_steps 顺序即可舍优先级(索引越小越先舍)。
    纯函数,无 IO。
    """
    optionals = list(optional_steps or [])
    window = deadline - chain_start
    must_total = sum(m for _, m in must_steps)

    if must_total > int(window.total_seconds() // 60):
        return BackchainResult(
            latest=[],
            feasible=False,
            must_shorten_hint=(
                f"必须动作共需 {must_total} 分钟,窗口仅 {int(window.total_seconds() // 60)} 分钟;"
                f"需把最早可开始提前至少 {must_total - int(window.total_seconds() // 60)} 分钟或缩短行程"
            ),
        )

    # 附加项从最可舍开始逐个移除,直到塞进窗口
    kept = list(optionals)
    dropped: list[str] = []
    while sum(m for _, m in kept) > int(window.total_seconds() // 60) - must_total:
        if not kept:
            break
        label, _ = kept.pop(0)
        dropped.append(label)

    # 逆推必须链各步最晚开始
    latest: list[tuple[str, str]] = []
    cursor = deadline
    for label, minutes in reversed(must_steps):
        cursor = cursor - timedelta(minutes=minutes)
        latest.append((label, cursor.strftime("%H:%M")))
    latest.reverse()

    used = must_total + sum(m for _, m in kept)
    return BackchainResult(
        latest=latest,
        kept_optional=kept,
        dropped_optional=dropped,
        feasible=True,
        buffer_min=int(window.total_seconds() // 60) - used,
    )


# ---------------------------------------------------------------- 行前行动日历

_CATEGORY_LABEL = {
    "ticket": "票务",
    "stay": "住宿",
    "reserve": "预约",
    "gear": "装备",
    "check": "出行检查",
}


def build_prep_calendar(request: TripRequest, today: date | None = None) -> list[dict]:
    """生成行前行动清单(确定性模板)。

    返回按建议执行日排序的 [{due_date, category, action}];已过期动作不返回。
    """
    if request.start_date is None:
        return []
    today = today or date.today()
    items: list[dict] = []

    def add(due: date, category: str, action: str) -> None:
        if due >= today:
            items.append({"due_date": due.isoformat(), "category": category, "action": action})

    start = request.start_date
    # 1) 大交通:已自订 → 确认出票;否则 → 预订/出票(铁路预售 15 天)
    if request.transport_fixed:
        add(today, "ticket", "确认已订往返交通出票(航班/车次号与时刻);不另行比价")
    else:
        add(start - timedelta(days=15), "ticket", "预订/出票往返大交通(12306/航司,提前 15 天开售)")
    # 2) 住宿:窗口 ≥21 天时提前预订
    if (start - today).days >= 21:
        add(start - timedelta(days=21), "stay", "预订全程住宿(优先可免费取消,再补确认)")
    # 3) 门票与预约类项目:出发前 7 天提示
    add(start - timedelta(days=7), "reserve", "预约景区门票/预约类项目(实名分时,刷身份证)")
    # 4) 装备:出发前 3 天
    add(start - timedelta(days=3), "gear", "装备与药品采购、行李试装(负重试走一次)")
    # 5) 出行检查:出发前 1 天
    add(start - timedelta(days=1), "check", "值机选座、电子票/预约码截图、行前检查单逐项打勾")

    return sorted(items, key=lambda it: it["due_date"])
