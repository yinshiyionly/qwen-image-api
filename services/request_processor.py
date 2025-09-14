"""
请求处理器

负责验证和预处理 API 请求，包括图像文件上传处理和格式验证。
"""

import io
import base64
from typing import Optional, Dict, Any, List
from PIL import Image
from fastapi import UploadFile, HTTPException
import logging

from models.requests import TextToImageRequest, ImageToImageRequest
from models.responses import ImageResponse, ErrorResponse

logger = logging.getLogger(__name__)


class RequestProcessor:
    """请求处理器类"""
    
    # 支持的图像格式
    SUPPORTED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "BMP"}
    
    # 支持的文件扩展名
    SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    
    # 最大文件大小 (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    # 最大图像尺寸
    MAX_IMAGE_DIMENSION = 2048

    def __init__(self, max_file_size: Optional[int] = None):
        """
        初始化请求处理器
        
        Args:
            max_file_size: 最大文件大小限制（字节）
        """
        self.max_file_size = max_file_size or self.MAX_FILE_SIZE
        logger.info(f"RequestProcessor initialized with max_file_size={self.max_file_size}")

    def validate_text_request(self, request: TextToImageRequest) -> bool:
        """
        验证文生图请求
        
        Args:
            request: 文生图请求对象
            
        Returns:
            bool: 验证是否通过
            
        Raises:
            HTTPException: 验证失败时抛出异常
        """
        try:
            # Pydantic 已经进行了基础验证，这里进行额外的业务逻辑验证
            
            # 检查提示词内容
            if not request.prompt.strip():
                raise HTTPException(
                    status_code=400,
                    detail="提示词不能为空或仅包含空白字符"
                )
            
            # 检查尺寸是否为合理的比例
            if request.width and request.height:
                aspect_ratio = request.width / request.height
                if aspect_ratio > 4 or aspect_ratio < 0.25:
                    logger.warning(f"Unusual aspect ratio: {aspect_ratio}")
            
            logger.info(f"Text request validation passed: prompt_length={len(request.prompt)}")
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Text request validation error: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"请求验证失败: {str(e)}"
            )

    def validate_image_request(self, request: ImageToImageRequest) -> bool:
        """
        验证图生图请求
        
        Args:
            request: 图生图请求对象
            
        Returns:
            bool: 验证是否通过
            
        Raises:
            HTTPException: 验证失败时抛出异常
        """
        try:
            # 基础验证
            if not request.prompt.strip():
                raise HTTPException(
                    status_code=400,
                    detail="提示词不能为空或仅包含空白字符"
                )
            
            # 检查强度参数的合理性
            if request.strength < 0.1:
                logger.warning(f"Very low strength value: {request.strength}")
            elif request.strength > 0.95:
                logger.warning(f"Very high strength value: {request.strength}")
            
            logger.info(f"Image request validation passed: prompt_length={len(request.prompt)}")
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Image request validation error: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"请求验证失败: {str(e)}"
            )

    def process_image_upload(self, file: UploadFile) -> Image.Image:
        """
        处理图像文件上传
        
        Args:
            file: 上传的文件对象
            
        Returns:
            PIL.Image.Image: 处理后的图像对象
            
        Raises:
            HTTPException: 文件处理失败时抛出异常
        """
        try:
            # 检查文件大小
            if hasattr(file, 'size') and file.size > self.max_file_size:
                raise HTTPException(
                    status_code=413,
                    detail=f"文件大小超过限制 ({self.max_file_size / 1024 / 1024:.1f}MB)"
                )
            
            # 检查文件扩展名
            if file.filename:
                file_ext = file.filename.lower().split('.')[-1]
                if f".{file_ext}" not in self.SUPPORTED_EXTENSIONS:
                    raise HTTPException(
                        status_code=415,
                        detail=f"不支持的文件格式。支持的格式: {', '.join(self.SUPPORTED_EXTENSIONS)}"
                    )
            
            # 读取文件内容
            file_content = file.file.read()
            
            # 检查实际文件大小
            if len(file_content) > self.max_file_size:
                raise HTTPException(
                    status_code=413,
                    detail=f"文件大小超过限制 ({self.max_file_size / 1024 / 1024:.1f}MB)"
                )
            
            # 尝试打开图像
            try:
                image = Image.open(io.BytesIO(file_content))
                
                # 验证图像格式
                if image.format not in self.SUPPORTED_IMAGE_FORMATS:
                    raise HTTPException(
                        status_code=415,
                        detail=f"不支持的图像格式: {image.format}。支持的格式: {', '.join(self.SUPPORTED_IMAGE_FORMATS)}"
                    )
                
                # 检查图像尺寸
                width, height = image.size
                if width > self.MAX_IMAGE_DIMENSION or height > self.MAX_IMAGE_DIMENSION:
                    raise HTTPException(
                        status_code=400,
                        detail=f"图像尺寸过大。最大支持尺寸: {self.MAX_IMAGE_DIMENSION}x{self.MAX_IMAGE_DIMENSION}"
                    )
                
                # 转换为 RGB 模式（如果需要）
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                    logger.info(f"Converted image from {image.mode} to RGB")
                
                logger.info(f"Image processed successfully: {width}x{height}, format={image.format}")
                return image
                
            except Exception as e:
                logger.error(f"Image processing error: {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"无法处理图像文件: {str(e)}"
                )
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"File upload processing error: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"文件处理失败: {str(e)}"
            )
        finally:
            # 重置文件指针
            if hasattr(file.file, 'seek'):
                file.file.seek(0)

    def format_image_response(
        self, 
        image: Image.Image, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> ImageResponse:
        """
        格式化图像响应
        
        Args:
            image: PIL 图像对象
            metadata: 额外的元数据
            
        Returns:
            ImageResponse: 格式化的响应对象
        """
        try:
            # 将图像转换为 base64
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            # 构建元数据
            response_metadata = {
                "width": image.size[0],
                "height": image.size[1],
                "format": "PNG",
                "mode": image.mode
            }
            
            if metadata:
                response_metadata.update(metadata)
            
            return ImageResponse(
                success=True,
                image=image_base64,
                metadata=response_metadata
            )
            
        except Exception as e:
            logger.error(f"Response formatting error: {e}")
            return ImageResponse(
                success=False,
                error=f"响应格式化失败: {str(e)}"
            )

    def format_error_response(
        self, 
        error_code: str, 
        error_message: str, 
        details: Optional[Dict[str, Any]] = None
    ) -> ErrorResponse:
        """
        格式化错误响应
        
        Args:
            error_code: 错误代码
            error_message: 错误消息
            details: 错误详情
            
        Returns:
            ErrorResponse: 格式化的错误响应
        """
        error_data = {
            "code": error_code,
            "message": error_message
        }
        
        if details:
            error_data["details"] = details
        
        return ErrorResponse(error=error_data)

    def get_supported_formats(self) -> List[str]:
        """
        获取支持的图像格式列表
        
        Returns:
            List[str]: 支持的格式列表
        """
        return list(self.SUPPORTED_IMAGE_FORMATS)

    def get_max_file_size(self) -> int:
        """
        获取最大文件大小限制
        
        Returns:
            int: 最大文件大小（字节）
        """
        return self.max_file_size