"""
API 中间件

包含安全验证、速率限制和性能优化的中间件。
"""

import asyncio
import logging
import time
from typing import Dict, Set, Optional
from datetime import datetime, timedelta
from collections import defaultdict, deque

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from models.responses import ErrorResponse

logger = logging.getLogger(__name__)


class FileValidationMiddleware(BaseHTTPMiddleware):
    """文件验证中间件"""
    
    def __init__(
        self,
        app: ASGIApp,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        allowed_content_types: Set[str] = None
    ):
        super().__init__(app)
        self.max_file_size = max_file_size
        self.allowed_content_types = allowed_content_types or {
            "image/jpeg",
            "image/png", 
            "image/webp",
            "image/bmp",
            "image/tiff"
        }
    
    async def dispatch(self, request: Request, call_next):
        """处理请求验证"""
        
        # 只对文件上传端点进行验证
        if request.url.path in ["/image-to-image"] and request.method == "POST":
            
            # 检查 Content-Length
            content_length = request.headers.get("content-length")
            if content_length:
                content_length = int(content_length)
                if content_length > self.max_file_size:
                    logger.warning(f"File too large: {content_length} bytes")
                    error_response = ErrorResponse(
                        error={
                            "code": "FILE_TOO_LARGE",
                            "message": f"文件大小超过限制 ({self.max_file_size} bytes)",
                            "details": {
                                "max_size": self.max_file_size,
                                "received_size": content_length
                            }
                        }
                    )
                    return JSONResponse(
                        status_code=413,
                        content=error_response.dict()
                    )
            
            # 检查 Content-Type
            content_type = request.headers.get("content-type", "")
            if content_type.startswith("multipart/form-data"):
                # multipart 请求会在路由层进一步验证文件类型
                pass
            elif content_type and not any(ct in content_type for ct in self.allowed_content_types):
                logger.warning(f"Unsupported content type: {content_type}")
                error_response = ErrorResponse(
                    error={
                        "code": "UNSUPPORTED_MEDIA_TYPE",
                        "message": "不支持的文件类型",
                        "details": {
                            "supported_types": list(self.allowed_content_types),
                            "received_type": content_type
                        }
                    }
                )
                return JSONResponse(
                    status_code=415,
                    content=error_response.dict()
                )
        
        response = await call_next(request)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """速率限制中间件"""
    
    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_size: int = 10
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_size = burst_size
        
        # 使用内存存储请求记录（生产环境建议使用 Redis）
        self.request_counts: Dict[str, deque] = defaultdict(deque)
        self.burst_counts: Dict[str, int] = defaultdict(int)
        self.burst_reset_times: Dict[str, datetime] = {}
        
        # 清理任务
        self._cleanup_task = None
    
    def _get_client_id(self, request: Request) -> str:
        """获取客户端标识"""
        # 优先使用 X-Forwarded-For 头
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # 使用客户端 IP
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _is_rate_limited(self, client_id: str) -> tuple[bool, Dict[str, int]]:
        """检查是否超过速率限制"""
        now = datetime.now()
        
        # 清理过期记录
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)
        
        requests = self.request_counts[client_id]
        
        # 移除过期的请求记录
        while requests and requests[0] < hour_ago:
            requests.popleft()
        
        # 计算最近一分钟和一小时的请求数
        minute_requests = sum(1 for req_time in requests if req_time > minute_ago)
        hour_requests = len(requests)
        
        # 检查突发请求限制
        burst_reset_time = self.burst_reset_times.get(client_id)
        if burst_reset_time and now - burst_reset_time > timedelta(minutes=1):
            self.burst_counts[client_id] = 0
            del self.burst_reset_times[client_id]
        
        burst_count = self.burst_counts[client_id]
        
        # 检查各种限制
        limits = {
            "requests_per_minute": minute_requests,
            "requests_per_hour": hour_requests,
            "burst_requests": burst_count
        }
        
        is_limited = (
            minute_requests >= self.requests_per_minute or
            hour_requests >= self.requests_per_hour or
            burst_count >= self.burst_size
        )
        
        return is_limited, limits
    
    def _record_request(self, client_id: str):
        """记录请求"""
        now = datetime.now()
        self.request_counts[client_id].append(now)
        
        # 更新突发计数
        self.burst_counts[client_id] += 1
        if client_id not in self.burst_reset_times:
            self.burst_reset_times[client_id] = now
    
    async def dispatch(self, request: Request, call_next):
        """处理速率限制"""
        
        # 跳过健康检查和信息端点
        if request.url.path in ["/health", "/info", "/", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        client_id = self._get_client_id(request)
        is_limited, limits = self._is_rate_limited(client_id)
        
        if is_limited:
            logger.warning(f"Rate limit exceeded for client {client_id}: {limits}")
            
            error_response = ErrorResponse(
                error={
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "请求频率过高，请稍后重试",
                    "details": {
                        "limits": {
                            "requests_per_minute": self.requests_per_minute,
                            "requests_per_hour": self.requests_per_hour,
                            "burst_size": self.burst_size
                        },
                        "current": limits,
                        "retry_after": 60  # 建议等待时间（秒）
                    }
                }
            )
            
            response = JSONResponse(
                status_code=429,
                content=error_response.dict()
            )
            response.headers["Retry-After"] = "60"
            return response
        
        # 记录请求
        self._record_request(client_id)
        
        # 继续处理请求
        response = await call_next(request)
        
        # 添加速率限制头信息
        response.headers["X-RateLimit-Limit-Minute"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Limit-Hour"] = str(self.requests_per_hour)
        response.headers["X-RateLimit-Remaining-Minute"] = str(
            max(0, self.requests_per_minute - limits["requests_per_minute"])
        )
        response.headers["X-RateLimit-Remaining-Hour"] = str(
            max(0, self.requests_per_hour - limits["requests_per_hour"])
        )
        
        return response


class ConcurrencyLimitMiddleware(BaseHTTPMiddleware):
    """并发限制中间件"""
    
    def __init__(
        self,
        app: ASGIApp,
        max_concurrent_requests: int = 4,
        queue_timeout: int = 30
    ):
        super().__init__(app)
        self.max_concurrent_requests = max_concurrent_requests
        self.queue_timeout = queue_timeout
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.active_requests = 0
        self.queued_requests = 0
    
    async def dispatch(self, request: Request, call_next):
        """处理并发限制"""
        
        # 跳过非推理端点
        if request.url.path not in ["/text-to-image", "/image-to-image"]:
            return await call_next(request)
        
        # 检查队列长度
        if self.queued_requests >= self.max_concurrent_requests * 2:
            logger.warning("Request queue full, rejecting request")
            
            error_response = ErrorResponse(
                error={
                    "code": "SERVICE_OVERLOADED",
                    "message": "服务器负载过高，请稍后重试",
                    "details": {
                        "active_requests": self.active_requests,
                        "queued_requests": self.queued_requests,
                        "max_concurrent": self.max_concurrent_requests
                    }
                }
            )
            
            response = JSONResponse(
                status_code=503,
                content=error_response.dict()
            )
            response.headers["Retry-After"] = "30"
            return response
        
        # 等待获取信号量
        self.queued_requests += 1
        start_time = time.time()
        
        try:
            # 使用超时等待信号量
            await asyncio.wait_for(
                self.semaphore.acquire(),
                timeout=self.queue_timeout
            )
            
            self.queued_requests -= 1
            self.active_requests += 1
            
            wait_time = time.time() - start_time
            if wait_time > 1.0:  # 记录较长的等待时间
                logger.info(f"Request waited {wait_time:.2f}s in queue")
            
            # 处理请求
            response = await call_next(request)
            
            # 添加并发信息头
            response.headers["X-Concurrency-Active"] = str(self.active_requests)
            response.headers["X-Concurrency-Queued"] = str(self.queued_requests)
            response.headers["X-Concurrency-Limit"] = str(self.max_concurrent_requests)
            
            if wait_time > 0.1:
                response.headers["X-Queue-Time"] = f"{wait_time:.3f}"
            
            return response
            
        except asyncio.TimeoutError:
            self.queued_requests -= 1
            logger.warning(f"Request timed out after {self.queue_timeout}s in queue")
            
            error_response = ErrorResponse(
                error={
                    "code": "QUEUE_TIMEOUT",
                    "message": f"请求在队列中等待超时 ({self.queue_timeout}s)",
                    "details": {
                        "queue_timeout": self.queue_timeout,
                        "active_requests": self.active_requests,
                        "queued_requests": self.queued_requests
                    }
                }
            )
            
            return JSONResponse(
                status_code=503,
                content=error_response.dict()
            )
            
        finally:
            if self.active_requests > 0:
                self.active_requests -= 1
                self.semaphore.release()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志和追踪中间件"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        """处理请求日志和追踪"""
        from services.logging import (
            set_request_context, clear_request_context, 
            request_tracker, performance_monitor, get_logger
        )
        
        # 设置请求上下文
        request_id = set_request_context()
        
        # 获取客户端信息
        client_ip = self._get_client_ip(request)
        
        # 开始请求追踪
        request_tracker.start_request(
            request_id=request_id,
            endpoint=request.url.path,
            method=request.method,
            client_ip=client_ip
        )
        
        logger = get_logger("request")
        start_time = time.time()
        
        # 记录请求开始
        logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
            user_agent=request.headers.get("user-agent", ""),
            content_length=request.headers.get("content-length", "0")
        )
        
        try:
            # 处理请求
            response = await call_next(request)
            
            # 计算处理时间
            duration = time.time() - start_time
            
            # 结束请求追踪
            request_tracker.end_request(request_id, response.status_code)
            
            # 记录性能指标
            performance_monitor.record_request(
                endpoint=request.url.path,
                duration=duration,
                status_code=response.status_code
            )
            
            # 记录请求完成
            logger.info(
                "Request completed",
                status_code=response.status_code,
                duration=duration,
                response_size=response.headers.get("content-length", "unknown")
            )
            
            # 添加请求 ID 到响应头
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{duration:.3f}"
            
            return response
            
        except Exception as e:
            # 计算处理时间
            duration = time.time() - start_time
            
            # 结束请求追踪（带错误信息）
            request_tracker.end_request(request_id, 500, str(e))
            
            # 记录性能指标
            performance_monitor.record_request(
                endpoint=request.url.path,
                duration=duration,
                status_code=500,
                error_type=type(e).__name__
            )
            
            # 记录错误
            logger.error(
                "Request failed",
                error=str(e),
                error_type=type(e).__name__,
                duration=duration
            )
            
            raise
        finally:
            # 清除请求上下文
            clear_request_context()
    
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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """安全头中间件"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        """添加安全头"""
        response = await call_next(request)
        
        # 添加安全相关的响应头
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # 对于 API 响应，添加缓存控制
        if request.url.path.startswith("/text-to-image") or request.url.path.startswith("/image-to-image"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        
        return response