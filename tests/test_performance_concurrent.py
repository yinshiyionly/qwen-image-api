"""
并发和性能测试

测试 API 服务的并发处理能力和性能基准。
"""

import pytest
import asyncio
import time
import threading
import concurrent.futures
from unittest.mock import Mock, patch, MagicMock
from PIL import Image
from fastapi.testclient import TestClient
import io
import gc
import psutil
import os

from api.app import qwen_api
from models.responses import ImageResponse


@pytest.fixture
def app():
    """创建测试应用实例"""
    return qwen_api.create_app()


@pytest.fixture
def client(app):
    """测试客户端"""
    return TestClient(app)


@pytest.fixture
def mock_model_manager():
    """模拟模型管理器"""
    mock = Mock()
    mock.is_model_loaded.return_value = True
    mock.get_model_info.return_value = {
        'loaded': True,
        'model_path': '/path/to/model',
        'device': 'cuda',
        'torch_dtype': 'float16'
    }
    mock.get_resource_stats.return_value = {
        'inference_count': 0,
        'error_count': 0,
        'memory_usage_mb': {'current': 1024, 'peak': 2048}
    }
    
    # 模拟推理时间
    def mock_text_to_image(*args, **kwargs):
        time.sleep(0.1)  # 模拟推理时间
        return Image.new('RGB', (512, 512), color='blue')
    
    def mock_image_to_image(*args, **kwargs):
        time.sleep(0.15)  # 模拟图生图推理时间
        return Image.new('RGB', (512, 512), color='green')
    
    mock.text_to_image.side_effect = mock_text_to_image
    mock.image_to_image.side_effect = mock_image_to_image
    
    return mock


@pytest.fixture
def mock_request_processor():
    """模拟请求处理器"""
    mock = Mock()
    mock.validate_text_request.return_value = True
    mock.validate_image_request.return_value = True
    mock.get_supported_formats.return_value = ['JPEG', 'PNG', 'WEBP']
    
    # 模拟图像处理
    test_image = Image.new('RGB', (512, 512), color='red')
    mock.process_image_upload.return_value = test_image
    
    # 模拟响应格式化
    mock.format_image_response.return_value = ImageResponse(
        success=True,
        image="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
        metadata={
            "width": 512,
            "height": 512,
            "inference_time": 0.1
        }
    )
    
    return mock


def create_test_image(width=256, height=256, color='green', format='PNG'):
    """创建测试图像"""
    image = Image.new('RGB', (width, height), color=color)
    img_buffer = io.BytesIO()
    image.save(img_buffer, format=format)
    img_buffer.seek(0)
    return img_buffer


class TestConcurrentRequests:
    """并发请求测试"""
    
    @patch('api.app.qwen_api.get_model_manager')
    @patch('api.app.qwen_api.get_request_processor')
    def test_concurrent_text_to_image_requests(self, mock_get_processor, mock_get_manager, 
                                              mock_model_manager, mock_request_processor, client):
        """测试并发文生图请求"""
        mock_get_manager.return_value = mock_model_manager
        mock_get_processor.return_value = mock_request_processor
        
        # 准备请求数据
        request_data = {
            "prompt": "并发测试图像",
            "width": 512,
            "height": 512
        }
        
        # 并发请求函数
        def make_request():
            response = client.post("/text-to-image", json=request_data)
            return response.status_code, response.json()
        
        # 执行并发请求
        num_concurrent = 5
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            start_time = time.time()
            futures = [executor.submit(make_request) for _ in range(num_concurrent)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
            end_time = time.time()
        
        # 验证所有请求都成功
        for status_code, response_data in results:
            assert status_code == 200
            assert response_data["success"] is True
        
        # 验证并发处理时间合理（应该比串行快）
        total_time = end_time - start_time
        expected_serial_time = num_concurrent * 0.1  # 每个请求0.1秒
        assert total_time < expected_serial_time * 0.8  # 并发应该快至少20%
        
        # 验证模型被调用了正确的次数
        assert mock_model_manager.text_to_image.call_count == num_concurrent
    
    @patch('api.app.qwen_api.get_model_manager')
    @patch('api.app.qwen_api.get_request_processor')
    def test_concurrent_image_to_image_requests(self, mock_get_processor, mock_get_manager, 
                                               mock_model_manager, mock_request_processor, client):
        """测试并发图生图请求"""
        mock_get_manager.return_value = mock_model_manager
        mock_get_processor.return_value = mock_request_processor
        
        def make_image_request():
            test_image_buffer = create_test_image()
            files = {"image": ("test.png", test_image_buffer, "image/png")}
            data = {
                "prompt": "并发图生图测试",
                "strength": 0.8
            }
            response = client.post("/image-to-image", files=files, data=data)
            return response.status_code, response.json()
        
        # 执行并发请求
        num_concurrent = 3
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            start_time = time.time()
            futures = [executor.submit(make_image_request) for _ in range(num_concurrent)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
            end_time = time.time()
        
        # 验证所有请求都成功
        for status_code, response_data in results:
            assert status_code == 200
            assert response_data["success"] is True
        
        # 验证并发处理
        total_time = end_time - start_time
        expected_serial_time = num_concurrent * 0.15  # 每个请求0.15秒
        assert total_time < expected_serial_time * 0.8
        
        assert mock_model_manager.image_to_image.call_count == num_concurrent
    
    @patch('api.app.qwen_api.get_model_manager')
    @patch('api.app.qwen_api.get_request_processor')
    def test_mixed_concurrent_requests(self, mock_get_processor, mock_get_manager, 
                                      mock_model_manager, mock_request_processor, client):
        """测试混合类型的并发请求"""
        mock_get_manager.return_value = mock_model_manager
        mock_get_processor.return_value = mock_request_processor
        
        def make_text_request():
            request_data = {"prompt": "文生图并发测试", "width": 512, "height": 512}
            response = client.post("/text-to-image", json=request_data)
            return "text", response.status_code, response.json()
        
        def make_image_request():
            test_image_buffer = create_test_image()
            files = {"image": ("test.png", test_image_buffer, "image/png")}
            data = {"prompt": "图生图并发测试", "strength": 0.8}
            response = client.post("/image-to-image", files=files, data=data)
            return "image", response.status_code, response.json()
        
        def make_health_request():
            response = client.get("/health")
            return "health", response.status_code, response.json()
        
        # 混合请求
        requests = [make_text_request, make_image_request, make_health_request] * 2
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(req_func) for req_func in requests]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # 验证所有请求都成功
        text_count = image_count = health_count = 0
        for req_type, status_code, response_data in results:
            assert status_code == 200
            if req_type == "text":
                assert response_data["success"] is True
                text_count += 1
            elif req_type == "image":
                assert response_data["success"] is True
                image_count += 1
            elif req_type == "health":
                assert "status" in response_data
                health_count += 1
        
        assert text_count == 2
        assert image_count == 2
        assert health_count == 2
    
    @patch('api.app.qwen_api.get_model_manager')
    @patch('api.app.qwen_api.get_request_processor')
    def test_concurrent_request_limits(self, mock_get_processor, mock_get_manager, 
                                      mock_model_manager, mock_request_processor, client):
        """测试并发请求限制"""
        mock_get_manager.return_value = mock_model_manager
        mock_get_processor.return_value = mock_request_processor
        
        # 模拟较长的处理时间
        def slow_inference(*args, **kwargs):
            time.sleep(0.5)
            return Image.new('RGB', (512, 512), color='blue')
        
        mock_model_manager.text_to_image.side_effect = slow_inference
        
        request_data = {"prompt": "慢速推理测试", "width": 512, "height": 512}
        
        def make_request():
            start = time.time()
            response = client.post("/text-to-image", json=request_data)
            end = time.time()
            return response.status_code, end - start
        
        # 发送大量并发请求
        num_concurrent = 10
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [executor.submit(make_request) for _ in range(num_concurrent)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # 验证请求处理
        success_count = 0
        response_times = []
        
        for status_code, response_time in results:
            if status_code == 200:
                success_count += 1
                response_times.append(response_time)
            # 某些请求可能因为并发限制而失败，这是正常的
        
        # 至少应该有一些请求成功
        assert success_count > 0
        
        # 验证响应时间分布合理
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            assert avg_response_time >= 0.5  # 至少包含推理时间
c
lass TestPerformanceBenchmarks:
    """性能基准测试"""
    
    @patch('api.app.qwen_api.get_model_manager')
    @patch('api.app.qwen_api.get_request_processor')
    def test_text_to_image_performance_baseline(self, mock_get_processor, mock_get_manager, 
                                               mock_model_manager, mock_request_processor, client):
        """测试文生图性能基准"""
        mock_get_manager.return_value = mock_model_manager
        mock_get_processor.return_value = mock_request_processor
        
        request_data = {
            "prompt": "性能基准测试图像",
            "width": 512,
            "height": 512,
            "num_inference_steps": 20
        }
        
        # 预热请求
        client.post("/text-to-image", json=request_data)
        
        # 性能测试
        num_requests = 10
        response_times = []
        
        for _ in range(num_requests):
            start_time = time.time()
            response = client.post("/text-to-image", json=request_data)
            end_time = time.time()
            
            assert response.status_code == 200
            response_times.append(end_time - start_time)
        
        # 计算性能指标
        avg_time = sum(response_times) / len(response_times)
        min_time = min(response_times)
        max_time = max(response_times)
        
        # 验证性能指标在合理范围内
        assert avg_time < 1.0  # 平均响应时间应该小于1秒（包括网络开销）
        assert min_time > 0.05  # 最小时间应该大于50ms（包含推理时间）
        assert max_time < 2.0  # 最大时间不应该超过2秒
        
        # 验证响应时间的一致性（标准差不应该太大）
        import statistics
        std_dev = statistics.stdev(response_times)
        assert std_dev < avg_time * 0.5  # 标准差不应该超过平均值的50%
    
    @patch('api.app.qwen_api.get_model_manager')
    @patch('api.app.qwen_api.get_request_processor')
    def test_image_to_image_performance_baseline(self, mock_get_processor, mock_get_manager, 
                                                mock_model_manager, mock_request_processor, client):
        """测试图生图性能基准"""
        mock_get_manager.return_value = mock_model_manager
        mock_get_processor.return_value = mock_request_processor
        
        def make_request():
            test_image_buffer = create_test_image()
            files = {"image": ("test.png", test_image_buffer, "image/png")}
            data = {
                "prompt": "性能基准图生图测试",
                "strength": 0.8,
                "num_inference_steps": 20
            }
            return client.post("/image-to-image", files=files, data=data)
        
        # 预热
        make_request()
        
        # 性能测试
        num_requests = 8
        response_times = []
        
        for _ in range(num_requests):
            start_time = time.time()
            response = make_request()
            end_time = time.time()
            
            assert response.status_code == 200
            response_times.append(end_time - start_time)
        
        # 计算性能指标
        avg_time = sum(response_times) / len(response_times)
        min_time = min(response_times)
        max_time = max(response_times)
        
        # 图生图通常比文生图稍慢
        assert avg_time < 1.5
        assert min_time > 0.1
        assert max_time < 3.0
    
    @patch('api.app.qwen_api.get_model_manager')
    def test_health_check_performance(self, mock_get_manager, mock_model_manager, client):
        """测试健康检查端点性能"""
        mock_get_manager.return_value = mock_model_manager
        
        # 健康检查应该非常快
        num_requests = 50
        response_times = []
        
        for _ in range(num_requests):
            start_time = time.time()
            response = client.get("/health")
            end_time = time.time()
            
            assert response.status_code == 200
            response_times.append(end_time - start_time)
        
        avg_time = sum(response_times) / len(response_times)
        max_time = max(response_times)
        
        # 健康检查应该非常快
        assert avg_time < 0.1  # 平均小于100ms
        assert max_time < 0.5  # 最大不超过500ms
    
    @patch('api.app.qwen_api.get_model_manager')
    @patch('api.app.qwen_api.get_request_processor')
    def test_throughput_measurement(self, mock_get_processor, mock_get_manager, 
                                   mock_model_manager, mock_request_processor, client):
        """测试吞吐量"""
        mock_get_manager.return_value = mock_model_manager
        mock_get_processor.return_value = mock_request_processor
        
        request_data = {"prompt": "吞吐量测试", "width": 512, "height": 512}
        
        # 测试时间窗口
        test_duration = 2.0  # 2秒
        start_time = time.time()
        request_count = 0
        
        while time.time() - start_time < test_duration:
            response = client.post("/text-to-image", json=request_data)
            if response.status_code == 200:
                request_count += 1
        
        actual_duration = time.time() - start_time
        throughput = request_count / actual_duration
        
        # 验证吞吐量合理（考虑到模拟的推理时间）
        assert throughput > 5  # 每秒至少5个请求
        assert request_count > 0


class TestResourceManagement:
    """资源管理和内存清理测试"""
    
    @patch('api.app.qwen_api.get_model_manager')
    @patch('api.app.qwen_api.get_request_processor')
    def test_memory_usage_stability(self, mock_get_processor, mock_get_manager, 
                                   mock_model_manager, mock_request_processor, client):
        """测试内存使用稳定性"""
        mock_get_manager.return_value = mock_model_manager
        mock_get_processor.return_value = mock_request_processor
        
        # 获取初始内存使用
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        request_data = {"prompt": "内存测试图像", "width": 512, "height": 512}
        
        # 执行多个请求
        num_requests = 20
        for i in range(num_requests):
            response = client.post("/text-to-image", json=request_data)
            assert response.status_code == 200
            
            # 每5个请求检查一次内存
            if (i + 1) % 5 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_increase = current_memory - initial_memory
                
                # 内存增长应该在合理范围内
                assert memory_increase < 100  # 不应该增长超过100MB
        
        # 强制垃圾回收
        gc.collect()
        
        # 最终内存检查
        final_memory = process.memory_info().rss / 1024 / 1024
        final_increase = final_memory - initial_memory
        
        # 最终内存增长应该很小
        assert final_increase < 50  # 不应该增长超过50MB
    
    @patch('api.app.qwen_api.get_model_manager')
    @patch('api.app.qwen_api.get_request_processor')
    def test_concurrent_memory_management(self, mock_get_processor, mock_get_manager, 
                                         mock_model_manager, mock_request_processor, client):
        """测试并发请求的内存管理"""
        mock_get_manager.return_value = mock_model_manager
        mock_get_processor.return_value = mock_request_processor
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        def make_request():
            request_data = {"prompt": "并发内存测试", "width": 512, "height": 512}
            response = client.post("/text-to-image", json=request_data)
            return response.status_code == 200
        
        # 并发执行请求
        num_concurrent = 8
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [executor.submit(make_request) for _ in range(num_concurrent)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # 验证所有请求成功
        assert all(results)
        
        # 检查内存使用
        peak_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = peak_memory - initial_memory
        
        # 并发请求的内存增长应该在合理范围内
        assert memory_increase < 200  # 不应该增长超过200MB
        
        # 等待一段时间让资源清理
        time.sleep(0.5)
        gc.collect()
        
        final_memory = process.memory_info().rss / 1024 / 1024
        final_increase = final_memory - initial_memory
        
        # 资源应该被适当清理
        assert final_increase < memory_increase * 0.8  # 至少清理20%
    
    @patch('api.app.qwen_api.get_model_manager')
    @patch('api.app.qwen_api.get_request_processor')
    def test_large_request_handling(self, mock_get_processor, mock_get_manager, 
                                   mock_model_manager, mock_request_processor, client):
        """测试大请求的处理"""
        mock_get_manager.return_value = mock_model_manager
        mock_get_processor.return_value = mock_request_processor
        
        # 模拟大图像处理
        def mock_large_image_processing(*args, **kwargs):
            # 模拟处理大图像的时间和内存使用
            time.sleep(0.3)
            return Image.new('RGB', (1024, 1024), color='blue')
        
        mock_model_manager.text_to_image.side_effect = mock_large_image_processing
        
        # 大尺寸请求
        large_request_data = {
            "prompt": "高分辨率测试图像",
            "width": 1024,
            "height": 1024,
            "num_inference_steps": 30
        }
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        # 执行大请求
        response = client.post("/text-to-image", json=large_request_data)
        assert response.status_code == 200
        
        peak_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = peak_memory - initial_memory
        
        # 大请求可能使用更多内存，但应该在合理范围内
        assert memory_increase < 300  # 不应该超过300MB
        
        # 等待资源清理
        time.sleep(0.5)
        gc.collect()
        
        final_memory = process.memory_info().rss / 1024 / 1024
        final_increase = final_memory - initial_memory
        
        # 资源应该被清理
        assert final_increase < memory_increase * 0.7  # 至少清理30%
    
    @patch('api.app.qwen_api.get_model_manager')
    @patch('api.app.qwen_api.get_request_processor')
    def test_error_handling_resource_cleanup(self, mock_get_processor, mock_get_manager, 
                                            mock_model_manager, mock_request_processor, client):
        """测试错误情况下的资源清理"""
        mock_get_manager.return_value = mock_model_manager
        mock_get_processor.return_value = mock_request_processor
        
        # 模拟推理错误
        from services.exceptions import InferenceError
        mock_model_manager.text_to_image.side_effect = InferenceError("模拟推理错误")
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        request_data = {"prompt": "错误测试", "width": 512, "height": 512}
        
        # 执行多个失败的请求
        for _ in range(10):
            response = client.post("/text-to-image", json=request_data)
            assert response.status_code == 500  # 应该返回错误
        
        # 检查内存是否稳定（错误情况下不应该泄漏内存）
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        
        # 即使有错误，内存增长也应该很小
        assert memory_increase < 30  # 不应该增长超过30MB


class TestStressTest:
    """压力测试"""
    
    @patch('api.app.qwen_api.get_model_manager')
    @patch('api.app.qwen_api.get_request_processor')
    def test_sustained_load(self, mock_get_processor, mock_get_manager, 
                           mock_model_manager, mock_request_processor, client):
        """测试持续负载"""
        mock_get_manager.return_value = mock_model_manager
        mock_get_processor.return_value = mock_request_processor
        
        request_data = {"prompt": "持续负载测试", "width": 512, "height": 512}
        
        # 持续发送请求
        duration = 3.0  # 3秒持续测试
        start_time = time.time()
        success_count = 0
        error_count = 0
        
        while time.time() - start_time < duration:
            try:
                response = client.post("/text-to-image", json=request_data)
                if response.status_code == 200:
                    success_count += 1
                else:
                    error_count += 1
            except Exception:
                error_count += 1
            
            # 短暂休息避免过度压力
            time.sleep(0.01)
        
        total_requests = success_count + error_count
        success_rate = success_count / total_requests if total_requests > 0 else 0
        
        # 验证服务在持续负载下的表现
        assert total_requests > 0
        assert success_rate > 0.8  # 至少80%的成功率
        assert success_count > 10  # 至少处理了10个成功请求
    
    @patch('api.app.qwen_api.get_model_manager')
    @patch('api.app.qwen_api.get_request_processor')
    def test_burst_load(self, mock_get_processor, mock_get_manager, 
                       mock_model_manager, mock_request_processor, client):
        """测试突发负载"""
        mock_get_manager.return_value = mock_model_manager
        mock_get_processor.return_value = mock_request_processor
        
        request_data = {"prompt": "突发负载测试", "width": 512, "height": 512}
        
        def make_burst_request():
            try:
                response = client.post("/text-to-image", json=request_data)
                return response.status_code == 200
            except Exception:
                return False
        
        # 突发大量并发请求
        num_burst = 15
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_burst) as executor:
            start_time = time.time()
            futures = [executor.submit(make_burst_request) for _ in range(num_burst)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
            end_time = time.time()
        
        success_count = sum(results)
        success_rate = success_count / num_burst
        total_time = end_time - start_time
        
        # 验证突发负载处理
        assert success_count > 0  # 至少有一些请求成功
        assert success_rate > 0.3  # 至少30%的成功率（突发情况下可能较低）
        assert total_time < 10.0  # 总时间不应该过长