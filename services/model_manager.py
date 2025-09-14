"""
模型管理器实现

负责 qwen-image 模型的加载、状态管理和推理功能。
"""

import logging
import gc
import torch
from typing import Dict, Any, Optional
from PIL import Image
import base64
import io
from threading import Lock

from .interfaces import ModelManagerInterface
from .exceptions import (
    ModelLoadError, ModelNotLoadedError, InferenceError, 
    ResourceError, ValidationError, DeviceError, MemoryError
)
from config.models import ModelConfig


logger = logging.getLogger(__name__)


class ModelManager(ModelManagerInterface):
    """qwen-image 模型管理器"""
    
    def __init__(self, model_path: str, config: Dict[str, Any]):
        """
        初始化模型管理器
        
        Args:
            model_path: 模型文件路径
            config: 模型配置字典
        """
        self.model_path = model_path
        self.config = ModelConfig(**config)
        self.model = None
        self.processor = None
        self._model_loaded = False
        self._lock = Lock()
        self._memory_usage = {'peak': 0, 'current': 0}
        self._inference_count = 0
        self._error_count = 0
        
        logger.info(f"ModelManager initialized with path: {model_path}")
        logger.info(f"Device: {self.config.device}, dtype: {self.config.torch_dtype}")
    
    def load_model(self) -> None:
        """
        加载 qwen-image 模型
        
        Raises:
            RuntimeError: 模型加载失败
            FileNotFoundError: 模型文件不存在
        """
        with self._lock:
            if self._model_loaded:
                logger.info("Model already loaded")
                return
            
            try:
                logger.info("Loading qwen-image model...")
                
                # 检查模型路径是否存在
                import os
                if not os.path.exists(self.model_path):
                    raise ModelLoadError(
                        f"Model path does not exist: {self.model_path}",
                        model_path=self.model_path
                    )
                
                # 检查可用内存
                self._check_memory_availability()
                
                # 设置设备
                device = self._get_device()
                
                # 加载 qwen-image 模型
                # 注意：这里使用模拟实现，实际部署时需要替换为真实的 qwen-image 模型
                self.model, self.processor = self._load_qwen_image_model(device)
                
                # 验证模型加载
                if self.model is None:
                    raise ModelLoadError("Failed to initialize qwen-image model")
                
                # 更新内存使用情况
                self._update_memory_usage()
                
                self._model_loaded = True
                logger.info(f"Model loaded successfully on device: {device}")
                
            except ModelLoadError:
                self._model_loaded = False
                self._error_count += 1
                raise
            except Exception as e:
                logger.error(f"Failed to load model: {str(e)}")
                self._model_loaded = False
                self._error_count += 1
                raise ModelLoadError(f"Model loading failed: {str(e)}", model_path=self.model_path)
    
    def text_to_image(self, prompt: str, **kwargs) -> Image.Image:
        """
        文生图推理
        
        Args:
            prompt: 文本提示词
            **kwargs: 推理参数 (width, height, num_inference_steps, guidance_scale)
            
        Returns:
            PIL.Image.Image: 生成的图像
            
        Raises:
            ModelNotLoadedError: 模型未加载
            ValidationError: 参数无效
            InferenceError: 推理失败
            MemoryError: 内存不足
        """
        if not self._model_loaded:
            raise ModelNotLoadedError()
        
        if not prompt or not prompt.strip():
            raise ValidationError("Prompt cannot be empty", parameter="prompt")
        
        try:
            logger.info(f"Generating image from text: {prompt[:50]}...")
            
            # 解析推理参数
            width = kwargs.get('width', 512)
            height = kwargs.get('height', 512)
            num_inference_steps = kwargs.get('num_inference_steps', 20)
            guidance_scale = kwargs.get('guidance_scale', 7.5)
            
            # 验证参数
            self._validate_generation_params(width, height, num_inference_steps, guidance_scale)
            
            # 检查内存可用性
            self._check_inference_memory(width, height)
            
            # 执行文生图推理
            with torch.no_grad():
                image = self._execute_text_to_image(
                    prompt=prompt,
                    width=width,
                    height=height,
                    num_inference_steps=num_inference_steps,
                    guidance_scale=guidance_scale
                )
            
            # 更新统计信息
            self._inference_count += 1
            self._update_memory_usage()
            
            logger.info(f"Image generated successfully: {width}x{height}")
            return image
            
        except (ValidationError, ModelNotLoadedError, MemoryError):
            self._error_count += 1
            raise
        except Exception as e:
            logger.error(f"Text-to-image generation failed: {str(e)}")
            self._error_count += 1
            raise InferenceError(f"Text-to-image generation failed: {str(e)}", inference_type="text_to_image")
    
    def image_to_image(self, image: Image.Image, prompt: str, **kwargs) -> Image.Image:
        """
        图生图推理
        
        Args:
            image: 输入图像
            prompt: 文本提示词
            **kwargs: 推理参数 (strength, width, height, num_inference_steps)
            
        Returns:
            PIL.Image.Image: 生成的图像
            
        Raises:
            ModelNotLoadedError: 模型未加载
            ValidationError: 参数无效
            InferenceError: 推理失败
            MemoryError: 内存不足
        """
        if not self._model_loaded:
            raise ModelNotLoadedError()
        
        if not prompt or not prompt.strip():
            raise ValidationError("Prompt cannot be empty", parameter="prompt")
        
        if not isinstance(image, Image.Image):
            raise ValidationError("Input must be a PIL Image", parameter="image")
        
        try:
            logger.info(f"Generating image from image+text: {prompt[:50]}...")
            
            # 解析推理参数
            strength = kwargs.get('strength', 0.8)
            width = kwargs.get('width', image.width)
            height = kwargs.get('height', image.height)
            num_inference_steps = kwargs.get('num_inference_steps', 20)
            
            # 验证参数
            self._validate_generation_params(width, height, num_inference_steps)
            if not 0.1 <= strength <= 1.0:
                raise ValidationError("Strength must be between 0.1 and 1.0", parameter="strength")
            
            # 检查内存可用性
            self._check_inference_memory(width, height)
            
            # 预处理输入图像
            processed_image = self._preprocess_image(image, width, height)
            
            # 执行图生图推理
            with torch.no_grad():
                result_image = self._execute_image_to_image(
                    image=processed_image,
                    prompt=prompt,
                    strength=strength,
                    width=width,
                    height=height,
                    num_inference_steps=num_inference_steps
                )
            
            # 更新统计信息
            self._inference_count += 1
            self._update_memory_usage()
            
            logger.info(f"Image-to-image generation completed: {width}x{height}")
            return result_image
            
        except (ValidationError, ModelNotLoadedError, MemoryError):
            self._error_count += 1
            raise
        except Exception as e:
            logger.error(f"Image-to-image generation failed: {str(e)}")
            self._error_count += 1
            raise InferenceError(f"Image-to-image generation failed: {str(e)}", inference_type="image_to_image")
    
    def is_model_loaded(self) -> bool:
        """
        检查模型是否已加载
        
        Returns:
            bool: 模型加载状态
        """
        return self._model_loaded
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息
        
        Returns:
            Dict[str, Any]: 模型信息字典
        """
        return {
            'loaded': self._model_loaded,
            'model_path': self.model_path,
            'device': self.config.device,
            'torch_dtype': self.config.torch_dtype,
            'max_memory': self.config.max_memory
        }
    
    def cleanup(self) -> None:
        """
        清理模型资源
        """
        with self._lock:
            if self.model is not None:
                logger.info("Cleaning up model resources...")
                
                # 清理模型
                del self.model
                self.model = None
                
                # 清理处理器
                if self.processor is not None:
                    del self.processor
                    self.processor = None
                
                # 清理 GPU 缓存
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                
                # 强制垃圾回收
                gc.collect()
                
                self._model_loaded = False
                logger.info("Model resources cleaned up")
    
    def _load_qwen_image_model(self, device: str) -> tuple:
        """
        加载 qwen-image 模型和处理器
        
        Args:
            device: 推理设备
            
        Returns:
            tuple: (model, processor) 元组
            
        Raises:
            RuntimeError: 模型加载失败
        """
        try:
            # 实际的 qwen-image 模型加载代码应该在这里
            # 以下是示例代码结构，需要根据实际的 qwen-image API 调整
            
            # 方案1: 如果使用 transformers 库
            # from transformers import AutoModel, AutoProcessor
            # model = AutoModel.from_pretrained(
            #     self.model_path,
            #     device_map=device,
            #     torch_dtype=getattr(torch, self.config.torch_dtype),
            #     trust_remote_code=True
            # )
            # processor = AutoProcessor.from_pretrained(self.model_path)
            
            # 方案2: 如果使用 diffusers 库
            # from diffusers import StableDiffusionPipeline, StableDiffusionImg2ImgPipeline
            # model = {
            #     'text_to_image': StableDiffusionPipeline.from_pretrained(
            #         self.model_path,
            #         torch_dtype=getattr(torch, self.config.torch_dtype)
            #     ).to(device),
            #     'image_to_image': StableDiffusionImg2ImgPipeline.from_pretrained(
            #         self.model_path,
            #         torch_dtype=getattr(torch, self.config.torch_dtype)
            #     ).to(device)
            # }
            # processor = None
            
            # 方案3: 如果使用专门的 qwen-image 库
            # from qwen_image import QwenImageModel, QwenImageProcessor
            # model = QwenImageModel.from_pretrained(
            #     self.model_path,
            #     device=device,
            #     torch_dtype=self.config.torch_dtype
            # )
            # processor = QwenImageProcessor.from_pretrained(self.model_path)
            
            # 临时模拟实现 - 实际部署时需要替换
            logger.info(f"Loading qwen-image model from {self.model_path}")
            
            # 模拟模型结构
            model = {
                'type': 'qwen-image',
                'device': device,
                'dtype': self.config.torch_dtype,
                'path': self.model_path,
                'loaded': True,
                # 在实际实现中，这里应该是真实的模型对象
                'text_to_image_pipeline': None,  # 实际的文生图管道
                'image_to_image_pipeline': None,  # 实际的图生图管道
            }
            
            # 模拟处理器
            processor = {
                'tokenizer': None,  # 实际的分词器
                'image_processor': None,  # 实际的图像处理器
            }
            
            logger.info("qwen-image model loaded successfully")
            return model, processor
            
        except Exception as e:
            logger.error(f"Failed to load qwen-image model: {str(e)}")
            raise RuntimeError(f"qwen-image model loading failed: {str(e)}")
    
    def _execute_text_to_image(self, prompt: str, width: int, height: int, 
                              num_inference_steps: int, guidance_scale: float) -> Image.Image:
        """
        执行文生图推理
        
        Args:
            prompt: 文本提示词
            width: 图像宽度
            height: 图像高度
            num_inference_steps: 推理步数
            guidance_scale: 引导比例
            
        Returns:
            PIL.Image.Image: 生成的图像
        """
        try:
            # 实际的推理代码应该在这里
            # 示例代码（需要根据实际的 qwen-image API 调整）:
            
            # 方案1: 使用 transformers
            # inputs = self.processor(text=prompt, return_tensors="pt")
            # with torch.no_grad():
            #     outputs = self.model.generate(
            #         **inputs,
            #         width=width,
            #         height=height,
            #         num_inference_steps=num_inference_steps,
            #         guidance_scale=guidance_scale
            #     )
            # image = self.processor.decode(outputs[0])
            
            # 方案2: 使用 diffusers
            # pipeline = self.model['text_to_image']
            # image = pipeline(
            #     prompt=prompt,
            #     width=width,
            #     height=height,
            #     num_inference_steps=num_inference_steps,
            #     guidance_scale=guidance_scale
            # ).images[0]
            
            # 方案3: 使用专门的 qwen-image API
            # image = self.model.text_to_image(
            #     prompt=prompt,
            #     width=width,
            #     height=height,
            #     num_inference_steps=num_inference_steps,
            #     guidance_scale=guidance_scale
            # )
            
            # 临时模拟实现 - 创建带有提示词信息的测试图像
            import hashlib
            from PIL import ImageDraw, ImageFont
            
            # 创建基础图像
            image = Image.new('RGB', (width, height), color='lightblue')
            
            # 添加文本信息（用于测试验证）
            draw = ImageDraw.Draw(image)
            try:
                # 尝试使用默认字体
                font = ImageFont.load_default()
            except:
                font = None
            
            # 在图像上绘制提示词的哈希值（用于验证）
            prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
            text = f"Text2Img: {prompt_hash}"
            draw.text((10, 10), text, fill='black', font=font)
            
            # 添加参数信息
            params_text = f"{width}x{height}, steps:{num_inference_steps}, scale:{guidance_scale}"
            draw.text((10, 30), params_text, fill='darkblue', font=font)
            
            return image
            
        except Exception as e:
            logger.error(f"Text-to-image inference failed: {str(e)}")
            raise RuntimeError(f"Text-to-image inference error: {str(e)}")
    
    def _execute_image_to_image(self, image: Image.Image, prompt: str, strength: float,
                               width: int, height: int, num_inference_steps: int) -> Image.Image:
        """
        执行图生图推理
        
        Args:
            image: 输入图像
            prompt: 文本提示词
            strength: 变换强度
            width: 输出宽度
            height: 输出高度
            num_inference_steps: 推理步数
            
        Returns:
            PIL.Image.Image: 生成的图像
        """
        try:
            # 实际的推理代码应该在这里
            # 示例代码（需要根据实际的 qwen-image API 调整）:
            
            # 方案1: 使用 transformers
            # inputs = self.processor(
            #     text=prompt,
            #     images=image,
            #     return_tensors="pt"
            # )
            # with torch.no_grad():
            #     outputs = self.model.generate(
            #         **inputs,
            #         width=width,
            #         height=height,
            #         num_inference_steps=num_inference_steps,
            #         strength=strength
            #     )
            # result_image = self.processor.decode(outputs[0])
            
            # 方案2: 使用 diffusers
            # pipeline = self.model['image_to_image']
            # result_image = pipeline(
            #     prompt=prompt,
            #     image=image,
            #     strength=strength,
            #     width=width,
            #     height=height,
            #     num_inference_steps=num_inference_steps
            # ).images[0]
            
            # 方案3: 使用专门的 qwen-image API
            # result_image = self.model.image_to_image(
            #     image=image,
            #     prompt=prompt,
            #     strength=strength,
            #     width=width,
            #     height=height,
            #     num_inference_steps=num_inference_steps
            # )
            
            # 临时模拟实现 - 基于输入图像创建变换后的图像
            import hashlib
            from PIL import ImageDraw, ImageFont, ImageEnhance
            
            # 调整输入图像尺寸
            result_image = image.resize((width, height), Image.Resampling.LANCZOS)
            
            # 根据强度调整图像
            if strength > 0.5:
                # 高强度：更多变化，调整亮度和对比度
                enhancer = ImageEnhance.Brightness(result_image)
                result_image = enhancer.enhance(1.0 + (strength - 0.5))
                
                enhancer = ImageEnhance.Contrast(result_image)
                result_image = enhancer.enhance(1.0 + (strength - 0.5) * 0.5)
            
            # 添加文本信息（用于测试验证）
            draw = ImageDraw.Draw(result_image)
            try:
                font = ImageFont.load_default()
            except:
                font = None
            
            # 在图像上绘制提示词的哈希值
            prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
            text = f"Img2Img: {prompt_hash}"
            draw.text((10, 10), text, fill='white', font=font)
            
            # 添加参数信息
            params_text = f"strength:{strength}, {width}x{height}"
            draw.text((10, 30), params_text, fill='yellow', font=font)
            
            return result_image
            
        except Exception as e:
            logger.error(f"Image-to-image inference failed: {str(e)}")
            raise RuntimeError(f"Image-to-image inference error: {str(e)}")
    
    def _get_device(self) -> str:
        """
        获取推理设备
        
        Returns:
            str: 设备名称
        """
        if self.config.device == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        elif self.config.device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA not available, falling back to CPU")
            return "cpu"
        else:
            return self.config.device
    
    def _validate_generation_params(self, width: int, height: int, 
                                  num_inference_steps: int, guidance_scale: float = None) -> None:
        """
        验证生成参数
        
        Args:
            width: 图像宽度
            height: 图像高度
            num_inference_steps: 推理步数
            guidance_scale: 引导比例（可选）
            
        Raises:
            ValueError: 参数无效
        """
        if not 256 <= width <= 2048:
            raise ValidationError("Width must be between 256 and 2048", parameter="width")
        
        if not 256 <= height <= 2048:
            raise ValidationError("Height must be between 256 and 2048", parameter="height")
        
        if not 1 <= num_inference_steps <= 100:
            raise ValidationError("num_inference_steps must be between 1 and 100", parameter="num_inference_steps")
        
        if guidance_scale is not None and not 1.0 <= guidance_scale <= 20.0:
            raise ValidationError("guidance_scale must be between 1.0 and 20.0", parameter="guidance_scale")
    
    def _preprocess_image(self, image: Image.Image, target_width: int, target_height: int) -> Image.Image:
        """
        预处理输入图像
        
        Args:
            image: 输入图像
            target_width: 目标宽度
            target_height: 目标高度
            
        Returns:
            PIL.Image.Image: 预处理后的图像
        """
        # 转换为 RGB 模式
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # 调整大小
        if image.size != (target_width, target_height):
            image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        return image
    
    def get_supported_formats(self) -> Dict[str, Any]:
        """
        获取支持的图像格式和参数范围
        
        Returns:
            Dict[str, Any]: 支持的格式和参数信息
        """
        return {
            'image_formats': ['JPEG', 'PNG', 'WEBP', 'BMP'],
            'max_resolution': {'width': 2048, 'height': 2048},
            'min_resolution': {'width': 256, 'height': 256},
            'inference_steps_range': {'min': 1, 'max': 100},
            'guidance_scale_range': {'min': 1.0, 'max': 20.0},
            'strength_range': {'min': 0.1, 'max': 1.0},
            'supported_dtypes': ['float16', 'float32', 'bfloat16'],
            'supported_devices': ['cpu', 'cuda', 'auto']
        }
    
    def format_inference_result(self, image: Image.Image, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        格式化推理结果
        
        Args:
            image: 生成的图像
            metadata: 推理元数据
            
        Returns:
            Dict[str, Any]: 格式化的结果
        """
        result = {
            'image': image,
            'width': image.width,
            'height': image.height,
            'mode': image.mode,
            'format': image.format or 'PNG',
            'size_bytes': len(image.tobytes()) if hasattr(image, 'tobytes') else None
        }
        
        if metadata:
            result['metadata'] = metadata
            
        return result
    
    def validate_inference_request(self, request_type: str, **kwargs) -> Dict[str, Any]:
        """
        验证推理请求参数
        
        Args:
            request_type: 请求类型 ('text_to_image' 或 'image_to_image')
            **kwargs: 请求参数
            
        Returns:
            Dict[str, Any]: 验证后的参数
            
        Raises:
            ValueError: 参数验证失败
        """
        if request_type not in ['text_to_image', 'image_to_image']:
            raise ValueError(f"Unsupported request type: {request_type}")
        
        # 通用参数验证
        validated_params = {}
        
        # 提示词验证
        prompt = kwargs.get('prompt', '')
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        validated_params['prompt'] = prompt.strip()
        
        # 尺寸参数验证
        width = kwargs.get('width', 512)
        height = kwargs.get('height', 512)
        self._validate_generation_params(width, height, 1)  # 临时验证尺寸
        validated_params['width'] = width
        validated_params['height'] = height
        
        # 推理步数验证
        num_inference_steps = kwargs.get('num_inference_steps', 20)
        if not 1 <= num_inference_steps <= 100:
            raise ValueError("num_inference_steps must be between 1 and 100")
        validated_params['num_inference_steps'] = num_inference_steps
        
        # 特定类型参数验证
        if request_type == 'text_to_image':
            guidance_scale = kwargs.get('guidance_scale', 7.5)
            if not 1.0 <= guidance_scale <= 20.0:
                raise ValueError("guidance_scale must be between 1.0 and 20.0")
            validated_params['guidance_scale'] = guidance_scale
            
        elif request_type == 'image_to_image':
            # 输入图像验证
            input_image = kwargs.get('image')
            if not isinstance(input_image, Image.Image):
                raise ValueError("Input image must be a PIL Image")
            validated_params['image'] = input_image
            
            # 强度参数验证
            strength = kwargs.get('strength', 0.8)
            if not 0.1 <= strength <= 1.0:
                raise ValueError("Strength must be between 0.1 and 1.0")
            validated_params['strength'] = strength
        
        return validated_params
    
    def _check_memory_availability(self) -> None:
        """
        检查内存可用性
        
        Raises:
            MemoryError: 内存不足
        """
        try:
            import psutil
            
            # 检查系统内存
            memory = psutil.virtual_memory()
            available_gb = memory.available / (1024**3)
            
            # 模型加载至少需要 2GB 内存
            min_required_gb = 2.0
            
            if available_gb < min_required_gb:
                raise MemoryError(
                    f"Insufficient memory for model loading. "
                    f"Available: {available_gb:.1f}GB, Required: {min_required_gb}GB"
                )
            
            # 检查 GPU 内存（如果使用 CUDA）
            if torch.cuda.is_available() and self.config.device in ['cuda', 'auto']:
                gpu_memory = torch.cuda.get_device_properties(0).total_memory
                gpu_available = gpu_memory - torch.cuda.memory_allocated(0)
                gpu_available_gb = gpu_available / (1024**3)
                
                if gpu_available_gb < min_required_gb:
                    logger.warning(f"Low GPU memory: {gpu_available_gb:.1f}GB available")
                    
        except ImportError:
            # psutil 不可用，跳过内存检查
            logger.warning("psutil not available, skipping memory check")
        except Exception as e:
            logger.warning(f"Memory check failed: {str(e)}")
    
    def _check_inference_memory(self, width: int, height: int) -> None:
        """
        检查推理内存需求
        
        Args:
            width: 图像宽度
            height: 图像高度
            
        Raises:
            MemoryError: 内存不足
        """
        try:
            # 估算内存需求（简化计算）
            pixels = width * height
            # 假设每个像素需要 4 字节（RGBA），加上模型中间结果的内存开销
            estimated_mb = (pixels * 4 * 3) / (1024**2)  # 3倍开销用于中间结果
            
            if torch.cuda.is_available() and self.config.device in ['cuda', 'auto']:
                # 检查 GPU 内存
                gpu_memory_free = torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated(0)
                gpu_free_mb = gpu_memory_free / (1024**2)
                
                if estimated_mb > gpu_free_mb * 0.8:  # 保留 20% 缓冲
                    raise MemoryError(
                        f"Insufficient GPU memory for inference. "
                        f"Estimated need: {estimated_mb:.1f}MB, Available: {gpu_free_mb:.1f}MB"
                    )
            else:
                # 检查系统内存
                import psutil
                memory = psutil.virtual_memory()
                available_mb = memory.available / (1024**2)
                
                if estimated_mb > available_mb * 0.8:
                    raise MemoryError(
                        f"Insufficient system memory for inference. "
                        f"Estimated need: {estimated_mb:.1f}MB, Available: {available_mb:.1f}MB"
                    )
                    
        except ImportError:
            # psutil 不可用，跳过内存检查
            pass
        except Exception as e:
            logger.warning(f"Inference memory check failed: {str(e)}")
    
    def _update_memory_usage(self) -> None:
        """更新内存使用统计"""
        try:
            if torch.cuda.is_available() and self.config.device in ['cuda', 'auto']:
                current_usage = torch.cuda.memory_allocated(0) / (1024**2)  # MB
                self._memory_usage['current'] = current_usage
                if current_usage > self._memory_usage['peak']:
                    self._memory_usage['peak'] = current_usage
        except Exception as e:
            logger.warning(f"Memory usage update failed: {str(e)}")
    
    def get_resource_stats(self) -> Dict[str, Any]:
        """
        获取资源使用统计
        
        Returns:
            Dict[str, Any]: 资源统计信息
        """
        stats = {
            'inference_count': self._inference_count,
            'error_count': self._error_count,
            'memory_usage_mb': self._memory_usage.copy(),
            'model_loaded': self._model_loaded
        }
        
        # 添加设备信息
        if torch.cuda.is_available():
            stats['gpu_info'] = {
                'device_name': torch.cuda.get_device_name(0),
                'total_memory_mb': torch.cuda.get_device_properties(0).total_memory / (1024**2),
                'allocated_memory_mb': torch.cuda.memory_allocated(0) / (1024**2),
                'cached_memory_mb': torch.cuda.memory_reserved(0) / (1024**2)
            }
        
        return stats
    
    def reset_stats(self) -> None:
        """重置统计信息"""
        self._inference_count = 0
        self._error_count = 0
        self._memory_usage = {'peak': 0, 'current': 0}
        logger.info("Resource statistics reset")
    
    def health_check(self) -> Dict[str, Any]:
        """
        执行健康检查
        
        Returns:
            Dict[str, Any]: 健康状态信息
        """
        health = {
            'status': 'healthy',
            'model_loaded': self._model_loaded,
            'device': self.config.device,
            'issues': []
        }
        
        try:
            # 检查模型状态
            if not self._model_loaded:
                health['issues'].append('Model not loaded')
                health['status'] = 'unhealthy'
            
            # 检查内存状态
            if torch.cuda.is_available() and self.config.device in ['cuda', 'auto']:
                gpu_memory_used = torch.cuda.memory_allocated(0) / torch.cuda.get_device_properties(0).total_memory
                if gpu_memory_used > 0.9:
                    health['issues'].append(f'High GPU memory usage: {gpu_memory_used:.1%}')
                    health['status'] = 'warning'
            
            # 检查错误率
            if self._inference_count > 0:
                error_rate = self._error_count / (self._inference_count + self._error_count)
                if error_rate > 0.1:  # 错误率超过 10%
                    health['issues'].append(f'High error rate: {error_rate:.1%}')
                    health['status'] = 'warning'
            
            # 设置最终状态
            if health['issues'] and health['status'] == 'healthy':
                health['status'] = 'warning'
                
        except Exception as e:
            health['status'] = 'error'
            health['issues'].append(f'Health check failed: {str(e)}')
        
        return health