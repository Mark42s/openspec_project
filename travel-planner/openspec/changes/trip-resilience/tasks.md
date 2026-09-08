# Tasks: Trip Resilience

## 1. 数据层
- [x] 1.1 `app/models.py`: `TripRequest` 新增 `motion_sickness: bool=False`、`travel_pace: Literal["relaxed","standard","intensive"]="standard"`、`pack_light: bool=False`（带描述）
- [x] 1.2 `app/models.py`: `PlanResponse` 新增 `resilience: dict | None = None`（描述：确定性韧性摘要）

## 2. 意图解析层
- [x] 2.1 `app/llm.py`: `parse_intent` prompt 增加场景字段规则（晕车/节奏/轻装 → 对应字段；未提及保持默认）
- [x] 2.2 `app/llm.py`: 新增 `_SCENE_HINTS` 词表与 `_apply_scene_hints(text, req)`（晕车/relaxed/intensive/轻装四类词），`parse_intent` 与 `parse_feedback` 两分支末尾调用（启发式分支同生效）
- [x] 2.3 `app/llm.py`: `parse_feedback` prompt 规则：仅在反馈提及时覆盖场景字段

## 3. 韧性模块（新增 `app/resilience.py`）
- [x] 3.1 `summary(request, note_plan_text)` → 附言规则生成（晕车+长途地面交通词、轻装+跨宿、intensive+>4 天）返回追加文本
- [x] 3.2 `backchain(deadline, steps, drop_order)` → 逐步骤最晚时刻 + 缓冲 + 超窗舍弃（纯函数）
- [x] 3.3 `build_prep_calendar(request)` → 行动清单（模板规则 + 相对日期倒推 + 过期过滤）

## 4. API 与组装层
- [x] 4.1 `app/main.py`: `_search_and_plan` 在 build_plan 后调用韧性附言追加到 note（模型正文不动），并组装 `plan.resilience`
- [x] 4.2 `app/main.py`: 新增 `GET /api/prep/{session_id}/calendar`（404/422 语义与 spec 一致）

## 5. 测试
- [x] 5.1 `tests/test_plan.py`: 场景解析——heuristic 词表命中三字段；refine 提及更新、未提及保持
- [x] 5.2 `tests/test_plan.py`: 附言——晕车/轻装/intensive 各命中场景与"无约束不加"；模型正文不被改动
- [x] 5.3 `tests/test_plan.py`: `backchain` 放得下与超窗舍弃两例
- [x] 5.4 `tests/test_plan.py`: `/api/prep/.../calendar`——21 天后出发+transport_fixed 的模板动作与日期、过期过滤、404/422

## 6. 全量验证与文档
- [x] 6.1 `.venv/bin/python -m pytest -q` 全绿（含既有用例回归）
- [x] 6.2 ruff 由 CI 覆盖（本机 MSYS 环境无法安装，跳过本地执行并注明）
- [x] 6.3 `openspec validate` 通过后提示用户进入 archive
