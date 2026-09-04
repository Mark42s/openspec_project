# Design: POI Enrichment

## D1: 数据流架构

```
真实 Provider API                    Mock Provider
┌─────────────────┐                 ┌──────────────────┐
│ Amap photos[]   │─────────┐       │ 高德搜索链接 URL  │
│ Amap id→URL     │         │       │ 固定景点名/地址   │
├─────────────────┤         │       └────────┬─────────┘
│ Tencent imgs[]  │─────────┤                │
│ Tencent id→URL  │         │ 合并逻辑       │
├─────────────────┤    ┌────▼──────┐    ┌────▼─────┐
│ Baidu thumbnail │────│search_pois│◄───│ MockPoi  │
│ Baidu detail_url│    │(cross-    │    └──────────┘
└─────────────────┘    │ verify)   │
                       └─────┬─────┘
                             │ Poi{url, image_url, ...}
                       ┌─────▼─────┐
                       │ build_plan│
                       │ (LLM)     │
                       └─────┬─────┘
                             │ PlanResponse.pois[]
                       ┌─────▼─────────┐
                       │ index.html    │
                       │ table+map+card│
                       └───────────────┘
```

## D2: 技术决策

### D2.1 地图展示方案:SVG 散点图 vs 高德 JS API

**选择 SVG 散点图。** 理由:
- 高德 JS API 需要单独的 Web JS Key(与 REST API Key 不同),增加配置负担
- POI 已有 `lng/lat` 字段,SVG 散点图即可表达相对位置关系
- 无需额外网络请求,性能更好
- 暗色主题适配更可控

### D2.2 图片来源:直接外链 vs 自行存储

**选择直接外链 Provider 返回的 URL。** 理由:
- MVP 阶段不引入图片存储/CDN 复杂度
- 高德/腾讯/百度 API 返回的图片 URL 可直接用于 `<img>` 标签
- 图片加载失败时自动 fallback 到占位符

### D2.3 Mock POI 地图链接:构造搜索 URL vs 固定 URL

**选择构造高德搜索 URL** (`uri.amap.com/search?query=...&city=...`)。理由:
- Mock 景点没有真实 POI id,无法构造详情页 URL
- 搜索 URL 对任意景点名都有效,且能引导用户到高德查看真实信息
- 不需要额外的 API key

## D3: 向后兼容策略

- 新字段 `url`/`image_url`/`website` 均为 `Optional[str]`,默认 `None`
- 前端渲染对所有新字段做 null 检查,缺失时展示占位符
- API 响应中新增字段不影响现有客户端(只读忽略未知字段)
- 测试 autouse fixture 强制 demo 模式,不受新字段影响
