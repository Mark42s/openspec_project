# Tasks: Add Plan Refinement

## 1. 数据模型
- [x] 1.1 `app/models.py`: 新增 `Activity{time,title,kind,poi_name,note}` 模型
- [x] 1.2 `app/models.py`: `ItineraryDay.activities` 由 `list[str]` 改为 `list[Activity]`
- [x] 1.3 `app/models.py`: `PlanResponse` 新增 `session_id: str | None`

## 2. 会话存储
- [x] 2.1 `app/sessions.py`: 定义 `PlanState`(request/bundle/pois/cost/plan/live_info/history/时间戳)
- [x] 2.2 `app/sessions.py`: 复用 `store.connect()` 建 `plan_sessions` 表
- [x] 2.3 `app/sessions.py`: 实现 `create`/`get`/`update`,整状态 JSON 序列化

## 3. 追问解析与细化
- [x] 3.1 `app/llm.py`: 新增 `parse_feedback(prior, feedback)`(LLM + `_merge_feedback_heuristic` 双模)
- [x] 3.2 `app/llm.py`: 抽 `_assemble_plan(...)` 供 `build_plan`/`refine_plan` 共享
- [x] 3.3 `app/llm.py`: 新增 `refine_plan(...)`(LLM 在上一版基础上更新 + `_refine_plan_demo`)
- [x] 3.4 `app/llm.py`: `_demo_days` 改生成结构化 `Activity`

## 4. 路由
- [x] 4.1 `app/main.py`: `_search_and_plan` 接受可选复用 bundle/pois
- [x] 4.2 `app/main.py`: `_transport_changed`/`_poi_changed` 判定重检索
- [x] 4.3 `app/main.py`: `POST /api/plan` 落会话并返回 `session_id`
- [x] 4.4 `app/main.py`: 新增 `POST /api/plan/{session_id}/refine`
- [x] 4.5 `app/main.py`: 新增 `GET /api/plan/{session_id}`

## 5. 前端
- [x] 5.1 `app/web/index.html`: 保存 `session_id`,新增「继续完善」输入框与按钮
- [x] 5.2 `app/web/index.html`: `render` 改为结构化时间轴(时间徽标 + 类别 + 标题 + POI 富化 + 备注)
- [x] 5.3 `app/web/index.html`: 显示追问历史(feedback → 每版 note)

## 6. 测试
- [x] 6.1 `tests/test_plan.py`: 会话 create/get/update 往返
- [x] 6.2 `tests/test_plan.py`: 首次规划返回 `session_id`
- [x] 6.3 `tests/test_plan.py`: refine 改预算 → over_budget、改天数 → days 数变化
- [x] 6.4 `tests/test_plan.py`: refine 未知会话 404、GET 会话回放
- [x] 6.5 `tests/test_plan.py`: 结构化 `activities` 字段存在

## 7. OpenSpec 文档
- [x] 7.1 `proposal.md`: 说明变更原因、内容、影响范围
- [x] 7.2 `design.md`: 会话状态、追问解析、重检索判定、风险说明
- [x] 7.3 `specs/plan-refinement/spec.md`: delta spec(WHEN/THEN 格式)
- [x] 7.4 `tasks.md`: 本文件
