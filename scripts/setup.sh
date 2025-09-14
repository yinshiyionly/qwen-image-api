#!/bin/bash

# Qwen Image API Service 环境设置脚本
# 用法: ./scripts/setup.sh [options]

set -e

# 默认配置
INSTALL_DOCKER=false
INSTALL_COMPOSE=false
SETUP_GPU=false
CREATE_DIRS=true
SETUP_SSL=false

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示帮助信息
show_help() {
    cat << EOF
Qwen Image API Service 环境设置脚本

用法: $0 [OPTIONS]

选项:
    --install-docker    安装 Docker
    --install-compose   安装 Docker Compose
    --setup-gpu         设置 GPU 支持
    --setup-ssl         设置 SSL 证书
    --no-dirs          跳过目录创建
    --help             显示此帮助信息

示例:
    $0                          # 基础设置
    $0 --install-docker         # 安装 Docker 并设置
    $0 --setup-gpu --setup-ssl  # 设置 GPU 和 SSL

EOF
}

# 检测操作系统
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
    elif type lsb_release >/dev/null 2>&1; then
        OS=$(lsb_release -si)
        VER=$(lsb_release -sr)
    elif [[ -f /etc/redhat-release ]]; then
        OS="Red Hat Enterprise Linux"
        VER=$(cat /etc/redhat-release | sed s/.*release\ // | sed s/\ .*//)
    else
        OS=$(uname -s)
        VER=$(uname -r)
    fi
    
    log_info "检测到操作系统: $OS $VER"
}

# 安装 Docker
install_docker() {
    if command -v docker &> /dev/null; then
        log_info "Docker 已安装"
        return
    fi
    
    log_info "安装 Docker..."
    
    case $OS in
        *"Ubuntu"*|*"Debian"*)
            # 更新包索引
            sudo apt-get update
            
            # 安装依赖
            sudo apt-get install -y \
                apt-transport-https \
                ca-certificates \
                curl \
                gnupg \
                lsb-release
            
            # 添加 Docker GPG 密钥
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
            
            # 添加 Docker 仓库
            echo \
                "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
                $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
            
            # 安装 Docker
            sudo apt-get update
            sudo apt-get install -y docker-ce docker-ce-cli containerd.io
            ;;
        *"CentOS"*|*"Red Hat"*)
            # 安装依赖
            sudo yum install -y yum-utils
            
            # 添加 Docker 仓库
            sudo yum-config-manager \
                --add-repo \
                https://download.docker.com/linux/centos/docker-ce.repo
            
            # 安装 Docker
            sudo yum install -y docker-ce docker-ce-cli containerd.io
            ;;
        *)
            log_error "不支持的操作系统: $OS"
            exit 1
            ;;
    esac
    
    # 启动 Docker 服务
    sudo systemctl start docker
    sudo systemctl enable docker
    
    # 添加用户到 docker 组
    sudo usermod -aG docker $USER
    
    log_success "Docker 安装完成"
    log_warning "请重新登录以使用 Docker 命令"
}

# 安装 Docker Compose
install_docker_compose() {
    if command -v docker-compose &> /dev/null; then
        log_info "Docker Compose 已安装"
        return
    fi
    
    log_info "安装 Docker Compose..."
    
    # 下载 Docker Compose
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
    sudo curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    
    # 设置执行权限
    sudo chmod +x /usr/local/bin/docker-compose
    
    # 创建符号链接
    sudo ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
    
    log_success "Docker Compose 安装完成"
}

# 设置 GPU 支持
setup_gpu() {
    log_info "设置 GPU 支持..."
    
    # 检查 NVIDIA GPU
    if ! command -v nvidia-smi &> /dev/null; then
        log_warning "未检测到 NVIDIA GPU 或驱动"
        return
    fi
    
    # 安装 NVIDIA Docker 运行时
    case $OS in
        *"Ubuntu"*|*"Debian"*)
            # 添加 NVIDIA Docker 仓库
            distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
            curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
            curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
            
            # 安装 nvidia-docker2
            sudo apt-get update
            sudo apt-get install -y nvidia-docker2
            ;;
        *"CentOS"*|*"Red Hat"*)
            # 添加 NVIDIA Docker 仓库
            distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
            curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.repo | sudo tee /etc/yum.repos.d/nvidia-docker.repo
            
            # 安装 nvidia-docker2
            sudo yum install -y nvidia-docker2
            ;;
    esac
    
    # 重启 Docker 服务
    sudo systemctl restart docker
    
    # 测试 GPU 支持
    if docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi; then
        log_success "GPU 支持设置完成"
    else
        log_error "GPU 支持设置失败"
    fi
}

# 创建目录结构
create_directories() {
    if [[ "$CREATE_DIRS" == false ]]; then
        return
    fi
    
    log_info "创建目录结构..."
    
    # 创建基础目录
    mkdir -p {logs,tmp,backups}
    mkdir -p {nginx/ssl,redis,monitoring/data}
    mkdir -p scripts
    
    # 设置权限
    chmod 755 scripts/*.sh 2>/dev/null || true
    chmod 700 nginx/ssl 2>/dev/null || true
    
    log_success "目录结构创建完成"
}

# 设置 SSL 证书
setup_ssl() {
    if [[ "$SETUP_SSL" == false ]]; then
        return
    fi
    
    log_info "设置 SSL 证书..."
    
    SSL_DIR="nginx/ssl"
    mkdir -p "$SSL_DIR"
    
    # 生成自签名证书（仅用于测试）
    if [[ ! -f "$SSL_DIR/cert.pem" ]] || [[ ! -f "$SSL_DIR/key.pem" ]]; then
        log_warning "生成自签名 SSL 证书（仅用于测试）"
        
        openssl req -x509 -newkey rsa:4096 -keyout "$SSL_DIR/key.pem" -out "$SSL_DIR/cert.pem" -days 365 -nodes \
            -subj "/C=CN/ST=State/L=City/O=Organization/CN=localhost"
        
        chmod 600 "$SSL_DIR"/*.pem
        
        log_warning "请在生产环境中使用正式的 SSL 证书"
    fi
    
    log_success "SSL 证书设置完成"
}

# 创建环境变量文件
create_env_file() {
    if [[ -f ".env" ]]; then
        log_info ".env 文件已存在"
        return
    fi
    
    log_info "创建环境变量文件..."
    
    cat > .env << EOF
# Qwen Image API Service 环境变量配置

# 模型配置
QWEN_MODEL_DEVICE=cpu
QWEN_MODEL_TORCH_DTYPE=float32
QWEN_MODEL_PATH=

# 服务器配置
QWEN_SERVER_HOST=0.0.0.0
QWEN_SERVER_PORT=8000
QWEN_SERVER_MAX_CONCURRENT_REQUESTS=4

# 安全配置
QWEN_SECURITY_ENABLE_RATE_LIMIT=true
QWEN_SECURITY_RATE_LIMIT_PER_MINUTE=60
QWEN_SECURITY_API_KEY=

# 日志配置
QWEN_LOG_LEVEL=INFO
QWEN_LOG_FILE_PATH=/app/logs/qwen-api.log

# 缓存配置
QWEN_CACHE_ENABLED=false
QWEN_CACHE_TYPE=memory

# 监控配置
QWEN_MONITORING_ENABLED=true
EOF
    
    log_success "环境变量文件创建完成"
}

# 检查系统要求
check_system_requirements() {
    log_info "检查系统要求..."
    
    # 检查内存
    MEMORY_GB=$(free -g | awk '/^Mem:/{print $2}')
    if [[ $MEMORY_GB -lt 4 ]]; then
        log_warning "系统内存不足 4GB，可能影响性能"
    fi
    
    # 检查磁盘空间
    DISK_GB=$(df -BG . | awk 'NR==2{print $4}' | sed 's/G//')
    if [[ $DISK_GB -lt 20 ]]; then
        log_warning "磁盘空间不足 20GB，可能影响运行"
    fi
    
    # 检查 CPU 核心数
    CPU_CORES=$(nproc)
    if [[ $CPU_CORES -lt 2 ]]; then
        log_warning "CPU 核心数不足 2 个，可能影响性能"
    fi
    
    log_info "系统要求检查完成 (内存: ${MEMORY_GB}GB, 磁盘: ${DISK_GB}GB, CPU: ${CPU_CORES} 核)"
}

# 显示设置完成信息
show_completion_info() {
    log_success "环境设置完成！"
    
    echo
    echo "=== 下一步操作 ==="
    echo "1. 配置模型路径:"
    echo "   编辑 config.yaml 或设置环境变量 QWEN_MODEL_PATH"
    echo
    echo "2. 部署服务:"
    echo "   ./scripts/deploy.sh dev    # 开发环境"
    echo "   ./scripts/deploy.sh prod   # 生产环境"
    echo
    echo "3. 管理服务:"
    echo "   ./scripts/manage.sh status # 查看状态"
    echo "   ./scripts/manage.sh logs   # 查看日志"
    echo
    echo "=== 配置文件 ==="
    echo "- config.yaml: 开发环境配置"
    echo "- config.prod.yaml: 生产环境配置"
    echo "- .env: 环境变量配置"
    echo
    
    if [[ "$INSTALL_DOCKER" == true ]]; then
        echo "=== 重要提醒 ==="
        echo "请重新登录或执行以下命令以使用 Docker:"
        echo "newgrp docker"
        echo
    fi
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --install-docker)
                INSTALL_DOCKER=true
                shift
                ;;
            --install-compose)
                INSTALL_COMPOSE=true
                shift
                ;;
            --setup-gpu)
                SETUP_GPU=true
                shift
                ;;
            --setup-ssl)
                SETUP_SSL=true
                shift
                ;;
            --no-dirs)
                CREATE_DIRS=false
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# 主函数
main() {
    log_info "开始设置 Qwen Image API Service 环境..."
    
    parse_args "$@"
    detect_os
    check_system_requirements
    
    if [[ "$INSTALL_DOCKER" == true ]]; then
        install_docker
    fi
    
    if [[ "$INSTALL_COMPOSE" == true ]]; then
        install_docker_compose
    fi
    
    if [[ "$SETUP_GPU" == true ]]; then
        setup_gpu
    fi
    
    create_directories
    setup_ssl
    create_env_file
    show_completion_info
}

# 错误处理
trap 'log_error "设置失败，请检查错误信息"; exit 1' ERR

# 执行主函数
main "$@"