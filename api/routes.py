"""
API 路由定义

包含所有 API 端点的路由处理函数。
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse

from models.requests import TextToImageRequest, ImageToImageRequest
from models.responses import ImageResponse, HealthResponse, InfoResponse, ErrorResponse
from services.exceptions import (
    ModelNotLoadedError, InferenceError, ValidationError, 
    MemoryError, ResourceError
)
from .app import qwen_api

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter()


def get_model_manager():
    """依赖注入：获取模型管理器"""
    return qwen_api.get_model_manager()


def get_request_processor():
    """依赖注入：获取请求处理器"""
    return qwen_api.get_request_processor()


@router.post("/text-to-image", response_model=ImageResponse)
async def text_to_image(
    request: TextToImageRequest,
    model_manager=Depends(get_model_manager),
    request_processor=Depends(get_request_processor)
):
    """
    文生图 API 端点
    
    根据文本描述生成图像
    """
    start_time = time.time()
    
    try:
        logger.info(f"Text-to-image request: prompt='{request.prompt[:50]}...'")
        
        # 验证请求
        request_processor.validate_text_request(request)
        
        # 检查模型状态
        if not model_manager.is_model_loaded():
            raise HTTPException(
                status_code=503,
                detail="模型未加载，服务暂时不可用"
            )
        
        # 执行推理
        image = model_manager.text_to_image(
            prompt=request.prompt,
            width=request.width,
            height=request.height,
            num_inference_steps=request.num_inference_steps,
            guidance_scale=request.guidance_scale
        )
        
        # 计算推理时间
        inference_time = time.time() - start_time
        
        # 构建元数据
        metadata = {
            "width": image.width,
            "height": image.height,
            "inference_time": round(inference_time, 3),
            "model": "qwen-image",
            "timestamp": datetime.now().isoformat(),
            "parameters": {
                "prompt": request.prompt,
                "width": request.width,
                "height": request.height,
                "num_inference_steps": request.num_inference_steps,
                "guidance_scale": request.guidance_scale
            }
        }
        
        # 格式化响应
        response = request_processor.format_image_response(image, metadata)
        
        logger.info(f"Text-to-image completed in {inference_time:.3f}s")
        return response
        
    except ModelNotLoadedError:
        logger.error("Model not loaded")
        raise HTTPException(
            status_code=503,
            detail="模型未加载，请稍后重试"
        )
    except ValidationError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"参数验证失败: {str(e)}"
        )
    except MemoryError as e:
        logger.error(f"Memory error: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"内存不足: {str(e)}"
        )
    except InferenceError as e:
        logger.error(f"Inference error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"图像生成失败: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in text-to-image: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="服务器内部错误"
        )


@router.post("/image-to-image", response_model=ImageResponse)
async def image_to_image(
    image: UploadFile = File(..., description="输入图像文件"),
    prompt: str = Form(..., description="文本描述"),
    strength: float = Form(0.8, description="变换强度"),
    width: int = Form(None, description="输出宽度"),
    height: int = Form(None, description="输出高度"),
    num_inference_steps: int = Form(20, description="推理步数"),
    model_manager=Depends(get_model_manager),
    request_processor=Depends(get_request_processor)
):
    """
    图生图 API 端点
    
    基于输入图像和文本描述生成新图像
    """
    start_time = time.time()
    
    try:
        logger.info(f"Image-to-image request: prompt='{prompt[:50]}...'")
        
        # 处理上传的图像
        input_image = request_processor.process_image_upload(image)
        
        # 构建请求对象进行验证
        img_request = ImageToImageRequest(
            prompt=prompt,
            strength=strength,
            width=width or input_image.width,
            height=height or input_image.height,
            num_inference_steps=num_inference_steps
        )
        
        # 验证请求
        request_processor.validate_image_request(img_request)
        
        # 检查模型状态
        if not model_manager.is_model_loaded():
            raise HTTPException(
                status_code=503,
                detail="模型未加载，服务暂时不可用"
            )
        
        # 执行推理
        result_image = model_manager.image_to_image(
            image=input_image,
            prompt=img_request.prompt,
            strength=img_request.strength,
            width=img_request.width,
            height=img_request.height,
            num_inference_steps=img_request.num_inference_steps
        )
        
        # 计算推理时间
        inference_time = time.time() - start_time
        
        # 构建元数据
        metadata = {
            "width": result_image.width,
            "height": result_image.height,
            "inference_time": round(inference_time, 3),
            "model": "qwen-image",
            "timestamp": datetime.now().isoformat(),
            "parameters": {
                "prompt": img_request.prompt,
                "strength": img_request.strength,
                "width": img_request.width,
                "height": img_request.height,
                "num_inference_steps": img_request.num_inference_steps
            },
            "input_image": {
                "original_width": input_image.width,
                "original_height": input_image.height,
                "format": input_image.format
            }
        }
        
        # 格式化响应
        response = request_processor.format_image_response(result_image, metadata)
        
        logger.info(f"Image-to-image completed in {inference_time:.3f}s")
        return response
        
    except ModelNotLoadedError:
        logger.error("Model not loaded")
        raise HTTPException(
            status_code=503,
            detail="模型未加载，请稍后重试"
        )
    except ValidationError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"参数验证失败: {str(e)}"
        )
    except MemoryError as e:
        logger.error(f"Memory error: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"内存不足: {str(e)}"
        )
    except InferenceError as e:
        logger.error(f"Inference error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"图像生成失败: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in image-to-image: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="服务器内部错误"
        )


@router.get("/health", response_model=HealthResponse)
async def health_check(
    model_manager=Depends(get_model_manager)
):
    """
    健康检查端点
    
    返回服务和模型的健康状态
    """
    try:
        # 获取模型状态
        model_loaded = model_manager.is_model_loaded()
        
        # 获取资源统计
        resource_stats = model_manager.get_resource_stats()
        
        # 构建内存使用信息
        memory_usage = {
            "model_memory_mb": resource_stats.get("memory_usage_mb", {}),
            "inference_count": resource_stats.get("inference_count", 0),
            "error_count": resource_stats.get("error_count", 0)
        }
        
        # 添加 GPU 信息（如果可用）
        if "gpu_info" in resource_stats:
            memory_usage["gpu"] = resource_stats["gpu_info"]
        
        # 添加系统内存信息
        try:
            import psutil
            system_memory = psutil.virtual_memory()
            memory_usage["system"] = {
                "total_gb": round(system_memory.total / (1024**3), 2),
                "available_gb": round(system_memory.available / (1024**3), 2),
                "used_percent": system_memory.percent
            }
        except ImportError:
            pass
        
        # 确定服务状态
        status = "healthy" if model_loaded else "degraded"
        
        # 获取服务运行时间
        uptime = qwen_api.get_uptime()
        
        response = HealthResponse(
            status=status,
            model_loaded=model_loaded,
            memory_usage=memory_usage,
            uptime=uptime,
            timestamp=datetime.now()
        )
        
        logger.debug(f"Health check: status={status}, model_loaded={model_loaded}")
        return response
        
    except Exception as e:
        logger.error(f"Health check error: {e}", exc_info=True)
        
        # 返回错误状态
        return HealthResponse(
            status="unhealthy",
            model_loaded=False,
            memory_usage={"error": str(e)},
            uptime=qwen_api.get_uptime(),
            timestamp=datetime.now()
        )


@router.get("/info", response_model=InfoResponse)
async def service_info(
    model_manager=Depends(get_model_manager),
    request_processor=Depends(get_request_processor)
):
    """
    服务信息端点
    
    返回模型信息和 API 详情
    """
    try:
        # 获取模型信息
        model_info = model_manager.get_model_info()
        
        # 获取支持的格式
        supported_formats = request_processor.get_supported_formats()
        
        # 获取支持的参数范围
        format_info = model_manager.get_supported_formats()
        
        response = InfoResponse(
            service_name="qwen-image-api-service",
            version="1.0.0",
            model_info={
                "name": "qwen-image",
                "loaded": model_info.get("loaded", False),
                "device": model_info.get("device", "unknown"),
                "dtype": model_info.get("torch_dtype", "unknown"),
                "path": model_info.get("model_path", "")
            },
            supported_formats=supported_formats,
            api_endpoints=[
                "/text-to-image",
                "/image-to-image", 
                "/health",
                "/info"
            ]
        )
        
        # 添加详细的格式和参数信息
        response.model_info.update({
            "supported_parameters": format_info
        })
        
        logger.debug("Service info requested")
        return response
        
    except Exception as e:
        logger.error(f"Service info error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="获取服务信息失败"
        )


@router.get("/metrics")
async def get_metrics():
    """
    性能指标端点
    
    返回服务性能指标和统计信息
    """
    try:
        from services.logging import performance_monitor, request_tracker
        
        # 获取性能指标
        metrics = performance_monitor.get_metrics()
        
        # 获取活跃请求信息
        active_requests = request_tracker.get_active_requests()
        
        # 添加活跃请求统计
        metrics["active_requests"] = {
            "count": len(active_requests),
            "requests": list(active_requests.values())
        }
        
        # 添加系统资源信息
        try:
            import psutil
            system_info = {
                "cpu_percent": psutil.cpu_percent(),
                "memory": {
                    "total": psutil.virtual_memory().total,
                    "available": psutil.virtual_memory().available,
                    "percent": psutil.virtual_memory().percent
                },
                "disk": {
                    "total": psutil.disk_usage('/').total,
                    "free": psutil.disk_usage('/').free,
                    "percent": psutil.disk_usage('/').percent
                }
            }
            metrics["system"] = system_info
        except ImportError:
            pass
        
        logger.debug("Metrics requested")
        return metrics
        
    except Exception as e:
        logger.error(f"Metrics error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="获取性能指标失败"
        )


# 根路径重定向到文档
@router.get("/")
async def root():
    """根路径，返回 API 基本信息"""
    return {
        "message": "Qwen Image API Service",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "info": "/info",
        "metrics": "/metrics"
    }