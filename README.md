# Qwen-Image API Service

基于 qwen-image 模型的 Python API 服务，提供文生图和图生图功能。

## 项目结构

```
.
├── api/                    # FastAPI 路由和端点
├── config/                 # 配置管理模块
├── models/                 # 数据模型和 Pydantic schemas
├── services/               # 业务逻辑和模型管理
├── tests/                  # 单元测试和集成测试
├── config.yaml            # 默认配置文件
├── requirements.txt       # Python 依赖
└── main.py               # 应用入口文件
```

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置

编辑 `config.yaml` 文件设置模型路径和服务参数。

## 运行服务

```bash
python main.py
```

## API 端点

- `POST /text-to-image` - 文生图
- `POST /image-to-image` - 图生图  
- `GET /health` - 健康检查
- `GET /info` - 服务信息