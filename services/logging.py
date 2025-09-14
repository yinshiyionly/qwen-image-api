"""
结构化日志系统

提供统一的日志记录、请求追踪和性能监控功能。
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from contextvars import ContextVar
from functools import wraps

import structlog
from structlog.stdlib import LoggerFactory

# 请求上下文变量
request_id_var: ContextVar[str] = ContextVar('request_id', default='')
user_id_var: ContextVar[str] = ContextVar('user_id', default='')


class RequestTracker:
    """请求追踪器"""
    
    def __init__(self):
        self.active_requests: Dict[str, Dict[str, Any]] = {}
    
    def start_request(self, request_id: str, endpoint: str, method: str, client_ip: str = None) -> Dict[str, Any]:
        """开始追踪请求"""
        request_info = {
            "request_id": request_id,
            "endpoint": endpoint,
            "method": method,
            "client_ip": client_ip,
            "start_time": time.time(),
            "timestamp": datetime.now().isoformat()
        }
        
        self.active_requests[request_id] = request_info
        return request_info
    
    def end_request(self, request_id: str, status_code: int, error: str = None) -> Dict[str, Any]:
        """结束请求追踪"""
        if request_id not in self.active_requests:
            return {}
        
        request_info = self.active_requests.pop(request_id)
        end_time = time.time()
        
        request_info.update({
            "end_time": end_time,
            "duration": end_time - request_info["start_time"],
            "status_code": status_code,
            "error": error
        })
        
        return request_info
    
    def get_active_requests(self) -> Dict[str, Dict[str, Any]]:
        """获取活跃请求"""
        return self.active_requests.copy()


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics = {
            "request_count": 0,
            "error_count": 0,
            "total_duration": 0.0,
            "avg_duration": 0.0,
            "endpoint_stats": {},
            "error_stats": {}
        }
    
    def record_request(self, endpoint: str, duration: float, status_code: int, error_type: str = None):
        """记录请求指标"""
        self.metrics["request_count"] += 1
        self.metrics["total_duration"] += duration
        self.metrics["avg_duration"] = self.metrics["total_duration"] / self.metrics["request_count"]
        
        # 端点统计
        if endpoint not in self.metrics["endpoint_stats"]:
            self.metrics["endpoint_stats"][endpoint] = {
                "count": 0,
                "total_duration": 0.0,
                "avg_duration": 0.0,
                "error_count": 0
            }
        
        endpoint_stats = self.metrics["endpoint_stats"][endpoint]
        endpoint_stats["count"] += 1
        endpoint_stats["total_duration"] += duration
        endpoint_stats["avg_duration"] = endpoint_stats["total_duration"] / endpoint_stats["count"]
        
        # 错误统计
        if status_code >= 400:
            self.metrics["error_count"] += 1
            endpoint_stats["error_count"] += 1
            
            if error_type:
                if error_type not in self.metrics["error_stats"]:
                    self.metrics["error_stats"][error_type] = 0
                self.metrics["error_stats"][error_type] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        return self.metrics.copy()
    
    def reset_metrics(self):
        """重置指标"""
        self.metrics = {
            "request_count": 0,
            "error_count": 0,
            "total_duration": 0.0,
            "avg_duration": 0.0,
            "endpoint_stats": {},
            "error_stats": {}
        }


def add_request_context(logger, method_name, event_dict):
    """添加请求上下文到日志"""
    request_id = request_id_var.get('')
    user_id = user_id_var.get('')
    
    if request_id:
        event_dict['request_id'] = request_id
    if user_id:
        event_dict['user_id'] = user_id
    
    return event_dict


def add_timestamp(logger, method_name, event_dict):
    """添加时间戳到日志"""
    event_dict['timestamp'] = datetime.now().isoformat()
    return event_dict


def configure_logging(log_level: str = "INFO", log_file: str = None, json_format: bool = True):
    """配置结构化日志"""
    
    # 配置 structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        add_timestamp,
        add_request_context,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    if json_format:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # 配置标准库日志
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(message)s",
        handlers=[
            logging.StreamHandler(),
            *([logging.FileHandler(log_file)] if log_file else [])
        ]
    )


def get_logger(name: str = None) -> structlog.stdlib.BoundLogger:
    """获取结构化日志器"""
    return structlog.get_logger(name)


def set_request_context(request_id: str = None, user_id: str = None):
    """设置请求上下文"""
    if request_id is None:
        request_id = str(uuid.uuid4())
    
    request_id_var.set(request_id)
    if user_id:
        user_id_var.set(user_id)
    
    return request_id


def clear_request_context():
    """清除请求上下文"""
    request_id_var.set('')
    user_id_var.set('')


def log_performance(func_name: str = None):
    """性能日志装饰器"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(func_name or func.__name__)
            start_time = time.time()
            
            try:
                logger.info("Function started", function=func.__name__)
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(
                    "Function completed",
                    function=func.__name__,
                    duration=duration,
                    success=True
                )
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    "Function failed",
                    function=func.__name__,
                    duration=duration,
                    error=str(e),
                    error_type=type(e).__name__,
                    success=False
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(func_name or func.__name__)
            start_time = time.time()
            
            try:
                logger.info("Function started", function=func.__name__)
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(
                    "Function completed",
                    function=func.__name__,
                    duration=duration,
                    success=True
                )
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    "Function failed",
                    function=func.__name__,
                    duration=duration,
                    error=str(e),
                    error_type=type(e).__name__,
                    success=False
                )
                raise
        
        # 检查是否是异步函数
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# 全局实例
request_tracker = RequestTracker()
performance_monitor = PerformanceMonitor()