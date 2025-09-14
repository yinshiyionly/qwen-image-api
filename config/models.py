"""
配置数据模型和验证

基于 Pydantic 的配置模型，提供数据验证和类型检查功能。
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
import os


class ModelConfig(BaseModel):
    """模型配置"""
    model_path: str = Field(..., description="模型文件路径")
    device: str = Field("cuda", description="推理设备 (cuda/cpu)")
    torch_dtype: str = Field("float16", description="PyTorch 数据类型")
    max_memory: Optional[str] = Field(None, description="最大内存限制")
    
    @validator('model_path')
    def validate_model_path(cls, v):
        if not v:
            raise ValueError("模型路径不能为空")
        return v
    
    @validator('device')
    def validate_device(cls, v):
        if v not in ['cuda', 'cpu', 'auto']:
            raise ValueError("设备类型必须是 'cuda', 'cpu' 或 'auto'")
        return v
    
    @validator('torch_dtype')
    def validate_torch_dtype(cls, v):
        valid_types = ['float16', 'float32', 'bfloat16']
        if v not in valid_types:
            raise ValueError(f"torch_dtype 必须是 {valid_types} 中的一个")
        return v


class SecurityConfig(BaseModel):
    """安全配置"""
    enable_rate_limiting: bool = Field(True, description="启用速率限制")
    requests_per_minute: int = Field(60, ge=1, le=1000, description="每分钟请求限制")
    requests_per_hour: int = Field(1000, ge=1, le=10000, description="每小时请求限制")
    burst_size: int = Field(10, ge=1, le=100, description="突发请求限制")
    enable_file_validation: bool = Field(True, description="启用文件验证")
    allowed_file_types: list = Field(
        default=["image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff"],
        description="允许的文件类型"
    )


class ServerConfig(BaseModel):
    """服务器配置"""
    host: str = Field("0.0.0.0", description="服务器主机地址")
    port: int = Field(8000, ge=1, le=65535, description="服务器端口")
    max_file_size: int = Field(10 * 1024 * 1024, ge=1024, description="最大文件大小 (字节)")
    max_concurrent_requests: int = Field(4, ge=1, le=100, description="最大并发请求数")
    request_timeout: int = Field(300, ge=10, le=3600, description="请求超时时间 (秒)")
    queue_timeout: int = Field(30, ge=5, le=300, description="队列等待超时时间 (秒)")
    
    @validator('host')
    def validate_host(cls, v):
        if not v:
            raise ValueError("主机地址不能为空")
        return v


class LogConfig(BaseModel):
    """日志配置"""
    level: str = Field("INFO", description="日志级别")
    format: str = Field(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="日志格式"
    )
    file_path: Optional[str] = Field(None, description="日志文件路径")
    
    @validator('level')
    def validate_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"日志级别必须是 {valid_levels} 中的一个")
        return v.upper()


class AppConfig(BaseModel):
    """应用程序完整配置"""
    model: ModelConfig
    server: ServerConfig = ServerConfig()
    security: SecurityConfig = SecurityConfig()
    log: LogConfig = LogConfig()
    
    class Config:
        extra = "forbid"  # 禁止额外字段


def validate_config_dict(config_dict: Dict[str, Any]) -> AppConfig:
    """
    验证配置字典并返回 AppConfig 实例
    
    Args:
        config_dict: 配置字典
        
    Returns:
        AppConfig: 验证后的配置对象
        
    Raises:
        ValueError: 配置验证失败
    """
    try:
        return AppConfig(**config_dict)
    except Exception as e:
        raise ValueError(f"配置验证失败: {str(e)}")


def get_default_config() -> Dict[str, Any]:
    """
    获取默认配置
    
    Returns:
        Dict[str, Any]: 默认配置字典
    """
    return {
        "model": {
            "model_path": "",
            "device": "cuda",
            "torch_dtype": "float16",
            "max_memory": None
        },
        "server": {
            "host": "0.0.0.0",
            "port": 8000,
            "max_file_size": 10 * 1024 * 1024,
            "max_concurrent_requests": 4,
            "request_timeout": 300,
            "queue_timeout": 30
        },
        "security": {
            "enable_rate_limiting": True,
            "requests_per_minute": 60,
            "requests_per_hour": 1000,
            "burst_size": 10,
            "enable_file_validation": True,
            "allowed_file_types": ["image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff"]
        },
        "log": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file_path": None
        }
    }