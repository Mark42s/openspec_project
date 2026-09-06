## Why

当前 `/api/plan` 是一次性接口:自然语言 → 解析 → 检索 → 费用 → 逐日规划,返回后无状态,用户无法在上一版计划的基础上继续追加信息、迭代完善。用户反馈两点:① 生成的计划不够详细;② 希望能追加交互信息,不断在现有基础上更新完善。

## What Changes

- **会话式多轮细化**:首次规划返回 `session_id`,后续通过 `POST /api/plan/{session_id}/refine` 提交追问(feedback),在上一版计划基础上更新,并保留逐轮历史。
- **追问可改约束参数**:预算/天数/目的地/日期/偏好等约束变化时,自动触发重新检索 + 重算费用 + 重排行程;仅调行程文本则不重检索。追加 `llm.parse_feedback`(LLM + 确定性启发式双模)。
- **逐日行程结构化细化**:每天由 `list[str]` 升级为结构化 `Activity[]`(时间/类别/关联景点/备注),前端按时间轴渲染并做 POI 富化。
- **服务端会话持久化**:新增 `app/sessions.py`,用 SQLite `plan_sessions` 表整状态 JSON 序列化,刷新/重启可继续。
- **演示模式同样支持细化**:无 key 时 `parse_feedback`/`refine_plan` 走确定性合并,保证端到端可演示、可测试。

非目标:不做多用户鉴权与会话隔离(单机 demo);不做历史清理/TTL 过期(留待后续)。

## Capabilities

### New Capabilities
- `plan-refinement`: 会话式多轮细化、追问改约束触发重检索重算、结构化逐日行程、服务端会话持久化、演示模式细化。

### Modified Capabilities
(无 —— 全部为新增 `plan-refinement` 能力)

## Impact

- **代码**: 新增 `app/sessions.py`;修改 `app/models.py`(新增 `Activity`、`ItineraryDay.activities` 改结构化、`PlanResponse` 加 `session_id`)、`app/llm.py`(新增 `parse_feedback`/`refine_plan`、抽 `_assemble_plan`、`_demo_days` 结构化)、`app/main.py`(`_search_and_plan` 复用 + 新增 refine/get 路由)、`app/web/index.html`(结构化时间轴 + 继续完善输入 + 历史)、`tests/test_plan.py`。
- **向后兼容**: `Activity` 字段全部可选/有默认;`ItineraryDay.activities` 由字符串列表改为对象列表,前端已同步升级;旧客户端若按字符串读取需适配。
- **API**: `POST /api/plan` 响应新增 `session_id` 与 `days[].activities[]`(结构化);新增 `POST /api/plan/{session_id}/refine` 与 `GET /api/plan/{session_id}`。
- **依赖**: 无新增(复用 stdlib sqlite3、已有 pydantic/httpx)。
