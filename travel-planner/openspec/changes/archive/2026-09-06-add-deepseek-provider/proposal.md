## Why

当前后端的大模型层只支持 Anthropic(Claude)协议:意图解析与逐日规划都用 `anthropic` SDK 的 `messages.parse(output_format=...)` 结构化输出,实时网页检索用 Anthropic 专有 `web_search` 服务端工具。用户在国内更常用 DeepSeek 等 **OpenAI 兼容** 供应商,其协议(`/chat/completions` + JSON 模式)与 Anthropic 不通用。本变更在不破坏现有 Anthropic 路径的前提下,新增一个「供应商」维度,让运行时配置能切换 Anthropic 与 OpenAI 兼容(DeepSeek)两种后端。

## What Changes

- **运行期配置**(`app/model_runtime.py`):新增 `provider` 字段(`anthropic` 默认 / `openai`),支持持久化与环境变量 `PLANNER_PROVIDER`;模型默认值随供应商切换(`openai` 默认 `deepseek-chat`)。
- **LLM 层**(`app/llm.py`):`parse_intent` / `build_plan` 按供应商分流——`openai` 走新增的 `_openai_parse()`(httpx POST `/chat/completions` + `response_format=json_object`,pydantic 校验);`gather_live_info` 对非 Anthropic 供应商返回空(禁用实时网页检索)。
- **接口**(`app/main.py`):`test_model_config` 按供应商分别验证(Anthropic 用 `models.retrieve`,`openai` 用 `GET /models`)。
- **页面**(`app/web/index.html`):「⚙️ 模型配置」新增供应商下拉(Anthropic / OpenAI 兼容),切换时提示正确的 base_url 与模型默认值。
- **测试**(`tests/test_plan.py`):供应商切换的配置往返、`_openai_parse` 的 JSON 模式解析(mock httpx)、非 Anthropic 时 `gather_live_info` 返回空。

## Capabilities

### New Capabilities
(无 —— 在既有 `model-config` spec 下扩展)

### Modified Capabilities
- `model-config`: 扩展运行时模型配置,新增「供应商」维度与 OpenAI 兼容(DeepSeek)调用路径。

## Impact

- **代码**: 修改 `app/model_runtime.py`(provider 字段)、`app/llm.py`(分流 + `_openai_parse`)、`app/main.py`(test 分流)、`app/web/index.html`(供应商下拉)、`tests/test_plan.py`(新增用例)。
- **依赖**: 无新增(复用既有 `httpx`)。
- **向后兼容**: 默认 `provider=anthropic`,现有配置与行为不变;演示模式(无 key)不受影响。
- **限制**: OpenAI 兼容协议不支持 Anthropic `web_search` 工具,故 `provider=openai` 时实时网页检索不可用(`web_research_used=false`)。
