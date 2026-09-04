"""travel-planner 应用包。

导入本包任意模块前先加载项目根 .env(不覆盖已存在的环境变量,便于测试注入)。
"""

from __future__ import annotations

from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # 未安装 dotenv 时静默,允许调用方自行注入环境变量
    pass
