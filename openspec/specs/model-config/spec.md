# model-config Specification

## Purpose
让用户能在演示页面直接配置 Anthropic API Key、Base URL 与解析/规划模型,保存后即时启用真实大模型的语义理解、逐日规划与可选实时网页搜索;全程不回显完整密钥。

## Requirements

### Requirement: 页面提供大模型配置入口
系统 SHALL 在网页提供模型配置区,并暴露 `GET/POST /api/config/model` 读取与保存配置(API Key / Base URL / 解析模型 / 规划模型)。

#### Scenario: 保存配置
- **WHEN** 用户在配置区填入 API Key 等并保存
- **THEN** 系统保存该配置并返回当前状态,响应中不含完整 Key(仅掩码如 `sk-a…abcd`)

#### Scenario: 清除配置
- **WHEN** 用户清空 API Key 并保存
- **THEN** 系统回到未配置状态,规划走内置演示模式

### Requirement: 配置即时生效
系统 SHALL 在保存后无需重启即让意图解析/逐日规划/实时检索使用新配置。

#### Scenario: 保存后立即生效
- **WHEN** 保存有效配置后紧接着发起一次规划
- **THEN** 该次规划走真实大模型路径(healthz/配置接口反映 configured=true)

### Requirement: 连通性测试
系统 SHALL 提供 `POST /api/config/model/test`,用已保存配置校验可达性;未配置时返回明确错误。

#### Scenario: 测试连接
- **WHEN** 已保存配置且网络/凭据可用
- **THEN** 返回 ok 与所连模型
- **WHEN** 未保存 Key 就测试
- **THEN** 返回 400 并提示先保存 Key
