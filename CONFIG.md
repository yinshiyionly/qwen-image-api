# 配置文档

本文档详细说明了 Qwen Image API Service 的配置选项和使用方法。

## 配置文件

### 主配置文件

- `config.yaml` - 主配置文件，包含所有默认配置
- `.env` - 环境变量配置文件（可选）

### 配置优先级

配置的优先级从高到低：

1. 命令行参数
2. 环境变量
3. 配置文件 (config.yaml)
4. 默认值

## 配置章节

### 模型配置 (model)

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `model_path` | string | "" | 模型文件路径，为空时使用模拟实现 |
| `device` | string | "cpu" | 推理设备：cpu, cuda, cuda:0 等 |
| `torch_dtype` | string | "float32" | 数据类型：float16, float32, bfloat16 |
| `max_memory` | string | null | 最大内存限制，如 "8GB", "4096MB" |
| `load_timeout` | int | 300 | 模型加载超时时间（秒） |
| `enable_optimization` | bool | false | 是否启用模型优化 |

### 服务器配置 (server)

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `host` | string | "0.0.0.0" | 监听地址 |
| `port` | int | 8000 | 监听端口 |
| `max_file_size` | int | 10485760 | 最大文件上传大小（字节） |
| `max_concurrent_requests` | int | 4 | 最大并发请求数 |
| `request_timeout` | int | 300 | 请求超时时间（秒） |
| `enable_cors` | bool | true | 是否启用 CORS |
| `cors_origins` | list | ["*"] | 允许的 CORS 源 |
| `workers` | int | 1 | 工作进程数 |

### 图像生成配置 (generation)

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `default_width` | int | 512 | 默认图像宽度 |
| `default_height` | int | 512 | 默认图像高度 |
| `min_size` | int | 256 | 最小图像尺寸 |
| `max_size` | int | 2048 | 最大图像尺寸 |
| `default_steps` | int | 20 | 默认推理步数 |
| `min_steps` | int | 1 | 最小推理步数 |
| `max_steps` | int | 100 | 最大推理步数 |
| `default_guidance_scale` | float | 7.5 | 默认引导强度 |
| `supported_formats` | list | ["jpg", "jpeg", "png", "webp"] | 支持的图像格式 |
| `output_format` | string | "png" | 输出格式 |
| `output_quality` | int | 95 | 输出质量（JPEG） |

### 安全配置 (security)

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_rate_limit` | bool | true | 是否启用速率限制 |
| `rate_limit_per_minute` | int | 60 | 每分钟最大请求数 |
| `validate_file_type` | bool | true | 是否验证文件类型 |
| `scan_malicious_content` | bool | false | 是否扫描恶意内容 |
| `api_key` | string | null | API 密钥 |

### 日志配置 (log)

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `level` | string | "INFO" | 日志级别 |
| `format` | string | "%(asctime)s - %(name)s - %(levelname)s - %(message)s" | 日志格式 |
| `file_path` | string | null | 日志文件路径 |
| `max_file_size` | int | 10485760 | 日志文件最大大小 |
| `backup_count` | int | 5 | 保留的日志文件数量 |
| `log_requests` | bool | true | 是否记录请求详情 |
| `log_responses` | bool | false | 是否记录响应详情 |

## 环境变量

环境变量使用 `QWEN_<SECTION>_<KEY>` 的命名格式，例如：

```bash
# 设置模型路径
export QWEN_MODEL_MODEL_PATH="/path/to/model"

# 设置推理设备
export QWEN_MODEL_DEVICE="cuda"

# 设置服务器端口
export QWEN_SERVER_PORT=8080

# 设置日志级别
export QWEN_LOG_LEVEL="DEBUG"
```

## 使用示例

### 基本使用

```bash
# 使用默认配置启动
python main.py

# 指定配置文件
python main.py --config /path/to/config.yaml

# 覆盖配置参数
python main.py --host 127.0.0.1 --port 8080 --log-level DEBUG
```

### 生产环境配置

```yaml
model:
  model_path: "/opt/models/qwen-image"
  device: "cuda"
  torch_dtype: "float16"
  max_memory: "8GB"

server:
  host: "0.0.0.0"
  port: 8000
  max_concurrent_requests: 8
  request_timeout: 600

security:
  api_key: "your-production-api-key"
  enable_rate_limit: true
  rate_limit_per_minute: 100

log:
  level: "WARNING"
  file_path: "/var/log/qwen-api/app.log"
  log_requests: true
  log_responses: false

monitoring:
  enabled: true
  detailed_metrics: true
```

### 开发环境配置

```yaml
model:
  model_path: ""  # 使用模拟实现
  device: "cpu"

server:
  port: 8000
  max_concurrent_requests: 2

security:
  enable_rate_limit: false

log:
  level: "DEBUG"
  log_requests: true
  log_responses: true

development:
  debug: true
  auto_reload: true
  enable_docs: true
```

## 配置验证

服务启动时会自动验证配置的有效性：

- 检查必需的配置项
- 验证数值范围
- 检查文件路径的存在性
- 验证设备可用性

如果配置无效，服务会输出详细的错误信息并拒绝启动。

## 故障排除

### 常见问题

1. **模型加载失败**
   - 检查 `model_path` 是否正确
   - 确认模型文件完整性
   - 检查设备可用性（CUDA）

2. **端口占用**
   - 修改 `server.port` 配置
   - 检查其他服务是否占用端口

3. **内存不足**
   - 调整 `model.max_memory` 限制
   - 减少 `server.max_concurrent_requests`
   - 使用更小的数据类型（float16）

4. **权限问题**
   - 检查日志文件路径权限
   - 确认模型文件读取权限

### 调试技巧

1. 启用调试日志：
   ```bash
   python main.py --log-level DEBUG
   ```

2. 使用模拟模式测试：
   ```yaml
   model:
     model_path: ""  # 空路径启用模拟模式
   ```

3. 检查配置加载：
   ```bash
   python -c "from config.manager import init_config; print(init_config().model_dump())"
   ```