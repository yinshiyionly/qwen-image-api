"""
配置模型单元测试
"""

import pytest
from pydantic import ValidationError
from config.models import (
    ModelConfig, 
    ServerConfig, 
    LogConfig, 
    AppConfig,
    validate_config_dict,
    get_default_config
)


class TestModelConfig:
    """ModelConfig 测试类"""
    
    def test_valid_model_config(self):
        """测试有效的模型配置"""
        config = ModelConfig(
            model_path="/path/to/model",
            device="cuda",
            torch_dtype="float16"
        )
        assert config.model_path == "/path/to/model"
        assert config.device == "cuda"
        assert config.torch_dtype == "float16"
        assert config.max_memory is None
    
    def test_model_config_with_defaults(self):
        """测试使用默认值的模型配置"""
        config = ModelConfig(model_path="/path/to/model")
        assert config.device == "cuda"
        assert config.torch_dtype == "float16"
        assert config.max_memory is None
    
    def test_empty_model_path(self):
        """测试空模型路径"""
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(model_path="")
        assert "模型路径不能为空" in str(exc_info.value)
    
    def test_invalid_device(self):
        """测试无效设备类型"""
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(model_path="/path/to/model", device="invalid")
        assert "设备类型必须是" in str(exc_info.value)
    
    def test_invalid_torch_dtype(self):
        """测试无效 torch 数据类型"""
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(model_path="/path/to/model", torch_dtype="invalid")
        assert "torch_dtype 必须是" in str(exc_info.value)
    
    def test_valid_devices(self):
        """测试所有有效设备类型"""
        for device in ['cuda', 'cpu', 'auto']:
            config = ModelConfig(model_path="/path/to/model", device=device)
            assert config.device == device
    
    def test_valid_torch_dtypes(self):
        """测试所有有效 torch 数据类型"""
        for dtype in ['float16', 'float32', 'bfloat16']:
            config = ModelConfig(model_path="/path/to/model", torch_dtype=dtype)
            assert config.torch_dtype == dtype


class TestServerConfig:
    """ServerConfig 测试类"""
    
    def test_valid_server_config(self):
        """测试有效的服务器配置"""
        config = ServerConfig(
            host="127.0.0.1",
            port=9000,
            max_file_size=5 * 1024 * 1024,
            max_concurrent_requests=8,
            request_timeout=600
        )
        assert config.host == "127.0.0.1"
        assert config.port == 9000
        assert config.max_file_size == 5 * 1024 * 1024
        assert config.max_concurrent_requests == 8
        assert config.request_timeout == 600
    
    def test_server_config_defaults(self):
        """测试服务器配置默认值"""
        config = ServerConfig()
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.max_file_size == 10 * 1024 * 1024
        assert config.max_concurrent_requests == 4
        assert config.request_timeout == 300
    
    def test_invalid_port_range(self):
        """测试无效端口范围"""
        with pytest.raises(ValidationError):
            ServerConfig(port=0)
        
        with pytest.raises(ValidationError):
            ServerConfig(port=65536)
    
    def test_invalid_file_size(self):
        """测试无效文件大小"""
        with pytest.raises(ValidationError):
            ServerConfig(max_file_size=512)  # 小于 1024
    
    def test_invalid_concurrent_requests(self):
        """测试无效并发请求数"""
        with pytest.raises(ValidationError):
            ServerConfig(max_concurrent_requests=0)
        
        with pytest.raises(ValidationError):
            ServerConfig(max_concurrent_requests=101)
    
    def test_invalid_timeout(self):
        """测试无效超时时间"""
        with pytest.raises(ValidationError):
            ServerConfig(request_timeout=5)  # 小于 10
        
        with pytest.raises(ValidationError):
            ServerConfig(request_timeout=3601)  # 大于 3600
    
    def test_empty_host(self):
        """测试空主机地址"""
        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(host="")
        assert "主机地址不能为空" in str(exc_info.value)


class TestLogConfig:
    """LogConfig 测试类"""
    
    def test_valid_log_config(self):
        """测试有效的日志配置"""
        config = LogConfig(
            level="DEBUG",
            format="%(message)s",
            file_path="/var/log/app.log"
        )
        assert config.level == "DEBUG"
        assert config.format == "%(message)s"
        assert config.file_path == "/var/log/app.log"
    
    def test_log_config_defaults(self):
        """测试日志配置默认值"""
        config = LogConfig()
        assert config.level == "INFO"
        assert "%(asctime)s" in config.format
        assert config.file_path is None
    
    def test_invalid_log_level(self):
        """测试无效日志级别"""
        with pytest.raises(ValidationError) as exc_info:
            LogConfig(level="INVALID")
        assert "日志级别必须是" in str(exc_info.value)
    
    def test_log_level_case_insensitive(self):
        """测试日志级别大小写不敏感"""
        config = LogConfig(level="debug")
        assert config.level == "DEBUG"
        
        config = LogConfig(level="Info")
        assert config.level == "INFO"


class TestAppConfig:
    """AppConfig 测试类"""
    
    def test_valid_app_config(self):
        """测试有效的应用配置"""
        config_data = {
            "model": {
                "model_path": "/path/to/model",
                "device": "cuda"
            },
            "server": {
                "port": 9000
            },
            "log": {
                "level": "DEBUG"
            }
        }
        config = AppConfig(**config_data)
        assert config.model.model_path == "/path/to/model"
        assert config.server.port == 9000
        assert config.log.level == "DEBUG"
    
    def test_app_config_with_defaults(self):
        """测试使用默认值的应用配置"""
        config_data = {
            "model": {
                "model_path": "/path/to/model"
            }
        }
        config = AppConfig(**config_data)
        assert config.model.device == "cuda"
        assert config.server.port == 8000
        assert config.log.level == "INFO"
    
    def test_app_config_extra_fields_forbidden(self):
        """测试禁止额外字段"""
        config_data = {
            "model": {
                "model_path": "/path/to/model"
            },
            "extra_field": "not_allowed"
        }
        with pytest.raises(ValidationError):
            AppConfig(**config_data)


class TestConfigValidation:
    """配置验证函数测试类"""
    
    def test_validate_config_dict_success(self):
        """测试配置字典验证成功"""
        config_dict = {
            "model": {
                "model_path": "/path/to/model"
            }
        }
        config = validate_config_dict(config_dict)
        assert isinstance(config, AppConfig)
        assert config.model.model_path == "/path/to/model"
    
    def test_validate_config_dict_failure(self):
        """测试配置字典验证失败"""
        config_dict = {
            "model": {
                "model_path": ""  # 无效的空路径
            }
        }
        with pytest.raises(ValueError) as exc_info:
            validate_config_dict(config_dict)
        assert "配置验证失败" in str(exc_info.value)
    
    def test_get_default_config(self):
        """测试获取默认配置"""
        default_config = get_default_config()
        assert "model" in default_config
        assert "server" in default_config
        assert "log" in default_config
        
        # 验证默认配置可以通过验证
        config = validate_config_dict({
            **default_config,
            "model": {**default_config["model"], "model_path": "/path/to/model"}
        })
        assert isinstance(config, AppConfig)