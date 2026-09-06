# Design: DeepSeek(OpenAI 兼容)供应商

## D1: 数据流

```
configured() = bool(api_key)
        │
        ▼
 provider() ── anthropic ──► anthropic SDK messages.parse(output_format)
        │                           + web_search 工具(gather_live_info)
        └───── openai ────► httpx POST {base}/chat/completions
                                    response_format=json_object
                                    → pydantic model_validate(json)
```

## D2: 技术决策

### D2.1 OpenAI 兼容调用:直接 httpx vs 引入 openai SDK

**选择直接 httpx。** 理由:
- 项目已在 `app/poi.py` 直接使用 httpx 调用三平台 REST,风格一致
- OpenAI 兼容的 `/chat/completions` + JSON 模式只需一个 POST,无需完整 SDK
- 避免新增 `openai` 依赖;DeepSeek/Qwen/Moonshot 等 OpenAI 兼容服务用同一套代码

### D2.2 结构化输出:JSON 模式 + pydantic 校验

**选择 `response_format={"type":"json_object"}` + `model_validate`。** 理由:
- OpenAI 兼容协议没有 Anthropic 的 typed `output_format`
- 把 pydantic `model_json_schema()` 塞进 prompt,模型按 schema 输出 JSON
- `model_validate` 保证字段类型正确;失败时与 Anthropic 异常同路径抛出,上层兜底

### D2.3 实时网页检索:仅 Anthropic 可用

**选择对 `provider=openai` 直接返回空。** 理由:
- `web_search_20260209` 是 Anthropic 服务端工具,OpenAI 兼容协议无对应物
- 与其引入第三方搜索 API(新增 key/成本),不如在 DeepSeek 下关闭该开关,`web_research_used=false`

### D2.4 供应商默认 base_url

**选择默认 `https://api.deepseek.com`。** 理由:
- 本项目首发目标是 DeepSeek;其它 OpenAI 兼容服务用户可自行填 base_url
- 页面切换供应商时自动提示该默认值,降低误填(如 `platform.deepseek.com` 网页控制台)概率

## D3: 向后兼容

- `provider` 缺省为 `anthropic`,未设置时所有行为与现在完全一致
- 演示模式(无 key)不触发任何供应商调用,不受影响
- 测试 autouse fixture `model_runtime.reset()` 已回到环境默认(provider=anthropic),离线确定性不变
