"""FastAPI 入口。

POST /api/plan = 意图解析 → 交通/酒店检索 → 多平台景点交叉 → 费用 → 逐日规划(可实时资讯);
GET / = 演示网页。
"""

from __future__ import annotations

from pathlib import Path

import anthropic
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app import costing, llm, model_runtime, poi, sessions
from app.models import CostBreakdown, PlanResponse, Poi, ResultBundle, TripRequest
from app.retrieval import search_all
from app.store import record_snapshot
from app.suppliers import resolve_suppliers

app = FastAPI(title="Travel Planner", version="0.2.0")

_WEB_DIR = Path(__file__).resolve().parent / "web"


class PlanRequest(BaseModel):
    text: str = Field(description="自然语言旅行需求,如:上海出发带老人去西安5天人均3000偏人文")
    web_research: bool | None = Field(
        default=None, description="覆盖 WEB_RESEARCH_ENABLED;true 时对该次规划启用实时网页检索"
    )


class RefineRequest(BaseModel):
    feedback: str = Field(description="对上一版计划的追问,如:预算降到2000 / 第二天轻松点")
    web_research: bool | None = Field(
        default=None, description="覆盖 WEB_RESEARCH_ENABLED;true 时对该次细化启用实时网页检索"
    )


class ModelConfigRequest(BaseModel):
    api_key: str | None = Field(default=None, description="API Key;空串表示清除")
    base_url: str | None = Field(default=None, description="自定义端点(如网关/代理);空串清除")
    provider: str | None = Field(default=None, description="供应商 anthropic/openai;空串恢复默认")
    parse_model: str | None = Field(default=None, description="意图解析模型;空串恢复默认")
    plan_model: str | None = Field(default=None, description="逐日规划模型;空串恢复默认")


def _search_and_plan(
    request: TripRequest,
    web_research: bool | None = None,
    bundle: ResultBundle | None = None,
    pois_list: list[Poi] | None = None,
) -> tuple[PlanResponse, ResultBundle, list[Poi], CostBreakdown, str]:
    """给定约束,检索(或复用候选)并产出计划;返回 (plan, bundle, pois, cost, live)。"""
    if not request.origin or not request.destinations:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "无法从需求中确定出发地与目的地,请补充后再试。",
                "missing_fields": request.missing_fields,
                "parsed": request.model_dump(mode="json"),
            },
        )

    rows = 0
    if bundle is None:
        bundle = search_all(request, resolve_suppliers())
        if request.local_tour:
            bundle.transport = []
        rows = record_snapshot(request, bundle)

    if pois_list is None:
        city = request.destinations[0]
        keywords = poi.keywords_for(request.preferences)
        providers = poi.resolve_poi_providers()
        pois_list = poi.search_pois(city, keywords, providers)

    cost = costing.estimate_cost(request, bundle, pois_list)
    live = llm.gather_live_info(pois_list, enabled=web_research)
    plan = llm.build_plan(request, bundle, pois_list, cost, live)
    plan.recorded_snapshot = rows > 0
    return plan, bundle, pois_list, cost, live


def _transport_changed(a: TripRequest, b: TripRequest) -> bool:
    return (
        a.origin, a.destinations, a.start_date, a.days,
        a.adults, a.elders, a.children,
    ) != (
        b.origin, b.destinations, b.start_date, b.days,
        b.adults, b.elders, b.children,
    )


def _poi_changed(a: TripRequest, b: TripRequest) -> bool:
    return a.destinations != b.destinations or a.preferences != b.preferences


@app.get("/healthz")
def healthz() -> dict:
    return {
        "status": "ok",
        "llm_configured": llm.configured(),
        "poi_providers": [p.name for p in poi.resolve_poi_providers()],
        "web_research_enabled": llm.web_research_enabled(),
    }


@app.get("/api/config/model")
def get_model_config() -> dict:
    """返回当前模型配置状态(不回显完整 key)。"""
    return model_runtime.public_info()


@app.post("/api/config/model")
def set_model_config(body: ModelConfigRequest) -> dict:
    """保存页面填写的大模型配置,即时生效。"""
    model_runtime.set_config(
        api_key=body.api_key,
        base_url=body.base_url,
        provider=body.provider,
        parse_model=body.parse_model,
        plan_model=body.plan_model,
    )
    return model_runtime.public_info()


@app.post("/api/config/model/test")
def test_model_config() -> dict:
    """按供应商连通测试(仅查询模型元数据,不产生生成 token)。"""
    if not model_runtime.configured():
        raise HTTPException(status_code=400, detail="请先填写并保存 API Key 再测试。")
    try:
        if model_runtime.provider() == "openai":
            base = model_runtime.effective_base_url()
            resp = httpx.get(
                f"{base}/models",
                headers={"Authorization": f"Bearer {model_runtime.api_key()}"},
                timeout=30.0,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"{resp.status_code} {resp.text[:300]}")
            return {"ok": True, "model": model_runtime.plan_model()}
        kwargs: dict = {"api_key": model_runtime.api_key()}
        base = model_runtime.anthropic_base_url()
        if base:
            kwargs["base_url"] = base
        model = anthropic.Anthropic(**kwargs).models.retrieve(
            model_id=model_runtime.plan_model()
        )
    except Exception as exc:  # noqa: BLE001 - 统一转 400,避免堆栈外泄为「未知错误」
        raise HTTPException(status_code=400, detail=f"连接失败: {exc}") from exc
    return {"ok": True, "model": getattr(model, "id", model_runtime.plan_model())}


@app.post("/api/plan", response_model=PlanResponse)
def plan(body: PlanRequest) -> PlanResponse:
    try:
        request = llm.parse_intent(body.text)
        plan, bundle, pois_list, cost, live = _search_and_plan(request, body.web_research)
        state = sessions.PlanState(
            request=request, bundle=bundle, pois=pois_list, cost=cost, plan=plan, live_info=live
        )
        sessions.create(state)  # 内部把 session_id 回填到 plan
        return plan
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - 统一转 500,避免泄露堆栈
        raise HTTPException(status_code=500, detail=f"规划失败: {exc}") from exc


@app.post("/api/plan/{session_id}/refine", response_model=PlanResponse)
def refine(session_id: str, body: RefineRequest) -> PlanResponse:
    """在既有会话的基础上按反馈更新计划;约束变了会重新检索与重算。"""
    state = sessions.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="会话不存在或已过期。")
    try:
        new_request = llm.parse_feedback(state.request, body.feedback)
        bundle = None if _transport_changed(state.request, new_request) else state.bundle
        pois_list = None if _poi_changed(state.request, new_request) else state.pois
        plan, bundle, pois_list, cost, live = _search_and_plan(
            new_request, body.web_research, bundle=bundle, pois_list=pois_list
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"细化失败: {exc}") from exc

    plan.session_id = session_id
    state.request = new_request
    state.bundle = bundle
    state.pois = pois_list
    state.cost = cost
    state.live_info = live
    state.plan = plan
    state.history.append({"feedback": body.feedback, "note": plan.note})
    sessions.update(session_id, state)
    return plan


@app.get("/api/plan/{session_id}", response_model=PlanResponse)
def get_plan(session_id: str) -> PlanResponse:
    """回放会话当前状态,供前端刷新恢复。"""
    state = sessions.get(session_id)
    if state is None or state.plan is None:
        raise HTTPException(status_code=404, detail="会话不存在或尚未生成计划。")
    plan = state.plan
    plan.session_id = session_id
    return plan


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(_WEB_DIR / "index.html", media_type="text/html")
