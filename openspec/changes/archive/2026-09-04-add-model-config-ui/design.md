## Context

此前只有 .env 静态配置,服务启动后不可改;页面需要在运行期改 Key/模型。改动点见 proposal.md。

## Goals / Non-Goals

**Goals:** 运行期可保存/清除模型配置、即时生效、不重启;密钥不回显;测试确定性(忽略持久化)。
**Non-Goals:** 多厂商兼容、加密存储、用量/费用限额。

## Decisions

**D1. 独立 `model_runtime` 模块做唯一真源,llm 全部读它。**
优先级:页面设置 > 持久化文件 > .env > 默认常量。**为何**:避免 env 与页面双真源打架;`configured()/_client()/parse_model()/plan_model()` 一处集中。
**D2. 持久化到 `data/model_config.json`(gitignore)**。**权衡**:明文本地文件,适合自部署 demo;不做加密(注明)。
**D3. 端点语义:空串=清除、缺字段=不动**。**为何**:页面能区分"保留"与"清掉";避免误清其它字段。
**D4. 连通测试用 `models.retrieve`(只查元数据)**。**为何**:不耗生成 token 即可验 Key/端点正确。
**D5. 测试 fixture 先删 key 环境变量再 `model_runtime.reset()`**,忽略磁盘文件。**为何**:保证 CI/离线确定性。

## Risks / Trade-offs

- 明文 Key 存本地文件 → data/ 已 gitignore;README 提醒用户自行保管。
- 页面 Password 框只是 UI 隐藏,非传输加密 → 走 HTTPS 部署时更安全(本地 demo 可接受)。
- runtime 一次加载缓存文件;多进程(uWSGI/多 worker)不共享 → 单进程 demo 场景足够;多 worker 部署时需改共享存储,属后续。

## Migration Plan

兼容旧行为:未配置(无 Key)时一切照旧走演示模式;无破坏性。

## Open Questions

无。
