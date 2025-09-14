"""
配置管理器单元测试
"""

import os
import json
import yaml
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from config.manager import ConfigManager, get_config_manager, init_config, get_current_config
from config.models import AppConfig


class TestConfigManager:
    """ConfigManager 测试类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.manager = ConfigManager()
    
    def test_init_without_config_path(self):
        """测试不指定配置文件路径的初始化"""
        manager = ConfigManager()
        assert manager._config_path is None
        assert manager._config is None
    
    def test_init_with_config_path(self):
        """测试指定配置文件路径的初始化"""
        config_path = "/path/to/config.yaml"
        manager = ConfigManager(config_path)
        assert manager._config_path == config_path
    
    def test_load_config_without_file(self):
        """测试不指定文件时加载默认配置"""
        config = self.manager.load_config()
        assert isinstance(config, AppConfig)
        assert config.server.port == 8000
        assert config.log.level == "INFO"
    
    def test_load_config_file_not_found(self):
        """测试配置文件不存在"""
        with pytest.raises(FileNotFoundError) as exc_info:
            self.manager.load_config("/nonexistent/config.yaml")
        assert "配置文件不存在" in str(exc_info.value)
    
    def test_load_yaml_config_success(self):
        """测试成功加载 YAML 配置文件"""
        config_data = {
            "model": {
                "model_path": "/path/to/model",
                "device": "cpu"
            },
            "server": {
                "port": 9000
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            config = self.manager.load_config(temp_path)
            assert config.model.model_path == "/path/to/model"
            assert config.model.device == "cpu"
            assert config.server.port == 9000
            # 验证默认值仍然存在
            assert config.server.host == "0.0.0.0"
        finally:
            os.unlink(temp_path)
    
    def test_load_json_config_success(self):
        """测试成功加载 JSON 配置文件"""
        config_data = {
            "model": {
                "model_path": "/path/to/model",
                "torch_dtype": "float32"
            },
            "log": {
                "level": "DEBUG"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name
        
        try:
            config = self.manager.load_config(temp_path)
            assert config.model.model_path == "/path/to/model"
            assert config.model.torch_dtype == "float32"
            assert config.log.level == "DEBUG"
        finally:
            os.unlink(temp_path)
    
    def test_load_config_unsupported_format(self):
        """测试不支持的配置文件格式"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("some content")
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError) as exc_info:
                self.manager.load_config(temp_path)
            assert "不支持的配置文件格式" in str(exc_info.value)
        finally:
            os.unlink(temp_path)
    
    def test_load_config_invalid_yaml(self):
        """测试无效的 YAML 格式"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError) as exc_info:
                self.manager.load_config(temp_path)
            assert "加载配置文件失败" in str(exc_info.value)
        finally:
            os.unlink(temp_path)
    
    def test_load_config_invalid_json(self):
        """测试无效的 JSON 格式"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"invalid": json content}')
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError) as exc_info:
                self.manager.load_config(temp_path)
            assert "加载配置文件失败" in str(exc_info.value)
        finally:
            os.unlink(temp_path)
    
    def test_merge_configs(self):
        """测试配置合并逻辑"""
        default_config = {
            "model": {
                "device": "cuda",
                "torch_dtype": "float16"
            },
            "server": {
                "host": "0.0.0.0",
                "port": 8000
            }
        }
        
        file_config = {
            "model": {
                "device": "cpu"  # 覆盖默认值
            },
            "server": {
                "port": 9000  # 覆盖默认值
            },
            "new_section": {  # 新增配置
                "key": "value"
            }
        }
        
        merged = self.manager._merge_configs(default_config, file_config)
        
        assert merged["model"]["device"] == "cpu"  # 被覆盖
        assert merged["model"]["torch_dtype"] == "float16"  # 保留默认值
        assert merged["server"]["host"] == "0.0.0.0"  # 保留默认值
        assert merged["server"]["port"] == 9000  # 被覆盖
        assert merged["new_section"]["key"] == "value"  # 新增
    
    def test_get_config_before_load(self):
        """测试在加载配置前获取配置"""
        with pytest.raises(RuntimeError) as exc_info:
            self.manager.get_config()
        assert "配置未加载" in str(exc_info.value)
    
    def test_get_config_after_load(self):
        """测试加载配置后获取配置"""
        self.manager.load_config()
        config = self.manager.get_config()
        assert isinstance(config, AppConfig)
    
    def test_get_model_config(self):
        """测试获取模型配置"""
        self.manager.load_config()
        model_config = self.manager.get_model_config()
        assert isinstance(model_config, dict)
        assert "device" in model_config
        assert "torch_dtype" in model_config
    
    def test_get_server_config(self):
        """测试获取服务器配置"""
        self.manager.load_config()
        server_config = self.manager.get_server_config()
        assert isinstance(server_config, dict)
        assert "host" in server_config
        assert "port" in server_config
    
    def test_get_log_config(self):
        """测试获取日志配置"""
        self.manager.load_config()
        log_config = self.manager.get_log_config()
        assert isinstance(log_config, dict)
        assert "level" in log_config
        assert "format" in log_config
    
    def test_validate_config_success(self):
        """测试配置验证成功"""
        self.manager.load_config()
        assert self.manager.validate_config() is True
    
    @patch('os.path.exists')
    def test_validate_config_model_path_not_exists(self, mock_exists):
        """测试模型路径不存在时的验证"""
        mock_exists.return_value = False
        
        config_data = {
            "model": {
                "model_path": "/nonexistent/model"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            self.manager.load_config(temp_path)
            assert self.manager.validate_config() is False
        finally:
            os.unlink(temp_path)
    
    def test_reload_config(self):
        """测试重新加载配置"""
        self.manager.load_config()
        original_config = self.manager.get_config()
        
        reloaded_config = self.manager.reload_config()
        assert isinstance(reloaded_config, AppConfig)
        # 由于没有改变配置文件，配置应该相同
        assert reloaded_config.dict() == original_config.dict()
    
    def test_save_config_yaml(self):
        """测试保存配置为 YAML 格式"""
        self.manager.load_config()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = f.name
        
        try:
            self.manager.save_config(temp_path, 'yaml')
            assert os.path.exists(temp_path)
            
            # 验证保存的文件可以重新加载
            new_manager = ConfigManager()
            config = new_manager.load_config(temp_path)
            assert isinstance(config, AppConfig)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_save_config_json(self):
        """测试保存配置为 JSON 格式"""
        self.manager.load_config()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            self.manager.save_config(temp_path, 'json')
            assert os.path.exists(temp_path)
            
            # 验证保存的文件可以重新加载
            new_manager = ConfigManager()
            config = new_manager.load_config(temp_path)
            assert isinstance(config, AppConfig)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_save_config_unsupported_format(self):
        """测试保存配置为不支持的格式"""
        self.manager.load_config()
        
        with pytest.raises(ValueError) as exc_info:
            self.manager.save_config("/tmp/config.txt", "txt")
        assert "不支持的格式" in str(exc_info.value)


class TestGlobalConfigManager:
    """全局配置管理器测试类"""
    
    def test_get_config_manager_singleton(self):
        """测试全局配置管理器单例模式"""
        manager1 = get_config_manager()
        manager2 = get_config_manager()
        assert manager1 is manager2
    
    def test_init_config(self):
        """测试初始化全局配置"""
        config = init_config()
        assert isinstance(config, AppConfig)
    
    def test_get_current_config(self):
        """测试获取当前全局配置"""
        init_config()
        config = get_current_config()
        assert isinstance(config, AppConfig)