"""
模型管理器单元测试
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from PIL import Image

from services.model_manager import ModelManager


class TestModelManager:
    """ModelManager 测试类"""
    
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
    
    def test_init(self, temp_model_path, model_config):
        """测试初始化"""
        manager = ModelManager(temp_model_path, model_config)
        
        assert manager.model_path == temp_model_path
        assert manager.config.device == "cpu"
        assert manager.config.torch_dtype == "float32"
        assert manager.model is None
        assert not manager.is_model_loaded()
    
    def test_init_with_invalid_config(self, temp_model_path):
        """测试无效配置初始化"""
        invalid_config = {
            "device": "invalid_device",
            "torch_dtype": "float32"
        }
        
        with pytest.raises(ValueError):
            ModelManager(temp_model_path, invalid_config)
    
    @patch('torch.cuda.is_available')
    def test_get_device_auto_cuda_available(self, mock_cuda_available, model_manager):
        """测试自动设备选择 - CUDA 可用"""
        mock_cuda_available.return_value = True
        model_manager.config.device = "auto"
        
        device = model_manager._get_device()
        assert device == "cuda"
    
    @patch('torch.cuda.is_available')
    def test_get_device_auto_cuda_unavailable(self, mock_cuda_available, model_manager):
        """测试自动设备选择 - CUDA 不可用"""
        mock_cuda_available.return_value = False
        model_manager.config.device = "auto"
        
        device = model_manager._get_device()
        assert device == "cpu"
    
    @patch('torch.cuda.is_available')
    def test_get_device_cuda_fallback(self, mock_cuda_available, model_manager):
        """测试 CUDA 回退到 CPU"""
        mock_cuda_available.return_value = False
        model_manager.config.device = "cuda"
        
        device = model_manager._get_device()
        assert device == "cpu"
    
    def test_load_model_success(self, model_manager):
        """测试模型加载成功"""
        model_manager.load_model()
        
        assert model_manager.is_model_loaded()
        assert model_manager.model is not None
    
    def test_load_model_nonexistent_path(self, model_config):
        """测试加载不存在的模型路径"""
        manager = ModelManager("/nonexistent/path", model_config)
        
        with pytest.raises(RuntimeError, match="Model loading failed"):
            manager.load_model()
    
    def test_load_model_already_loaded(self, model_manager):
        """测试重复加载模型"""
        model_manager.load_model()
        assert model_manager.is_model_loaded()
        
        # 再次加载应该不会出错
        model_manager.load_model()
        assert model_manager.is_model_loaded()
    
    def test_text_to_image_success(self, model_manager):
        """测试文生图成功"""
        model_manager.load_model()
        
        image = model_manager.text_to_image("test prompt")
        
        assert isinstance(image, Image.Image)
        assert image.size == (512, 512)  # 默认尺寸
    
    def test_text_to_image_with_params(self, model_manager):
        """测试带参数的文生图"""
        model_manager.load_model()
        
        image = model_manager.text_to_image(
            "test prompt",
            width=256,
            height=256,
            num_inference_steps=10,
            guidance_scale=5.0
        )
        
        assert isinstance(image, Image.Image)
        assert image.size == (256, 256)
    
    def test_text_to_image_model_not_loaded(self, model_manager):
        """测试模型未加载时的文生图"""
        with pytest.raises(RuntimeError, match="Model not loaded"):
            model_manager.text_to_image("test prompt")
    
    def test_text_to_image_empty_prompt(self, model_manager):
        """测试空提示词"""
        model_manager.load_model()
        
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            model_manager.text_to_image("")
        
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            model_manager.text_to_image("   ")
    
    def test_text_to_image_invalid_params(self, model_manager):
        """测试无效参数"""
        model_manager.load_model()
        
        # 无效宽度
        with pytest.raises(ValueError, match="Width must be between"):
            model_manager.text_to_image("test", width=100)
        
        # 无效高度
        with pytest.raises(ValueError, match="Height must be between"):
            model_manager.text_to_image("test", height=3000)
        
        # 无效推理步数
        with pytest.raises(ValueError, match="num_inference_steps must be between"):
            model_manager.text_to_image("test", num_inference_steps=0)
        
        # 无效引导比例
        with pytest.raises(ValueError, match="guidance_scale must be between"):
            model_manager.text_to_image("test", guidance_scale=0.5)
    
    def test_image_to_image_success(self, model_manager):
        """测试图生图成功"""
        model_manager.load_model()
        
        input_image = Image.new('RGB', (512, 512), color='red')
        result_image = model_manager.image_to_image(input_image, "test prompt")
        
        assert isinstance(result_image, Image.Image)
        assert result_image.size == (512, 512)
    
    def test_image_to_image_with_params(self, model_manager):
        """测试带参数的图生图"""
        model_manager.load_model()
        
        input_image = Image.new('RGB', (256, 256), color='red')
        result_image = model_manager.image_to_image(
            input_image,
            "test prompt",
            strength=0.5,
            width=512,
            height=512,
            num_inference_steps=15
        )
        
        assert isinstance(result_image, Image.Image)
        assert result_image.size == (512, 512)
    
    def test_image_to_image_model_not_loaded(self, model_manager):
        """测试模型未加载时的图生图"""
        input_image = Image.new('RGB', (512, 512), color='red')
        
        with pytest.raises(RuntimeError, match="Model not loaded"):
            model_manager.image_to_image(input_image, "test prompt")
    
    def test_image_to_image_invalid_input(self, model_manager):
        """测试无效输入"""
        model_manager.load_model()
        
        # 无效图像类型
        with pytest.raises(ValueError, match="Input must be a PIL Image"):
            model_manager.image_to_image("not_an_image", "test prompt")
        
        # 空提示词
        input_image = Image.new('RGB', (512, 512), color='red')
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            model_manager.image_to_image(input_image, "")
    
    def test_image_to_image_invalid_strength(self, model_manager):
        """测试无效强度参数"""
        model_manager.load_model()
        input_image = Image.new('RGB', (512, 512), color='red')
        
        with pytest.raises(ValueError, match="Strength must be between"):
            model_manager.image_to_image(input_image, "test", strength=0.05)
        
        with pytest.raises(ValueError, match="Strength must be between"):
            model_manager.image_to_image(input_image, "test", strength=1.5)
    
    def test_preprocess_image_rgb_conversion(self, model_manager):
        """测试图像 RGB 转换"""
        # 创建 RGBA 图像
        rgba_image = Image.new('RGBA', (100, 100), color=(255, 0, 0, 128))
        
        processed = model_manager._preprocess_image(rgba_image, 200, 200)
        
        assert processed.mode == 'RGB'
        assert processed.size == (200, 200)
    
    def test_preprocess_image_resize(self, model_manager):
        """测试图像尺寸调整"""
        original_image = Image.new('RGB', (100, 100), color='blue')
        
        processed = model_manager._preprocess_image(original_image, 256, 256)
        
        assert processed.size == (256, 256)
        assert processed.mode == 'RGB'
    
    def test_get_model_info(self, model_manager):
        """测试获取模型信息"""
        info = model_manager.get_model_info()
        
        assert 'loaded' in info
        assert 'model_path' in info
        assert 'device' in info
        assert 'torch_dtype' in info
        assert 'max_memory' in info
        
        assert info['loaded'] == False  # 模型未加载
        assert info['device'] == 'cpu'
        assert info['torch_dtype'] == 'float32'
    
    def test_get_model_info_loaded(self, model_manager):
        """测试加载后的模型信息"""
        model_manager.load_model()
        info = model_manager.get_model_info()
        
        assert info['loaded'] == True
    
    @patch('torch.cuda.is_available')
    @patch('torch.cuda.empty_cache')
    def test_cleanup(self, mock_empty_cache, mock_cuda_available, model_manager):
        """测试资源清理"""
        mock_cuda_available.return_value = True
        
        # 加载模型
        model_manager.load_model()
        assert model_manager.is_model_loaded()
        
        # 清理资源
        model_manager.cleanup()
        
        assert not model_manager.is_model_loaded()
        assert model_manager.model is None
        mock_empty_cache.assert_called_once()
    
    def test_validate_generation_params_valid(self, model_manager):
        """测试有效的生成参数验证"""
        # 应该不抛出异常
        model_manager._validate_generation_params(512, 512, 20, 7.5)
        model_manager._validate_generation_params(256, 1024, 50)  # 不带 guidance_scale
    
    def test_validate_generation_params_invalid(self, model_manager):
        """测试无效的生成参数验证"""
        # 无效宽度
        with pytest.raises(ValueError, match="Width must be between"):
            model_manager._validate_generation_params(100, 512, 20)
        
        # 无效高度
        with pytest.raises(ValueError, match="Height must be between"):
            model_manager._validate_generation_params(512, 3000, 20)
        
        # 无效推理步数
        with pytest.raises(ValueError, match="num_inference_steps must be between"):
            model_manager._validate_generation_params(512, 512, 0)
        
        # 无效引导比例
        with pytest.raises(ValueError, match="guidance_scale must be between"):
            model_manager._validate_generation_params(512, 512, 20, 0.5)


class TestModelManagerIntegration:
    """ModelManager 集成测试"""
    
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
            
            # 清理
            manager.cleanup()
    
    def test_full_text_to_image_workflow(self, model_manager):
        """测试完整的文生图工作流"""
        # 加载模型
        model_manager.load_model()
        assert model_manager.is_model_loaded()
        
        # 生成图像
        image = model_manager.text_to_image(
            "A beautiful landscape",
            width=256,
            height=256,
            num_inference_steps=10
        )
        
        assert isinstance(image, Image.Image)
        assert image.size == (256, 256)
        
        # 获取模型信息
        info = model_manager.get_model_info()
        assert info['loaded'] == True
        
        # 清理资源
        model_manager.cleanup()
        assert not model_manager.is_model_loaded()
    
    def test_full_image_to_image_workflow(self, model_manager):
        """测试完整的图生图工作流"""
        # 加载模型
        model_manager.load_model()
        
        # 创建输入图像
        input_image = Image.new('RGB', (300, 300), color='green')
        
        # 生成图像
        result_image = model_manager.image_to_image(
            input_image,
            "Transform this image",
            strength=0.7,
            width=512,
            height=512
        )
        
        assert isinstance(result_image, Image.Image)
        assert result_image.size == (512, 512)
        
        # 清理资源
        model_manager.cleanup()
    
    def test_get_supported_formats(self, model_manager):
        """测试获取支持的格式"""
        formats = model_manager.get_supported_formats()
        
        assert 'image_formats' in formats
        assert 'max_resolution' in formats
        assert 'min_resolution' in formats
        assert 'inference_steps_range' in formats
        assert 'guidance_scale_range' in formats
        assert 'strength_range' in formats
        
        assert 'JPEG' in formats['image_formats']
        assert 'PNG' in formats['image_formats']
        assert formats['max_resolution']['width'] == 2048
        assert formats['min_resolution']['width'] == 256
    
    def test_format_inference_result(self, model_manager):
        """测试推理结果格式化"""
        test_image = Image.new('RGB', (512, 512), color='red')
        metadata = {'prompt': 'test', 'steps': 20}
        
        result = model_manager.format_inference_result(test_image, metadata)
        
        assert result['image'] == test_image
        assert result['width'] == 512
        assert result['height'] == 512
        assert result['mode'] == 'RGB'
        assert result['metadata'] == metadata
    
    def test_format_inference_result_no_metadata(self, model_manager):
        """测试无元数据的结果格式化"""
        test_image = Image.new('RGB', (256, 256), color='blue')
        
        result = model_manager.format_inference_result(test_image)
        
        assert result['image'] == test_image
        assert result['width'] == 256
        assert result['height'] == 256
        assert 'metadata' not in result
    
    def test_validate_inference_request_text_to_image(self, model_manager):
        """测试文生图请求验证"""
        params = model_manager.validate_inference_request(
            'text_to_image',
            prompt='test prompt',
            width=512,
            height=512,
            num_inference_steps=20,
            guidance_scale=7.5
        )
        
        assert params['prompt'] == 'test prompt'
        assert params['width'] == 512
        assert params['height'] == 512
        assert params['num_inference_steps'] == 20
        assert params['guidance_scale'] == 7.5
    
    def test_validate_inference_request_image_to_image(self, model_manager):
        """测试图生图请求验证"""
        test_image = Image.new('RGB', (512, 512), color='green')
        
        params = model_manager.validate_inference_request(
            'image_to_image',
            prompt='test prompt',
            image=test_image,
            width=512,
            height=512,
            num_inference_steps=15,
            strength=0.7
        )
        
        assert params['prompt'] == 'test prompt'
        assert params['image'] == test_image
        assert params['width'] == 512
        assert params['height'] == 512
        assert params['num_inference_steps'] == 15
        assert params['strength'] == 0.7
    
    def test_validate_inference_request_invalid_type(self, model_manager):
        """测试无效请求类型验证"""
        with pytest.raises(ValueError, match="Unsupported request type"):
            model_manager.validate_inference_request('invalid_type', prompt='test')
    
    def test_validate_inference_request_empty_prompt(self, model_manager):
        """测试空提示词验证"""
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            model_manager.validate_inference_request('text_to_image', prompt='')
        
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            model_manager.validate_inference_request('text_to_image', prompt='   ')
    
    def test_validate_inference_request_invalid_params(self, model_manager):
        """测试无效参数验证"""
        # 无效尺寸
        with pytest.raises(ValueError, match="Width must be between"):
            model_manager.validate_inference_request(
                'text_to_image',
                prompt='test',
                width=100
            )
        
        # 无效推理步数
        with pytest.raises(ValueError, match="num_inference_steps must be between"):
            model_manager.validate_inference_request(
                'text_to_image',
                prompt='test',
                num_inference_steps=0
            )
        
        # 无效引导比例
        with pytest.raises(ValueError, match="guidance_scale must be between"):
            model_manager.validate_inference_request(
                'text_to_image',
                prompt='test',
                guidance_scale=0.5
            )
    
    def test_validate_inference_request_image_to_image_invalid(self, model_manager):
        """测试图生图无效参数验证"""
        # 无效图像类型
        with pytest.raises(ValueError, match="Input image must be a PIL Image"):
            model_manager.validate_inference_request(
                'image_to_image',
                prompt='test',
                image='not_an_image'
            )
        
        # 无效强度
        test_image = Image.new('RGB', (512, 512), color='red')
        with pytest.raises(ValueError, match="Strength must be between"):
            model_manager.validate_inference_request(
                'image_to_image',
                prompt='test',
                image=test_image,
                strength=0.05
            )