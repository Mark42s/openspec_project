"""Pydantic v1/v2 兼容层。

本项目要求 pydantic>=2.8,但在某些环境中可能只有 v1 可用。
此模块提供 v2 API 的 v1 polyfill,保证代码在两种版本下都能运行。
"""

from __future__ import annotations

import json

import pydantic

# 检测版本
_PYDANTIC_V2 = int(pydantic.VERSION.split(".")[0]) >= 2

if _PYDANTIC_V2:
    # v2 原生:直接使用
    def model_dump(model: pydantic.BaseModel, *, mode: str = "python", exclude: set | None = None) -> dict:
        return model.model_dump(mode="python" if mode == "python" else "json", exclude=exclude)  # type: ignore[return-value]

    def model_dump_json(model: pydantic.BaseModel) -> str:
        return model.model_dump_json()  # type: ignore[return-value]

    def model_validate_json(cls: type, text: str):
        return cls.model_validate_json(text)  # type: ignore[return-value]

    def model_copy(model: pydantic.BaseModel, *, deep: bool = False):
        return model.model_copy(deep=deep)  # type: ignore[return-value]

    def model_json_schema(cls: type) -> dict:
        return cls.model_json_schema()  # type: ignore[return-value]
else:
    # v1 polyfill: 把 v2 API 映射到 v1
    def model_dump(model: pydantic.BaseModel, *, mode: str = "python", exclude: set | None = None) -> dict:
        d = model.dict(exclude=exclude)
        if mode == "json":
            return _to_json_serializable(d)
        return d

    def model_dump_json(model: pydantic.BaseModel) -> str:
        return model.json()

    def model_validate_json(cls: type, text: str):
        return cls.parse_raw(text)

    def model_copy(model: pydantic.BaseModel, *, deep: bool = False):
        return model.copy(deep=deep)

    def model_json_schema(cls: type) -> dict:
        return cls.schema()

    def _to_json_serializable(obj):
        if isinstance(obj, dict):
            return {k: _to_json_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_to_json_serializable(i) for i in obj]
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        return obj


# 给 BaseModel 打补丁,让所有模型实例都有 v2 风格的方法
if not _PYDANTIC_V2:
    def _v2_dump(self, *, mode: str = "python", exclude: set | None = None) -> dict:
        return model_dump(self, mode=mode, exclude=exclude)

    def _v2_dump_json(self) -> str:
        return model_dump_json(self)

    pydantic.BaseModel.model_dump = _v2_dump  # type: ignore[attr-defined]
    pydantic.BaseModel.model_dump_json = _v2_dump_json  # type: ignore[attr-defined]

    @classmethod
    def _v2_validate_json(cls, text: str):
        return model_validate_json(cls, text)

    pydantic.BaseModel.model_validate_json = _v2_validate_json  # type: ignore[attr-defined]

    def _v2_copy(self, *, deep: bool = False):
        return model_copy(self, deep=deep)

    pydantic.BaseModel.model_copy = _v2_copy  # type: ignore[attr-defined]

    @classmethod
    def _v2_json_schema(cls):
        return model_json_schema(cls)

    pydantic.BaseModel.model_json_schema = _v2_json_schema  # type: ignore[attr-defined]

    @classmethod
    def _v2_validate(cls, obj):
        return cls.parse_obj(obj) if isinstance(obj, dict) else cls(**obj)

    pydantic.BaseModel.model_validate = _v2_validate  # type: ignore[attr-defined]
