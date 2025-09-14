#!/bin/bash

# Qwen Image API Service 部署脚本
# 用法: ./scripts/deploy.sh [dev|prod] [options]

set -e

# 默认配置
ENVIRONMENT="dev"
BUILD_IMAGE=true
PULL_LATEST=false
BACKUP_DATA=true
HEALTH_CHECK=true

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
Qwen Image API Service 部署脚本

用法: $0 [ENVIRONMENT] [OPTIONS]

环境:
    dev     开发环境部署 (默认)
    prod    生产环境部署

选项:
    --no-build          跳过镜像构建
    --pull              拉取最新镜像
    --no-backup         跳过数据备份
    --no-health-check   跳过健康检查
    --help              显示此帮助信息

示例:
    $0 dev                    # 开发环境部署
    $0 prod --no-build        # 生产环境部署，跳过构建
    $0 prod --pull            # 生产环境部署，拉取最新镜像

EOF
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            dev|prod)
                ENVIRONMENT="$1"
                shift
                ;;
            --no-build)
                BUILD_IMAGE=false
                shift
                ;;
            --pull)
                PULL_LATEST=true
                shift
                ;;
            --no-backup)
                BACKUP_DATA=false
                shift
                ;;
            --no-health-check)
                HEALTH_CHECK=false
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

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose 未安装"
        exit 1
    fi
    
    log_success "依赖检查完成"
}

# 检查环境
check_environment() {
    log_info "检查环境配置..."
    
    if [[ "$ENVIRONMENT" == "prod" ]]; then
        if [[ ! -f "config.prod.yaml" ]]; then
            log_error "生产环境配置文件 config.prod.yaml 不存在"
            exit 1
        fi
        
        if [[ ! -f ".env" ]]; then
            log_warning "环境变量文件 .env 不存在，将使用默认配置"
        fi
        
        # 检查 SSL 证书
        if [[ ! -f "nginx/ssl/cert.pem" ]] || [[ ! -f "nginx/ssl/key.pem" ]]; then
            log_warning "SSL 证书不存在，HTTPS 将不可用"
        fi
    fi
    
    log_success "环境检查完成"
}

# 创建必要目录
create_directories() {
    log_info "创建必要目录..."
    
    mkdir -p logs tmp
    
    if [[ "$ENVIRONMENT" == "prod" ]]; then
        mkdir -p nginx/ssl monitoring/data
    fi
    
    log_success "目录创建完成"
}

# 备份数据
backup_data() {
    if [[ "$BACKUP_DATA" == false ]]; then
        return
    fi
    
    log_info "备份数据..."
    
    BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # 备份配置文件
    if [[ -f "config.yaml" ]]; then
        cp config.yaml "$BACKUP_DIR/"
    fi
    
    if [[ -f "config.prod.yaml" ]]; then
        cp config.prod.yaml "$BACKUP_DIR/"
    fi
    
    # 备份日志
    if [[ -d "logs" ]]; then
        cp -r logs "$BACKUP_DIR/"
    fi
    
    log_success "数据备份完成: $BACKUP_DIR"
}

# 构建镜像
build_image() {
    if [[ "$BUILD_IMAGE" == false ]]; then
        return
    fi
    
    log_info "构建 Docker 镜像..."
    
    docker build -t qwen-image-api:latest .
    
    if [[ "$ENVIRONMENT" == "prod" ]]; then
        docker tag qwen-image-api:latest qwen-image-api:prod
    fi
    
    log_success "镜像构建完成"
}

# 拉取镜像
pull_images() {
    if [[ "$PULL_LATEST" == false ]]; then
        return
    fi
    
    log_info "拉取最新镜像..."
    
    if [[ "$ENVIRONMENT" == "prod" ]]; then
        docker-compose -f docker-compose.prod.yml pull
    else
        docker-compose pull
    fi
    
    log_success "镜像拉取完成"
}

# 停止现有服务
stop_services() {
    log_info "停止现有服务..."
    
    if [[ "$ENVIRONMENT" == "prod" ]]; then
        docker-compose -f docker-compose.prod.yml down || true
    else
        docker-compose down || true
    fi
    
    log_success "服务停止完成"
}

# 启动服务
start_services() {
    log_info "启动服务..."
    
    if [[ "$ENVIRONMENT" == "prod" ]]; then
        docker-compose -f docker-compose.prod.yml up -d
    else
        docker-compose up -d
    fi
    
    log_success "服务启动完成"
}

# 健康检查
health_check() {
    if [[ "$HEALTH_CHECK" == false ]]; then
        return
    fi
    
    log_info "执行健康检查..."
    
    # 等待服务启动
    sleep 30
    
    # 检查容器状态
    if [[ "$ENVIRONMENT" == "prod" ]]; then
        COMPOSE_FILE="docker-compose.prod.yml"
    else
        COMPOSE_FILE="docker-compose.yml"
    fi
    
    if ! docker-compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        log_error "服务启动失败"
        docker-compose -f "$COMPOSE_FILE" logs
        exit 1
    fi
    
    # 检查 API 健康状态
    MAX_RETRIES=10
    RETRY_COUNT=0
    
    while [[ $RETRY_COUNT -lt $MAX_RETRIES ]]; do
        if curl -f -s http://localhost:8000/health > /dev/null; then
            log_success "健康检查通过"
            return
        fi
        
        log_info "等待服务就绪... ($((RETRY_COUNT + 1))/$MAX_RETRIES)"
        sleep 10
        ((RETRY_COUNT++))
    done
    
    log_error "健康检查失败"
    exit 1
}

# 显示部署信息
show_deployment_info() {
    log_success "部署完成！"
    
    echo
    echo "=== 部署信息 ==="
    echo "环境: $ENVIRONMENT"
    echo "时间: $(date)"
    
    if [[ "$ENVIRONMENT" == "prod" ]]; then
        echo "API 地址: https://localhost"
        echo "监控地址: http://localhost:3000"
    else
        echo "API 地址: http://localhost:8000"
        echo "API 文档: http://localhost:8000/docs"
    fi
    
    echo
    echo "=== 常用命令 ==="
    echo "查看日志: docker-compose logs -f qwen-image-api"
    echo "查看状态: docker-compose ps"
    echo "停止服务: docker-compose down"
    echo "重启服务: docker-compose restart"
    
    if [[ "$ENVIRONMENT" == "prod" ]]; then
        echo "生产环境命令需要添加 -f docker-compose.prod.yml 参数"
    fi
}

# 主函数
main() {
    log_info "开始部署 Qwen Image API Service..."
    
    parse_args "$@"
    check_dependencies
    check_environment
    create_directories
    backup_data
    build_image
    pull_images
    stop_services
    start_services
    health_check
    show_deployment_info
}

# 错误处理
trap 'log_error "部署失败，请检查错误信息"; exit 1' ERR

# 执行主函数
main "$@"