# travel-planner spec delta

## ADDED Requirements

### Requirement: 解析出行场景字段(晕车/体力档/轻装)
系统 SHALL 在意图解析时从文本识别出行场景约束并填入结构化字段：声明晕车（"我晕车/容易晕/山路怕晕"等）置 `motion_sickness=true`；明确节奏偏好时置 `travel_pace`（relaxed/standard/intensive，未提为 standard）；声明不想携带大件行李（"不拖行李/轻装/背包就走"等）置 `pack_light=true`。识别采用"模型提示 + 确定性词表兜底"双层：LLM 漏识别时由确定性规则保证置位；refine 追问中再次提到时更新，未提及则保持原值。

#### Scenario: 完整自然语言声明场景
- **WHEN** 用户输入"我有点晕车，这次想轻装，节奏不要太赶"
- **THEN** 解析结果 `motion_sickness=true`、`travel_pace=relaxed`、`pack_light=true`

#### Scenario: 模型漏识别但文本命中词表
- **WHEN** 模型输出未置位，但原文含"晕车""容易晕"等词
- **THEN** 确定性规则将 `motion_sickness` 置为 true

#### Scenario: refine 追问中提及场景
- **WHEN** 用户对既有会话反馈"其实我晕车，汽车别坐太久"
- **THEN** 新约束 `motion_sickness=true`；未提及的其它场景字段保持原值
