#!/usr/bin/env python3
"""
实现验证脚本

验证 FastAPI 应用的基本功能是否正常。
"""

import sys
import os

def validate_imports():
    """验证模块导入"""
    print("Validating imports...")
    
    try:
        # 测试配置管理器
        from config.manager import get_config_manager, init_config
        print("  ✓ Config manager imports OK")
        
        # 测试模型
        from models.requests import TextToImageRequest, ImageToImageRequest
        from models.responses import ImageResponse, HealthResponse, InfoResponse
        print("  ✓ Model imports OK")
        
        # 测试服务
        from services.model_manager import ModelManager
        from services.request_processor import RequestProcessor
        print("  ✓ Service imports OK")
        
        # 测试 API
        from api.app import QwenImageAPI
        from api.routes import router
        print("  ✓ API imports OK")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_config():
    """验证配置功能"""
    print("Validating configuration...")
    
    try:
        from config.manager import init_config
        
        # 使用默认配置初始化
        config = init_config()
        print(f"  ✓ Config initialized: {config.server.host}:{config.server.port}")
        
        # 验证配置结构
        assert hasattr(config, 'model')
        assert hasattr(config, 'server')
        assert hasattr(config, 'log')
        print("  ✓ Config structure OK")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Config error: {e}")
        return False


def validate_api_creation():
    """验证 API 应用创建"""
    print("Validating API creation...")
    
    try:
        from api.app import QwenImageAPI
        from config.manager import init_config
        
        # 初始化配置
        init_config()
        
        # 创建 API 实例
        api = QwenImageAPI()
        app = api.create_app()
        
        print("  ✓ FastAPI app created")
        
        # 检查路由
        routes = [route.path for route in app.routes]
        expected_routes = ["/", "/text-to-image", "/image-to-image", "/health", "/info"]
        
        for route in expected_routes:
            if any(route in r for r in routes):
                print(f"  ✓ Route {route} found")
            else:
                print(f"  ⚠ Route {route} not found in {routes}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ API creation error: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_models():
    """验证数据模型"""
    print("Validating data models...")
    
    try:
        from models.requests import TextToImageRequest, ImageToImageRequest
        from models.responses import ImageResponse, HealthResponse, InfoResponse
        
        # 测试文生图请求模型
        text_req = TextToImageRequest(
            prompt="测试提示词",
            width=512,
            height=512,
            num_inference_steps=20,
            guidance_scale=7.5
        )
        print("  ✓ TextToImageRequest model OK")
        
        # 测试图生图请求模型
        img_req = ImageToImageRequest(
            prompt="测试提示词",
            strength=0.8,
            width=512,
            height=512,
            num_inference_steps=20
        )
        print("  ✓ ImageToImageRequest model OK")
        
        # 测试响应模型
        img_resp = ImageResponse(
            success=True,
            image="test_base64",
            metadata={"width": 512, "height": 512}
        )
        print("  ✓ ImageResponse model OK")
        
        health_resp = HealthResponse(
            status="healthy",
            model_loaded=True,
            memory_usage={},
            uptime=100.0
        )
        print("  ✓ HealthResponse model OK")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Model validation error: {e}")
        return False


def main():
    """主验证函数"""
    print("🔍 Validating FastAPI implementation...\n")
    
    tests = [
        validate_imports,
        validate_config,
        validate_models,
        validate_api_creation
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
            print()
        except Exception as e:
            print(f"❌ Test {test.__name__} failed: {e}")
            results.append(False)
            print()
    
    # 总结
    passed = sum(results)
    total = len(results)
    
    print(f"📊 Validation Summary: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All validations passed! FastAPI implementation looks good.")
        return True
    else:
        print("❌ Some validations failed. Please check the errors above.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)