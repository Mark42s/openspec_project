# Tasks: DeepSeek(OpenAI 兼容)供应商

## 1. 运行期配置
- [x] 1.1 `app/model_runtime.py`: 新增 `provider` 字段 + `provider()` getter + `PLANNER_PROVIDER` 环境变量
- [x] 1.2 `app/model_runtime.py`: 模型默认值随供应商切换(openai → deepseek-chat)
- [x] 1.3 `app/model_runtime.py`: `set_config` / `public_info` 支持 provider

## 2. LLM 层
- [x] 2.1 `app/llm.py`: 新增 `_openai_parse()`(httpx POST /chat/completions + JSON 模式 + pydantic 校验)
- [x] 2.2 `app/llm.py`: `parse_intent` 按供应商分流
- [x] 2.3 `app/llm.py`: `build_plan` 按供应商分流
- [x] 2.4 `app/llm.py`: `gather_live_info` 对非 Anthropic 供应商返回空

## 3. 接口
- [x] 3.1 `app/main.py`: `test_model_config` 按供应商分流(openai 用 GET /models)

## 4. 前端
- [x] 4.1 `app/web/index.html`: 配置面板新增供应商下拉
- [x] 4.2 切换供应商时提示 base_url/模型默认值,保存时带 provider

## 5. 测试
- [x] 5.1 `tests/test_plan.py`: provider 配置往返 + 模型默认值随供应商
- [x] 5.2 `tests/test_plan.py`: `_openai_parse` 用 mock httpx 验证 JSON 模式解析
- [x] 5.3 `tests/test_plan.py`: 非 Anthropic 供应商 `gather_live_info` 返回空

## 6. OpenSpec 文档
- [x] 6.1 `proposal.md` / `design.md` / `specs/model-config/spec.md` / `tasks.md`
