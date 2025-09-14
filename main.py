"""
Main entry point for the qwen-image API service.
"""

import logging
import sys
import argparse
from pathlib import Path

import uvicorn

from config.manager import init_config
from api import app

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="Qwen Image API Service")
    
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="配置文件路径 (默认使用内置配置)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="服务器主机地址 (覆盖配置文件)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="服务器端口 (覆盖配置文件)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="启用自动重载 (开发模式)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="日志级别"
    )
    
    return parser.parse_args()


def setup_logging(log_level: str, log_file: str = None):
    """设置日志配置"""
    # 设置根日志级别
    logging.getLogger().setLevel(getattr(logging, log_level))
    
    # 如果指定了日志文件，添加文件处理器
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        
        logging.getLogger().addHandler(file_handler)
        logger.info(f"Log file configured: {log_file}")


def main():
    """主函数"""
    args = parse_args()
    
    try:
        # 初始化配置
        logger.info("Initializing configuration...")
        config = init_config(args.config)
        
        # 设置日志
        setup_logging(
            log_level=args.log_level or config.log.level,
            log_file=config.log.file_path
        )
        
        # 获取服务器配置
        server_config = config.server
        host = args.host or server_config.host
        port = args.port or server_config.port
        
        logger.info(f"Starting server on {host}:{port}")
        logger.info(f"Model path: {config.model.model_path or 'Not configured'}")
        logger.info(f"Device: {config.model.device}")
        
        # 启动服务器
        uvicorn.run(
            app,
            host=host,
            port=port,
            reload=args.reload,
            log_level=args.log_level.lower(),
            access_log=True
        )
        
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    except Exception as e:
        logger.error(f"Failed to start service: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()