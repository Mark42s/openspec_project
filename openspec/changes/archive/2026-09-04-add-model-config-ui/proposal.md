## Why

演示页目前只能用内置启发式+模拟数据跑(未配 key),无法在网页里"把真实大模型能力打开"来增强语义理解、逐日规划与实时网页搜索。用户需要在页面直接配置 Anthropic API Key(及可选 Base URL/模型),保存后即时生效,无需改文件或重启。

## What Changes

- 新增运行期配置模块 `app/model_runtime.py`:内存保存 API Key / Base URL / 解析模型 / 规划模型,支持持久化到 `data/model_config.json`(已 gitignore),优先级 页面设置 > 持久化 > .env > 默认。
- `app/llm.py` 改为从运行期配置取 `configured/_client/parse_model/plan_model`,保存后**即时生效**。
- 新增 API:`GET /api/config/model`、`POST /api/config/model`(保存/清除)、`POST /api/config/model/test`(连通测试,仅查模型元数据,不耗生成 token)。
- 页面新增"⚙️ 模型配置"区:填 Key(密码框)/Base URL/解析模型/规划模型,保存/测试/清除;响应**不回显完整 key**(只给掩码)。
- 测试隔离:`pytest` fixture 重置运行期配置,忽略持久化文件。

非目标:多 provider(OpenAI/DeepSeek 等)接入、密钥托管/加密、费率限制。

## Capabilities

### New Capabilities

- `model-config`: 提供运行期的大模型配置能力——页面/API 可保存 Anthropic Key 与模型选择、即时生效、连通测试,且密钥不回显。

### Modified Capabilities

(无)

## Impact

- **代码**:新增 `app/model_runtime.py`;修改 `app/llm.py`(读取运行期配置)、`app/main.py`(3 个配置端点)、`app/web/index.html`(配置区 + JS)。
- **数据**:`data/model_config.json`(运行期生成,已被 .gitignore 忽略)。
- **测试**:`tests/test_plan.py` 增 fixture 重置与配置端点 roundtrip 用例。
