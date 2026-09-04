## Why

现有 MVP 只能给"比价建议",还称不上"可用的旅行计划"。用户要的 demo 应能**根据需求制定计划:搜索景点、规划逐日路线、计算费用、搜索旅游资源信息**。其中景点真实性尤其关键——单源合成不可信,需要**多平台交叉**验证。

## What Changes

- 新增 `app/poi.py`:景点检索——高德/腾讯/百度三类 POI 平台并发查询 + **名称归一化交叉验证**(≥2 平台命中视为可信),mock 真实知名景点兜底,零配置可演示。
- 新增 `app/costing.py`:**确定性费用计算**(往返交通×2 + 住宿晚数 + 门票 + 每日餐饮),不经模型心算。
- 扩展 `app/llm.py`:规划步骤升级为按天(day-by-day)输出;新增可选 `gather_live_info()`——**默认关闭**、开启时用 Claude 网页搜索补最新开放时间/票价/攻略并标记 `web_research_used`。
- 扩展数据模型 `app/models.py`:`Poi`、`ItineraryDay`、`CostBreakdown`,`PlanResponse` 增 `days/pois/cost_breakdown/web_research_used`。
- 新增极简单文件网页 `app/web/index.html`,`GET /` 直达,输入需求即可看行程与费用。
- `.env.example` 增 `AMAP_KEY/TENCENT_MAP_KEY/BAIDU_MAP_KEY`、`POI_PROVIDERS`、`WEB_RESEARCH_ENABLED`。

非目标(**边界**):多城市串联最优、跨平台价格一致性、下单/支付/退改、价格预测、真实交通/酒店接入(仍为 mock)。

## Capabilities

### New Capabilities
- `itinerary-planning`: 在已有比价基础上,多平台交叉检索真实景点、按用户偏好/天数/预算生成逐日行程、确定性计算费用,并提供网页演示与可选的实时资讯检索。

### Modified Capabilities

(无 —— 仅新增能力,不改既有 `travel-planner` 行为。)

## Impact

- **代码**:新增 `app/poi.py`、`app/costing.py`、`app/web/index.html`;修改 `app/models.py`、`app/llm.py`、`app/main.py`、`tests/test_plan.py`。
- **API**:`POST /api/plan` 响应扩展;新增 `GET /`(网页);`/healthz` 增 POI 源状态。
- **配置**:`AMAP_KEY`/`TENCENT_MAP_KEY`/`BAIDU_MAP_KEY`、`POI_PROVIDERS`、`WEB_RESEARCH_ENABLED`。
- **OpenSpec**:引入 capability `itinerary-planning` 并并入主 specs。
