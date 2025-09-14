#!/usr/bin/env python3
"""
启动测试脚本

测试 FastAPI 应用是否能正常启动。
"""

import sys
import asyncio
from contextlib import asynccontextmanager

async def test_app_startup():
    """测试应用启动"""
    print("Testing FastAPI application startup...")
    
    try:
        # 初始化配置
        from config.manager import init_config
        config = init_config("config.yaml")
        print(f"✓ Configuration loaded: {config.server.host}:{config.server.port}")
        
        # 创建 API 应用
        from api.app import QwenImageAPI
        api = QwenImageAPI()
        
        # 创建 FastAPI 应用
        app = api.create_app()
        print("✓ FastAPI application created")
        
        # 测试生命周期管理
        print("✓ Testing lifespan context manager...")
        
        # 模拟启动和关闭
        async with api.lifespan(app):
            print("✓ Application startup completed")
            
            # 验证组件初始化
            assert api.request_processor is not None
            print("✓ Request processor initialized")
            
            assert api.model_manager is not None
            print("✓ Model manager initialized")
            
            # 测试基本功能
            uptime = api.get_uptime()
            assert uptime >= 0
            print(f"✓ Uptime tracking works: {uptime:.3f}s")
        
        print("✓ Application shutdown completed")
        
        return True
        
    except Exception as e:
        print(f"❌ Startup test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_route_registration():
    """测试路由注册"""
    print("\nTesting route registration...")
    
    try:
        from api import app
        
        # 获取所有路由
        routes = []
        for route in app.routes:
            if hasattr(route, 'path'):
                routes.append(f"{route.methods} {route.path}" if hasattr(route, 'methods') else route.path)
        
        print("Registered routes:")
        for route in routes:
            print(f"  - {route}")
        
        # 检查必需的路由
        required_paths = ["/", "/text-to-image", "/image-to-image", "/health", "/info"]
        
        for path in required_paths:
            found = any(path in str(route) for route in routes)
            if found:
                print(f"✓ Route {path} registered")
            else:
                print(f"❌ Route {path} missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Route registration test failed: {e}")
        return False


async def main():
    """主测试函数"""
    print("🚀 Testing FastAPI Application Startup\n")
    
    tests = [
        test_app_startup,
        test_route_registration
    ]
    
    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
            print()
        except Exception as e:
            print(f"❌ Test {test.__name__} failed: {e}")
            results.append(False)
            print()
    
    # 总结
    passed = sum(results)
    total = len(results)
    
    print(f"📊 Test Summary: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All startup tests passed! Application is ready to run.")
        return True
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)