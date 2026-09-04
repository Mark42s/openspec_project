## 1. 数据模型扩展(app/models.py)

- [x] 1.1 新增 `Poi`(name/address/location/category/sources/verified/rating/ticket_price/open_hours/description/is_mock)与 `ItineraryDay`(day/title/activities/lodging_note),验证可构造与 JSON 序列化
- [x] 1.2 新增 `CostBreakdown`(transport/hotels/tickets/meals/total/per_person),验证字段校验
- [x] 1.3 扩展 `PlanResponse`:增 `days`、`pois`、`cost_breakdown`、`web_research_used`(默认 False),验证反序列化 round-trip

## 2. 多平台景点交叉(app/poi.py)

- [x] 2.1 定义 `PoiProvider` ABC 与 `PoiProviderResult`,验证可被实现类实例化
- [x] 2.2 实现 `AmapProvider`(GET restapi.amap.com/v3/place/text)、`TencentProvider`(apis.map.qq.com/ws/place/v1/search)、`BaiduProvider`(api.map.baidu.com/place/v2/search),各 key 从环境读取,验证单测用 httpx MockTransport 断言请求 URL 与字段解析
- [x] 2.3 实现 `MockPoiProvider`(内置真实知名景点名单,如西安:兵马俑/大雁塔/钟楼/回民街),验证无 key 时可返回且 `is_mock` 标记
- [x] 2.4 实现偏好→关键词映射(人文/美食/自然/亲子/默认),验证映射函数输出符合预期
- [x] 2.5 实现名称归一化(去空白/去常见后缀)与交叉验证(≥2 平台命中 verified=True),验证两条:双源命中 → verified,单源 → verified=False
- [x] 2.6 实现 `search_pois(city, keywords) -> list[Poi]`(并发查源、交叉、排序),并实现 `resolve_poi_providers()`,验证 0 个 key 时仅 mock、单 provider 抛错不影响整体

## 3. 确定性费用计算(app/costing.py)

- [x] 3.1 实现 `estimate_cost(request, transport, hotel, pois) -> CostBreakdown`(transport 取最低×2、hotels×晚数、tickets 各 POI 门票、meals 天数×人数×档),验证固定输入输出确定值
- [x] 3.2 晚数=days-1、人数=adults+elders+children 等口径与既有 `llm.demo` 一致,验证 demo 模式下 cost 与响应一致

## 4. 逐日规划 + 实时资讯(app/llm.py)

- [x] 4.1 把 `build_plan` 升级:读入 `Poi[]` 与 `CostBreakdown`,结构化输出含 `days[]`(逐日)与既有字段,验证有 key 路径的 output schema 覆盖新字段
- [x] 4.2 无 key 演示规划改为确定性分日(首日 1-2 点/中间轮转/末日宽松;带老人每日上限 2 点加午休),验证 3 天 demo 输出 days 结构、预算不足仍 over_budget
- [x] 4.3 新增 `gather_live_info(pois) -> str`:仅 `WEB_RESEARCH_ENABLED=1` 且 configured 时用 `web_search_20260209` 有界(≤3 次)抓实时开放时间/票价/攻略并返回压缩文本,否则返回空串;验证关/无 key 返回空且无网络调用
- [x] 4.4 `main` 链路把 live 文本并入规划 prompt,并按是否使用置 `web_research_used`

## 5. 链路与网页(app/main.py + app/web/index.html)

- [x] 5.1 `_run_plan` 增加:检索 POI(按目的地+偏好关键词)→ 费用计算 → 规划(含 live)步骤,并把 `days/pois/cost_breakdown/web_research_used` 填进响应,验证完整 JSON 各字段存在
- [x] 5.2 `POST /api/plan` 响应模型用扩展后的 `PlanResponse`;`/healthz` 增 `poi_providers` 启用列表,验证返回正确
- [x] 5.3 新增 `app/web/index.html`(单文件、fetch /api/plan、渲染逐日/费用/来源/实时标记)与 `GET /` 返回该页面,验证 curl `/` 返回 200 且含表单

## 6. 测试与收尾

- [x] 6.1 补充 `tests/test_plan.py`:POI 交叉(双源 verified/单源未验证/无 key mock)、费用确定性、逐日演示(days 非空且天数匹配)、`GET /` 200、`WEB_RESEARCH_ENABLED=0` 时 `web_research_used=false`,验证 `pytest` 通过
- [x] 6.2 `ruff check .` 通过
- [x] 6.3 更新 `.env.example`(AMAP/TENCENT_MAP/BAIDU_MAP key、POI_PROVIDERS、WEB_RESEARCH_ENABLED)与 `README.md`(新能力、网页用法、key 申请提示),验证文档示例与实现一致
