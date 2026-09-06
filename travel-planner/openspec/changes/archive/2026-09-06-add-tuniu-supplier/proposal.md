## Why

现有交通/酒店检索只有 `MockAdapter`:车次号来自 5 个城市的硬编码表、价格是伪随机、酒店名是「城市名替换」的假数据。用户实测发现「车次错的离谱、价格缺失」——对一个要「自动检索真实出行/酒店/路线」的产品,假数据让它失去意义。

途牛 2026 年 3 月上线了国内首个 MCP 开放平台,注册登录 → 申请 API Key 即可调用,覆盖火车票、机票、酒店、门票、邮轮、度假产品,返回真实可下单数据,且**个人开发者可注册**(无企业资质门槛)。本变更把途牛接为第一个真实供应商,替换 mock,让交通/酒店检索产出真实车次、票价、到发站与酒店价格。

## What Changes

- **途牛适配器**(`app/suppliers/tuniu.py`):从占位改为真实 JSON-RPC 2.0 调用(`POST {base}/mcp/{train|flight|hotel}`,认证头 `apiKey`),把火车 `searchLowestPriceTrain`、机票 `searchLowestPriceFlight`、酒店 `tuniuHotelSearch` 的结果归一化为内部报价模型。
- **供应商选择**(`app/suppliers/__init__.py`):有 `TUNIU_API_KEY` 时用真实源,**不混入 mock**;仅全部真实源不可用时才回落 mock(避免假车次污染真实结果)。
- **报价模型**(`app/models.py`):`TransportQuote` 新增 `departure_station`/`arrival_station`(火车到发站、机票机场+航站楼),解决「怎么到达」的展示。
- **规划展示**(`app/llm.py`):`_fmt_transport` 优先展示真实到发站。
- **日期解析兜底**(`app/llm.py`):意图解析向模型注入「今天日期」,并把解析出的过去日期确定性滚动到最近的未来同月日——否则真实供应商会因过去日期拒绝查询、导致费用归零。
- **配置**(`.env.example`/`.env`):`TUNIU_API_KEY` 说明更新,移除已废弃的 `TUNIU_ENABLED`。
- **测试**(`tests/test_plan.py`):途牛字段映射(mock httpx)、供应商选择、日期滚动兜底。

## Capabilities

### New Capabilities
(无)

### Modified Capabilities
- `travel-planner`: 扩展「多源并发检索与去重 / 无凭证兜底」,新增真实途牛供应商接入与出发日期解析锚定。

## Impact

- **代码**: 修改 `app/suppliers/tuniu.py`(真实实现)、`app/suppliers/__init__.py`(供应商选择)、`app/models.py`(站点字段)、`app/llm.py`(展示 + 日期兜底)、`.env.example`/`.env`、`tests/test_plan.py`。
- **依赖**: 无新增(复用既有 `httpx`)。
- **向后兼容**: 无 `TUNIU_API_KEY` 时行为与之前完全一致(回落 mock);有 key 时真实数据替换 mock。
- **限制**: 本期只做检索不做下单;机票按单一 `origin` 城市搜索(用户「无锡机场出发」这类跨城机场需后续增加「出发机场」字段)。
