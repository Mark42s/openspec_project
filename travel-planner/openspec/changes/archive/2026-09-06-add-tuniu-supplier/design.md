# 设计:接入途牛 MCP 开放平台(真实交通/酒店检索)

## 背景与协议

途牛 MCP 开放平台以 JSON-RPC 2.0 over MCP 暴露业务能力,端点按服务拆分:

| 服务 | 端点 | 检索工具 |
|---|---|---|
| 火车 | `https://openapi.tuniu.cn/mcp/train` | `searchLowestPriceTrain` |
| 机票 | `https://openapi.tuniu.cn/mcp/flight` | `searchLowestPriceFlight` |
| 酒店 | `https://openapi.tuniu.cn/mcp/hotel` | `tuniuHotelSearch` |

认证:自定义头 `apiKey: <TUNIU_API_KEY>`(非 `Authorization`)。请求体 `{jsonrpc, id, method:"tools/call", params:{name, arguments}}`;`Accept` 必须同时含 `application/json` 与 `text/event-stream`(否则 406)。工具结果在 `result.content[0].text`,是一个 **JSON 字符串**,需二次解析。

## 字段映射

- **火车**: `trainNum→operator`、`departStationName/destStationName→departure_station/arrival_station`、`departureTime/arrivalTime→HH:MM`、座位价按 `二等座(edzPrice)→一等座(ydzPrice)→商务座(swzPrice)→无座(wzPrice)` 取第一个可用者作为该车次参考价与 `travel_class`。价格为字符串,需 `float`。
- **机票**: `flightNumber→operator`、`departureAirport+departureTerminal→departure_station`、`price = basePrice + totalTax`、`cabinClass→travel_class`。
- **酒店**: `hotelName→name`、`roomName→room_type`、`lowestPrice→price_per_night`、`commentScore→rating`、`refund` 非「不可取消」→ `is_refundable=true`。

## 供应商选择(resolve_suppliers)

`resolve_suppliers()` 改为:有 `TUNIU_API_KEY` → 返回 `[TuniuAdapter()]`;否则 `[MockAdapter()]`。**真实源与 mock 不同时出现**,避免假车次混入真实结果。`is_mock = all(s.name == "mock")` 据此正确为 `false`。

## 日期解析兜底

真实供应商对过去日期返回「无结果」,而 LLM(尤其 DeepSeek)可能把「9月29日」解析成错误年份。两层修复:1) `parse_intent` 在提示里注入 `今天是 <iso>` 并说明按今年/明年解析;2) 确定性 `_clamp_start_date()`:若 `start_date < today`,保留月日、逐年 +1 直到不早于今天(处理 2/29 非闰年)。兜底在 `parse_intent` 统一出口执行,覆盖 openai 与 anthropic 两路。

## 风险 / 说明

- 途牛返回的 `commentScore` 是 1~5 整数分(实测均为 5),非 4.x 小数,展示时需知晓。
- 机票按单一 `origin` 城市搜;「无锡机场出发」需后续加「出发机场」字段(见 proposal Impact)。
- 本期只做检索不下单;途牛同时提供 `bookTrain`/`tuniuHotelCreateOrder`/`saveOrder` 等下单工具,留待后续 change。
