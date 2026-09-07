"""多轮规划会话存储:把一次规划及其历史存 SQLite,支持追问式细化。

复用 store 的 PLANNER_DB_PATH 与 connect(),新增 plan_sessions 表;整状态 JSON 序列化存一列。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field

from app.models import CostBreakdown, PlanResponse, Poi, ResultBundle, TripRequest
from app.store import connect

_EXPIRY_DAYS = 7


class HistoryEntry(BaseModel):
    """一次细化追问的完整记录,含旧版计划快照供回退。"""

    feedback: str
    note: str
    snapshot: dict | None = None  # 该版完整 PlanResponse 的 model_dump(mode='json')
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))


class PlanState(BaseModel):
    """一次规划会话的完整状态,供 refine 在上一版基础上更新。"""

    request: TripRequest
    bundle: ResultBundle
    pois: list[Poi] = Field(default_factory=list)
    cost: CostBreakdown = Field(default_factory=CostBreakdown)
    plan: PlanResponse | None = None
    live_info: str = ""
    history: list[HistoryEntry] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    expires_at: str = Field(default_factory=lambda: (datetime.now(timezone.utc) + timedelta(days=_EXPIRY_DAYS)).isoformat(timespec="seconds"))


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
    state = PlanState.model_validate_json(row[0])
    # 检查过期
    try:
        expires = datetime.fromisoformat(state.expires_at)
        if datetime.now(timezone.utc) > expires:
            _delete(session_id)
            return None
    except (ValueError, KeyError):
        pass  # 旧数据无 expires_at,不过期
    return state


def _delete(session_id: str) -> None:
    conn = _connect()
    try:
        conn.execute("DELETE FROM plan_sessions WHERE session_id = ?", (session_id,))
        conn.commit()
    finally:
        conn.close()


def update(session_id: str, state: PlanState) -> None:
    state.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn = _connect()
    try:
        conn.execute(
            "UPDATE plan_sessions SET state_json = ?, updated_at = ? WHERE session_id = ?",
            (state.model_dump_json(), state.updated_at, session_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_all() -> list[dict]:
    """列出所有未过期会话的摘要,供前端左侧面板使用。"""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT state_json FROM plan_sessions ORDER BY updated_at DESC"
        ).fetchall()
    finally:
        conn.close()

    result = []
    now = datetime.now(timezone.utc)
    for (state_json,) in rows:
        try:
            raw = json.loads(state_json)
            sid = raw.get("session_id", "")
            req = raw.get("request", {})
            summary = req.get("origin", "?")
            dests = req.get("destinations", [])
            if dests:
                summary += " → " + "、".join(dests)
            days = req.get("days")
            if days:
                summary += f" {days}天"
            history = raw.get("history", [])
            result.append({
                "session_id": sid,
                "request_summary": summary,
                "created_at": raw.get("created_at", ""),
                "updated_at": raw.get("updated_at", ""),
                "history_count": len(history),
                "expires_at": raw.get("expires_at", ""),
            })
        except (json.JSONDecodeError, KeyError):
            continue
    return result
