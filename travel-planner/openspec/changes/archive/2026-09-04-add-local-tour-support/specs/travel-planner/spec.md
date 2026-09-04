## ADDED Requirements

### Requirement: 支持周边游(未指明具体目的地)需求
系统 SHALL 在用户未指明具体目的地但表达"周边/自驾/附近/省内"等周边游意图时,以出发地作为游览中心解析(destinations=[出发地]、local_tour=true),而不是报目的地缺失;规划应按本地/周边理解,不计入长途城际交通。

#### Scenario: 周边自驾且明确出发地
- **WHEN** 用户提交「苏州出发,国庆节带娃去周边自驾,6 天」且没有指定具体目的地
- **THEN** 系统解析出出发地=苏州、天数=6、local_tour=true,返回围绕苏州本地/周边的 6 天计划,费用不含城际交通(transport=0)

#### Scenario: 仍有具体城市目的地
- **WHEN** 用户明确说「去杭州」等具体目的地
- **THEN** 系统保持原语义解析,local_tour=false,按城际交通规划
