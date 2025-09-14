"""
Qwen Image API Service 负载测试脚本

使用 Locust 进行 API 负载测试

运行方法:
    pip install locust
    locust -f tests/load_test.py --host=http://localhost:8000
"""

import base64
import io
import json
import random
from locust import HttpUser, task, between
from PIL import Image


class QwenImageAPIUser(HttpUser):
    """Qwen Image API 用户行为模拟"""
    
    wait_time = between(1, 5)  # 请求间隔 1-5 秒
    
    def on_start(self):
        """用户开始时的初始化"""
        # 创建测试图像
        self.test_image = self._create_test_image()
        
        # 测试提示词列表
        self.test_prompts = [
            "一只可爱的小猫在花园里玩耍",
            "美丽的山水风景画",
            "现代城市夜景",
            "古典建筑风格的房屋",
            "抽象艺术作品",
            "卡通风格的动物",
            "科幻未来城市",
            "传统中国水墨画"
        ]
    
    def _create_test_image(self):
        """创建测试用的图像"""
        # 创建一个简单的测试图像
        img = Image.new('RGB', (512, 512), color='red')
        
        # 转换为字节
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        return img_bytes.getvalue()
    
    @task(3)
    def health_check(self):
        """健康检查 - 高频率任务"""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")
    
    @task(1)
    def get_info(self):
        """获取服务信息"""
        with self.client.get("/info", catch_response=True) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "service_name" in data:
                        response.success()
                    else:
                        response.failure("Invalid info response")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Info request failed: {response.status_code}")
    
    @task(2)
    def text_to_image(self):
        """文生图测试"""
        prompt = random.choice(self.test_prompts)
        
        payload = {
            "prompt": prompt,
            "width": random.choice([256, 512, 768]),
            "height": random.choice([256, 512, 768]),
            "num_inference_steps": random.choice([10, 20, 30]),
            "guidance_scale": random.uniform(5.0, 10.0)
        }
        
        with self.client.post(
            "/text-to-image",
            json=payload,
            timeout=300,  # 5分钟超时
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get("success") and "image" in data:
                        response.success()
                    else:
                        response.failure("Invalid text-to-image response")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 503:
                response.failure("Service unavailable")
            else:
                response.failure(f"Text-to-image failed: {response.status_code}")
    
    @task(1)
    def image_to_image(self):
        """图生图测试"""
        prompt = random.choice(self.test_prompts)
        
        files = {
            'image': ('test.png', self.test_image, 'image/png')
        }
        
        data = {
            'prompt': prompt,
            'strength': random.uniform(0.5, 1.0),
            'num_inference_steps': random.choice([10, 20, 30])
        }
        
        with self.client.post(
            "/image-to-image",
            files=files,
            data=data,
            timeout=300,  # 5分钟超时
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get("success") and "image" in data:
                        response.success()
                    else:
                        response.failure("Invalid image-to-image response")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 503:
                response.failure("Service unavailable")
            else:
                response.failure(f"Image-to-image failed: {response.status_code}")


class HighLoadUser(QwenImageAPIUser):
    """高负载用户 - 更频繁的请求"""
    
    wait_time = between(0.5, 2)  # 更短的等待时间
    
    @task(5)
    def health_check(self):
        """更频繁的健康检查"""
        super().health_check()
    
    @task(3)
    def text_to_image_fast(self):
        """快速文生图测试 - 使用较小的图像和较少的步数"""
        prompt = random.choice(self.test_prompts)
        
        payload = {
            "prompt": prompt,
            "width": 256,
            "height": 256,
            "num_inference_steps": 10,
            "guidance_scale": 7.5
        }
        
        with self.client.post(
            "/text-to-image",
            json=payload,
            timeout=120,  # 2分钟超时
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Fast text-to-image failed: {response.status_code}")


class StressTestUser(QwenImageAPIUser):
    """压力测试用户 - 极高频率请求"""
    
    wait_time = between(0.1, 0.5)  # 极短等待时间
    
    @task(10)
    def health_check_stress(self):
        """压力测试健康检查"""
        self.client.get("/health")
    
    @task(1)
    def info_stress(self):
        """压力测试信息获取"""
        self.client.get("/info")


# 自定义测试场景
class WebsiteUser(HttpUser):
    """网站用户行为模拟"""
    
    tasks = {QwenImageAPIUser: 3, HighLoadUser: 1}
    wait_time = between(5, 15)


if __name__ == "__main__":
    # 可以直接运行此脚本进行简单测试
    import requests
    import time
    
    base_url = "http://localhost:8000"
    
    print("开始简单负载测试...")
    
    # 测试健康检查
    start_time = time.time()
    for i in range(10):
        response = requests.get(f"{base_url}/health")
        print(f"Health check {i+1}: {response.status_code}")
    
    end_time = time.time()
    print(f"10次健康检查耗时: {end_time - start_time:.2f}秒")
    
    # 测试文生图
    print("\n测试文生图...")
    payload = {
        "prompt": "测试图像",
        "width": 256,
        "height": 256,
        "num_inference_steps": 10
    }
    
    start_time = time.time()
    response = requests.post(f"{base_url}/text-to-image", json=payload)
    end_time = time.time()
    
    print(f"文生图测试: {response.status_code}, 耗时: {end_time - start_time:.2f}秒")
    
    print("简单负载测试完成")