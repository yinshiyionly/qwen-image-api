"""
日志系统测试

测试结构化日志、请求追踪和性能监控功能。
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch
from datetime import datetime

from services.logging import (
    RequestTracker, PerformanceMonitor, configure_logging, get_logger,
    set_request_context, clear_request_context, log_performance,
    request_tracker, performance_monitor
)


class TestRequestTracker:
    """请求追踪器测试"""
    
    def setup_method(self):
        """设置测试"""
        self.tracker = RequestTracker()
    
    def test_start_request(self):
        """测试开始请求追踪"""
        request_info = self.tracker.start_request(
            request_id="test-123",
            endpoint="/test",
            method="GET",
            client_ip="127.0.0.1"
        )
        
        assert request_info["request_id"] == "test-123"
        assert request_info["endpoint"] == "/test"
        assert request_info["method"] == "GET"
        assert request_info["client_ip"] == "127.0.0.1"
        assert "start_time" in request_info
        assert "timestamp" in request_info
        
        # 检查活跃请求
        active_requests = self.tracker.get_active_requests()
        assert "test-123" in active_requests
        assert active_requests["test-123"] == request_info
    
    def test_end_request(self):
        """测试结束请求追踪"""
        # 开始请求
        self.tracker.start_request("test-123", "/test", "GET")
        
        # 等待一小段时间
        time.sleep(0.01)
        
        # 结束请求
        request_info = self.tracker.end_request("test-123", 200)
        
        assert request_info["status_code"] == 200
        assert "end_time" in request_info
        assert "duration" in request_info
        assert request_info["duration"] > 0
        assert request_info["error"] is None
        
        # 检查活跃请求（应该被移除）
        active_requests = self.tracker.get_active_requests()
        assert "test-123" not in active_requests
    
    def test_end_request_with_error(self):
        """测试带错误的请求结束"""
        self.tracker.start_request("test-123", "/test", "GET")
        
        request_info = self.tracker.end_request("test-123", 500, "Internal error")
        
        assert request_info["status_code"] == 500
        assert request_info["error"] == "Internal error"
    
    def test_end_nonexistent_request(self):
        """测试结束不存在的请求"""
        request_info = self.tracker.end_request("nonexistent", 200)
        
        assert request_info == {}
    
    def test_multiple_active_requests(self):
        """测试多个活跃请求"""
        self.tracker.start_request("req-1", "/test1", "GET")
        self.tracker.start_request("req-2", "/test2", "POST")
        
        active_requests = self.tracker.get_active_requests()
        assert len(active_requests) == 2
        assert "req-1" in active_requests
        assert "req-2" in active_requests
        
        # 结束一个请求
        self.tracker.end_request("req-1", 200)
        
        active_requests = self.tracker.get_active_requests()
        assert len(active_requests) == 1
        assert "req-2" in active_requests


class TestPerformanceMonitor:
    """性能监控器测试"""
    
    def setup_method(self):
        """设置测试"""
        self.monitor = PerformanceMonitor()
    
    def test_record_successful_request(self):
        """测试记录成功请求"""
        self.monitor.record_request("/test", 1.5, 200)
        
        metrics = self.monitor.get_metrics()
        
        assert metrics["request_count"] == 1
        assert metrics["error_count"] == 0
        assert metrics["total_duration"] == 1.5
        assert metrics["avg_duration"] == 1.5
        
        # 检查端点统计
        endpoint_stats = metrics["endpoint_stats"]["/test"]
        assert endpoint_stats["count"] == 1
        assert endpoint_stats["total_duration"] == 1.5
        assert endpoint_stats["avg_duration"] == 1.5
        assert endpoint_stats["error_count"] == 0
    
    def test_record_error_request(self):
        """测试记录错误请求"""
        self.monitor.record_request("/test", 0.5, 500, "InternalError")
        
        metrics = self.monitor.get_metrics()
        
        assert metrics["request_count"] == 1
        assert metrics["error_count"] == 1
        
        # 检查端点统计
        endpoint_stats = metrics["endpoint_stats"]["/test"]
        assert endpoint_stats["error_count"] == 1
        
        # 检查错误统计
        assert metrics["error_stats"]["InternalError"] == 1
    
    def test_multiple_requests_statistics(self):
        """测试多个请求的统计"""
        self.monitor.record_request("/test1", 1.0, 200)
        self.monitor.record_request("/test1", 2.0, 200)
        self.monitor.record_request("/test2", 0.5, 404)
        
        metrics = self.monitor.get_metrics()
        
        assert metrics["request_count"] == 3
        assert metrics["error_count"] == 1
        assert metrics["total_duration"] == 3.5
        assert metrics["avg_duration"] == 3.5 / 3
        
        # 检查端点统计
        test1_stats = metrics["endpoint_stats"]["/test1"]
        assert test1_stats["count"] == 2
        assert test1_stats["avg_duration"] == 1.5
        assert test1_stats["error_count"] == 0
        
        test2_stats = metrics["endpoint_stats"]["/test2"]
        assert test2_stats["count"] == 1
        assert test2_stats["error_count"] == 1
    
    def test_reset_metrics(self):
        """测试重置指标"""
        self.monitor.record_request("/test", 1.0, 200)
        
        # 重置前检查
        metrics = self.monitor.get_metrics()
        assert metrics["request_count"] == 1
        
        # 重置
        self.monitor.reset_metrics()
        
        # 重置后检查
        metrics = self.monitor.get_metrics()
        assert metrics["request_count"] == 0
        assert metrics["error_count"] == 0
        assert metrics["total_duration"] == 0.0
        assert metrics["avg_duration"] == 0.0
        assert metrics["endpoint_stats"] == {}
        assert metrics["error_stats"] == {}


class TestRequestContext:
    """请求上下文测试"""
    
    def test_set_and_clear_context(self):
        """测试设置和清除上下文"""
        # 设置上下文
        request_id = set_request_context(user_id="user123")
        
        assert request_id is not None
        assert len(request_id) > 0
        
        # 清除上下文
        clear_request_context()
        
        # 上下文应该被清除（这里我们无法直接验证，但不应该抛出异常）
    
    def test_custom_request_id(self):
        """测试自定义请求 ID"""
        custom_id = "custom-request-123"
        request_id = set_request_context(request_id=custom_id, user_id="user456")
        
        assert request_id == custom_id


class TestLogPerformanceDecorator:
    """性能日志装饰器测试"""
    
    @pytest.mark.asyncio
    async def test_async_function_logging(self):
        """测试异步函数日志记录"""
        
        @log_performance("test_async")
        async def async_test_function(value):
            await asyncio.sleep(0.01)
            return value * 2
        
        with patch('services.logging.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            result = await async_test_function(5)
            
            assert result == 10
            
            # 检查日志调用
            assert mock_logger.info.call_count == 2  # 开始和完成
            
            # 检查开始日志
            start_call = mock_logger.info.call_args_list[0]
            assert "Function started" in start_call[0][0]
            assert start_call[1]["function"] == "async_test_function"
            
            # 检查完成日志
            end_call = mock_logger.info.call_args_list[1]
            assert "Function completed" in end_call[0][0]
            assert end_call[1]["success"] is True
            assert "duration" in end_call[1]
    
    def test_sync_function_logging(self):
        """测试同步函数日志记录"""
        
        @log_performance("test_sync")
        def sync_test_function(value):
            time.sleep(0.01)
            return value * 3
        
        with patch('services.logging.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            result = sync_test_function(4)
            
            assert result == 12
            
            # 检查日志调用
            assert mock_logger.info.call_count == 2
    
    @pytest.mark.asyncio
    async def test_async_function_error_logging(self):
        """测试异步函数错误日志记录"""
        
        @log_performance("test_error")
        async def failing_async_function():
            await asyncio.sleep(0.01)
            raise ValueError("Test error")
        
        with patch('services.logging.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            with pytest.raises(ValueError):
                await failing_async_function()
            
            # 检查错误日志
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args
            assert "Function failed" in error_call[0][0]
            assert error_call[1]["success"] is False
            assert error_call[1]["error"] == "Test error"
            assert error_call[1]["error_type"] == "ValueError"


class TestLoggingConfiguration:
    """日志配置测试"""
    
    def test_configure_logging(self):
        """测试日志配置"""
        # 这个测试主要确保配置函数不会抛出异常
        configure_logging(log_level="DEBUG", json_format=False)
        
        # 获取日志器
        logger = get_logger("test")
        assert logger is not None
        
        # 测试日志记录
        logger.info("Test message", extra_field="test_value")
    
    @patch('services.logging.structlog')
    def test_configure_logging_with_file(self, mock_structlog):
        """测试带文件的日志配置"""
        configure_logging(log_level="INFO", log_file="/tmp/test.log", json_format=True)
        
        # 验证 structlog 被配置
        mock_structlog.configure.assert_called_once()


class TestGlobalInstances:
    """全局实例测试"""
    
    def test_global_request_tracker(self):
        """测试全局请求追踪器"""
        assert request_tracker is not None
        assert isinstance(request_tracker, RequestTracker)
    
    def test_global_performance_monitor(self):
        """测试全局性能监控器"""
        assert performance_monitor is not None
        assert isinstance(performance_monitor, PerformanceMonitor)