"""
API 响应模型定义

包含图像生成、健康检查和服务信息的响应数据模型。
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class ImageResponse(BaseModel):
    """图像生成响应模型"""
    
    success: bool = Field(description="请求是否成功")
    image: Optional[str] = Field(None, description="base64 编码的图像数据")
    metadata: Optional[Dict[str, Any]] = Field(None, description="生成元数据")
    error: Optional[str] = Field(None, description="错误信息")

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
                "metadata": {
                    "width": 512,
                    "height": 512,
                    "inference_time": 2.5,
                    "model": "qwen-image",
                    "timestamp": "2024-01-01T12:00:00Z"
                },
                "error": None
            }
        }


class HealthResponse(BaseModel):
    """健康检查响应模型"""
    
    status: str = Field(description="服务状态")
    model_loaded: bool = Field(description="模型是否已加载")
    memory_usage: Dict[str, Any] = Field(description="内存使用情况")
    uptime: float = Field(description="服务运行时间（秒）")
    timestamp: datetime = Field(default_factory=datetime.now, description="检查时间")

    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "model_loaded": True,
                "memory_usage": {
                    "total": "16GB",
                    "used": "8GB",
                    "available": "8GB",
                    "gpu_memory": {
                        "total": "24GB",
                        "used": "12GB",
                        "available": "12GB"
                    }
                },
                "uptime": 3600.5,
                "timestamp": "2024-01-01T12:00:00Z"
            }
        }


class InfoResponse(BaseModel):
    """服务信息响应模型"""
    
    service_name: str = Field(description="服务名称")
    version: str = Field(description="服务版本")
    model_info: Dict[str, Any] = Field(description="模型信息")
    supported_formats: List[str] = Field(description="支持的图像格式")
    api_endpoints: List[str] = Field(description="可用的 API 端点")

    class Config:
        schema_extra = {
            "example": {
                "service_name": "qwen-image-api-service",
                "version": "1.0.0",
                "model_info": {
                    "name": "qwen-image",
                    "version": "latest",
                    "device": "cuda",
                    "dtype": "float16"
                },
                "supported_formats": ["JPEG", "PNG", "WEBP"],
                "api_endpoints": [
                    "/text-to-image",
                    "/image-to-image",
                    "/health",
                    "/info"
                ]
            }
        }


class ErrorResponse(BaseModel):
    """错误响应模型"""
    
    success: bool = Field(False, description="请求是否成功")
    error: Dict[str, Any] = Field(description="错误详情")

    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "error": {
                    "code": "INVALID_PROMPT",
                    "message": "提示词不能为空",
                    "details": {
                        "field": "prompt",
                        "value": "",
                        "constraint": "min_length=1"
                    }
                }
            }
        }