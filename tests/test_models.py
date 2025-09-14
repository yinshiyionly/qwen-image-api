"""
数据模型单元测试

测试 API 请求和响应模型的验证功能。
"""

import pytest
from pydantic import ValidationError
from datetime import datetime

from models.requests import TextToImageRequest, ImageToImageRequest
from models.responses import ImageResponse, HealthResponse, InfoResponse, ErrorResponse


class TestTextToImageRequest:
    """文生图请求模型测试"""

    def test_valid_request(self):
        """测试有效的请求数据"""
        request = TextToImageRequest(
            prompt="一只可爱的小猫",
            width=512,
            height=512,
            num_inference_steps=20,
            guidance_scale=7.5
        )
        
        assert request.prompt == "一只可爱的小猫"
        assert request.width == 512
        assert request.height == 512
        assert request.num_inference_steps == 20
        assert request.guidance_scale == 7.5

    def test_minimal_request(self):
        """测试最小有效请求（仅必需字段）"""
        request = TextToImageRequest(prompt="测试提示词")
        
        assert request.prompt == "测试提示词"
        assert request.width == 512  # 默认值
        assert request.height == 512  # 默认值
        assert request.num_inference_steps == 20  # 默认值
        assert request.guidance_scale == 7.5  # 默认值

    def test_empty_prompt_validation(self):
        """测试空提示词验证"""
        with pytest.raises(ValidationError) as exc_info:
            TextToImageRequest(prompt="")
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "value_error.any_str.min_length"

    def test_prompt_too_long_validation(self):
        """测试提示词过长验证"""
        long_prompt = "a" * 1001  # 超过最大长度
        
        with pytest.raises(ValidationError) as exc_info:
            TextToImageRequest(prompt=long_prompt)
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "value_error.any_str.max_length"

    def test_width_validation(self):
        """测试宽度参数验证"""
        # 测试最小值边界
        with pytest.raises(ValidationError):
            TextToImageRequest(prompt="test", width=255)
        
        # 测试最大值边界
        with pytest.raises(ValidationError):
            TextToImageRequest(prompt="test", width=2049)
        
        # 测试有效边界值
        request_min = TextToImageRequest(prompt="test", width=256)
        request_max = TextToImageRequest(prompt="test", width=2048)
        
        assert request_min.width == 256
        assert request_max.width == 2048

    def test_height_validation(self):
        """测试高度参数验证"""
        # 测试最小值边界
        with pytest.raises(ValidationError):
            TextToImageRequest(prompt="test", height=255)
        
        # 测试最大值边界  
        with pytest.raises(ValidationError):
            TextToImageRequest(prompt="test", height=2049)

    def test_num_inference_steps_validation(self):
        """测试推理步数验证"""
        # 测试最小值边界
        with pytest.raises(ValidationError):
            TextToImageRequest(prompt="test", num_inference_steps=0)
        
        # 测试最大值边界
        with pytest.raises(ValidationError):
            TextToImageRequest(prompt="test", num_inference_steps=101)

    def test_guidance_scale_validation(self):
        """测试引导比例验证"""
        # 测试最小值边界
        with pytest.raises(ValidationError):
            TextToImageRequest(prompt="test", guidance_scale=0.9)
        
        # 测试最大值边界
        with pytest.raises(ValidationError):
            TextToImageRequest(prompt="test", guidance_scale=20.1)


class TestImageToImageRequest:
    """图生图请求模型测试"""

    def test_valid_request(self):
        """测试有效的请求数据"""
        request = ImageToImageRequest(
            prompt="转换为水彩画风格",
            strength=0.8,
            width=512,
            height=512,
            num_inference_steps=20
        )
        
        assert request.prompt == "转换为水彩画风格"
        assert request.strength == 0.8
        assert request.width == 512
        assert request.height == 512
        assert request.num_inference_steps == 20

    def test_minimal_request(self):
        """测试最小有效请求"""
        request = ImageToImageRequest(prompt="测试提示词")
        
        assert request.prompt == "测试提示词"
        assert request.strength == 0.8  # 默认值
        assert request.width is None  # 默认值
        assert request.height is None  # 默认值
        assert request.num_inference_steps == 20  # 默认值

    def test_strength_validation(self):
        """测试强度参数验证"""
        # 测试最小值边界
        with pytest.raises(ValidationError):
            ImageToImageRequest(prompt="test", strength=0.09)
        
        # 测试最大值边界
        with pytest.raises(ValidationError):
            ImageToImageRequest(prompt="test", strength=1.01)
        
        # 测试有效边界值
        request_min = ImageToImageRequest(prompt="test", strength=0.1)
        request_max = ImageToImageRequest(prompt="test", strength=1.0)
        
        assert request_min.strength == 0.1
        assert request_max.strength == 1.0


class TestImageResponse:
    """图像响应模型测试"""

    def test_successful_response(self):
        """测试成功响应"""
        response = ImageResponse(
            success=True,
            image="base64_encoded_data",
            metadata={
                "width": 512,
                "height": 512,
                "inference_time": 2.5
            }
        )
        
        assert response.success is True
        assert response.image == "base64_encoded_data"
        assert response.metadata["width"] == 512
        assert response.error is None

    def test_error_response(self):
        """测试错误响应"""
        response = ImageResponse(
            success=False,
            error="模型推理失败"
        )
        
        assert response.success is False
        assert response.image is None
        assert response.error == "模型推理失败"


class TestHealthResponse:
    """健康检查响应模型测试"""

    def test_healthy_response(self):
        """测试健康状态响应"""
        response = HealthResponse(
            status="healthy",
            model_loaded=True,
            memory_usage={"total": "16GB", "used": "8GB"},
            uptime=3600.5
        )
        
        assert response.status == "healthy"
        assert response.model_loaded is True
        assert response.memory_usage["total"] == "16GB"
        assert response.uptime == 3600.5
        assert isinstance(response.timestamp, datetime)


class TestInfoResponse:
    """服务信息响应模型测试"""

    def test_info_response(self):
        """测试服务信息响应"""
        response = InfoResponse(
            service_name="qwen-image-api-service",
            version="1.0.0",
            model_info={"name": "qwen-image", "device": "cuda"},
            supported_formats=["JPEG", "PNG"],
            api_endpoints=["/text-to-image", "/image-to-image"]
        )
        
        assert response.service_name == "qwen-image-api-service"
        assert response.version == "1.0.0"
        assert response.model_info["name"] == "qwen-image"
        assert "JPEG" in response.supported_formats
        assert "/text-to-image" in response.api_endpoints


class TestErrorResponse:
    """错误响应模型测试"""

    def test_error_response(self):
        """测试错误响应"""
        response = ErrorResponse(
            error={
                "code": "INVALID_PROMPT",
                "message": "提示词不能为空",
                "details": {"field": "prompt"}
            }
        )
        
        assert response.success is False
        assert response.error["code"] == "INVALID_PROMPT"
        assert response.error["message"] == "提示词不能为空"