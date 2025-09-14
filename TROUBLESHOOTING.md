# 故障排除指南

本文档提供了 Qwen Image API Service 常见问题的解决方案。

## 目录

- [服务启动问题](#服务启动问题)
- [模型加载问题](#模型加载问题)
- [性能问题](#性能问题)
- [网络和连接问题](#网络和连接问题)
- [资源使用问题](#资源使用问题)
- [Docker 相关问题](#docker-相关问题)
- [配置问题](#配置问题)
- [日志和监控](#日志和监控)

## 服务启动问题

### 问题：服务无法启动

**症状**：
```
docker-compose up 失败
容器启动后立即退出
```

**诊断步骤**：
```bash
# 查看容器日志
docker-compose logs qwen-image-api

# 查看容器状态
docker-compose ps

# 检查配置文件
docker-compose config
```

**常见原因和解决方案**：

1. **端口被占用**
   ```bash
   # 检查端口使用情况
   netstat -tlnp | grep 8000
   
   # 解决方案：修改端口或停止占用进程
   export QWEN_SERVER_PORT=8001
   ```

2. **配置文件错误**
   ```bash
   # 验证 YAML 语法
   python -c "import yaml; yaml.safe_load(open('config.yaml'))"
   
   # 检查配置文件权限
   ls -la config*.yaml
   ```

3. **依赖缺失**
   ```bash
   # 重新构建镜像
   docker-compose build --no-cache
   ```

### 问题：健康检查失败

**症状**：
```
Health check failed
容器状态显示 unhealthy
```

**解决方案**：
```bash
# 手动测试健康检查
curl -f http://localhost:8000/health

# 检查服务是否真正启动
docker exec qwen-image-api ps aux

# 增加健康检查超时时间
# 在 docker-compose.yml 中修改
healthcheck:
  start_period: 120s
  timeout: 30s
```

## 模型加载问题

### 问题：模型文件未找到

**症状**：
```
Model not found at path: /app/models/qwen-image
FileNotFoundError: Model files not accessible
```

**解决方案**：
```bash
# 检查模型文件路径
ls -la /path/to/your/models/

# 检查 Docker 卷挂载
docker inspect qwen-image-api | grep -A 10 "Mounts"

# 修正模型路径配置
export QWEN_MODEL_PATH=/correct/path/to/model
```

### 问题：模型加载超时

**症状**：
```
Model loading timeout after 300 seconds
CUDA initialization failed
```

**解决方案**：
```bash
# 增加加载超时时间
export QWEN_MODEL_LOAD_TIMEOUT=600

# 检查 GPU 可用性
nvidia-smi

# 使用 CPU 模式
export QWEN_MODEL_DEVICE=cpu
```

### 问题：CUDA 内存不足

**症状**：
```
CUDA out of memory
RuntimeError: CUDA error: out of memory
```

**解决方案**：
```bash
# 使用半精度模型
export QWEN_MODEL_TORCH_DTYPE=float16

# 限制最大内存使用
export QWEN_MODEL_MAX_MEMORY=4GB

# 减少并发请求数
export QWEN_SERVER_MAX_CONCURRENT_REQUESTS=2

# 清理 GPU 内存
docker restart qwen-image-api
```

## 性能问题

### 问题：推理速度慢

**症状**：
- 图像生成时间过长
- 请求超时
- 响应时间超过预期

**优化方案**：

1. **模型优化**
   ```yaml
   model:
     torch_dtype: "float16"
     enable_optimization: true
     device: "cuda"
   ```

2. **参数调整**
   ```yaml
   generation:
     default_steps: 15  # 减少推理步数
     default_width: 512
     default_height: 512
   ```

3. **硬件优化**
   ```bash
   # 使用更快的 GPU
   # 增加系统内存
   # 使用 SSD 存储
   ```

### 问题：并发处理能力不足

**症状**：
- 503 Service Unavailable
- 请求排队时间长
- 系统负载过高

**解决方案**：
```bash
# 增加并发请求数（根据硬件调整）
export QWEN_SERVER_MAX_CONCURRENT_REQUESTS=8

# 启用多进程
export QWEN_SERVER_WORKERS=2

# 使用负载均衡
# 部署多个实例
```

## 网络和连接问题

### 问题：API 请求失败

**症状**：
```
Connection refused
Timeout errors
502 Bad Gateway (使用 Nginx 时)
```

**诊断步骤**：
```bash
# 检查服务是否运行
curl http://localhost:8000/health

# 检查网络连接
telnet localhost 8000

# 检查防火墙设置
sudo ufw status
```

**解决方案**：
```bash
# 检查端口绑定
docker port qwen-image-api

# 修复网络配置
docker-compose down
docker-compose up -d

# 检查 Nginx 配置（如果使用）
nginx -t
```

### 问题：文件上传失败

**症状**：
```
413 Request Entity Too Large
400 Bad Request
File upload timeout
```

**解决方案**：
```bash
# 增加文件大小限制
export QWEN_SERVER_MAX_FILE_SIZE=20971520  # 20MB

# 修改 Nginx 配置
client_max_body_size 25M;

# 增加超时时间
proxy_read_timeout 600s;
```

## 资源使用问题

### 问题：内存使用过高

**症状**：
- 系统内存不足
- OOM (Out of Memory) 错误
- 容器被杀死

**解决方案**：
```bash
# 限制容器内存使用
docker run --memory=4g qwen-image-api

# 在 docker-compose.yml 中设置
deploy:
  resources:
    limits:
      memory: 4G

# 启用内存清理
export QWEN_MODEL_ENABLE_OPTIMIZATION=true
```

### 问题：磁盘空间不足

**症状**：
```
No space left on device
Disk full errors
```

**解决方案**：
```bash
# 清理 Docker 资源
docker system prune -a

# 清理日志文件
find logs -name "*.log" -mtime +7 -delete

# 清理临时文件
rm -rf tmp/*

# 设置日志轮转
# 在 docker-compose.yml 中
logging:
  options:
    max-size: "100m"
    max-file: "5"
```

## Docker 相关问题

### 问题：镜像构建失败

**症状**：
```
Docker build fails
Package installation errors
Permission denied
```

**解决方案**：
```bash
# 清理构建缓存
docker builder prune

# 使用 --no-cache 重新构建
docker build --no-cache -t qwen-image-api .

# 检查 Dockerfile 语法
docker build --dry-run .
```

### 问题：容器权限问题

**症状**：
```
Permission denied
Cannot write to mounted volume
```

**解决方案**：
```bash
# 检查文件权限
ls -la logs/ tmp/

# 修复权限
sudo chown -R 1000:1000 logs/ tmp/

# 在 Dockerfile 中设置正确的用户
USER qwen
```

### 问题：网络连接问题

**症状**：
- 容器间无法通信
- 外部网络访问失败

**解决方案**：
```bash
# 检查 Docker 网络
docker network ls
docker network inspect qwen-network

# 重新创建网络
docker-compose down
docker-compose up -d
```

## 配置问题

### 问题：环境变量不生效

**症状**：
- 配置更改未生效
- 使用默认值而非设置值

**解决方案**：
```bash
# 检查环境变量
docker exec qwen-image-api env | grep QWEN

# 重启容器使配置生效
docker-compose restart qwen-image-api

# 验证配置加载
curl http://localhost:8000/info
```

### 问题：配置文件格式错误

**症状**：
```
YAML parsing error
Configuration validation failed
```

**解决方案**：
```bash
# 验证 YAML 语法
python -c "import yaml; print(yaml.safe_load(open('config.yaml')))"

# 使用在线 YAML 验证器
# 检查缩进和特殊字符
```

## 日志和监控

### 查看详细日志

```bash
# 查看实时日志
docker-compose logs -f qwen-image-api

# 查看特定时间段的日志
docker-compose logs --since="2024-01-01T00:00:00" qwen-image-api

# 查看错误日志
docker-compose logs qwen-image-api | grep ERROR

# 查看系统日志
journalctl -u docker
```

### 性能监控

```bash
# 查看资源使用情况
docker stats qwen-image-api

# 查看系统负载
top
htop

# 查看 GPU 使用情况
nvidia-smi -l 1

# 查看网络连接
netstat -tlnp
```

### 调试模式

```bash
# 启用调试模式
export QWEN_DEVELOPMENT_DEBUG=true
export QWEN_LOG_LEVEL=DEBUG

# 重启服务
docker-compose restart qwen-image-api

# 查看详细日志
docker-compose logs -f qwen-image-api
```

## 常用诊断命令

### 系统状态检查

```bash
# 检查服务状态
./scripts/manage.sh status

# 健康检查
./scripts/manage.sh health

# 查看资源使用
./scripts/manage.sh monitor
```

### 快速修复脚本

```bash
#!/bin/bash
# 快速诊断和修复脚本

echo "=== Qwen Image API 快速诊断 ==="

# 检查 Docker 服务
if ! systemctl is-active --quiet docker; then
    echo "启动 Docker 服务..."
    sudo systemctl start docker
fi

# 检查容器状态
if ! docker-compose ps | grep -q "Up"; then
    echo "重启服务..."
    docker-compose down
    docker-compose up -d
fi

# 等待服务启动
sleep 30

# 健康检查
if curl -f -s http://localhost:8000/health > /dev/null; then
    echo "✅ 服务正常运行"
else
    echo "❌ 服务异常，查看日志："
    docker-compose logs --tail=50 qwen-image-api
fi
```

## 获取帮助

如果以上解决方案都无法解决问题，请：

1. **收集诊断信息**：
   ```bash
   # 生成诊断报告
   ./scripts/manage.sh status > diagnostic_report.txt
   docker-compose logs qwen-image-api >> diagnostic_report.txt
   ```

2. **提交 Issue**：
   - 包含完整的错误信息
   - 提供系统环境信息
   - 附上配置文件（去除敏感信息）

3. **联系支持团队**：
   - 提供诊断报告
   - 描述问题复现步骤
   - 说明已尝试的解决方案