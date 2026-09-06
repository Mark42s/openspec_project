# plan-refinement spec delta

## Added Requirements

### Requirement: 会话式多轮细化
系统 SHALL 在首次规划成功返回一个 `session_id`,并允许用户通过 `POST /api/plan/{session_id}/refine` 提交追问,在上一版计划基础上更新;每次细化返回同一 `session_id`,并记录逐轮追问历史。

#### Scenario: 首次规划返回会话 ID
- **WHEN** 用户提交一次规划请求并成功返回
- **THEN** 响应含非空 `session_id`,前端据此进入多轮细化

#### Scenario: 基于上一版追问更新
- **WHEN** 用户携带 `session_id` 提交 `{feedback}` 追问
- **THEN** 系统返回更新后的计划,`session_id` 不变,且历史追加本轮 `{feedback, note}`

#### Scenario: 会话不存在
- **WHEN** 用户用不存在的 `session_id` 调用 refine
- **THEN** 系统返回 404,提示会话不存在或已过期

### Requirement: 追问改约束触发重检索与重算
系统 SHALL 把追问解析为约束增量;当出发地/目的地/日期/天数/人数变化时重新检索交通与酒店,当目的地或偏好变化时重新检索景点,并在预算变化时重算费用;费用始终由规则确定性重算,不经模型心算。

#### Scenario: 改预算只重算不重检索
- **WHEN** 用户追问「预算降到 100」而其它约束不变
- **THEN** 系统复用原检索候选、重算费用并标记 `over_budget`(若超出),不重新调用供应商

#### Scenario: 改天数触发重检索与重排
- **WHEN** 用户追问「改成 7 天」
- **THEN** 系统重新检索/复用并重排,返回 7 天的逐日计划

#### Scenario: 改目的地重新检索景点
- **WHEN** 用户追问「改去北京」
- **THEN** 系统按新目的地重新检索交通/酒店与景点,再重排行程

### Requirement: 结构化逐日行程
系统 SHALL 把每天的安排细化为结构化活动序列,每项含时段(`time`)、标题(`title`)、类别(`kind`)、关联景点(`poi_name`)与备注(`note`);字段可缺省但不阻塞整体规划。

#### Scenario: 返回结构化活动
- **WHEN** 规划完成
- **THEN** 每个 `days[]` 含 `activities[]`,每项含 `title` 与 `kind`(`transport/meal/sight/hotel/rest/note` 之一),部分项含 `time` 与 `poi_name`

### Requirement: 服务端会话持久化
系统 SHALL 把会话完整状态持久化到 SQLite,使同一 `session_id` 在服务重启后仍可继续细化;并可通过 `GET /api/plan/{session_id}` 回放当前状态。

#### Scenario: 重启后继续细化
- **WHEN** 服务重启后用户用既有 `session_id` 调用 refine 或 GET
- **THEN** 系统从 SQLite 加载会话状态并正常返回/更新,而非 404

### Requirement: 演示模式同样支持细化
系统 SHALL 在未配置大模型密钥时,用确定性启发式解析追问并产出结构化计划,保证多轮细化可离线演示与测试。

#### Scenario: 无密钥确定性合并
- **WHEN** 未配置 `ANTHROPIC_API_KEY`/`TUNIU_API_KEY` 且用户提交追问
- **THEN** 系统用确定性规则合并约束、复用 mock 数据并返回结构化计划,全程不依赖网络
