"""
请求处理器单元测试

测试 RequestProcessor 类的验证和预处理功能。
"""

import pytest
import io
from unittest.mock import Mock, patch
from PIL import Image
from fastapi import UploadFile, HTTPException

from services.request_processor import RequestProcessor
from models.requests import TextToImageRequest, ImageToImageRequest
from models.responses import ImageResponse, ErrorResponse


class TestRequestProcessor:
    """请求处理器测试类"""

    def setup_method(self):
        """测试前的设置"""
        self.processor = RequestProcessor()

    def test_init_default_settings(self):
        """测试默认初始化设置"""
        processor = RequestProcessor()
        assert processor.max_file_size == 10 * 1024 * 1024  # 10MB
        assert processor.SUPPORTED_IMAGE_FORMATS == {"JPEG", "PNG", "WEBP", "BMP"}

    def test_init_custom_settings(self):
        """测试自定义初始化设置"""
        custom_size = 5 * 1024 * 1024  # 5MB
        processor = RequestProcessor(max_file_size=custom_size)
        assert processor.max_file_size == custom_size

    def test_validate_text_request_success(self):
        """测试文生图请求验证成功"""
        request = TextToImageRequest(
            prompt="一只可爱的小猫",
            width=512,
            height=512
        )
        
        result = self.processor.validate_text_request(request)
        assert result is True

    def test_validate_text_request_empty_prompt(self):
        """测试空提示词验证失败"""
        request = TextToImageRequest(prompt="   ")  # 仅空白字符
        
        with pytest.raises(HTTPException) as exc_info:
            self.processor.validate_text_request(request)
        
        assert exc_info.value.status_code == 400
        assert "提示词不能为空" in exc_info.value.detail

    def test_validate_text_request_extreme_aspect_ratio(self):
        """测试极端宽高比的警告处理"""
        request = TextToImageRequest(
            prompt="测试",
            width=2048,
            height=256  # 8:1 的极端比例
        )
        
        # 应该通过验证但记录警告
        with patch('services.request_processor.logger') as mock_logger:
            result = self.processor.validate_text_request(request)
            assert result is True
            mock_logger.warning.assert_called()

    def test_validate_image_request_success(self):
        """测试图生图请求验证成功"""
        request = ImageToImageRequest(
            prompt="转换为水彩画风格",
            strength=0.8
        )
        
        result = self.processor.validate_image_request(request)
        assert result is True

    def test_validate_image_request_empty_prompt(self):
        """测试图生图空提示词验证失败"""
        request = ImageToImageRequest(prompt="")
        
        with pytest.raises(HTTPException) as exc_info:
            self.processor.validate_image_request(request)
        
        assert exc_info.value.status_code == 400

    def test_validate_image_request_extreme_strength(self):
        """测试极端强度值的警告处理"""
        # 测试极低强度
        request_low = ImageToImageRequest(prompt="测试", strength=0.05)
        with patch('services.request_processor.logger') as mock_logger:
            result = self.processor.validate_image_request(request_low)
            assert result is True
            mock_logger.warning.assert_called()

        # 测试极高强度
        request_high = ImageToImageRequest(prompt="测试", strength=0.98)
        with patch('services.request_processor.logger') as mock_logger:
            result = self.processor.validate_image_request(request_high)
            assert result is True
            mock_logger.warning.assert_called()

    def create_test_image(self, width=512, height=512, format='PNG'):
        """创建测试图像"""
        image = Image.new('RGB', (width, height), color='red')
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        buffer.seek(0)
        return buffer

    def create_upload_file(self, content, filename, content_type="image/png"):
        """创建模拟的上传文件"""
        file = Mock(spec=UploadFile)
        file.filename = filename
        file.content_type = content_type
        file.file = content
        file.size = len(content.getvalue()) if hasattr(content, 'getvalue') else None
        return file

    def test_process_image_upload_success(self):
        """测试图像上传处理成功"""
        # 创建测试图像
        image_buffer = self.create_test_image()
        upload_file = self.create_upload_file(image_buffer, "test.png")
        
        result = self.processor.process_image_upload(upload_file)
        
        assert isinstance(result, Image.Image)
        assert result.mode == 'RGB'
        assert result.size == (512, 512)

    def test_process_image_upload_unsupported_extension(self):
        """测试不支持的文件扩展名"""
        image_buffer = self.create_test_image()
        upload_file = self.create_upload_file(image_buffer, "test.gif")
        
        with pytest.raises(HTTPException) as exc_info:
            self.processor.process_image_upload(upload_file)
        
        assert exc_info.value.status_code == 415
        assert "不支持的文件格式" in exc_info.value.detail

    def test_process_image_upload_file_too_large(self):
        """测试文件过大"""
        # 创建一个大文件的模拟
        large_content = io.BytesIO(b'x' * (11 * 1024 * 1024))  # 11MB
        upload_file = self.create_upload_file(large_content, "test.png")
        
        with pytest.raises(HTTPException) as exc_info:
            self.processor.process_image_upload(upload_file)
        
        assert exc_info.value.status_code == 413
        assert "文件大小超过限制" in exc_info.value.detail

    def test_process_image_upload_image_too_large(self):
        """测试图像尺寸过大"""
        # 创建超大尺寸图像
        large_image_buffer = self.create_test_image(width=3000, height=3000)
        upload_file = self.create_upload_file(large_image_buffer, "test.png")
        
        with pytest.raises(HTTPException) as exc_info:
            self.processor.process_image_upload(upload_file)
        
        assert exc_info.value.status_code == 400
        assert "图像尺寸过大" in exc_info.value.detail

    def test_process_image_upload_convert_mode(self):
        """测试图像模式转换"""
        # 创建 RGBA 模式的图像
        image = Image.new('RGBA', (512, 512), color=(255, 0, 0, 128))
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        
        upload_file = self.create_upload_file(buffer, "test.png")
        
        with patch('services.request_processor.logger') as mock_logger:
            result = self.processor.process_image_upload(upload_file)
            
            assert result.mode == 'RGB'
            mock_logger.info.assert_called()

    def test_process_image_upload_invalid_image(self):
        """测试无效图像文件"""
        # 创建非图像内容
        invalid_content = io.BytesIO(b'not an image')
        upload_file = self.create_upload_file(invalid_content, "test.png")
        
        with pytest.raises(HTTPException) as exc_info:
            self.processor.process_image_upload(upload_file)
        
        assert exc_info.value.status_code == 400
        assert "无法处理图像文件" in exc_info.value.detail

    def test_format_image_response_success(self):
        """测试图像响应格式化成功"""
        # 创建测试图像
        image = Image.new('RGB', (512, 512), color='blue')
        metadata = {"inference_time": 2.5, "model": "qwen-image"}
        
        response = self.processor.format_image_response(image, metadata)
        
        assert isinstance(response, ImageResponse)
        assert response.success is True
        assert response.image is not None
        assert response.metadata["width"] == 512
        assert response.metadata["height"] == 512
        assert response.metadata["inference_time"] == 2.5

    def test_format_image_response_no_metadata(self):
        """测试无元数据的图像响应格式化"""
        image = Image.new('RGB', (256, 256), color='green')
        
        response = self.processor.format_image_response(image)
        
        assert response.success is True
        assert response.metadata["width"] == 256
        assert response.metadata["height"] == 256
        assert response.metadata["format"] == "PNG"

    def test_format_error_response(self):
        """测试错误响应格式化"""
        error_code = "INVALID_INPUT"
        error_message = "输入参数无效"
        details = {"field": "prompt", "value": ""}
        
        response = self.processor.format_error_response(
            error_code, error_message, details
        )
        
        assert isinstance(response, ErrorResponse)
        assert response.success is False
        assert response.error["code"] == error_code
        assert response.error["message"] == error_message
        assert response.error["details"] == details

    def test_format_error_response_no_details(self):
        """测试无详情的错误响应格式化"""
        response = self.processor.format_error_response(
            "GENERAL_ERROR", "通用错误"
        )
        
        assert response.error["code"] == "GENERAL_ERROR"
        assert response.error["message"] == "通用错误"
        assert "details" not in response.error

    def test_get_supported_formats(self):
        """测试获取支持的格式列表"""
        formats = self.processor.get_supported_formats()
        
        assert isinstance(formats, list)
        assert "JPEG" in formats
        assert "PNG" in formats
        assert "WEBP" in formats
        assert "BMP" in formats

    def test_get_max_file_size(self):
        """测试获取最大文件大小"""
        size = self.processor.get_max_file_size()
        assert size == 10 * 1024 * 1024  # 10MB

    def test_custom_max_file_size(self):
        """测试自定义最大文件大小"""
        custom_size = 5 * 1024 * 1024
        processor = RequestProcessor(max_file_size=custom_size)
        
        assert processor.get_max_file_size() == custom_size