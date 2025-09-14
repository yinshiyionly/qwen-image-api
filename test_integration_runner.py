#!/usr/bin/env python3
"""
集成测试运行器

验证集成测试的实现是否正确。
"""

import sys
import importlib.util
from pathlib import Path

def validate_test_files():
    """验证测试文件的语法和导入"""
    test_files = [
        "tests/test_integration_api.py",
        "tests/test_performance_concurrent.py"
    ]
    
    for test_file in test_files:
        print(f"验证 {test_file}...")
        
        # 检查文件是否存在
        if not Path(test_file).exists():
            print(f"❌ 文件不存在: {test_file}")
            return False
        
        # 尝试编译文件
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                source = f.read()
            
            compile(source, test_file, 'exec')
            print(f"✅ 语法检查通过: {test_file}")
            
        except SyntaxError as e:
            print(f"❌ 语法错误 {test_file}: {e}")
            return False
        except Exception as e:
            print(f"❌ 编译错误 {test_file}: {e}")
            return False
    
    return True

def check_test_structure():
    """检查测试结构"""
    print("\n检查测试结构...")
    
    # 检查集成测试文件
    integration_file = "tests/test_integration_api.py"
    with open(integration_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    required_classes = [
        "TestTextToImageIntegration",
        "TestImageToImageIntegration", 
        "TestHealthCheckIntegration",
        "TestServiceInfoIntegration",
        "TestErrorScenarios",
        "TestResponseHeaders"
    ]
    
    for class_name in required_classes:
        if f"class {class_name}" in content:
            print(f"✅ 找到测试类: {class_name}")
        else:
            print(f"❌ 缺少测试类: {class_name}")
            return False
    
    # 检查性能测试文件
    performance_file = "tests/test_performance_concurrent.py"
    with open(performance_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    required_perf_classes = [
        "TestConcurrentRequests",
        "TestPerformanceBenchmarks",
        "TestResourceManagement",
        "TestStressTest"
    ]
    
    for class_name in required_perf_classes:
        if f"class {class_name}" in content:
            print(f"✅ 找到性能测试类: {class_name}")
        else:
            print(f"❌ 缺少性能测试类: {class_name}")
            return False
    
    return True

def check_test_coverage():
    """检查测试覆盖范围"""
    print("\n检查测试覆盖范围...")
    
    integration_file = "tests/test_integration_api.py"
    with open(integration_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否覆盖了主要的测试场景
    required_scenarios = [
        "test_text_to_image_complete_flow",
        "test_text_to_image_model_not_loaded_error",
        "test_text_to_image_validation_error",
        "test_image_to_image_complete_flow",
        "test_image_to_image_invalid_file_format",
        "test_health_check_healthy_state",
        "test_health_check_degraded_state",
        "test_service_info_complete",
        "test_invalid_endpoint",
        "test_malformed_json_request"
    ]
    
    missing_scenarios = []
    for scenario in required_scenarios:
        if scenario in content:
            print(f"✅ 覆盖场景: {scenario}")
        else:
            missing_scenarios.append(scenario)
    
    if missing_scenarios:
        print(f"❌ 缺少测试场景: {missing_scenarios}")
        return False
    
    # 检查性能测试场景
    performance_file = "tests/test_performance_concurrent.py"
    with open(performance_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    required_perf_scenarios = [
        "test_concurrent_text_to_image_requests",
        "test_concurrent_image_to_image_requests",
        "test_mixed_concurrent_requests",
        "test_text_to_image_performance_baseline",
        "test_memory_usage_stability",
        "test_sustained_load"
    ]
    
    for scenario in required_perf_scenarios:
        if scenario in content:
            print(f"✅ 覆盖性能场景: {scenario}")
        else:
            missing_scenarios.append(scenario)
    
    return len(missing_scenarios) == 0

def main():
    """主函数"""
    print("🧪 集成测试验证开始...")
    
    # 验证测试文件
    if not validate_test_files():
        print("\n❌ 测试文件验证失败")
        return 1
    
    # 检查测试结构
    if not check_test_structure():
        print("\n❌ 测试结构检查失败")
        return 1
    
    # 检查测试覆盖范围
    if not check_test_coverage():
        print("\n❌ 测试覆盖范围检查失败")
        return 1
    
    print("\n✅ 集成测试验证通过!")
    print("\n📋 测试总结:")
    print("- ✅ API 端点集成测试已创建")
    print("- ✅ 文生图端点完整流程测试")
    print("- ✅ 图生图端点完整流程测试")
    print("- ✅ 错误场景和边界条件测试")
    print("- ✅ 并发请求处理测试")
    print("- ✅ 性能基准测试")
    print("- ✅ 资源管理和内存清理测试")
    
    print("\n🚀 可以使用以下命令运行测试:")
    print("pytest tests/test_integration_api.py -v")
    print("pytest tests/test_performance_concurrent.py -v")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())