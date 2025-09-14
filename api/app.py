"""
FastAPI 应用程序

主要的 FastAPI 应用实例，包含路由、中间件和异常处理器。
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from config.manager import get_config_manager
from services.model_manager import ModelManager
from services.request_processor import RequestProcessor
from models.responses import ErrorResponse
from .middleware import (
    FileValidationMiddleware,
    RateLimitMiddleware, 
    ConcurrencyLimitMiddleware,
    SecurityHeadersMiddleware,
    RequestLoggingMiddleware
)
from services.error_handler import error_handler
from services.logging import configure_logging, get_logger

logger = logging.getLogger(__name__)


class QwenImageAPI:
    """Qwen Image API 应用类"""
    
    def __init__(self):
        self.config_manager = get_config_manager()
        self.model_manager: ModelManager = None
        self.request_processor: RequestProcessor = None
        self.app_start_time = None
        
    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        """应用生命周期管理"""
        # 启动事件
        self.app_start_time = time.time()
        
        try:
            # 加载配置
            config = self.config_manager.get_config()
            
            # 配置日志系统
            configure_logging(
                log_level=config.log.level,
                log_file=config.log.file_path,
                json_format=True
            )
            
            # 获取结构化日志器
            startup_logger = get_logger("startup")
            startup_logger.info("Starting Qwen Image API service...")
            startup_logger.info(
                "Configuration loaded",
                server_host=config.server.host,
                server_port=config.server.port,
                log_level=config.log.level,
                rate_limiting_enabled=config.security.enable_rate_limiting,
                file_validation_enabled=config.security.enable_file_validation
            )
            
            # 初始化请求处理器
            self.request_processor = RequestProcessor(
                max_file_size=config.server.max_file_size
            )
            startup_logger.info("Request processor initialized")
            
            # 初始化模型管理器
            model_config = self.config_manager.get_model_config()
            self.model_manager = ModelManager(
                model_path=model_config['model_path'],
                config=model_config
            )
            
            # 加载模型（如果模型路径已配置）
            if model_config['model_path']:
                try:
                    self.model_manager.load_model()
                    startup_logger.info("Model loaded successfully", model_path=model_config['model_path'])
                except Exception as e:
                    startup_logger.error("Failed to load model", error=str(e), model_path=model_config['model_path'])
                    # 不阻止服务启动，允许在运行时重试加载模型
            else:
                startup_logger.warning("Model path not configured, model not loaded")
            
            startup_logger.info("Qwen Image API service started successfully")
            
        except Exception as e:
            startup_logger.error("Failed to start service", error=str(e))
            raise
        
        yield
        
        # 关闭事件
        shutdown_logger = get_logger("shutdown")
        shutdown_logger.info("Shutting down Qwen Image API service...")
        
        try:
            # 清理模型资源
            if self.model_manager:
                self.model_manager.cleanup()
                shutdown_logger.info("Model resources cleaned up")
                
        except Exception as e:
            shutdown_logger.error("Error during shutdown", error=str(e))
        
        shutdown_logger.info("Qwen Image API service shut down")
    
    def create_app(self) -> FastAPI:
        """创建 FastAPI 应用实例"""
        
        app = FastAPI(
            title="Qwen Image API Service",
            description="基于 qwen-image 模型的图像生成 API 服务",
            version="1.0.0",
            lifespan=self.lifespan
        )
        
        # 获取配置
        config = self.config_manager.get_config()
        
        # 添加请求日志和追踪中间件（最外层）
        app.add_middleware(RequestLoggingMiddleware)
        
        # 添加安全头中间件
        app.add_middleware(SecurityHeadersMiddleware)
        
        # 添加并发限制中间件
        app.add_middleware(
            ConcurrencyLimitMiddleware,
            max_concurrent_requests=config.server.max_concurrent_requests,
            queue_timeout=config.server.queue_timeout
        )
        
        # 添加速率限制中间件（如果启用）
        if config.security.enable_rate_limiting:
            app.add_middleware(
                RateLimitMiddleware,
                requests_per_minute=config.security.requests_per_minute,
                requests_per_hour=config.security.requests_per_hour,
                burst_size=config.security.burst_size
            )
        
        # 添加文件验证中间件（如果启用）
        if config.security.enable_file_validation:
            app.add_middleware(
                FileValidationMiddleware,
                max_file_size=config.server.max_file_size,
                allowed_content_types=set(config.security.allowed_file_types)
            )
        
        # 添加 CORS 中间件
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # 生产环境中应该限制具体的域名
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # 添加请求日志中间件
        @app.middleware("http")
        async def log_requests(request: Request, call_next):
            start_time = time.time()
            
            # 记录请求信息
            logger.info(
                f"Request: {request.method} {request.url.path} "
                f"from {request.client.host if request.client else 'unknown'}"
            )
            
            # 处理请求
            response = await call_next(request)
            
            # 计算处理时间
            process_time = time.time() - start_time
            
            # 记录响应信息
            logger.info(
                f"Response: {response.status_code} "
                f"in {process_time:.3f}s"
            )
            
            # 添加响应头
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
        
        # 全局异常处理器 - 使用统一的错误处理系统
        @app.exception_handler(HTTPException)
        async def http_exception_handler(request: Request, exc: HTTPException):
            """HTTP 异常处理器"""
            return error_handler.handle_exception(request, exc)
        
        @app.exception_handler(RequestValidationError)
        async def validation_exception_handler(request: Request, exc: RequestValidationError):
            """请求验证异常处理器"""
            return error_handler.handle_exception(request, exc)
        
        @app.exception_handler(StarletteHTTPException)
        async def starlette_exception_handler(request: Request, exc: StarletteHTTPException):
            """Starlette HTTP 异常处理器"""
            return error_handler.handle_exception(request, exc)
        
        @app.exception_handler(Exception)
        async def general_exception_handler(request: Request, exc: Exception):
            """通用异常处理器"""
            # 在开发环境中包含堆栈跟踪
            include_traceback = config.log.level.upper() == "DEBUG"
            return error_handler.handle_exception(request, exc, include_traceback=include_traceback)
        
        return app
    
    def get_model_manager(self) -> ModelManager:
        """获取模型管理器实例"""
        if self.model_manager is None:
            raise RuntimeError("Model manager not initialized")
        return self.model_manager
    
    def get_request_processor(self) -> RequestProcessor:
        """获取请求处理器实例"""
        if self.request_processor is None:
            raise RuntimeError("Request processor not initialized")
        return self.request_processor
    
    def get_uptime(self) -> float:
        """获取服务运行时间（秒）"""
        if self.app_start_time is None:
            return 0.0
        return time.time() - self.app_start_time


# 全局应用实例
qwen_api = QwenImageAPI()