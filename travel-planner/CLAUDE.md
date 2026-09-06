# CLAUDE.md — Travel Planner 项目指南(跨机器交接用)

> 本文件是给**另一台电脑上的 Claude Code** 接续开发的入口。规格(spec)是本项目的真源,
> 详见 `openspec/specs/<capability>/spec.md`;本文件只补规格写不到的运行/约定/进度上下文。

## 项目是什么

国内旅行规划后端(FastAPI)。用户输入一段**自然语言旅行需求**(如「上海出发带老人去西安5天人均3000偏人文」),
服务自动:解析为结构化约束 → 并发比价国内交通/酒店 → 多平台交叉检索景点 → 确定性算费用 → 生成**逐日行程建议**,
并在浏览器页面演示。当前为 **MVP**:交通/住宿是确定性 mock 数据,POI 高德配了真实 key(见下文),未接真实途牛。

## 当前进度快照(2026-09-04 首次入库)

已归档 **4 个 OpenSpec change**(`openspec/changes/archive/`),沉淀为 **3 份能力规格**(`openspec/specs/`):

| 能力 spec | 覆盖 | 状态 |
|---|---|---|
| `travel-planner` | 意图解析 / 多源并发检索去重 / 无凭证兜底 / 价格快照 / 周边游语义 | ✅ |
| `itinerary-planning` | 多平台景点交叉(高德·腾讯·百度) / 逐日行程 / 确定性费用 / 实时网页资讯开关 | ✅ |
| `model-config` | 页面「⚙️ 模型配置」:运行时切换大模型(语义理解/规划/实时搜索) | ✅ |

验证状态:pytest 16 passed、ruff 0、uvicorn + `GET /` 网页正常。Docker 未本机跑(仅交付物)。

## 如何运行(每台机器都要做一次)

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows;macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env              # 再填自己的密钥,见「配置与密钥」
.venv\Scripts/python -m uvicorn app.main:app --reload   # 打开 http://localhost:8000
```

测试与静态检查(测试必须能离线绿,见「测试约定」):

```bash
.venv\Scripts/python -m pytest -q
.venv\Scripts/python -m ruff check .
```

## 架构:受控 workflow(重要 —— 勿改成 agent 自主循环)

**为什么**:单次规划 token 可控在 ≈¥0.3–0.6;若让模型自主循环查源,同任务可达 ¥3–17/次(量级差异)。
且旅行候选空间形状确定,确定性并发查表比模型逐个调工具更准、更快。

**模型只在两处介入**,其余全是确定性代码:
1. **意图解析**(轻量模型):自然语言 → 结构化 `TripRequest`;无 key → 规则解析。
2. **逐日规划/汇总**(主模型):读去重后的 top-N 候选做权衡 → `PlanResponse`。

请求链路(`app/main.py::_run_plan`):
`parse_intent` → 校验 origin/dest → `search_all`(交通/酒店并发去重)→ 周边游则清空城际交通 →
`record_snapshot`(SQLite)→ `poi.search_pois`(多平台交叉,≥2 命中 `verified`)→ `costing.estimate_cost`(规则计算)→
`llm.gather_live_info`(可选实时网页检索,默认关)→ `llm.build_plan`(逐日)。

## 代码地图

| 路径 | 职责 |
|---|---|
| `app/main.py` | FastAPI 入口:`/api/plan`、`/healthz`、`/api/config/model`(+test)、`GET /` 网页 |
| `app/llm.py` | 意图解析 / 逐日规划 / 实时网页检索;统一读 `model_runtime` |
| `app/model_runtime.py` | 运行期模型配置真源(优先级:**页面 > data/model_config.json > .env > 默认**) |
| `app/poi.py` | POI 多平台交叉(Amap/Tencent/Baidu Provider + Mock 兜底)、`keywords_for` |
| `app/retrieval.py` + `app/suppliers/` | 交通/酒店并发检索去重;`MockAdapter` 确定性,`TuniuAdapter` 占位 |
| `app/costing.py` | 确定性费用分解(交通往返+住宿+门票+餐饮),`MEAL_RATE=80` |
| `app/store.py` | SQLite 价格快照 `price_snapshots` |
| `app/models.py` | pydantic 模型:TripRequest/Quote/Bundle/Poi/ItineraryDay/Cost/PlanResponse |
| `app/web/index.html` | 单文件页面(无构建);含「⚙️ 模型配置」面板 |
| `tests/test_plan.py` | 端到端 + 单元,autouse fixture 强制演示模式 |
| `openspec/` | spec + 归档 change(见「OpenSpec 工作流」) |

## 配置与密钥

- **`.env` 已被 gitignore**,每台机器自己 `cp .env.example .env` 再填。已有键:`AMAP_KEY`(真实,已配)、`POI_PROVIDERS=amap`。
- **页面模型配置**保存到 `data/model_config.json`(也 gitignore):保存 API Key 即运行时生效,不配则演示模式。Key 明文落盘,注意保管。
- **供应商切换**:`provider` 取值 `anthropic`(默认)/ `openai`(OpenAI 兼容,如 DeepSeek)。`openai` 时 base_url 默认 `https://api.deepseek.com`、模型默认 `deepseek-chat`;实时网页检索仅 Anthropic 可用(`openai` 下自动关闭,`web_research_used=false`)。页面「⚙️ 模型配置」有供应商下拉;环境变量 `PLANNER_PROVIDER` 可设默认。
- 真实链路三平台 key 含义:AMAP/TENCENT/BAIDU(高德/腾讯/百度 POI);只配高德时,单平台命中不标「多平台确认」。缺 key 自动回落内置演示景点(mock)。
- `WEB_RESEARCH_ENABLED=0` 默认关;页面勾选或用 `web_research:true` 单次开。实时网页检索需已配置模型(且 provider=anthropic)。

## 测试约定

`tests/test_plan.py` 的 **autouse fixture `_force_demo_mode`** 会删掉所有 POI/Tuniu/Anthropic key 并 `model_runtime.reset()`,
保证测试**离线且确定性**。新增用例不得依赖真实网络/LLM 或本机 `.env`/`data/`。

## OpenSpec 工作流(如何接着开发新功能)

OpenSpec CLI 需各自机器安装(见 `openspec list/status/validate`;本机装在 `F:\dev\ai\npm-global`,另机另行安装)。
助手命令与 skill 已入库 `.claude/`。标准流程(**在仓库内对 Claude 说**):

1. `/opsx:propose "想做的功能"` → 生成 change(proposal/spec/design/tasks)
2. `/opsx:apply` → 按 tasks 实现 + 补测试,每步校验
3. `/opsx:archive` → 通过后归档,delta 同步进主 spec
4. 复查:`openspec validate <change>`;archive 前保证 `openspec validate` 全绿

格式铁律:requirements 用 `### Requirement:` + `#### Scenario:`(WHEN/THEN),**必须精确 4 个 `#`**。

## 安全与合入

- `.env`、`data/`、`.claude/settings.local.json` 永不入库(gitignore 已挡)。
- commit 前 `git status` 复核无密钥文件。
- CI 在 `.github/workflows/ci.yml`(跑 pytest+ruff)。

## Roadmap(README 同步)

未做(按序):接入真实途牛分销/MCP → 价格历史查询接口与买点提示 → 美团/携程供应商 → 补腾讯/百度 POI key 拿真实「多平台确认」→ 解析「国庆」等相对日期 → 多城市串联行程优化。
