## Why

当前景点(POI)数据只有名称/地址/类别/票价等基础字段,前端表格仅 5 列纯文本。用户希望规划结果更直观:景点有图片、有地图链接、有交互式分布图、行程卡片也展示景点信息。本变更在不改变两段式 workflow 架构的前提下,从数据层到展示层全面丰富 POI 信息。

## What Changes

- **POI 模型扩展**(`app/models.py`):新增 `url`(地图详情页链接)、`image_url`(首张封面图)、`website`(官网/百科链接)三个可选字段。
- **Provider 数据提取**(`app/poi.py`):高德提取 `photos` 首图 + 构造 POI 详情页 URL;腾讯提取 `imgs` 首图 + 详情页 URL;百度提取 `detail_info.thumbnail` 和 `detail_url`;Mock 景点加高德搜索链接。合并逻辑优先保留有 url/image_url 的记录。
- **LLM prompt 增强**(`app/llm.py`):`_poi_line()` 加入链接信息;`gather_live_info()` 扩展收集官网链接。
- **前端全面升级**(`app/web/index.html`):景点表格加图片缩略图列+地图链接列;SVG 交互式景点分布地图(基于 lng/lat);行程卡片自动匹配景点名并嵌入小图+链接;完整暗色主题适配;图片点击放大 lightbox。
- **测试增强**(`tests/test_plan.py`):验证 POI url/image_url 字段传递。

非目标:不接入真实图片存储服务(直接外链 POI provider 返回的 URL);不做地图 JS API 嵌入(用 SVG 散点图替代,无需额外 key)。

## Capabilities

### New Capabilities
(无 —— 在既有 `itinerary-planning` spec 下扩展)

### Modified Capabilities
- `itinerary-planning`: 扩展多平台交叉检索景点的返回数据,增加图片与地图链接字段;扩展网页演示界面,增加图片展示与景点分布地图。

## Impact

- **代码**: 修改 `app/models.py`(Poi 加 3 字段)、`app/poi.py`(4 个 Provider 提取 URL/图片)、`app/llm.py`(_poi_line 加链接)、`app/web/index.html`(表格/地图/卡片全面升级)、`tests/test_plan.py`(新字段验证)。
- **向后兼容**: 新字段均为 `Optional`,现有调用方不受影响;前端表格列增加但不影响已有数据渲染。
- **API**: `POST /api/plan` 响应中 `pois[]` 新增 `url`/`image_url`/`website` 字段(可能为 null)。
- **依赖**: 无新增。
