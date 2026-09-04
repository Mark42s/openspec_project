## 1. 项目脚手架与配置

- [x] 1.1 创建 pyproject.toml(依赖 fastapi、uvicorn、anthropic、pydantic、httpx;dev 依赖 pytest、ruff),并验证 `python -m venv .venv && pip install -e .[dev]` 成功
- [x] 1.2 创建 app/ 包结构与 __init__.py,验证 `python -c "import app"` 无报错
- [x] 1.3 创建 .env.example 与 .gitignore,验证 .venv、.env、数据库文件、__pycache__ 被忽略

## 2. 数据模型与 schemas(pydantic)

- [x] 2.1 在 app/models.py 定义 TripRequest(出发地/目的地候选/日期/天数/人数/预算/偏好,含必填约束)与缺失字段标记,验证单元测试可构造与校验
- [x] 2.2 定义供应商归一化结果模型 TransportQuote/HotelQuote(供应商/标识/价格/币种/舱位/房型/时间戳),验证序列化 JSON round-trip 通过
- [x] 2.3 定义 PlanResponse(建议行程 JSON + sources 列表 + is_mock 标记 + 预算不足提示字段),验证可反序列化

## 3. 供应商适配层

- [x] 3.1 在 app/suppliers/base.py 定义 SupplierAdapter 抽象接口与查询上下文 dataclass,验证可被 mock 实现实例化
- [x] 3.2 在 app/suppliers/mock.py 实现确定性 mock 数据源(车票+酒店,对相同输入返回稳定结果),验证两次相同查询结果一致且含 is_mock 语义
- [x] 3.3 在 app/suppliers/tuniu.py 实现途牛占位适配器:未配置凭证或调用抛错时抛特定异常,由上层回落 mock,验证回落逻辑单测通过
- [x] 3.4 在 app/suppliers/__init__.py 提供 resolve_suppliers() 工厂(按环境变量选择启用源),验证无凭证时仅返回 mock

## 4. 检索聚合

- [x] 4.1 在 app/retrieval.py 用 ThreadPool/httpx 并发调用启用源,收集 TransportQuote/HotelQuote 列表,验证并发结果聚合测试通过
- [x] 4.2 实现去重归一化(同一房型/车次多源取最低价,保留来源清单),验证重复源数据被合并
- [x] 4.3 实现规则初筛压缩 top-N(按价格与人群适配规则截断候选),验证超出数量上限的候选被裁掉

## 5. SQLite 价格快照

- [x] 5.1 在 app/store.py 用 sqlite3 建库建表 price_snapshots(约束哈希/类别/供应商/标识/价格/币种/采集时间),验证建表幂等
- [x] 5.2 实现 record_snapshot() 在每次检索后写入快照,验证插入后可查询到记录

## 6. LLM 受控 workflow

- [x] 6.1 在 app/llm.py 实现意图解析步骤:调用 Anthropic structured output(轻量模型,output_config.format 强 schema)把自然语言解析为 TripRequest,缺失字段自动标记,验证用固定输入返回合法 TripRequest
- [x] 6.2 实现汇总建议步骤:把 top-N 候选与约束喂给主模型,输出 PlanResponse 结构化行程(含推荐、日预算、理由、预算不足提示),验证输出满足 schema
- [x] 6.3 两步骤均读环境变量切换模型与 max_tokens,无 ANTHROPIC_API_KEY 时抛清晰错误;验证错误信息可读

## 7. FastAPI 入口

- [x] 7.1 在 app/main.py 暴露 POST /api/plan:接收自然语言需求 → 意图解析 → 并发检索 → 快照 → 汇总建议 → PlanResponse,验证 uvicorn 启动后 /api/plan 返回 200 与合法 JSON(mock 链路,无需真实 key 前置:key 缺失时允许以「无 key 演示模式」返回 mock+占位建议,便于本地与 CI)
- [x] 7.2 增加 /healthz 探活端点,验证返回 ok

## 8. 测试

- [x] 8.1 编写 tests/test_plan.py 覆盖全链路(2.1 场景:完整需求→结构化约束;预算不足场景→显式提示;mock 标记),验证 `pytest` 通过
- [x] 8.2 编写供应商回落/去重/快照单元测试,验证 `pytest` 全绿
- [x] 8.3 运行 `ruff check .` 无告警

## 9. 部署交付物

- [x] 9.1 编写 docker-compose.yml(web 服务与环境变量注入),验证 `docker compose config` 语法通过(本机无 Docker 时于 README 注明)
- [x] 9.2 编写 .github/workflows/ci.yml(run ruff + pytest),验证文件语法正确
- [x] 9.3 编写 README.md(架构图、token 成本表、免责声明「价格以实际下单页为准」、本地与 Docker 运行说明),验证文档含本地 curl 示例可复现
