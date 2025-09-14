"""
Core interfaces and abstract classes for the qwen-image API service.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from PIL import Image


class ModelManagerInterface(ABC):
    """Abstract interface for model management."""
    
    @abstractmethod
    def __init__(self, model_path: str, config: Dict[str, Any]):
        """Initialize the model manager with path and configuration."""
        pass
    
    @abstractmethod
    def load_model(self) -> None:
        """Load the qwen-image model."""
        pass
    
    @abstractmethod
    def text_to_image(self, prompt: str, **kwargs) -> Image.Image:
        """Generate image from text prompt."""
        pass
    
    @abstractmethod
    def image_to_image(self, image: Image.Image, prompt: str, **kwargs) -> Image.Image:
        """Generate image from input image and text prompt."""
        pass
    
    @abstractmethod
    def is_model_loaded(self) -> bool:
        """Check if model is loaded and ready."""
        pass


class RequestProcessorInterface(ABC):
    """Abstract interface for request processing."""
    
    @abstractmethod
    def validate_text_request(self, request: Any) -> bool:
        """Validate text-to-image request."""
        pass
    
    @abstractmethod
    def validate_image_request(self, request: Any) -> bool:
        """Validate image-to-image request."""
        pass
    
    @abstractmethod
    def process_image_upload(self, file: Any) -> Image.Image:
        """Process uploaded image file."""
        pass
    
    @abstractmethod
    def format_response(self, image: Image.Image) -> Dict[str, Any]:
        """Format image response."""
        pass


class ConfigManagerInterface(ABC):
    """Abstract interface for configuration management."""
    
    @abstractmethod
    def load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from file."""
        pass
    
    @abstractmethod
    def get_model_config(self) -> Dict[str, Any]:
        """Get model configuration."""
        pass
    
    @abstractmethod
    def get_server_config(self) -> Dict[str, Any]:
        """Get server configuration."""
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """Validate configuration parameters."""
        pass