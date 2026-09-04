# itinerary-planning spec delta

## Added Requirements

### Requirement: POI 返回地图链接与封面图
系统 SHALL 在向多个 POI 平台检索景点时,提取并返回地图详情页链接(`url`)和首张封面图 URL(`image_url`);Mock 兜底时构造高德搜索链接作为 `url`。

#### Scenario: 高德平台返回景点含图片和详情页 URL
- **WHEN** 高德 API 返回某景点含 `photos` 数组和 `id` 字段
- **THEN** 系统取 `photos[0].url` 作为 `image_url`,构造 `https://uri.amap.com/poi/{id}` 作为 `url`

#### Scenario: 无真实 key 时 Mock 景点也有地图链接
- **WHEN** 系统使用 MockPoiProvider 返回内置景点
- **THEN** 每个景点的 `url` 为 `https://uri.amap.com/search?query={name}&city={city}`,`image_url` 为 None

### Requirement: 前端景点表格展示图片与链接
系统 SHALL 在网页演示界面的景点表格中,新增「图片」列(缩略图 64x48,点击放大)和「详情」列(地图详情页链接);图片加载失败时自动显示占位符。

#### Scenario: 景点有封面图
- **WHEN** POI 的 `image_url` 非空
- **THEN** 表格图片列显示该 URL 的缩略图,点击可放大查看

#### Scenario: 景点无封面图
- **WHEN** POI 的 `image_url` 为空
- **THEN** 表格图片列显示 📷 占位符

### Requirement: 景点分布地图
系统 SHALL 在景点表格上方绘制交互式 SVG 景点分布地图,使用 POI 的 `lng/lat` 坐标标点;hover 显示名称/票价/链接,click 跳转地图详情页;坐标数据不足(＜2 个)时显示提示信息。

#### Scenario: 有足够带坐标的景点
- **WHEN** 响应中 ≥2 个 POI 含有效 `lng` 和 `lat`
- **THEN** 渲染 SVG 散点图,每个景点一个彩色圆点+名称标签,hover 显示 tooltip

#### Scenario: 坐标数据不足
- **WHEN** 响应中 ＜2 个 POI 含有效 `lng` 和 `lat`
- **THEN** 显示「景点坐标数据不足,无法绘制分布图」提示

### Requirement: 行程卡片富化展示
系统 SHALL 在逐日行程卡片中,自动匹配 `activities` 文本中的景点名,匹配到的景点在对应活动项旁嵌入缩略图和地图链接。

#### Scenario: 活动文本包含已知景点名
- **WHEN** 某日 `activities` 中某条文本包含 `pois` 列表中某景点的完整名称
- **THEN** 在该活动项前嵌入 32x24 缩略图和「[地图]」链接
