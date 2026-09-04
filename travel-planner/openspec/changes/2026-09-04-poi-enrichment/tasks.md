# Tasks: POI Enrichment

## 1. 数据层
- [x] 1.1 `app/models.py`: Poi 增加 `url`/`image_url`/`website` 三个 Optional 字段
- [x] 1.2 `app/poi.py`: AmapProvider 提取 `photos[0].url` 和构造 `uri.amap.com/poi/{id}` URL
- [x] 1.3 `app/poi.py`: TencentProvider 提取 `imgs[0]` 和构造详情页 URL
- [x] 1.4 `app/poi.py`: BaiduProvider 提取 `detail_info.thumbnail` 和 `detail_url`
- [x] 1.5 `app/poi.py`: MockPoiProvider 为每个 mock 景点构造高德搜索链接
- [x] 1.6 `app/poi.py`: `search_pois` 合并逻辑优先保留 url/image_url

## 2. LLM 层
- [x] 2.1 `app/llm.py`: `_poi_line()` 加入 url 和 image_url 信息
- [x] 2.2 `app/llm.py`: `gather_live_info()` 扩展收集官网链接

## 3. 前端层
- [x] 3.1 `app/web/index.html`: CSS 变量化(支持暗色主题)、新增图片/地图样式
- [x] 3.2 景点表格增加「图片」列(缩略图+lightbox)和「详情」列(地图链接)
- [x] 3.3 SVG 交互式景点分布地图(基于 lng/lat,固定 viewBox 避免 clientWidth=0)
- [x] 3.4 行程卡片自动匹配景点名,嵌入小图+地图链接
- [x] 3.5 图片加载失败自动 fallback 到占位符
- [x] 3.6 Lightbox 点击外部关闭

## 4. 测试
- [x] 4.1 `tests/test_plan.py`: 验证 MockPoiProvider 返回的景点都有 url 字段
- [x] 4.2 `tests/test_plan.py`: 验证 `/api/plan` 响应中 POI 的 url/image_url 字段存在

## 5. OpenSpec 文档
- [x] 5.1 `proposal.md`: 说明变更原因、内容、影响范围
- [x] 5.2 `design.md`: 数据流架构图、技术决策(D1-D3)、向后兼容策略
- [x] 5.3 `specs/itinerary-planning/spec.md`: delta spec(WHEN/THEN 格式)
- [x] 5.4 `tasks.md`: 本文件
