"""
中间件测试

测试安全和性能中间件的功能。
"""

import asyncio
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import Response

from api.middleware import (
    FileValidationMiddleware,
    RateLimitMiddleware,
    ConcurrencyLimitMiddleware,
    SecurityHeadersMiddleware
)


class TestFileValidationMiddleware:
    """文件验证中间件测试"""
    
    def test_file_size_validation(self):
        """测试文件大小验证"""
        app = FastAPI()
        
        # 添加中间件，设置较小的文件大小限制
        app.add_middleware(
            FileValidationMiddleware,
            max_file_size=1024,  # 1KB
            allowed_content_types={"image/jpeg", "image/png"}
        )
        
        @app.post("/image-to-image")
        async def mock_endpoint():
            return {"success": True}
        
        client = TestClient(app)
        
        # 测试文件过大的情况
        response = client.post(
            "/image-to-image",
            headers={"content-length": "2048"}  # 2KB
        )
        
        assert response.status_code == 413
        assert "FILE_TOO_LARGE" in response.json()["error"]["code"]
    
    def test_content_type_validation(self):
        """测试内容类型验证"""
        app = FastAPI()
        
        app.add_middleware(
            FileValidationMiddleware,
            max_file_size=10 * 1024 * 1024,
            allowed_content_types={"image/jpeg", "image/png"}
        )
        
        @app.post("/image-to-image")
        async def mock_endpoint():
            return {"success": True}
        
        client = TestClient(app)
        
        # 测试不支持的内容类型
        response = client.post(
            "/image-to-image",
            headers={"content-type": "application/pdf"}
        )
        
        assert response.status_code == 415
        assert "UNSUPPORTED_MEDIA_TYPE" in response.json()["error"]["code"]
    
    def test_valid_request_passes(self):
        """测试有效请求通过验证"""
        app = FastAPI()
        
        app.add_middleware(
            FileValidationMiddleware,
            max_file_size=10 * 1024 * 1024,
            allowed_content_types={"image/jpeg", "image/png"}
        )
        
        @app.post("/image-to-image")
        async def mock_endpoint():
            return {"success": True}
        
        client = TestClient(app)
        
        # 测试有效的 multipart 请求
        response = client.post(
            "/image-to-image",
            headers={
                "content-type": "multipart/form-data; boundary=test",
                "content-length": "1024"
            }
        )
        
        # 应该通过中间件验证（虽然可能在路由层失败）
        assert response.status_code != 413
        assert response.status_code != 415


class TestRateLimitMiddleware:
    """速率限制中间件测试"""
    
    def test_rate_limit_enforcement(self):
        """测试速率限制执行"""
        app = FastAPI()
        
        # 设置很低的限制进行测试
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=2,
            requests_per_hour=10,
            burst_size=2
        )
        
        @app.get("/test")
        async def mock_endpoint():
            return {"success": True}
        
        client = TestClient(app)
        
        # 前两个请求应该成功
        response1 = client.get("/test")
        assert response1.status_code == 200
        
        response2 = client.get("/test")
        assert response2.status_code == 200
        
        # 第三个请求应该被限制
        response3 = client.get("/test")
        assert response3.status_code == 429
        assert "RATE_LIMIT_EXCEEDED" in response3.json()["error"]["code"]
    
    def test_health_endpoint_bypass(self):
        """测试健康检查端点绕过速率限制"""
        app = FastAPI()
        
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=1,
            requests_per_hour=1,
            burst_size=1
        )
        
        @app.get("/health")
        async def health_endpoint():
            return {"status": "healthy"}
        
        @app.get("/test")
        async def test_endpoint():
            return {"success": True}
        
        client = TestClient(app)
        
        # 健康检查端点应该不受限制
        for _ in range(5):
            response = client.get("/health")
            assert response.status_code == 200
        
        # 但是其他端点应该受限制
        client.get("/test")  # 第一个请求
        response = client.get("/test")  # 第二个请求应该被限制
        assert response.status_code == 429
    
    def test_rate_limit_headers(self):
        """测试速率限制响应头"""
        app = FastAPI()
        
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=10,
            requests_per_hour=100,
            burst_size=5
        )
        
        @app.get("/test")
        async def mock_endpoint():
            return {"success": True}
        
        client = TestClient(app)
        
        response = client.get("/test")
        assert response.status_code == 200
        
        # 检查速率限制头
        assert "X-RateLimit-Limit-Minute" in response.headers
        assert "X-RateLimit-Limit-Hour" in response.headers
        assert "X-RateLimit-Remaining-Minute" in response.headers
        assert "X-RateLimit-Remaining-Hour" in response.headers


class TestConcurrencyLimitMiddleware:
    """并发限制中间件测试"""
    
    @pytest.mark.asyncio
    async def test_concurrency_limit(self):
        """测试并发限制"""
        app = FastAPI()
        
        # 设置很低的并发限制
        app.add_middleware(
            ConcurrencyLimitMiddleware,
            max_concurrent_requests=1,
            queue_timeout=1
        )
        
        request_started = asyncio.Event()
        request_can_finish = asyncio.Event()
        
        @app.post("/text-to-image")
        async def slow_endpoint():
            request_started.set()
            await request_can_finish.wait()
            return {"success": True}
        
        @app.get("/test")
        async def fast_endpoint():
            return {"success": True}
        
        # 非推理端点不应该受并发限制影响
        with TestClient(app) as client:
            response = client.get("/test")
            assert response.status_code == 200
    
    def test_concurrency_headers(self):
        """测试并发信息头"""
        app = FastAPI()
        
        app.add_middleware(
            ConcurrencyLimitMiddleware,
            max_concurrent_requests=4,
            queue_timeout=30
        )
        
        @app.post("/text-to-image")
        async def mock_endpoint():
            return {"success": True}
        
        client = TestClient(app)
        
        response = client.post("/text-to-image")
        
        # 检查并发信息头
        assert "X-Concurrency-Active" in response.headers
        assert "X-Concurrency-Queued" in response.headers
        assert "X-Concurrency-Limit" in response.headers
        assert response.headers["X-Concurrency-Limit"] == "4"


class TestSecurityHeadersMiddleware:
    """安全头中间件测试"""
    
    def test_security_headers_added(self):
        """测试安全头被添加"""
        app = FastAPI()
        
        app.add_middleware(SecurityHeadersMiddleware)
        
        @app.get("/test")
        async def mock_endpoint():
            return {"success": True}
        
        client = TestClient(app)
        
        response = client.get("/test")
        
        # 检查安全头
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    
    def test_cache_headers_for_api_endpoints(self):
        """测试 API 端点的缓存头"""
        app = FastAPI()
        
        app.add_middleware(SecurityHeadersMiddleware)
        
        @app.post("/text-to-image")
        async def api_endpoint():
            return {"success": True}
        
        @app.get("/info")
        async def info_endpoint():
            return {"info": "test"}
        
        client = TestClient(app)
        
        # API 端点应该有缓存控制头
        response = client.post("/text-to-image")
        assert response.headers["Cache-Control"] == "no-cache, no-store, must-revalidate"
        assert response.headers["Pragma"] == "no-cache"
        assert response.headers["Expires"] == "0"
        
        # 其他端点不应该有这些头
        response = client.get("/info")
        assert "Cache-Control" not in response.headers or "no-cache" not in response.headers["Cache-Control"]


class TestMiddlewareIntegration:
    """中间件集成测试"""
    
    def test_multiple_middleware_stack(self):
        """测试多个中间件协同工作"""
        app = FastAPI()
        
        # 添加多个中间件
        app.add_middleware(SecurityHeadersMiddleware)
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=10,
            requests_per_hour=100,
            burst_size=5
        )
        app.add_middleware(
            FileValidationMiddleware,
            max_file_size=1024 * 1024,
            allowed_content_types={"image/jpeg"}
        )
        
        @app.post("/image-to-image")
        async def mock_endpoint():
            return {"success": True}
        
        client = TestClient(app)
        
        response = client.post(
            "/image-to-image",
            headers={
                "content-type": "multipart/form-data; boundary=test",
                "content-length": "1024"
            }
        )
        
        # 应该通过所有中间件
        assert response.status_code != 413  # 文件大小检查
        assert response.status_code != 415  # 内容类型检查
        assert response.status_code != 429  # 速率限制检查
        
        # 应该有安全头
        assert "X-Content-Type-Options" in response.headers
        assert "X-RateLimit-Limit-Minute" in response.headers