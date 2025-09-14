"""
模型管理器异常类定义
"""


class ModelManagerError(Exception):
    """模型管理器基础异常类"""
    pass


class ModelLoadError(ModelManagerError):
    """模型加载异常"""
    def __init__(self, message: str, model_path: str = None):
        super().__init__(message)
        self.model_path = model_path


class ModelNotLoadedError(ModelManagerError):
    """模型未加载异常"""
    def __init__(self, message: str = "Model not loaded. Call load_model() first."):
        super().__init__(message)


class InferenceError(ModelManagerError):
    """推理异常"""
    def __init__(self, message: str, inference_type: str = None):
        super().__init__(message)
        self.inference_type = inference_type


class ResourceError(ModelManagerError):
    """资源管理异常"""
    def __init__(self, message: str, resource_type: str = None):
        super().__init__(message)
        self.resource_type = resource_type


class ValidationError(ModelManagerError):
    """参数验证异常"""
    def __init__(self, message: str, parameter: str = None):
        super().__init__(message)
        self.parameter = parameter


class DeviceError(ModelManagerError):
    """设备相关异常"""
    def __init__(self, message: str, device: str = None):
        super().__init__(message)
        self.device = device


class MemoryError(ResourceError):
    """内存不足异常"""
    def __init__(self, message: str = "Insufficient memory for model operation"):
        super().__init__(message, "memory")


class TimeoutError(ModelManagerError):
    """超时异常"""
    def __init__(self, message: str, timeout_seconds: int = None):
        super().__init__(message)
        self.timeout_seconds = timeout_seconds