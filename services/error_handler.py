"""
统一错误处理系统

提供统一的错误处理、响应格式化和错误分类功能。
"""

import traceback
from typing import Dict, Any, Optional, Type
from enum import Enum

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError

from models.responses import ErrorResponse
from services.logging import get_logger, performance_monitor
from services.exceptions import (
    ModelNotLoadedError, InferenceError, ValidationError as CustomValidationError,
    MemoryError as CustomMemoryError, ResourceError
)

logger = get_logger(__name__)


class ErrorCategory(Enum):
    """错误分类"""
    CLIENT_ERROR = "client_error"
    SERVER_ERROR = "server_error"
    VALIDATION_ERROR = "validation_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    RESOURCE_ERROR = "resource_error"
    MODEL_ERROR = "model_error"
    NETWORK_ERROR = "network_error"
    UNKNOWN_ERROR = "unknown_error"


class ErrorCode(Enum):
    """标准错误代码"""
    # 客户端错误 (4xx)
    BAD_REQUEST = "BAD_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    NOT_ACCEPTABLE = "NOT_ACCEPTABLE"
    REQUEST_TIMEOUT = "REQUEST_TIMEOUT"
    CONFLICT = "CONFLICT"
    GONE = "GONE"
    LENGTH_REQUIRED = "LENGTH_REQUIRED"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    URI_TOO_LONG = "URI_TOO_LONG"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    RANGE_NOT_SATISFIABLE = "RANGE_NOT_SATISFIABLE"
    EXPECTATION_FAILED = "EXPECTATION_FAILED"
    UNPROCESSABLE_ENTITY = "UNPROCESSABLE_ENTITY"
    TOO_MANY_REQUESTS = "TOO_MANY_REQUESTS"
    
    # 服务器错误 (5xx)
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    BAD_GATEWAY = "BAD_GATEWAY"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    GATEWAY_TIMEOUT = "GATEWAY_TIMEOUT"
    HTTP_VERSION_NOT_SUPPORTED = "HTTP_VERSION_NOT_SUPPORTED"
    
    # 自定义错误
    VALIDATION_ERROR = "VALIDATION_ERROR"
    MODEL_NOT_LOADED = "MODEL_NOT_LOADED"
    INFERENCE_ERROR = "INFERENCE_ERROR"
    MEMORY_ERROR = "MEMORY_ERROR"
    RESOURCE_ERROR = "RESOURCE_ERROR"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    QUEUE_TIMEOUT = "QUEUE_TIMEOUT"
    SERVICE_OVERLOADED = "SERVICE_OVERLOADED"


class ErrorHandler:
    """统一错误处理器"""
    
    def __init__(self):
        self.error_mappings = self._setup_error_mappings()
    
    def _setup_error_mappings(self) -> Dict[Type[Exception], Dict[str, Any]]:
        """设置错误映射"""
        return {
            # FastAPI 异常
            HTTPException: {
                "category": ErrorCategory.CLIENT_ERROR,
                "get_code": lambda e: f"HTTP_{e.status_code}",
                "get_message": lambda e: e.detail,
                "get_status_code": lambda e: e.status_code
            },
            
            # 请求验证异常
            RequestValidationError: {
                "category": ErrorCategory.VALIDATION_ERROR,
                "get_code": lambda e: ErrorCode.VALIDATION_ERROR.value,
                "get_message": lambda e: "请求参数验证失败",
                "get_status_code": lambda e: 422
            },
            
            # Pydantic 验证异常
            ValidationError: {
                "category": ErrorCategory.VALIDATION_ERROR,
                "get_code": lambda e: ErrorCode.VALIDATION_ERROR.value,
                "get_message": lambda e: "数据验证失败",
                "get_status_code": lambda e: 422
            },
            
            # 自定义异常
            ModelNotLoadedError: {
                "category": ErrorCategory.MODEL_ERROR,
                "get_code": lambda e: ErrorCode.MODEL_NOT_LOADED.value,
                "get_message": lambda e: "模型未加载",
                "get_status_code": lambda e: 503
            },
            
            InferenceError: {
                "category": ErrorCategory.MODEL_ERROR,
                "get_code": lambda e: ErrorCode.INFERENCE_ERROR.value,
                "get_message": lambda e: f"模型推理失败: {str(e)}",
                "get_status_code": lambda e: 500
            },
            
            CustomValidationError: {
                "category": ErrorCategory.VALIDATION_ERROR,
                "get_code": lambda e: ErrorCode.VALIDATION_ERROR.value,
                "get_message": lambda e: f"参数验证失败: {str(e)}",
                "get_status_code": lambda e: 400
            },
            
            CustomMemoryError: {
                "category": ErrorCategory.RESOURCE_ERROR,
                "get_code": lambda e: ErrorCode.MEMORY_ERROR.value,
                "get_message": lambda e: f"内存不足: {str(e)}",
                "get_status_code": lambda e: 503
            },
            
            ResourceError: {
                "category": ErrorCategory.RESOURCE_ERROR,
                "get_code": lambda e: ErrorCode.RESOURCE_ERROR.value,
                "get_message": lambda e: f"资源错误: {str(e)}",
                "get_status_code": lambda e: 503
            },
            
            # 系统异常
            MemoryError: {
                "category": ErrorCategory.RESOURCE_ERROR,
                "get_code": lambda e: ErrorCode.MEMORY_ERROR.value,
                "get_message": lambda e: "系统内存不足",
                "get_status_code": lambda e: 503
            },
            
            TimeoutError: {
                "category": ErrorCategory.SERVER_ERROR,
                "get_code": lambda e: ErrorCode.GATEWAY_TIMEOUT.value,
                "get_message": lambda e: "请求超时",
                "get_status_code": lambda e: 504
            },
            
            FileNotFoundError: {
                "category": ErrorCategory.CLIENT_ERROR,
                "get_code": lambda e: ErrorCode.NOT_FOUND.value,
                "get_message": lambda e: "文件未找到",
                "get_status_code": lambda e: 404
            },
            
            PermissionError: {
                "category": ErrorCategory.CLIENT_ERROR,
                "get_code": lambda e: ErrorCode.FORBIDDEN.value,
                "get_message": lambda e: "权限不足",
                "get_status_code": lambda e: 403
            }
        }
    
    def handle_exception(
        self,
        request: Request,
        exc: Exception,
        include_traceback: bool = False
    ) -> JSONResponse:
        """处理异常并返回统一格式的响应"""
        
        # 获取错误信息
        error_info = self._get_error_info(exc)
        
        # 记录错误日志
        self._log_error(request, exc, error_info)
        
        # 记录性能指标
        performance_monitor.record_request(
            endpoint=request.url.path,
            duration=0.0,  # 在中间件中会更新
            status_code=error_info["status_code"],
            error_type=error_info["category"].value
        )
        
        # 构建错误响应
        error_details = {
            "path": str(request.url.path),
            "method": request.method,
            "timestamp": error_info["timestamp"]
        }
        
        # 添加异常特定的详细信息
        if isinstance(exc, RequestValidationError):
            error_details["validation_errors"] = exc.errors()
        elif isinstance(exc, ValidationError):
            error_details["validation_errors"] = exc.errors()
        elif hasattr(exc, 'details'):
            error_details.update(exc.details)
        
        # 在开发环境中包含堆栈跟踪
        if include_traceback:
            error_details["traceback"] = traceback.format_exc()
        
        error_response = ErrorResponse(
            error={
                "code": error_info["code"],
                "message": error_info["message"],
                "category": error_info["category"].value,
                "details": error_details
            }
        )
        
        return JSONResponse(
            status_code=error_info["status_code"],
            content=error_response.dict()
        )
    
    def _get_error_info(self, exc: Exception) -> Dict[str, Any]:
        """获取错误信息"""
        from datetime import datetime
        
        exc_type = type(exc)
        
        # 查找匹配的错误映射
        mapping = None
        for error_type, error_mapping in self.error_mappings.items():
            if isinstance(exc, error_type):
                mapping = error_mapping
                break
        
        if mapping:
            return {
                "category": mapping["category"],
                "code": mapping["get_code"](exc),
                "message": mapping["get_message"](exc),
                "status_code": mapping["get_status_code"](exc),
                "timestamp": datetime.now().isoformat()
            }
        else:
            # 未知错误的默认处理
            return {
                "category": ErrorCategory.UNKNOWN_ERROR,
                "code": ErrorCode.INTERNAL_SERVER_ERROR.value,
                "message": "服务器内部错误",
                "status_code": 500,
                "timestamp": datetime.now().isoformat()
            }
    
    def _log_error(self, request: Request, exc: Exception, error_info: Dict[str, Any]):
        """记录错误日志"""
        
        # 确定日志级别
        status_code = error_info["status_code"]
        if status_code >= 500:
            log_level = "error"
        elif status_code >= 400:
            log_level = "warning"
        else:
            log_level = "info"
        
        # 构建日志上下文
        log_context = {
            "error_code": error_info["code"],
            "error_category": error_info["category"].value,
            "status_code": status_code,
            "path": str(request.url.path),
            "method": request.method,
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("user-agent", ""),
            "exception_type": type(exc).__name__,
            "exception_message": str(exc)
        }
        
        # 添加请求参数（敏感信息除外）
        if hasattr(request, 'query_params'):
            log_context["query_params"] = dict(request.query_params)
        
        # 记录日志
        log_method = getattr(logger, log_level)
        log_method(
            f"Request failed: {error_info['message']}",
            **log_context,
            exc_info=status_code >= 500  # 只在服务器错误时包含异常信息
        )
    
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端 IP 地址"""
        # 优先使用 X-Forwarded-For 头
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # 使用 X-Real-IP 头
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # 使用客户端 IP
        if request.client:
            return request.client.host
        
        return "unknown"


# 全局错误处理器实例
error_handler = ErrorHandler()


def create_error_response(
    code: str,
    message: str,
    status_code: int = 500,
    details: Dict[str, Any] = None
) -> JSONResponse:
    """创建标准错误响应"""
    
    error_response = ErrorResponse(
        error={
            "code": code,
            "message": message,
            "details": details or {}
        }
    )
    
    return JSONResponse(
        status_code=status_code,
        content=error_response.dict()
    )