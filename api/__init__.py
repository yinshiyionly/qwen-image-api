"""
API 模块

FastAPI 应用程序和路由的入口点。
"""

from .app import qwen_api
from .routes import router

# 创建 FastAPI 应用实例
app = qwen_api.create_app()

# 注册路由
app.include_router(router)

__all__ = ["app", "qwen_api"]