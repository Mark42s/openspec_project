"""多轮规划会话存储:把一次规划及其历史存 SQLite,支持追问式细化。

复用 store 的 PLANNER_DB_PATH 与 connect(),新增 plan_sessions 表;整状态 JSON 序列化存一列。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models import CostBreakdown, PlanResponse, Poi, ResultBundle, TripRequest
from app.store import connect


class PlanState(BaseModel):
    """一次规划会话的完整状态,供 refine 在上一版基础上更新。"""

    request: TripRequest
    bundle: ResultBundle
    pois: list[Poi] = Field(default_factory=list)
    cost: CostBreakdown = Field(default_factory=CostBreakdown)
    plan: PlanResponse | None = None
    live_info: str = ""
    history: list[dict[str, str]] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat(timespec="seconds"))
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat(timespec="seconds"))


def _connect():
    conn = connect()  # 复用同一 DB 路径,并确保 price_snapshots 表存在
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS plan_sessions (
            session_id TEXT PRIMARY KEY,
            state_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def create(state: PlanState) -> str:
    """写入会话并返回 session_id;同时把 id 回填到 state.plan.session_id。"""
    sid = _new_id()
    if state.plan is not None:
        state.plan.session_id = sid
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO plan_sessions (session_id, state_json, updated_at) VALUES (?,?,?)",
            (sid, state.model_dump_json(), state.updated_at),
        )
        conn.commit()
    finally:
        conn.close()
    return sid


def get(session_id: str) -> PlanState | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT state_json FROM plan_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return PlanState.model_validate_json(row[0])


def update(session_id: str, state: PlanState) -> None:
    state.updated_at = datetime.utcnow().isoformat(timespec="seconds")
    conn = _connect()
    try:
        conn.execute(
            "UPDATE plan_sessions SET state_json = ?, updated_at = ? WHERE session_id = ?",
            (state.model_dump_json(), state.updated_at, session_id),
        )
        conn.commit()
    finally:
        conn.close()
