# Tasks: 接入真实途牛供应商(火车/机票/酒店)

## 1. 途牛适配器
- [x] 1.1 `app/suppliers/tuniu.py`: 实现 JSON-RPC 2.0 客户端 `_rpc()`(端点 + apiKey 头 + SSE/JSON 解析)
- [x] 1.2 `app/suppliers/tuniu.py`: `search_transport` 接火车 `searchLowestPriceTrain` + 机票 `searchLowestPriceFlight`
- [x] 1.3 `app/suppliers/tuniu.py`: `search_hotel` 接 `tuniuHotelSearch`
- [x] 1.4 `app/suppliers/tuniu.py`: 字段映射(火车/机票/酒店 → 内部报价模型)

## 2. 供应商选择
- [x] 2.1 `app/suppliers/__init__.py`: 有 `TUNIU_API_KEY` 用真实源,无 key 回落 mock(不混入)

## 3. 报价模型与展示
- [x] 3.1 `app/models.py`: `TransportQuote` 新增 `departure_station`/`arrival_station`
- [x] 3.2 `app/llm.py`: `_fmt_transport` 优先展示真实到发站

## 4. 日期解析兜底
- [x] 4.1 `app/llm.py`: `parse_intent` 提示注入今天日期
- [x] 4.2 `app/llm.py`: 新增 `_clamp_start_date()` 过去日期滚动到未来

## 5. 配置
- [x] 5.1 `.env.example` / `.env`: `TUNIU_API_KEY` 说明,移除 `TUNIU_ENABLED`

## 6. 测试
- [x] 6.1 `tests/test_plan.py`: 途牛火车/机票字段映射(mock httpx)
- [x] 6.2 `tests/test_plan.py`: 途牛酒店字段映射(mock httpx)
- [x] 6.3 `tests/test_plan.py`: 供应商选择(有 key → tuniu / 无 key → mock)
- [x] 6.4 `tests/test_plan.py`: `_clamp_start_date` 滚动兜底

## 7. OpenSpec 文档
- [x] 7.1 `proposal.md` / `design.md` / `specs/travel-planner/spec.md` / `tasks.md`
