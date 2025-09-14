#!/usr/bin/env python3
"""
基本 API 功能测试脚本

验证 FastAPI 应用的基本功能是否正常。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

def test_basic_functionality():
    """测试基本功能"""
    print("Testing basic API functionality...")
    
    try:
        # 导入应用
        from api import app
        
        # 创建测试客户端
        client = TestClient(app)
        
        # 模拟依赖
        mock_model_manager = Mock()
        mock_model_manager.is_model_loaded.return_value = False
        mock_model_manager.get_model_info.return_value = {
            'loaded': False,
            'model_path': '',
            'device': 'cpu',
            'torch_dtype': 'float32'
        }
        mock_model_manager.get_resource_stats.return_value = {
            'inference_count': 0,
            'error_count': 0,
            'memory_usage_mb': {'current': 0, 'peak': 0}
        }
        mock_model_manager.get_supported_formats.return_value = {
            'image_formats': ['JPEG', 'PNG', 'WEBP'],
            'max_resolution': {'width': 2048, 'height': 2048}
        }
        
        mock_request_processor = Mock()
        mock_request_processor.get_supported_formats.return_value = ['JPEG', 'PNG', 'WEBP']
        
        # 测试根端点
        with patch('api.app.qwen_api.get_model_manager', return_value=mock_model_manager), \
             patch('api.app.qwen_api.get_request_processor', return_value=mock_request_processor), \
             patch('api.app.qwen_api.get_uptime', return_value=0.0):
            
            print("1. Testing root endpoint...")
            response = client.get("/")
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            print("   ✓ Root endpoint works")
            
            print("2. Testing health endpoint...")
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "model_loaded" in data
            print("   ✓ Health endpoint works")
            
            print("3. Testing info endpoint...")
            response = client.get("/info")
            assert response.status_code == 200
            data = response.json()
            assert "service_name" in data
            assert "version" in data
            print("   ✓ Info endpoint works")
            
            print("4. Testing text-to-image validation...")
            # 测试无效请求
            response = client.post("/text-to-image", json={"prompt": ""})
            assert response.status_code == 422  # 验证错误
            print("   ✓ Text-to-image validation works")
        
        print("\n✅ All basic tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_basic_functionality()
    sys.exit(0 if success else 1)