## Why

一次真实的多城市出行规划（无锡→贵阳→荔波→西江→榕江，国庆 7 天）暴露出工具在**行程执行韧性**上的盲区：用户的晕车/体力档/轻装诉求无处表达；"赶 G2860 高铁"这类死线全靠人工倒排；抢票与预约日期散落在对话里。这些恰恰决定行程能否真正落地——规划不该止步于"去哪玩"，还应回答"这样走累不累、赶不赶得上、该提前准备什么"。

## What Changes

从规划对话提炼的工程清单分三阶段，**本 change 只落地 Phase 1**，Phase 2/3 记入 roadmap 不实现：

**Phase 1（本 change）— 出行韧性：场景感知 + 强度提示 + 倒排与行前日历**
- `TripRequest` 新增出行场景字段：`motion_sickness`（晕车）、`travel_pace`（体力档：relaxed/standard/intensive）、`pack_light`（轻装无箱）；意图解析（LLM + 确定性兜底）识别并在 refine 追问中保持
- 行程响应新增确定性**韧性附言**（不经模型编造）：晕车时对长途汽车段提示"坐前排/备药、勿低头看手机"；强度高的日期标注并建议休息窗口
- 新增确定性模块 `app/resilience.py`：
  - 倒排计算：给定"不可错过事件"（班次/开园/预约时段）与各前置步骤耗时，反推最晚离开时刻并给出缓冲分钟与"超时砍项顺序"
  - 行前行动日历：按出发日期与行程约束（是否已购交通等）生成结构化动作清单（确认出票/订住宿/预约门票/装备/出发检查）
- 新端点 `GET /api/prep/{session_id}/calendar` 返回行动日历

**Phase 2（roadmap）**：多节点行程模型——城市序列 + 每节点停留/迁移段，死线引擎接入真实班次。

**Phase 3（roadmap）**：景区动线知识库（站点序列/观光车方向/变更公告）与行程 HTML/PDF 导出端点。

## Capabilities

### New Capabilities
- `trip-resilience`: 行程执行韧性——场景字段的确定性提示、倒排时刻计算、行前行动日历端点

### Modified Capabilities
- `travel-planner`: 意图解析新增出行场景字段（晕车/体力档/轻装），`PlanResponse` 携带 `resilience` 摘要
- `itinerary-planning`: 逐日行程的组装阶段追加确定性健康与强度提示（列入计划 note）

## Impact

- 代码：`app/models.py`（TripRequest/PlanResponse 字段）、`app/llm.py`（parse 规则与提示词、heuristic 识别）、`app/main.py`（组装韧性附言、新增 calendar 端点）、新增 `app/resilience.py`（纯函数 + 日历生成）
- 测试：`tests/test_plan.py` 新增场景解析、附言生成、倒排计算、日历端点用例；既有用例保持离线确定性
- 无破坏性变更：新字段全带默认值；refine 对旧会话兼容（缺失字段按默认）
- 不影响：检索/费用/逐日模型输出流程
