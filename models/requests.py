"""
API 请求模型定义

包含文生图和图生图的请求数据模型，使用 Pydantic 进行数据验证。
"""

from pydantic import BaseModel, Field
from typing import Optional


class TextToImageRequest(BaseModel):
    """文生图请求模型"""
    
    prompt: str = Field(
        ..., 
        min_length=1, 
        max_length=1000,
        description="图像生成的文本描述"
    )
    width: Optional[int] = Field(
        512, 
        ge=256, 
        le=2048,
        description="生成图像的宽度"
    )
    height: Optional[int] = Field(
        512, 
        ge=256, 
        le=2048,
        description="生成图像的高度"
    )
    num_inference_steps: Optional[int] = Field(
        20, 
        ge=1, 
        le=100,
        description="推理步数"
    )
    guidance_scale: Optional[float] = Field(
        7.5, 
        ge=1.0, 
        le=20.0,
        description="引导比例"
    )

    class Config:
        schema_extra = {
            "example": {
                "prompt": "一只可爱的小猫坐在花园里",
                "width": 512,
                "height": 512,
                "num_inference_steps": 20,
                "guidance_scale": 7.5
            }
        }


class ImageToImageRequest(BaseModel):
    """图生图请求模型"""
    
    prompt: str = Field(
        ..., 
        min_length=1, 
        max_length=1000,
        description="图像修改的文本描述"
    )
    strength: Optional[float] = Field(
        0.8, 
        ge=0.1, 
        le=1.0,
        description="修改强度"
    )
    width: Optional[int] = Field(
        None, 
        ge=256, 
        le=2048,
        description="输出图像的宽度"
    )
    height: Optional[int] = Field(
        None, 
        ge=256, 
        le=2048,
        description="输出图像的高度"
    )
    num_inference_steps: Optional[int] = Field(
        20, 
        ge=1, 
        le=100,
        description="推理步数"
    )

    class Config:
        schema_extra = {
            "example": {
                "prompt": "将这张图片转换为水彩画风格",
                "strength": 0.8,
                "width": 512,
                "height": 512,
                "num_inference_steps": 20
            }
        }