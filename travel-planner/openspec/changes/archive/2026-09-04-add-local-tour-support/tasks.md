## 1. 解析支持周边游

- [x] 1.1 TripRequest 增 `local_tour` 字段,验证模型构造/序列化通过
- [x] 1.2 城市词表扩充(苏州等常见城市)与周边关键词规则,验证启发式能识别「苏州出发…周边自驾」的 origin/dest
- [x] 1.3 启发式与 LLM prompt 均支持:无具体目的地+周边词 → destinations=[出发地]、local_tour=true,验证两端解析结果一致(单元测试)

## 2. 周边游规划语义

- [x] 2.1 main 聚合后若 local_tour 清空 transport,验证 /api/plan 周边需求 transport=0
- [x] 2.2 演示规划首日文案/note 体现本地自驾、不计长途,验证 6 天周边请求返回 days 且推荐无 transport
- [x] 2.3 明确目的地的旧输入行为不变(local_tour=false 走城际),验证原有 happy path 仍绿

## 3. 收尾

- [x] 3.1 新增周边游端到端测试,`pytest` 全绿(15 passed)
- [x] 3.2 `ruff check .` 通过
