"""
错误处理系统测试

测试统一错误处理和响应格式化功能。
"""

import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from services.error_handler import ErrorHandler, ErrorCategory, ErrorCode, create_error_response
from services.exceptions import ModelNotLoadedError, InferenceError, ValidationError as CustomValidationError


class TestErrorHandler:
    """错误处理器测试"""
    
    def setup_method(self):
        """设置测试"""
        self.error_handler = ErrorHandler()
        self.mock_request = Mock(spec=Request)
        self.mock_request.url.path = "/test"
        self.mock_request.method = "POST"
        self.mock_request.headers = {"user-agent": "test-client"}
        self.mock_request.client.host = "127.0.0.1"
    
    def test_http_exception_handling(self):
        """测试 HTTP 异常处理"""
        exc = HTTPException(status_code=404, detail="Not found")
        
        response = self.error_handler.handle_exception(self.mock_request, exc)
        
        assert response.status_code == 404
        response_data = response.body.decode()
        assert "HTTP_404" in response_data
        assert "Not found" in response_data
    
    def test_validation_error_handling(self):
        """测试验证错误处理"""
        # 模拟 RequestValidationError
        exc = RequestValidationError([{"loc": ["field"], "msg": "field required", "type": "value_error.missing"}])
        
        response = self.error_handler.handle_exception(self.mock_request, exc)
        
        assert response.status_code == 422
        response_data = response.body.decode()
        assert "VALIDATION_ERROR" in response_data
        assert "请求参数验证失败" in response_data
    
    def test_custom_model_exception_handling(self):
        """测试自定义模型异常处理"""
        exc = ModelNotLoadedError("Model not available")
        
        response = self.error_handler.handle_exception(self.mock_request, exc)
        
        assert response.status_code == 503
        response_data = response.body.decode()
        assert "MODEL_NOT_LOADED" in response_data
        assert "模型未加载" in response_data
    
    def test_inference_error_handling(self):
        """测试推理错误处理"""
        exc = InferenceError("Inference failed")
        
        response = self.error_handler.handle_exception(self.mock_request, exc)
        
        assert response.status_code == 500
        response_data = response.body.decode()
        assert "INFERENCE_ERROR" in response_data
        assert "模型推理失败" in response_data
    
    def test_custom_validation_error_handling(self):
        """测试自定义验证错误处理"""
        exc = CustomValidationError("Invalid parameter")
        
        response = self.error_handler.handle_exception(self.mock_request, exc)
        
        assert response.status_code == 400
        response_data = response.body.decode()
        assert "VALIDATION_ERROR" in response_data
        assert "参数验证失败" in response_data
    
    def test_system_exception_handling(self):
        """测试系统异常处理"""
        exc = MemoryError("Out of memory")
        
        response = self.error_handler.handle_exception(self.mock_request, exc)
        
        assert response.status_code == 503
        response_data = response.body.decode()
        assert "MEMORY_ERROR" in response_data
        assert "系统内存不足" in response_data
    
    def test_unknown_exception_handling(self):
        """测试未知异常处理"""
        exc = RuntimeError("Unknown error")
        
        response = self.error_handler.handle_exception(self.mock_request, exc)
        
        assert response.status_code == 500
        response_data = response.body.decode()
        assert "INTERNAL_SERVER_ERROR" in response_data
        assert "服务器内部错误" in response_data
    
    def test_error_response_structure(self):
        """测试错误响应结构"""
        exc = HTTPException(status_code=400, detail="Bad request")
        
        response = self.error_handler.handle_exception(self.mock_request, exc)
        
        # 解析响应内容
        import json
        response_data = json.loads(response.body.decode())
        
        # 检查响应结构
        assert "success" in response_data
        assert response_data["success"] is False
        assert "error" in response_data
        
        error = response_data["error"]
        assert "code" in error
        assert "message" in error
        assert "category" in error
        assert "details" in error
        
        # 检查详细信息
        details = error["details"]
        assert "path" in details
        assert "method" in details
        assert "timestamp" in details
        assert details["path"] == "/test"
        assert details["method"] == "POST"
    
    @patch('services.error_handler.logger')
    def test_error_logging(self, mock_logger):
        """测试错误日志记录"""
        exc = HTTPException(status_code=500, detail="Server error")
        
        self.error_handler.handle_exception(self.mock_request, exc)
        
        # 验证日志被调用
        mock_logger.error.assert_called_once()
        
        # 检查日志参数
        call_args = mock_logger.error.call_args
        assert "Request failed" in call_args[0][0]
        assert "error_code" in call_args[1]
        assert "status_code" in call_args[1]
        assert "path" in call_args[1]
    
    def test_client_ip_extraction(self):
        """测试客户端 IP 提取"""
        # 测试 X-Forwarded-For 头
        self.mock_request.headers = {"x-forwarded-for": "192.168.1.1, 10.0.0.1"}
        
        response = self.error_handler.handle_exception(
            self.mock_request, 
            HTTPException(status_code=400, detail="Test")
        )
        
        # IP 应该被记录在日志中
        assert response.status_code == 400
    
    def test_include_traceback_option(self):
        """测试包含堆栈跟踪选项"""
        exc = RuntimeError("Test error")
        
        # 不包含堆栈跟踪
        response1 = self.error_handler.handle_exception(
            self.mock_request, exc, include_traceback=False
        )
        response_data1 = response1.body.decode()
        assert "traceback" not in response_data1
        
        # 包含堆栈跟踪
        response2 = self.error_handler.handle_exception(
            self.mock_request, exc, include_traceback=True
        )
        response_data2 = response2.body.decode()
        assert "traceback" in response_data2


class TestCreateErrorResponse:
    """创建错误响应函数测试"""
    
    def test_create_basic_error_response(self):
        """测试创建基本错误响应"""
        response = create_error_response(
            code="TEST_ERROR",
            message="Test error message",
            status_code=400
        )
        
        assert response.status_code == 400
        
        import json
        response_data = json.loads(response.body.decode())
        
        assert response_data["success"] is False
        assert response_data["error"]["code"] == "TEST_ERROR"
        assert response_data["error"]["message"] == "Test error message"
        assert response_data["error"]["details"] == {}
    
    def test_create_error_response_with_details(self):
        """测试创建带详细信息的错误响应"""
        details = {"field": "value", "count": 42}
        
        response = create_error_response(
            code="DETAILED_ERROR",
            message="Detailed error",
            status_code=422,
            details=details
        )
        
        assert response.status_code == 422
        
        import json
        response_data = json.loads(response.body.decode())
        
        assert response_data["error"]["details"] == details
    
    def test_create_error_response_default_status(self):
        """测试默认状态码"""
        response = create_error_response(
            code="DEFAULT_ERROR",
            message="Default error"
        )
        
        assert response.status_code == 500


class TestErrorCategories:
    """错误分类测试"""
    
    def test_error_category_enum(self):
        """测试错误分类枚举"""
        assert ErrorCategory.CLIENT_ERROR.value == "client_error"
        assert ErrorCategory.SERVER_ERROR.value == "server_error"
        assert ErrorCategory.VALIDATION_ERROR.value == "validation_error"
        assert ErrorCategory.MODEL_ERROR.value == "model_error"
    
    def test_error_code_enum(self):
        """测试错误代码枚举"""
        assert ErrorCode.BAD_REQUEST.value == "BAD_REQUEST"
        assert ErrorCode.INTERNAL_SERVER_ERROR.value == "INTERNAL_SERVER_ERROR"
        assert ErrorCode.VALIDATION_ERROR.value == "VALIDATION_ERROR"
        assert ErrorCode.MODEL_NOT_LOADED.value == "MODEL_NOT_LOADED"