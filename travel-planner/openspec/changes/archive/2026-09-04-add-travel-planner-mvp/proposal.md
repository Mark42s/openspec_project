## Why

用户做旅游规划时,需要在多个网站间人工反复比价机票/车票/酒店与当地旅游信息,费时且易漏最优组合。本变更建立一个「旅游规划」后端服务:接收一段自然语言旅行需求,自动并发检索国内数据源并去重比价,再由大模型汇总为行程建议。核心取舍是**受控 workflow**:模型只在「意图解析」与「汇总建议」两处介入,比价交给确定性并发代码——既快、可控,又比让模型自主反复搜索节省一个量级的 token。

## What Changes

- 新建 `app/` FastAPI 服务,暴露 `POST /api/plan`:自然语言 → 结构化行程 JSON。
- 引入**供应商适配层**(`app/suppliers/`):统一接口 `base.py`,本期实现确定性 mock 数据源与途牛适配器骨架;无真实凭证时自动回落到 mock,保证端到端可跑可测。
- 实现**两段式受控 LLM workflow**(`app/llm.py`):意图解析(轻量,structured output)+ 汇总建议(主模型),不引入自主 agent 循环。
- 新增 **SQLite 价格历史**(`app/store.py`):每次检索记录快照,本期仅落库供未来走势分析,不做预测。
- 附带部署配置:`.env.example`、`docker-compose.yml`、GitHub Actions CI、README。

非目标(**BREAKING-free 边界**):自动下单、支付、退改签不在本期,避免高风险动作;本期不保证跨供应商价格一致性,价格以实际下单页为准。

## Capabilities

### New Capabilities
- `travel-planner`: 把自然语言旅行需求解析为结构化约束,检索并去重国内机票/车票/酒店价格,汇总给出行程建议,并记录每次价格快照。

### Modified Capabilities

(无 —— 全新项目,尚无既有 spec 变更。)

## Impact

- **代码**: 新增 `app/`(FastAPI 入口、pydantic 模型、LLM 编排、供应商适配层、检索聚合、SQLite 存储)与 `tests/`。
- **API**: 新增 `POST /api/plan`。
- **依赖**: `fastapi`、`uvicorn`、`anthropic`、`pydantic`、`httpx`、pytest/ruff(dev)。
- **配置**: `.env`(`ANTHROPIC_API_KEY`、`TUNIU_*`、`PLANNER_DB_PATH`);`docker-compose.yml` 与 CI 为交付物。
- **OpenSpec**: 引入首个 capability `specs/travel-planner/spec.md`,归档后成为 `openspec/specs/` 基线。
