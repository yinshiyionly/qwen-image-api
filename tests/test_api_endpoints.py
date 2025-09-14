"""
API 端点测试

测试 FastAPI 应用的各个端点功能。
"""

import pytest
import io
from unittest.mock import Mock, patch, MagicMock
from PIL import Image
from fastapi.testclient import TestClient

from api import app
from models.responses import ImageResponse, HealthResponse, InfoResponse


@pytest.fixture
def client():
    """测试客户端"""
    return TestClient(app)


@pytest.fixture
def mock_model_manager():
    """模拟模型管理器"""
    mock = Mock()
    mock.is_model_loaded.return_value = True
    mock.get_model_info.return_value = {
        'loaded': True,
        'model_path': '/path/to/model',
        'device': 'cuda',
        'torch_dtype': 'float16'
    }
    mock.get_resource_stats.return_value = {
        'inference_count': 10,
        'error_count': 0,
        'memory_usage_mb': {'current': 1024, 'peak': 2048}
    }
    mock.get_supported_formats.return_value = {
        'image_formats': ['JPEG', 'PNG', 'WEBP'],
        'max_resolution': {'width': 2048, 'height': 2048}
    }
    
    # 创建测试图像
    test_image = Image.new('RGB', (512, 512), color='blue')
    mock.text_to_image.return_value = test_image
    mock.image_to_image.return_value = test_image
    
    return mock


@pytest.fixture
def mock_request_processor():
    """模拟请求处理器"""
    mock = Mock()
    mock.validate_text_request.return_value = True
    mock.validate_image_request.return_value = True
    mock.get_supported_formats.return_value = ['JPEG', 'PNG', 'WEBP']
    
    # 模拟图像处理
    test_image = Image.new('RGB', (512, 512), color='red')
    mock.process_image_upload.return_value = test_image
    
    # 模拟响应格式化
    mock.format_image_response.return_value = ImageResponse(
        success=True,
        image="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
        metadata={
            "width": 512,
            "height": 512,
            "inference_time": 1.5
        }
    )
    
    return mock


class TestAPIEndpoints:
    """API 端点测试类"""
    
    @patch('api.app.qwen_api.get_model_manager')
    @patch('api.app.qwen_api.get_request_processor')
    def test_root_endpoint(self, mock_get_processor, mock_get_manager, client):
        """测试根端点"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
    
    @patch('api.app.qwen_api.get_model_manager')
    @patch('api.app.qwen_api.get_request_processor')
    def test_text_to_image_success(self, mock_get_processor, mock_get_manager, 
                                  mock_model_manager, mock_request_processor, client):
        """测试文生图成功场景"""
        mock_get_manager.return_value = mock_model_manager
        mock_get_processor.return_value = mock_request_processor
        
        request_data = {
            "prompt": "一只可爱的小猫",
            "width": 512,
            "height": 512,
            "num_inference_steps": 20,
            "guidance_scale": 7.5
        }
        
        response = client.post("/text-to-image", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "image" in data
        assert "metadata" in data
        
        # 验证调用
        mock_request_processor.validate_text_request.assert_called_once()
        mock_model_manager.is_model_loaded.assert_called_once()
        mock_model_manager.text_to_image.assert_called_once()
    
    @patch('api.app.qwen_api.get_model_manager')
    @patch('api.app.qwen_api.get_request_processor')
    def test_text_to_image_model_not_loaded(self, mock_get_processor, mock_get_manager, 
                                           mock_model_manager, mock_request_processor, client):
        """测试模型未加载的情况"""
        mock_get_manager.return_value = mock_model_manager
        mock_get_processor.return_value = mock_request_processor
        mock_model_manager.is_model_loaded.return_value = False
        
        request_data = {
            "prompt": "一只可爱的小猫",
            "width": 512,
            "height": 512
        }
        
        response = client.post("/text-to-image", json=request_data)
        assert response.status_code == 503
        
        data = response.json()
        assert data["success"] is False
        assert "模型未加载" in data["error"]["message"]
    
    @patch('api.app.qwen_api.get_model_manager')
    @patch('api.app.qwen_api.get_request_processor')
    def test_text_to_image_validation_error(self, mock_get_processor, mock_get_manager, 
                                           mock_model_manager, mock_request_processor, client):
        """测试参数验证错误"""
        mock_get_manager.return_value = mock_model_manager
        mock_get_processor.return_value = mock_request_processor
        
        # 空提示词
        request_data = {
            "prompt": "",
            "width": 512,
            "height": 512
        }
        
        response = client.post("/text-to-image", json=request_data)
        assert response.status_code == 422  # Pydantic 验证错误
    
    @patch('api.app.qwen_api.get_model_manager')
    @patch('api.app.qwen_api.get_request_processor')
    def test_image_to_image_success(self, mock_get_processor, mock_get_manager, 
                                   mock_model_manager, mock_request_processor, client):
        """测试图生图成功场景"""
        mock_get_manager.return_value = mock_model_manager
        mock_get_processor.return_value = mock_request_processor
        
        # 创建测试图像文件
        test_image = Image.new('RGB', (256, 256), color='green')
        img_buffer = io.BytesIO()
        test_image.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        files = {"image": ("test.png", img_buffer, "image/png")}
        data = {
            "prompt": "转换为水彩画风格",
            "strength": 0.8,
            "width": 512,
            "height": 512,
            "num_inference_steps": 20
        }
        
        response = client.post("/image-to-image", files=files, data=data)
        assert response.status_code == 200
        
        response_data = response.json()
        assert response_data["success"] is True
        assert "image" in response_data
        assert "metadata" in response_data
        
        # 验证调用
        mock_request_processor.process_image_upload.assert_called_once()
        mock_request_processor.validate_image_request.assert_called_once()
        mock_model_manager.image_to_image.assert_called_once()
    
    @patch('api.app.qwen_api.get_model_manager')
    def test_health_check_healthy(self, mock_get_manager, mock_model_manager, client):
        """测试健康检查 - 健康状态"""
        mock_get_manager.return_value = mock_model_manager
        
        with patch('api.app.qwen_api.get_uptime', return_value=3600.0):
            response = client.get("/health")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["model_loaded"] is True
        assert "memory_usage" in data
        assert "uptime" in data
        assert "timestamp" in data
    
    @patch('api.app.qwen_api.get_model_manager')
    def test_health_check_degraded(self, mock_get_manager, mock_model_manager, client):
        """测试健康检查 - 降级状态"""
        mock_get_manager.return_value = mock_model_manager
        mock_model_manager.is_model_loaded.return_value = False
        
        with patch('api.app.qwen_api.get_uptime', return_value=1800.0):
            response = client.get("/health")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "degraded"
        assert data["model_loaded"] is False
    
    @patch('api.app.qwen_api.get_model_manager')
    @patch('api.app.qwen_api.get_request_processor')
    def test_service_info(self, mock_get_processor, mock_get_manager, 
                         mock_model_manager, mock_request_processor, client):
        """测试服务信息端点"""
        mock_get_manager.return_value = mock_model_manager
        mock_get_processor.return_value = mock_request_processor
        
        response = client.get("/info")
        assert response.status_code == 200
        
        data = response.json()
        assert data["service_name"] == "qwen-image-api-service"
        assert data["version"] == "1.0.0"
        assert "model_info" in data
        assert "supported_formats" in data
        assert "api_endpoints" in data
        
        # 验证端点列表
        expected_endpoints = [
            "/text-to-image",
            "/image-to-image",
            "/health",
            "/info"
        ]
        for endpoint in expected_endpoints:
            assert endpoint in data["api_endpoints"]


class TestAPIErrorHandling:
    """API 错误处理测试"""
    
    @patch('api.app.qwen_api.get_model_manager')
    @patch('api.app.qwen_api.get_request_processor')
    def test_validation_error_handling(self, mock_get_processor, mock_get_manager, client):
        """测试验证错误处理"""
        # 发送无效的请求数据
        invalid_data = {
            "prompt": "test",
            "width": -1,  # 无效宽度
            "height": 5000  # 超出范围
        }
        
        response = client.post("/text-to-image", json=invalid_data)
        assert response.status_code == 422
        
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"
    
    @patch('api.app.qwen_api.get_model_manager')
    def test_internal_error_handling(self, mock_get_manager, client):
        """测试内部错误处理"""
        # 模拟内部错误
        mock_get_manager.side_effect = Exception("Internal error")
        
        response = client.get("/health")
        assert response.status_code == 200  # health 端点有自己的错误处理
        
        data = response.json()
        assert data["status"] == "unhealthy"
    
    def test_not_found_error(self, client):
        """测试 404 错误"""
        response = client.get("/nonexistent")
        assert response.status_code == 404


class TestAPIMiddleware:
    """API 中间件测试"""
    
    @patch('api.app.qwen_api.get_model_manager')
    @patch('api.app.qwen_api.get_request_processor')
    def test_request_logging_middleware(self, mock_get_processor, mock_get_manager, client):
        """测试请求日志中间件"""
        mock_get_manager.return_value = Mock()
        mock_get_processor.return_value = Mock()
        
        response = client.get("/")
        
        # 检查响应头中是否包含处理时间
        assert "X-Process-Time" in response.headers
        assert float(response.headers["X-Process-Time"]) >= 0
    
    def test_cors_middleware(self, client):
        """测试 CORS 中间件"""
        response = client.options("/", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        })
        
        # 检查 CORS 头
        assert "access-control-allow-origin" in response.headers