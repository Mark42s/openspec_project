## Why

演示页收到「苏州出发,国庆去周边自驾 6 天」这类**周边游**需求会报"无法确定目的地":既有解析只认"去某具体城市",也不理解"周边/自驾"语义;且城市词表过小(缺苏州等常见城市),演示模式 heuristic 无法识别出发地。

## What Changes

- 意图解析扩展:**城市词表扩充**(增加苏州、无锡、扬州、宁波、珠海等常见城市)。
- **周边游语义**:当用户未指明具体目的地但提到 周边/自驾/附近/省内 等,把目的地设为出发地、`local_tour=true`,不再报"目的地缺失"。
- `TripRequest` 新增 `local_tour` 字段;周边游时**清空城际交通**(交通费计 0),规划围绕出发地本地/周边,`note` 标注周边自驾。
- 启发式/LLM 两条解析路径同步支持(LLM prompt 加入周边规则)。

非目标:周边游的具体郊县路线推荐、跨城串联、真实交通接入。

## Capabilities

### New Capabilities

(无)

### Modified Capabilities

- `travel-planner`: 在"解析自然语言旅行需求"能力上新增周边游支持——未指明具体目的地时以出发地为游览中心,不再视为缺目的地。

## Impact

- **代码**:`app/models.py`(TripRequest.local_tour)、`app/llm.py`(城市表/解析启发式/LLM 规则/演示分日与 note)、`app/main.py`(周边游清空城际交通)。
- **测试**:`tests/test_plan.py` 增周边游解析与端到端用例。
- **OpenSpec**:delta 并入 `openspec/specs/travel-planner/spec.md`。
