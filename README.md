# Travel Planner

根据一段**自然语言旅行需求**,自动并发检索国内机票/车票/酒店报价、去重比价,再由大模型汇总成**结构化行程建议**,并记录每次价格快照的 FastAPI 服务。

> ⚠️ **免责声明**:本服务(MVP)默认以确定性 mock 数据运行,价格**不是真实可用价**,仅用于演示流程与本地联调。任何报价请以实际下单平台的页面为准;服务**不会**代表你下单、支付或退改。

---

## 特性

- **自然语言 → 结构化约束**:解析出发地/目的地/日期/天数/人数/预算/偏好,缺失字段显式标记。
- **多源并发检索 + 去重**:供应商适配层统一接口,同车次/房型多源合并取最低价;单个源失败不影响整体。
- **多平台景点交叉检索**:高德/腾讯/百度 并发查 POI,≥2 平台命中标记「多平台确认」;无 key 回落内置真实知名景点。
- **逐日行程规划**:按偏好(带老人/亲子/慢节奏)/天数/预算组织 day-by-day,首日安顿、末日宽松。
- **确定性费用计算**:往返交通 + 住宿 + 门票 + 每日餐饮,分解与人均为规则计算(不经模型心算)。
- **可选的实时网页检索**(默认关):对 top 景点用 Claude 网页搜索补最新开放时间/票价/攻略,响应标注 `web_research_used`。
- **价格快照**:每次检索自动落 SQLite(`price_snapshots`),为未来价格走势分析留底。
- **无凭证兜底**:未配置 `ANTHROPIC_API_KEY` 时进入**演示模式**(确定性建议),本地与 CI 无需真实模型即可端到端跑通。
- **网页演示**:`GET /` 单文件页面,输入需求即见逐日行程、费用与来源。
- **规格驱动**:全流程用 [OpenSpec](https://github.com/Fission-AI/OpenSpec) 管理,规格在 [`openspec/`](openspec/)。

## 架构

```
        POST /api/plan { text }
                  │
        ┌─────────▼─────────┐   受控两段式 workflow(design.md D1)
        │  意图解析          │   LLM① structured output → TripRequest
        │  (轻量模型)        │   无 key → 确定性规则解析
        └─────────┬─────────┘
                  │ TripRequest(缺失字段已标记)
        ┌─────────▼─────────┐   确定性并发代码,不经 LLM(D1)
        │  检索聚合          │   resolve_suppliers() → Mock / Tuniu(占位)
        │  retrieval.py     │   并发查询 → dedup → 规则初筛 top-N
        └─────────┬─────────┘
                  ▼
        ┌───────────────────┐   快照写入 SQLite(store.py)
        │  price_snapshots   │
        └───────────────────┘
        ┌─────────▼─────────┐   LLM② 读 top-N 候选做权衡
        │  汇总建议          │   structured output → PlanResponse
        └───────────────────┘
```

设计取舍(为何不让模型自主反复搜索):旅行规划候选空间形状确定,确定性并发查表比模型逐个调工具**更准、更快、便宜一个量级**(token 估算见下)。

## 快速开始(本地)

要求 Python ≥ 3.11。

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"

# 无 ANTHROPIC_API_KEY 也能跑(演示模式):
uvicorn app.main:app --reload
```

调用:

```bash
curl -s -X POST localhost:8000/api/plan \
  -H "Content-Type: application/json" \
  -d '{"text":"上海出发带老人去西安5天人均3000偏人文"}'
```

浏览器打开 <http://localhost:8000> 可直接在网页输入需求,查看逐日行程/费用/景点来源。

### 在页面启用真实大模型(可选)

打开页面顶部的「⚙️ 模型配置」,填入 Anthropic API Key(可再选 Base URL/解析与规划模型)→ **保存** → **测试连接** 即可。保存后无需重启:
语义理解(意图解析)、逐日规划与可选实时网页搜索会切到真实大模型;不配则始终为内置演示模式。
Key 明文持久化在 `data/model_config.json`(**已被 gitignore**,不入库),接口只回传掩码;请自行妥善保管。

连真实模型:把 `ANTHROPIC_API_KEY` 填入 `.env`(参考 `.env.example`);模型路由见下表。健康检查:`curl localhost:8000/healthz`。

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `ANTHROPIC_API_KEY` | 空 | 为空时进入演示模式(mock + 确定性建议) |
| `PLANNER_PARSE_MODEL` | `claude-haiku-4-5` | 意图解析模型(轻量档) |
| `PLANNER_PLAN_MODEL` | `claude-sonnet-5` | 汇总建议模型(可升 `claude-opus-5`) |
| `TUNIU_API_KEY` | 空 | 途牛凭证(本期为占位;缺则自动回落 mock) |
| `TUNIU_ENABLED` | `0` | 置 `1` 才尝试途牛 |
| `PLANNER_DB_PATH` | `data/travel.db` | SQLite 快照路径 |
| `AMAP_KEY` / `TENCENT_MAP_KEY` / `BAIDU_MAP_KEY` | 空 | 高德/腾讯/百度 POI 密钥(多平台交叉;配 1~2 个即生效) |
| `POI_PROVIDERS` | `amap,tencent,baidu` | 启用的 POI 平台;缺 key 自动跳过,一个不配则回落内置演示景点 |
| `WEB_RESEARCH_ENABLED` | `0` | 置 `1` 启用实时网页检索(或用接口 `web_research: true` 单次开启) |

## Docker 部署

```bash
cp .env.example .env     # 填 ANTHROPIC_API_KEY
docker compose up --build
```

镜像暴露 `8000`。数据库经 volume `planner-data` 持久化到 `/data/travel.db`。

## LLM 成本参考(每次规划,2026-09 官方价)

两段式受控调用 + 候选经规则初筛,单次完整规划 token 用量可控。参考值:

| 路由 | 累计输入 | 累计输出 | 参考成本 |
|---|---|---|---|
| 意图解析 Haiku + 汇总 Sonnet(默认) | ~12–18k | ~3–4k | ≈ ¥0.3–0.6 |
| 全 Sonnet | ~12–18k | ~3–4k | ≈ ¥0.4–0.7 |
| 全 Opus(质量优先) | ~12–18k | ~3–4k | ≈ ¥1–1.5 |

> 量级结论:个人自用、每天规划数次,月成本在几十元内;主要成本在未来真实供应商 API 配额。**如果改成让模型自主循环查源**,同样任务可达每次 ¥3–17,故本项目刻意采用受控 workflow。

## OpenSpec(规格驱动开发)

- 变更:查看进行中/历史变更 `openspec list`
- 新增功能:在本仓库内对 AI 说 `/opsx:propose "想做的功能"`,评审后再 `/opsx:apply`
- 归档:`/opsx:archive`
- 能力规格:`openspec/specs/travel-planner/spec.md` 与 `openspec/specs/itinerary-planning/spec.md`(归档后由 change delta 同步)

CLI:`openspec status / validate / show add-travel-planner-mvp / show add-itinerary-planning`

## Roadmap

- [x] 多平台景点交叉 + 逐日行程 + 费用分解 + 网页 + 实时资讯(2026-09-04)
- [ ] 接入真实途牛(官方 MCP 开放平台 / 分销 API,独立 change)
- [ ] 价格历史查询接口与走势/买点提示
- [ ] 多供应商并行(美团/携程)
- [ ] 多城市串联行程优化
