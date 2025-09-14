"""
配置管理器

负责从文件加载配置、处理默认值和配置合并逻辑。
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional, Union
import logging

from .models import AppConfig, validate_config_dict, get_default_config

logger = logging.getLogger(__name__)


class ConfigManager:
    """配置管理器类"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，如果为 None 则使用默认配置
        """
        self._config: Optional[AppConfig] = None
        self._config_path = config_path
        self._default_config = get_default_config()
    
    def load_config(self, config_path: Optional[str] = None) -> AppConfig:
        """
        从文件加载配置
        
        Args:
            config_path: 配置文件路径，如果为 None 则使用初始化时的路径
            
        Returns:
            AppConfig: 加载并验证后的配置对象
            
        Raises:
            FileNotFoundError: 配置文件不存在
            ValueError: 配置文件格式错误或验证失败
        """
        if config_path:
            self._config_path = config_path
        
        if not self._config_path:
            logger.info("未指定配置文件，使用默认配置")
            self._config = validate_config_dict(self._default_config)
            return self._config
        
        config_file = Path(self._config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {self._config_path}")
        
        try:
            # 根据文件扩展名选择解析方法
            if config_file.suffix.lower() in ['.yaml', '.yml']:
                file_config = self._load_yaml_config(config_file)
            elif config_file.suffix.lower() == '.json':
                file_config = self._load_json_config(config_file)
            else:
                raise ValueError(f"不支持的配置文件格式: {config_file.suffix}")
            
            # 合并默认配置和文件配置
            merged_config = self._merge_configs(self._default_config, file_config)
            
            # 验证配置
            self._config = validate_config_dict(merged_config)
            
            logger.info(f"成功加载配置文件: {self._config_path}")
            return self._config
            
        except Exception as e:
            raise ValueError(f"加载配置文件失败 {self._config_path}: {str(e)}")
    
    def _load_yaml_config(self, config_file: Path) -> Dict[str, Any]:
        """
        加载 YAML 配置文件
        
        Args:
            config_file: 配置文件路径
            
        Returns:
            Dict[str, Any]: 配置字典
        """
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"YAML 格式错误: {str(e)}")
    
    def _load_json_config(self, config_file: Path) -> Dict[str, Any]:
        """
        加载 JSON 配置文件
        
        Args:
            config_file: 配置文件路径
            
        Returns:
            Dict[str, Any]: 配置字典
        """
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 格式错误: {str(e)}")
    
    def _merge_configs(self, default: Dict[str, Any], file_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        合并默认配置和文件配置
        
        Args:
            default: 默认配置字典
            file_config: 文件配置字典
            
        Returns:
            Dict[str, Any]: 合并后的配置字典
        """
        merged = default.copy()
        
        for key, value in file_config.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                # 递归合并嵌套字典
                merged[key] = self._merge_configs(merged[key], value)
            else:
                # 直接覆盖或添加新键
                merged[key] = value
        
        return merged
    
    def get_config(self) -> AppConfig:
        """
        获取当前配置
        
        Returns:
            AppConfig: 当前配置对象
            
        Raises:
            RuntimeError: 配置未加载
        """
        if self._config is None:
            raise RuntimeError("配置未加载，请先调用 load_config()")
        return self._config
    
    def get_model_config(self) -> Dict[str, Any]:
        """
        获取模型配置
        
        Returns:
            Dict[str, Any]: 模型配置字典
        """
        config = self.get_config()
        return config.model.dict()
    
    def get_server_config(self) -> Dict[str, Any]:
        """
        获取服务器配置
        
        Returns:
            Dict[str, Any]: 服务器配置字典
        """
        config = self.get_config()
        return config.server.dict()
    
    def get_log_config(self) -> Dict[str, Any]:
        """
        获取日志配置
        
        Returns:
            Dict[str, Any]: 日志配置字典
        """
        config = self.get_config()
        return config.log.dict()
    
    def validate_config(self) -> bool:
        """
        验证当前配置是否有效
        
        Returns:
            bool: 配置是否有效
        """
        try:
            config = self.get_config()
            # 执行额外的业务逻辑验证
            return self._validate_business_rules(config)
        except Exception as e:
            logger.error(f"配置验证失败: {str(e)}")
            return False
    
    def _validate_business_rules(self, config: AppConfig) -> bool:
        """
        验证业务规则
        
        Args:
            config: 配置对象
            
        Returns:
            bool: 验证是否通过
        """
        # 验证模型路径是否存在（如果不为空）
        if config.model.model_path and not os.path.exists(config.model.model_path):
            logger.warning(f"模型路径不存在: {config.model.model_path}")
            return False
        
        # 验证日志文件路径的父目录是否存在（如果指定了日志文件）
        if config.log.file_path:
            log_dir = os.path.dirname(config.log.file_path)
            if log_dir and not os.path.exists(log_dir):
                logger.warning(f"日志目录不存在: {log_dir}")
                return False
        
        return True
    
    def reload_config(self) -> AppConfig:
        """
        重新加载配置文件
        
        Returns:
            AppConfig: 重新加载的配置对象
        """
        logger.info("重新加载配置文件")
        return self.load_config()
    
    def save_config(self, output_path: str, format: str = 'yaml') -> None:
        """
        保存当前配置到文件
        
        Args:
            output_path: 输出文件路径
            format: 输出格式 ('yaml' 或 'json')
            
        Raises:
            RuntimeError: 配置未加载
            ValueError: 不支持的格式
        """
        config = self.get_config()
        config_dict = config.dict()
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        if format.lower() == 'yaml':
            with open(output_file, 'w', encoding='utf-8') as f:
                yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
        elif format.lower() == 'json':
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
        else:
            raise ValueError(f"不支持的格式: {format}")
        
        logger.info(f"配置已保存到: {output_path}")


# 全局配置管理器实例
_global_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """
    获取全局配置管理器实例
    
    Returns:
        ConfigManager: 配置管理器实例
    """
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = ConfigManager()
    return _global_config_manager


def init_config(config_path: Optional[str] = None) -> AppConfig:
    """
    初始化全局配置
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        AppConfig: 加载的配置对象
    """
    manager = get_config_manager()
    return manager.load_config(config_path)


def get_current_config() -> AppConfig:
    """
    获取当前全局配置
    
    Returns:
        AppConfig: 当前配置对象
    """
    manager = get_config_manager()
    return manager.get_config()