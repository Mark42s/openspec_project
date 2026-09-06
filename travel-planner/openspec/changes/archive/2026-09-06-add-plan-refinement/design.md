# 设计:会话式多轮细化行程

## 背景与协议

细化建立在既有 `/api/plan` 一次性链路(parse → `search_all` → `record_snapshot` → `poi.search_pois` → `costing.estimate_cost` → `gather_live_info` → `build_plan`)之上,复用而非重写。核心新增:

1. 首次规划把完整中间态(`TripRequest` + `ResultBundle` + `pois` + `cost` + `PlanResponse`)存进 SQLite 会话,返回 `session_id`。
2. 后续 `refine` 加载会话 → `parse_feedback` 合并出新的 `TripRequest` → 判断哪些检索维度变了 → 按需重检索/复用 → 重算费用 → `refine_plan` 在上一版基础上更新。

## 会话状态(PlanState)

`app/sessions.py` 定义 `PlanState`(pydantic),整状态 `model_dump(mode="json")` 存 SQLite 单列:

| 字段 | 说明 |
|---|---|
| `request` | 最新 `TripRequest` 约束 |
| `bundle` | 交通/酒店候选(`ResultBundle`) |
| `pois` | 景点列表 |
| `cost` | 费用分解 |
| `plan` | 上一版 `PlanResponse` |
| `live_info` | 实时资讯文本 |
| `history` | `[{feedback, note}]` 逐轮追问记录 |

复用 `store.connect()`(同 `PLANNER_DB_PATH`),`CREATE TABLE IF NOT EXISTS plan_sessions(session_id TEXT PK, state_json TEXT, updated_at TEXT)`。`session_id = uuid4().hex[:12]`。

## 追问解析(parse_feedback)

- **LLM 模式**(有 key):复用 `parse_intent` 的 structured-output 路径,但 prompt 为「现有约束 `{...}` + 用户追问 `{feedback}` → 输出合并后的完整约束,未提及字段保持原值」;出口统一过 `_clamp_start_date`。
- **演示模式**(无 key):`_merge_feedback_heuristic(prior, feedback)` 复制 prior,正则覆盖:预算 `(?:人均|预算)[^0-9]*?(\d+(?:\.\d+)?)`、天数 `(\d+)\s*天`、目的地(命中 `_CITIES`)、偏好(`_PREF_TRIGGERS`)、老人/亲子计数。

## 重检索判定

`app/main.py` 提供 `_transport_changed(a,b)`(origin/destinations/start_date/days/adults/elders/children 任一变化)与 `_poi_changed(a,b)`(destinations 或 preferences 变化)。二者为真时才重新 `search_all`/`poi.search_pois`,否则复用 `state.bundle`/`state.pois` —— **预算变化不重检索、只重算费用**(预算不影响检索候选)。费用始终确定性重算 `costing.estimate_cost`,不经模型心算。

## 结构化逐日行程(Activity)

`Activity{time,title,kind,poi_name,note}`,字段全部可选/有默认(缺 time/kind 不阻塞)。`kind ∈ transport/meal/sight/hotel/rest/note`。`build_plan`/`refine_plan` prompt 明确要求输出带时段的 `Activity`;`_demo_days` 改生成结构化 `Activity`。`_assemble_plan(...)` 抽为 `build_plan`/`refine_plan` 共享,负责费用回填、预算状态、`sources`/`is_mock` 等。

## 路由

- `POST /api/plan`:原链路完成后 `sessions.create(state)` → `plan.session_id = id` → 返回。
- `POST /api/plan/{session_id}/refine`:加载 state(404 若无)→ `parse_feedback` → 按需重检索 → 重算 → `refine_plan` → `sessions.update` + `history.append` → 返回(同 session_id)。
- `GET /api/plan/{session_id}`:回放当前 state.plan,供前端刷新恢复。

## 风险 / 说明

- 结构化 `Activity` 对 LLM 输出要求更高;字段全部可选,解析失败走 demo 兜底,不阻塞主链路。
- 重检索只在约束字段真正变化时触发,避免每轮打途牛(限流/慢)。
- 会话 JSON 存整状态,单机 demo 体积可控;不做历史清理,后续可加 TTL 过期。
