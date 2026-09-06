# model-config spec delta

## Added Requirements

### Requirement: 供应商可切换为 OpenAI 兼容协议
系统 SHALL 在运行时模型配置中新增 `provider` 字段,取值 `anthropic`(默认)或 `openai`;当为 `openai` 时,意图解析与逐日规划改用 OpenAI 兼容的 `/chat/completions` + JSON 模式调用。

#### Scenario: 切换到 OpenAI 兼容供应商
- **WHEN** 配置 `provider=openai` 且提供 `api_key`
- **THEN** `parse_intent` 与 `build_plan` 通过 `POST {base_url}/chat/completions` 以 `response_format=json_object` 调用,并用 pydantic 校验返回 JSON

#### Scenario: OpenAI 兼容供应商未指定 base_url
- **WHEN** `provider=openai` 且未配置 `base_url`
- **THEN** 系统默认使用 `https://api.deepseek.com`

#### Scenario: 保持 Anthropic 默认
- **WHEN** `provider` 未设置或为 `anthropic`
- **THEN** 沿用 Anthropic `messages.parse(output_format=...)` 结构化输出,行为不变

### Requirement: 模型默认值随供应商切换
系统 SHALL 在 `provider=openai` 且未显式指定模型时,默认使用 `deepseek-chat`;`provider=anthropic` 时沿用 `claude-*` 默认值。

#### Scenario: OpenAI 兼容供应商未指定模型
- **WHEN** `provider=openai` 且 `parse_model`/`plan_model` 为空
- **THEN** 解析与规划模型均解析为 `deepseek-chat`

### Requirement: 实时网页检索仅 Anthropic 供应商可用
系统 SHALL 在 `provider=openai` 时禁用实时网页检索(`gather_live_info` 返回空串),因为 OpenAI 兼容协议不支持 Anthropic 的 `web_search` 服务端工具。

#### Scenario: OpenAI 兼容供应商请求实时资讯
- **WHEN** `provider=openai` 且请求启用实时网页检索
- **THEN** `gather_live_info` 返回空串,`PlanResponse.web_research_used` 为 `false`

### Requirement: 页面可配置供应商
系统 SHALL 在网页「⚙️ 模型配置」面板提供供应商下拉(Anthropic / OpenAI 兼容),保存后即时生效;选择 OpenAI 兼容时提示 base_url 默认值与模型默认值。

#### Scenario: 在页面切换供应商并保存
- **WHEN** 用户在配置面板选择「OpenAI 兼容」并保存
- **THEN** 后端 `provider` 持久化为 `openai`,后续规划走 OpenAI 兼容路径

### Requirement: 连接测试支持两种供应商
系统 SHALL 让「测试连接」按供应商分别验证连通性:Anthropic 用 `models.retrieve`,OpenAI 兼容用 `GET /models`。

#### Scenario: 测试 OpenAI 兼容供应商
- **WHEN** 用户对 `provider=openai` 的配置点「测试连接」
- **THEN** 系统对 `{base_url}/models` 发起 GET 并据状态码返回成功或失败
