## 1. 运行期配置模块

- [x] 1.1 新增 `app/model_runtime.py`(内存+持久化 JSON、优先级、掩码、reset),验证可 set/get/清除且持久化到指定路径
- [x] 1.2 `app/llm.py` 的 configured/_client/parse_model/plan_model 改读运行期配置,验证保存后 configured 翻转、默认模型取自 runtime

## 2. 配置 API 与页面

- [x] 2.1 `GET/POST /api/config/model` 与 `POST /api/config/model/test`,验证 roundtrip:设置→configured true 且不回显完整 key;空串清除→false
- [x] 2.2 页面新增「模型配置」区(Key/Base URL/解析/规划模型 + 保存/测试/清除),验证 GET / 包含配置表单元素与交互脚本

## 3. 收尾

- [x] 3.1 测试 fixture 重置运行期配置(忽略持久化文件),`pytest` 全绿(16 passed)
- [x] 3.2 `ruff check .` 通过
