## Purpose

在已有的交通/酒店比价之上,让用户提交一段自然语言旅行需求后,得到一份真正可用的旅行计划:系统会多平台交叉检索真实景点、按偏好/天数/预算逐日排行程、确定性计算费用,并通过极简网页展示。

## ADDED Requirements

### Requirement: 多平台交叉检索景点
系统 SHALL 向多个已配置的 POI 平台(高德/腾讯/百度)并发检索目标城市景点,并按名称归一化做**交叉验证**:同一景点被 ≥2 个平台命中记为可信,仅 1 个平台出现则保留但标记为未验证。

#### Scenario: 景点被两个平台同时命中
- **WHEN** 系统查询某城市「博物馆」类 POI,返回中兵马俑在 高德 与 腾讯 均出现且名称归一化后一致
- **THEN** 该景点 `verified` 为 true,`sources` 列出两个平台名

#### Scenario: 景点仅被单一平台返回
- **WHEN** 某候选景点只出现在一个平台的结果中
- **THEN** 系统仍返回该景点,但 `verified` 为 false,并在响应中标注其来源单一,提示真实性待人工确认

#### Scenario: 未配置任何平台密钥
- **WHEN** 环境未配置高德/腾讯/百度任一密钥
- **THEN** 系统自动使用内置的真实知名景点数据(mock)保证可演示,并在结果中标明 `is_mock`

### Requirement: 逐日行程规划
系统 SHALL 根据用户的偏好(老人/亲子/慢节奏等)、天数与预算,把检索到的景点与交通/住宿候选组织成 day-by-day 行程;预算不足时应显式提示而不伪造低价。

#### Scenario: 带老人的慢节奏行程
- **WHEN** 用户需求含「带老人」且总天数 5 天
- **THEN** 系统返回 5 天的逐日安排,每日景点数量受控并包含返程日的宽松安排,且各日说明体现慢节奏

#### Scenario: 预算不足
- **WHEN** 所有候选与门票累加超出用户人均预算
- **THEN** 系统标记 `over_budget` 并给出最接近预算的替代建议,而不是虚构更低价格

### Requirement: 确定性费用计算
系统 SHALL 用规则(而非模型心算)计算费用,至少含往返交通、住宿、景点门票与每日餐饮,并给出人均花费。

#### Scenario: 返回费用分解
- **WHEN** 规划完成且包含交通、酒店与 N 个景点
- **THEN** 系统返回 `cost_breakdown`,含 `transport/hotels/tickets/meals/total/per_person` 各分项

### Requirement: 网页演示界面
系统 SHALL 在根路径提供一个无需构建的单页:用户输入自然语言需求即可看到逐日行程、费用与来源标注。

#### Scenario: 打开根路径
- **WHEN** 用户访问 `/`
- **THEN** 系统返回可直接提交需求的 HTML 页面

### Requirement: 可选的实时资讯检索
系统 SHALL 在 `WEB_RESEARCH_ENABLED=1` 且配置了模型密钥时,对 top 景点做有界的网页搜索补充最新开放时间/票价,并在响应标 `web_research_used=true`;默认关闭时不做该检索。

#### Scenario: 开启实时检索
- **WHEN** 用户请求开启且条件满足
- **THEN** 系统返回的行程包含实时资讯文本段,且 `web_research_used` 为 true

#### Scenario: 默认关闭
- **WHEN** 未开启(默认)或无模型密钥
- **THEN** 系统不使用网页搜索,`web_research_used` 为 false,规划仍可用
