"""
模型管理器错误处理和资源管理测试
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from PIL import Image

from services.model_manager import ModelManager
from services.exceptions import (
    ModelLoadError, ModelNotLoadedError, InferenceError,
    ValidationError, MemoryError
)


class TestModelManagerErrorHandling:
    """ModelManager 错误处理测试"""
    
    @pytest.fixture
    def model_config(self):
        """测试配置"""
        return {
            "device": "cpu",
            "torch_dtype": "float32",
            "max_memory": None
        }
    
    @pytest.fixture
    def temp_model_path(self):
        """临时模型路径"""
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = os.path.join(temp_dir, "test_model")
            os.makedirs(model_path, exist_ok=True)
            yield model_path
    
    @pytest.fixture
    def model_manager(self, temp_model_path, model_config):
        """ModelManager 实例"""
        return ModelManager(temp_model_path, model_config)
    
    def test_model_load_error_nonexistent_path(self, model_config):
        """测试不存在路径的模型加载错误"""
        manager = ModelManager("/nonexistent/path", model_config)
        
        with pytest.raises(ModelLoadError) as exc_info:
            manager.load_model()
        
        assert "Model path does not exist" in str(exc_info.value)
        assert exc_info.value.model_path == "/nonexistent/path"
        assert manager._error_count == 1
    
    def test_text_to_image_model_not_loaded_error(self, model_manager):
        """测试模型未加载错误"""
        with pytest.raises(ModelNotLoadedError):
            model_manager.text_to_image("test prompt")
        
        assert model_manager._error_count == 1
    
    def test_image_to_image_model_not_loaded_error(self, model_manager):
        """测试图生图模型未加载错误"""
        test_image = Image.new('RGB', (512, 512), color='red')
        
        with pytest.raises(ModelNotLoadedError):
            model_manager.image_to_image(test_image, "test prompt")
        
        assert model_manager._error_count == 1
    
    def test_text_to_image_validation_errors(self, model_manager):
        """测试文生图参数验证错误"""
        model_manager.load_model()
        
        # 空提示词
        with pytest.raises(ValidationError) as exc_info:
            model_manager.text_to_image("")
        assert exc_info.value.parameter == "prompt"
        
        # 无效宽度
        with pytest.raises(ValidationError) as exc_info:
            model_manager.text_to_image("test", width=100)
        assert exc_info.value.parameter == "width"
        
        # 无效高度
        with pytest.raises(ValidationError) as exc_info:
            model_manager.text_to_image("test", height=3000)
        assert exc_info.value.parameter == "height"
        
        # 无效推理步数
        with pytest.raises(ValidationError) as exc_info:
            model_manager.text_to_image("test", num_inference_steps=0)
        assert exc_info.value.parameter == "num_inference_steps"
        
        # 无效引导比例
        with pytest.raises(ValidationError) as exc_info:
            model_manager.text_to_image("test", guidance_scale=0.5)
        assert exc_info.value.parameter == "guidance_scale"
        
        assert model_manager._error_count == 5
    
    def test_image_to_image_validation_errors(self, model_manager):
        """测试图生图参数验证错误"""
        model_manager.load_model()
        
        # 无效图像类型
        with pytest.raises(ValidationError) as exc_info:
            model_manager.image_to_image("not_an_image", "test")
        assert exc_info.value.parameter == "image"
        
        # 空提示词
        test_image = Image.new('RGB', (512, 512), color='red')
        with pytest.raises(ValidationError) as exc_info:
            model_manager.image_to_image(test_image, "")
        assert exc_info.value.parameter == "prompt"
        
        # 无效强度
        with pytest.raises(ValidationError) as exc_info:
            model_manager.image_to_image(test_image, "test", strength=0.05)
        assert exc_info.value.parameter == "strength"
        
        assert model_manager._error_count == 3
    
    @patch('services.model_manager.psutil')
    def test_memory_check_insufficient_memory(self, mock_psutil, model_manager):
        """测试内存不足检查"""
        # 模拟内存不足
        mock_memory = Mock()
        mock_memory.available = 1024**3  # 1GB
        mock_psutil.virtual_memory.return_value = mock_memory
        
        with pytest.raises(MemoryError) as exc_info:
            model_manager._check_memory_availability()
        
        assert "Insufficient memory for model loading" in str(exc_info.value)
    
    @patch('services.model_manager.psutil')
    def test_memory_check_sufficient_memory(self, mock_psutil, model_manager):
        """测试内存充足检查"""
        # 模拟内存充足
        mock_memory = Mock()
        mock_memory.available = 4 * 1024**3  # 4GB
        mock_psutil.virtual_memory.return_value = mock_memory
        
        # 应该不抛出异常
        model_manager._check_memory_availability()
    
    @patch('torch.cuda.is_available')
    @patch('torch.cuda.get_device_properties')
    @patch('torch.cuda.memory_allocated')
    def test_gpu_memory_check(self, mock_memory_allocated, mock_device_props, 
                             mock_cuda_available, model_manager):
        """测试 GPU 内存检查"""
        mock_cuda_available.return_value = True
        model_manager.config.device = "cuda"
        
        # 模拟 GPU 内存不足
        mock_props = Mock()
        mock_props.total_memory = 2 * 1024**3  # 2GB
        mock_device_props.return_value = mock_props
        mock_memory_allocated.return_value = 1.8 * 1024**3  # 1.8GB 已使用
        
        with pytest.raises(MemoryError):
            model_manager._check_inference_memory(2048, 2048)  # 大图像
    
    @patch('services.model_manager.ModelManager._execute_text_to_image')
    def test_inference_error_handling(self, mock_execute, model_manager):
        """测试推理错误处理"""
        model_manager.load_model()
        
        # 模拟推理失败
        mock_execute.side_effect = RuntimeError("Inference failed")
        
        with pytest.raises(InferenceError) as exc_info:
            model_manager.text_to_image("test prompt")
        
        assert exc_info.value.inference_type == "text_to_image"
        assert "Text-to-image generation failed" in str(exc_info.value)
        assert model_manager._error_count == 1


class TestModelManagerResourceManagement:
    """ModelManager 资源管理测试"""
    
    @pytest.fixture
    def model_manager(self):
        """测试用 ModelManager"""
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = os.path.join(temp_dir, "test_model")
            os.makedirs(model_path, exist_ok=True)
            
            config = {
                "device": "cpu",
                "torch_dtype": "float32",
                "max_memory": None
            }
            
            manager = ModelManager(model_path, config)
            yield manager
            manager.cleanup()
    
    def test_resource_stats_initial(self, model_manager):
        """测试初始资源统计"""
        stats = model_manager.get_resource_stats()
        
        assert stats['inference_count'] == 0
        assert stats['error_count'] == 0
        assert stats['memory_usage_mb']['peak'] == 0
        assert stats['memory_usage_mb']['current'] == 0
        assert stats['model_loaded'] == False
    
    def test_resource_stats_after_inference(self, model_manager):
        """测试推理后的资源统计"""
        model_manager.load_model()
        
        # 执行推理
        model_manager.text_to_image("test prompt")
        model_manager.text_to_image("another test")
        
        stats = model_manager.get_resource_stats()
        
        assert stats['inference_count'] == 2
        assert stats['error_count'] == 0
        assert stats['model_loaded'] == True
    
    def test_resource_stats_with_errors(self, model_manager):
        """测试包含错误的资源统计"""
        # 不加载模型，直接推理会产生错误
        try:
            model_manager.text_to_image("test")
        except ModelNotLoadedError:
            pass
        
        try:
            model_manager.text_to_image("test2")
        except ModelNotLoadedError:
            pass
        
        stats = model_manager.get_resource_stats()
        
        assert stats['inference_count'] == 0
        assert stats['error_count'] == 2
    
    def test_reset_stats(self, model_manager):
        """测试重置统计信息"""
        model_manager.load_model()
        model_manager.text_to_image("test")
        
        # 重置前检查
        stats = model_manager.get_resource_stats()
        assert stats['inference_count'] == 1
        
        # 重置
        model_manager.reset_stats()
        
        # 重置后检查
        stats = model_manager.get_resource_stats()
        assert stats['inference_count'] == 0
        assert stats['error_count'] == 0
        assert stats['memory_usage_mb']['peak'] == 0
    
    def test_health_check_healthy(self, model_manager):
        """测试健康检查 - 健康状态"""
        model_manager.load_model()
        
        health = model_manager.health_check()
        
        assert health['status'] == 'healthy'
        assert health['model_loaded'] == True
        assert len(health['issues']) == 0
    
    def test_health_check_model_not_loaded(self, model_manager):
        """测试健康检查 - 模型未加载"""
        health = model_manager.health_check()
        
        assert health['status'] == 'unhealthy'
        assert health['model_loaded'] == False
        assert 'Model not loaded' in health['issues']
    
    def test_health_check_high_error_rate(self, model_manager):
        """测试健康检查 - 高错误率"""
        model_manager.load_model()
        
        # 执行一些成功的推理
        model_manager.text_to_image("test1")
        model_manager.text_to_image("test2")
        
        # 模拟一些错误
        for _ in range(5):
            model_manager._error_count += 1
        
        health = model_manager.health_check()
        
        assert health['status'] == 'warning'
        assert any('High error rate' in issue for issue in health['issues'])
    
    @patch('torch.cuda.is_available')
    @patch('torch.cuda.memory_allocated')
    @patch('torch.cuda.get_device_properties')
    def test_health_check_high_gpu_memory(self, mock_device_props, mock_memory_allocated, 
                                         mock_cuda_available, model_manager):
        """测试健康检查 - 高 GPU 内存使用"""
        mock_cuda_available.return_value = True
        model_manager.config.device = "cuda"
        model_manager.load_model()
        
        # 模拟高内存使用
        mock_props = Mock()
        mock_props.total_memory = 1024**3  # 1GB
        mock_device_props.return_value = mock_props
        mock_memory_allocated.return_value = 0.95 * 1024**3  # 95% 使用
        
        health = model_manager.health_check()
        
        assert health['status'] == 'warning'
        assert any('High GPU memory usage' in issue for issue in health['issues'])
    
    @patch('torch.cuda.is_available')
    def test_gpu_info_in_stats(self, mock_cuda_available, model_manager):
        """测试统计信息中的 GPU 信息"""
        mock_cuda_available.return_value = True
        
        with patch('torch.cuda.get_device_name') as mock_device_name, \
             patch('torch.cuda.get_device_properties') as mock_device_props, \
             patch('torch.cuda.memory_allocated') as mock_memory_allocated, \
             patch('torch.cuda.memory_reserved') as mock_memory_reserved:
            
            mock_device_name.return_value = "Test GPU"
            mock_props = Mock()
            mock_props.total_memory = 8 * 1024**3  # 8GB
            mock_device_props.return_value = mock_props
            mock_memory_allocated.return_value = 2 * 1024**3  # 2GB
            mock_memory_reserved.return_value = 3 * 1024**3  # 3GB
            
            stats = model_manager.get_resource_stats()
            
            assert 'gpu_info' in stats
            assert stats['gpu_info']['device_name'] == "Test GPU"
            assert stats['gpu_info']['total_memory_mb'] == 8 * 1024
            assert stats['gpu_info']['allocated_memory_mb'] == 2 * 1024
            assert stats['gpu_info']['cached_memory_mb'] == 3 * 1024


class TestModelManagerIntegrationWithErrors:
    """ModelManager 错误处理集成测试"""
    
    @pytest.fixture
    def model_manager(self):
        """集成测试用的 ModelManager"""
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = os.path.join(temp_dir, "test_model")
            os.makedirs(model_path, exist_ok=True)
            
            config = {
                "device": "cpu",
                "torch_dtype": "float32",
                "max_memory": None
            }
            
            manager = ModelManager(model_path, config)
            yield manager
            manager.cleanup()
    
    def test_full_error_recovery_workflow(self, model_manager):
        """测试完整的错误恢复工作流"""
        # 1. 尝试在模型未加载时推理（应该失败）
        with pytest.raises(ModelNotLoadedError):
            model_manager.text_to_image("test")
        
        # 2. 加载模型
        model_manager.load_model()
        assert model_manager.is_model_loaded()
        
        # 3. 成功推理
        image = model_manager.text_to_image("test prompt")
        assert isinstance(image, Image.Image)
        
        # 4. 检查统计信息
        stats = model_manager.get_resource_stats()
        assert stats['inference_count'] == 1
        assert stats['error_count'] == 1  # 第一次失败的推理
        
        # 5. 健康检查
        health = model_manager.health_check()
        assert health['status'] in ['healthy', 'warning']  # 可能因为错误率而警告
        
        # 6. 重置统计并再次检查
        model_manager.reset_stats()
        health = model_manager.health_check()
        assert health['status'] == 'healthy'