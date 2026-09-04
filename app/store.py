"""价格快照存储:每次检索把报价落 SQLite,供未来走势分析(spec: 记录价格快照)。

本期只写不读、不做预测。零外部依赖(stdlib sqlite3)。
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from app.models import ResultBundle, TripRequest

_INSERT_SQL = (
    "INSERT INTO price_snapshots "
    "(constraint_hash, category, supplier, item_key, detail, price, currency, captured_at) "
    "VALUES (?,?,?,?,?,?,?,?)"
)


def _db_path() -> str:
    return os.getenv("PLANNER_DB_PATH", str(Path("data") / "travel.db"))


def connect() -> sqlite3.Connection:
    path = _db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS price_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            constraint_hash TEXT NOT NULL,
            category TEXT NOT NULL,
            supplier TEXT NOT NULL,
            item_key TEXT NOT NULL,
            detail TEXT NOT NULL,
            price REAL NOT NULL,
            currency TEXT NOT NULL,
            captured_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _hash_request(request: TripRequest) -> str:
    raw = json.dumps(
        request.model_dump(mode="json"), ensure_ascii=False, sort_keys=True
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def record_snapshot(
    request: TripRequest,
    bundle: ResultBundle,
    conn: sqlite3.Connection | None = None,
) -> int:
    """把本次检索结果写入快照表,返回写入行数。"""
    owned = conn is None
    if owned:
        conn = connect()
    constraint_hash = _hash_request(request)
    now = datetime.utcnow().isoformat(timespec="seconds")
    rows = 0
    try:
        for q in bundle.transport:
            conn.execute(
                _INSERT_SQL,
                (
                    constraint_hash,
                    "transport",
                    q.supplier,
                    q.dedup_key,
                    json.dumps(q.model_dump(mode="json"), ensure_ascii=False),
                    q.price,
                    q.currency,
                    now,
                ),
            )
            rows += 1
        for h in bundle.hotels:
            conn.execute(
                _INSERT_SQL,
                (
                    constraint_hash,
                    "hotel",
                    h.supplier,
                    h.dedup_key,
                    json.dumps(h.model_dump(mode="json"), ensure_ascii=False),
                    h.price_per_night,
                    h.currency,
                    now,
                ),
            )
            rows += 1
        conn.commit()
    finally:
        if owned:
            conn.close()
    return rows
