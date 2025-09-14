# Qwen-Image API Service

基于 qwen-image 模型的 Python API 服务，提供文生图（text-to-image）和图生图（image-to-image）功能。

## 目录

- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [部署方式](#部署方式)
  - [Docker 部署](#docker-部署)
  - [Docker Compose 部署](#docker-compose-部署)
  - [生产环境部署](#生产环境部署)
- [配置说明](#配置说明)
- [API 文档](#api-文档)
- [监控和日志](#监控和日志)
- [故障排除](#故障排除)
- [性能优化](#性能优化)

## 项目结构

```
.
├── api/                    # FastAPI 路由和端点
│   ├── __init__.py
│   ├── app.py             # FastAPI 应用实例
│   ├── middleware.py      # 中间件
│   └── routes.py          # API 路由定义
├── config/                 # 配置管理模块
│   ├── __init__.py
│   ├── manager.py         # 配置管理器
│   └── models.py          # 配置数据模型
├── models/                 # 数据模型和 Pydantic schemas
│   ├── __init__.py
│   ├── requests.py        # 请求模型
│   └── responses.py       # 响应模型
├── services/               # 业务逻辑和模型管理
│   ├── __init__.py
│   ├── error_handler.py   # 错误处理
│   ├── exceptions.py      # 自定义异常
│   ├── interfaces.py      # 接口定义
│   ├── logging.py         # 日志服务
│   ├── model_manager.py   # 模型管理器
│   └── request_processor.py # 请求处理器
├── tests/                  # 单元测试和集成测试
├── nginx/                  # Nginx 配置文件
├── redis/                  # Redis 配置文件
├── monitoring/             # 监控配置
├── scripts/                # 部署和管理脚本
├── config.yaml            # 默认配置文件
├── config.prod.yaml       # 生产环境配置
├── requirements.txt       # Python 依赖
├── Dockerfile             # Docker 镜像构建文件
├── docker-compose.yml     # 开发环境 Docker Compose
├── docker-compose.prod.yml # 生产环境 Docker Compose
└── main.py               # 应用入口文件
```

## 快速开始

### 本地开发

1. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

2. **配置模型路径**
   ```bash
   # 编辑 config.yaml，设置模型路径
   model:
     model_path: "/path/to/your/qwen-image-model"
   ```

3. **启动服务**
   ```bash
   python main.py
   ```

4. **访问 API 文档**
   ```
   http://localhost:8000/docs
   ```

### 使用 Docker

1. **构建镜像**
   ```bash
   docker build -t qwen-image-api .
   ```

2. **运行容器**
   ```bash
   docker run -p 8000:8000 \
     -v /path/to/models:/app/models:ro \
     -v ./config.yaml:/app/config.yaml:ro \
     qwen-image-api
   ```

## 部署方式

### Docker 部署

#### 基础部署

```bash
# 1. 构建镜像
docker build -t qwen-image-api .

# 2. 运行容器
docker run -d \
  --name qwen-image-api \
  -p 8000:8000 \
  -v /path/to/models:/app/models:ro \
  -v ./logs:/app/logs \
  -e QWEN_MODEL_DEVICE=cuda \
  qwen-image-api
```

#### GPU 支持

```bash
# 使用 NVIDIA Docker 运行时
docker run -d \
  --name qwen-image-api \
  --gpus all \
  -p 8000:8000 \
  -v /path/to/models:/app/models:ro \
  -v ./logs:/app/logs \
  -e QWEN_MODEL_DEVICE=cuda \
  qwen-image-api
```

### Docker Compose 部署

#### 开发环境

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f qwen-image-api

# 停止服务
docker-compose down
```

#### 生产环境

```bash
# 使用生产配置启动
docker-compose -f docker-compose.prod.yml up -d

# 查看服务状态
docker-compose -f docker-compose.prod.yml ps

# 查看资源使用情况
docker stats
```

### 生产环境部署

#### 1. 准备环境

```bash
# 创建必要的目录
mkdir -p /opt/qwen-image-api/{logs,models,tmp}
mkdir -p /opt/qwen-image-api/nginx/ssl

# 设置权限
chown -R 1000:1000 /opt/qwen-image-api/logs
chown -R 1000:1000 /opt/qwen-image-api/tmp
```

#### 2. 配置 SSL 证书

```bash
# 将 SSL 证书放置到指定目录
cp your-cert.pem /opt/qwen-image-api/nginx/ssl/cert.pem
cp your-key.pem /opt/qwen-image-api/nginx/ssl/key.pem
```

#### 3. 配置环境变量

```bash
# 创建 .env 文件
cat > .env << EOF
# 模型配置
QWEN_MODEL_DEVICE=cuda
QWEN_MODEL_TORCH_DTYPE=float16
QWEN_MODEL_PATH=/app/models/qwen-image

# 安全配置
QWEN_SECURITY_API_KEY=your-secret-api-key
QWEN_SECURITY_RATE_LIMIT_PER_MINUTE=120

# 缓存配置
QWEN_CACHE_ENABLED=true
QWEN_CACHE_TYPE=redis

# 监控配置
QWEN_MONITORING_ENABLED=true
EOF
```

#### 4. 启动生产服务

```bash
# 启动服务
docker-compose -f docker-compose.prod.yml up -d

# 验证服务状态
curl -f http://localhost/health
```

## 配置说明

### 环境变量配置

所有配置项都可以通过环境变量覆盖，格式为 `QWEN_<SECTION>_<KEY>`：

```bash
# 模型配置
QWEN_MODEL_DEVICE=cuda
QWEN_MODEL_TORCH_DTYPE=float16
QWEN_MODEL_MAX_MEMORY=8GB

# 服务器配置
QWEN_SERVER_HOST=0.0.0.0
QWEN_SERVER_PORT=8000
QWEN_SERVER_MAX_CONCURRENT_REQUESTS=8

# 安全配置
QWEN_SECURITY_ENABLE_RATE_LIMIT=true
QWEN_SECURITY_API_KEY=your-api-key
```

### 配置文件

- `config.yaml` - 开发环境配置
- `config.prod.yaml` - 生产环境配置

详细配置选项请参考配置文件中的注释。

## API 文档

### 端点列表

| 端点 | 方法 | 描述 |
|------|------|------|
| `/text-to-image` | POST | 文生图 |
| `/image-to-image` | POST | 图生图 |
| `/health` | GET | 健康检查 |
| `/info` | GET | 服务信息 |
| `/metrics` | GET | 监控指标 |

### 使用示例

#### 文生图

```bash
curl -X POST "http://localhost:8000/text-to-image" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "一只可爱的小猫在花园里玩耍",
    "width": 512,
    "height": 512,
    "num_inference_steps": 20
  }'
```

#### 图生图

```bash
curl -X POST "http://localhost:8000/image-to-image" \
  -F "image=@input.jpg" \
  -F "prompt=将这张图片转换为油画风格" \
  -F "strength=0.8"
```

### API 认证

如果配置了 API 密钥，需要在请求头中包含：

```bash
curl -H "X-API-Key: your-api-key" \
  -X POST "http://localhost:8000/text-to-image" \
  ...
```

## 监控和日志

### 日志管理

```bash
# 查看实时日志
docker-compose logs -f qwen-image-api

# 查看错误日志
docker-compose logs qwen-image-api | grep ERROR

# 日志轮转配置在 docker-compose.prod.yml 中
```

### 监控指标

访问 Grafana 仪表板：
```
http://localhost:3000
用户名: admin
密码: admin123
```

### 健康检查

```bash
# 检查服务健康状态
curl http://localhost:8000/health

# 检查详细信息
curl http://localhost:8000/info
```

## 故障排除

### 常见问题

#### 1. 模型加载失败

**症状**: 服务启动时报错 "Model not found"

**解决方案**:
```bash
# 检查模型路径
ls -la /path/to/models/

# 检查配置
docker exec qwen-image-api cat /app/config.yaml

# 查看详细错误
docker logs qwen-image-api
```

#### 2. GPU 内存不足

**症状**: CUDA out of memory 错误

**解决方案**:
```bash
# 调整模型配置
export QWEN_MODEL_MAX_MEMORY=4GB
export QWEN_MODEL_TORCH_DTYPE=float16

# 或修改配置文件
model:
  max_memory: "4GB"
  torch_dtype: "float16"
```

#### 3. 请求超时

**症状**: 请求处理时间过长

**解决方案**:
```bash
# 增加超时时间
export QWEN_SERVER_REQUEST_TIMEOUT=600

# 调整 Nginx 超时
# 编辑 nginx/nginx.conf
proxy_read_timeout 900s;
```

#### 4. 文件上传失败

**症状**: 413 Request Entity Too Large

**解决方案**:
```bash
# 调整文件大小限制
export QWEN_SERVER_MAX_FILE_SIZE=20971520  # 20MB

# 调整 Nginx 限制
client_max_body_size 25M;
```

### 调试模式

```bash
# 启用调试模式
export QWEN_DEVELOPMENT_DEBUG=true
export QWEN_LOG_LEVEL=DEBUG

# 重启服务
docker-compose restart qwen-image-api
```

### 性能分析

```bash
# 查看资源使用情况
docker stats qwen-image-api

# 查看进程信息
docker exec qwen-image-api ps aux

# 查看内存使用
docker exec qwen-image-api free -h
```

## 性能优化

### 硬件要求

**最低配置**:
- CPU: 4 核
- 内存: 8GB
- 存储: 50GB

**推荐配置**:
- CPU: 8 核以上
- 内存: 16GB 以上
- GPU: NVIDIA RTX 3080 或更高
- 存储: SSD 100GB 以上

### 优化建议

#### 1. 模型优化

```yaml
model:
  torch_dtype: "float16"  # 使用半精度
  enable_optimization: true
  max_memory: "6GB"
```

#### 2. 并发优化

```yaml
server:
  max_concurrent_requests: 4  # 根据 GPU 内存调整
  workers: 2  # 多进程部署
```

#### 3. 缓存优化

```yaml
cache:
  enabled: true
  type: "redis"
  ttl: 7200  # 2小时缓存
```

#### 4. 网络优化

```bash
# 启用 HTTP/2
# 在 nginx.conf 中
listen 443 ssl http2;

# 启用 Gzip 压缩
gzip on;
gzip_types application/json;
```

### 负载测试

```bash
# 安装测试工具
pip install locust

# 运行负载测试
locust -f tests/load_test.py --host=http://localhost:8000
```

## 安全注意事项

1. **API 密钥**: 在生产环境中务必设置 API 密钥
2. **HTTPS**: 使用 SSL/TLS 加密传输
3. **速率限制**: 配置适当的速率限制
4. **文件验证**: 启用文件类型和大小验证
5. **网络隔离**: 使用防火墙限制访问

## 许可证

本项目采用 MIT 许可证。详见 LICENSE 文件。

## 贡献

欢迎提交 Issue 和 Pull Request。

## 支持

如有问题，请提交 Issue 或联系维护团队。