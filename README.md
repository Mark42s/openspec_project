# OpenSpec Projects

本仓库是使用 [OpenSpec](https://github.com/Fission-AI/OpenSpec) 规格驱动开发的多个项目的合集。每个子项目文件夹是自包含的：代码、spec 文档、AI 协作记录都在各自文件夹内。

## 子项目

| 子项目 | 说明 |
|---|---|
| [travel-planner/](travel-planner/) | 国内旅行规划后端(FastAPI)：自然语言需求 → 结构化约束 → 并发检索 → 逐日行程 |

## 协作约定

- 每个子项目有自己的 `CLAUDE.md`、`openspec/`、`.env.example` 等
- `.claude/` 是仓库级 Claude Code 配置(skills/commands)，对所有子项目生效
- 开发某子项目时，先进入其子目录再执行命令
- OpenSpec CLI 在各子项目内独立运行(`openspec list/status/validate`)

## 如何开始

进入目标子项目目录，阅读其 `CLAUDE.md` 获取运行/架构/进度详情。
