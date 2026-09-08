# trip-resilience 设计

## 背景与目标

真实规划对话（贵阳→荔波→西江→榕江，国庆 7 天）中，用户反复表达"晕车、不想拖行李、体力有限、赶不上高铁怎么办、要提前抢什么票"——工具对这些**执行层约束**无感知。本 change 把三类能力以**确定性模块**落地（沿用既有"模型软提示 + 规则硬兜底"的成熟模式，见 transport_fixed）：

1. 场景字段识别（意图解析层）
2. 韧性附言（计划组装层，纯规则、不进模型提示词）
3. 倒排计算 + 行前行动日历（新模块与新端点）

## D1 场景字段：模型软层 + 词表硬兜底

`TripRequest` 新增（全部带默认值，旧会话/旧请求零破坏）：

```python
motion_sickness: bool = False      # 晕车
travel_pace: Literal["relaxed", "standard", "intensive"] = "standard"
pack_light: bool = False           # 轻装/无大件行李
```

**解析双层**（与 `_apply_transport_hints` 同模式）：
- 软层：`parse_intent` / `parse_feedback` 的 prompt 各加一条规则说明三字段映射；refine 侧规则为"仅在反馈提及时覆盖"。
- 硬层：确定性 `_apply_scene_hints(text, req)` 词表扫描：
  - `晕车|容易晕|怕晕|山路晕` → `motion_sickness=True`
  - `轻松|不赶|休闲|慢慢玩|体力一般|节奏放慢` → relaxed；`紧凑|特种兵|暴走|能走|节奏快|体力好` → intensive
  - `不想拖行李|轻装|不拖箱|背包走|不拎箱` → `pack_light=True`
- 两个 parse 分支末尾都调用；heuristic 分支同样生效（离线测试可直接覆盖硬层）。

## D2 韧性附言：组装期纯规则追加

在 `_assemble_plan` 与 demo 两条路径收口处（`main.py::_search_and_plan` 调用 `build_plan` 之后）调用 `resilience.summary(request, plan, bundle) -> str`（空串则不动 note）：

- 条件与文案（确定性）：
  - `motion_sickness` 且计划文本/交通候选含 `拼车|包车|大巴|班车` → 追加"途中多山路/长途乘车：坐前部靠窗、上车前半小时服晕车药、勿低头看手机。"
  - `pack_light` 且存在跨住宿迁移 → 追加"全程轻装：景区日背包寄存酒店/民宿前台，随身只带小包。"
  - `travel_pace == intensive` 且 `days > 4` → 追加"行程紧凑已超 4 天，建议在第 3–4 天留半日恢复窗口。"
- 追加到 `plan.note` 末尾；摘要同时供 `resilience` 字段使用。
- 附言生成不依赖模型，不修改 `days`/活动正文，测试离线可断言。

## D3 倒排计算：纯函数库

`resilience.backchain(deadline, steps, drop_order)`：

```python
# steps: [(label, minutes)] 按执行顺序；drop_order: 可舍弃的 label（从后往前舍）
def backchain(deadline: datetime, steps: list[tuple[str, int]],
              drop_order: list[str]) -> BackchainResult
```

- 从 deadline 逆推每步最晚开始时刻；超窗口则按 `drop_order` 顺序从列表末尾舍弃，直到放得下或无可舍（返回 `feasible=False` + 必须舍弃的步骤与瓶颈）。
- 返回 `BackchainResult{plan: [(label, latest)], buffer_min, feasible, must_drop}`。
- 纯函数、无 IO，供本 change 的日历与未来 Phase 2（接入真实班次）复用；本期先以单测锁定行为。

## D4 行前行动日历端点

`GET /api/prep/{session_id}/calendar`（只读、无副作用）：

1. 取会话 → 无则 404；`start_date` 缺失 → 422。
2. 规则模板生成（确定性）：
   - 今天 → 出发日窗口内逐项（用 `request` 的 `start_date/days/transport_fixed/...` 选择模板）：
     - `transport_fixed` → "确认往返交通出票/行程单"；否则 → "预订/出票往返大交通"
     - "预订全程住宿（可免费取消优先）"（出发 21 天前以上才出现）
     - 铁路出行段开抢日 = 用车日前 15 天（对 start_date 首段）
     - "预约景区门票/预约类项目" = 出发前 7 天提示
     - 出发前 3 天："装备与药物采购、行李试装"
     - 出发前 1 天："值机选座、电子票截图、检查单"
   - 日期超过今天的动作保留，过期动作不返回。
3. 响应：`{session_id, departure_date, days, items: [{due_date, category, action}]}`。

## D5 模型/兼容性与测试

- `models.py` 字段默认值 → pydantic 兼容旧快照（缺失字段走默认）；`PlanResponse.resilience` 默认 None。
- 前端不改（摘要并入 note；`resilience` 字段仅为 API 增量）。
- 测试（离线、无 LLM）：
  - 解析：heuristic 命中词表三字段；refine 提及更新、未提及保持。
  - 附言：三种条件命中与"无约束不加"；不修改正文。
  - backchain：放得下/超窗口舍弃两例。
  - calendar：21 天后出发+transport_fixed → 模板动作与日期、过期过滤、404/422。
- ruff/pytest 维持绿（本机 ruff 不可用，CI 覆盖）。

## 文件清单

| 文件 | 改动 |
|---|---|
| `app/models.py` | +3 字段；PlanResponse +`resilience` |
| `app/llm.py` | parse/refine prompt 规则；`_apply_scene_hints` 词表与调用 |
| `app/resilience.py` | 新增：`summary` / `backchain` / `build_prep_calendar` |
| `app/main.py` | note 追加与 resilience 字段；`GET /api/prep/{id}/calendar` |
| `tests/test_plan.py` | +1 组场景解析、+1 组附言、+1 组 backchain、+1 组 calendar |
