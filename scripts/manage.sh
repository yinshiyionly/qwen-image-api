#!/bin/bash

# Qwen Image API Service 管理脚本
# 用法: ./scripts/manage.sh [command] [options]

set -e

# 默认配置
ENVIRONMENT="dev"
SERVICE_NAME="qwen-image-api"

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
Qwen Image API Service 管理脚本

用法: $0 [COMMAND] [OPTIONS]

命令:
    start       启动服务
    stop        停止服务
    restart     重启服务
    status      查看服务状态
    logs        查看服务日志
    health      检查服务健康状态
    backup      备份数据
    restore     恢复数据
    update      更新服务
    cleanup     清理资源
    monitor     监控服务资源使用

选项:
    --env [dev|prod]    指定环境 (默认: dev)
    --follow            跟踪日志输出
    --tail N            显示最后 N 行日志
    --help              显示此帮助信息

示例:
    $0 start --env prod         # 启动生产环境服务
    $0 logs --follow            # 跟踪日志输出
    $0 logs --tail 100          # 显示最后100行日志
    $0 status                   # 查看服务状态

EOF
}

# 获取 Docker Compose 文件
get_compose_file() {
    if [[ "$ENVIRONMENT" == "prod" ]]; then
        echo "docker-compose.prod.yml"
    else
        echo "docker-compose.yml"
    fi
}

# 启动服务
start_service() {
    log_info "启动服务 (环境: $ENVIRONMENT)..."
    
    COMPOSE_FILE=$(get_compose_file)
    docker-compose -f "$COMPOSE_FILE" up -d
    
    log_success "服务启动完成"
}

# 停止服务
stop_service() {
    log_info "停止服务 (环境: $ENVIRONMENT)..."
    
    COMPOSE_FILE=$(get_compose_file)
    docker-compose -f "$COMPOSE_FILE" down
    
    log_success "服务停止完成"
}

# 重启服务
restart_service() {
    log_info "重启服务 (环境: $ENVIRONMENT)..."
    
    COMPOSE_FILE=$(get_compose_file)
    docker-compose -f "$COMPOSE_FILE" restart
    
    log_success "服务重启完成"
}

# 查看服务状态
show_status() {
    log_info "查看服务状态 (环境: $ENVIRONMENT)..."
    
    COMPOSE_FILE=$(get_compose_file)
    
    echo
    echo "=== Docker Compose 服务状态 ==="
    docker-compose -f "$COMPOSE_FILE" ps
    
    echo
    echo "=== 容器资源使用情况 ==="
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
    
    echo
    echo "=== 磁盘使用情况 ==="
    df -h | grep -E "(Filesystem|/dev/)"
}

# 查看日志
show_logs() {
    local follow_flag=""
    local tail_lines=""
    
    # 解析日志选项
    while [[ $# -gt 0 ]]; do
        case $1 in
            --follow)
                follow_flag="-f"
                shift
                ;;
            --tail)
                tail_lines="--tail $2"
                shift 2
                ;;
            *)
                shift
                ;;
        esac
    done
    
    log_info "查看服务日志 (环境: $ENVIRONMENT)..."
    
    COMPOSE_FILE=$(get_compose_file)
    docker-compose -f "$COMPOSE_FILE" logs $follow_flag $tail_lines $SERVICE_NAME
}

# 健康检查
health_check() {
    log_info "执行健康检查..."
    
    # 检查容器状态
    COMPOSE_FILE=$(get_compose_file)
    if ! docker-compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        log_error "服务未运行"
        return 1
    fi
    
    # 检查 API 健康状态
    if curl -f -s http://localhost:8000/health > /dev/null; then
        log_success "API 健康检查通过"
    else
        log_error "API 健康检查失败"
        return 1
    fi
    
    # 检查服务信息
    echo
    echo "=== 服务信息 ==="
    curl -s http://localhost:8000/info | python3 -m json.tool || echo "无法获取服务信息"
}

# 备份数据
backup_data() {
    log_info "备份数据..."
    
    BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # 备份配置文件
    cp config*.yaml "$BACKUP_DIR/" 2>/dev/null || true
    cp .env "$BACKUP_DIR/" 2>/dev/null || true
    
    # 备份日志
    if [[ -d "logs" ]]; then
        cp -r logs "$BACKUP_DIR/"
    fi
    
    # 备份 Docker 卷数据
    COMPOSE_FILE=$(get_compose_file)
    docker-compose -f "$COMPOSE_FILE" exec -T redis redis-cli BGSAVE || true
    
    log_success "数据备份完成: $BACKUP_DIR"
}

# 恢复数据
restore_data() {
    local backup_dir="$1"
    
    if [[ -z "$backup_dir" ]]; then
        log_error "请指定备份目录"
        echo "用法: $0 restore /path/to/backup"
        return 1
    fi
    
    if [[ ! -d "$backup_dir" ]]; then
        log_error "备份目录不存在: $backup_dir"
        return 1
    fi
    
    log_info "恢复数据从: $backup_dir"
    
    # 停止服务
    stop_service
    
    # 恢复配置文件
    cp "$backup_dir"/*.yaml . 2>/dev/null || true
    cp "$backup_dir"/.env . 2>/dev/null || true
    
    # 恢复日志
    if [[ -d "$backup_dir/logs" ]]; then
        rm -rf logs
        cp -r "$backup_dir/logs" .
    fi
    
    # 启动服务
    start_service
    
    log_success "数据恢复完成"
}

# 更新服务
update_service() {
    log_info "更新服务..."
    
    # 备份数据
    backup_data
    
    # 拉取最新代码
    if [[ -d ".git" ]]; then
        git pull
    fi
    
    # 重新构建镜像
    docker build -t qwen-image-api:latest .
    
    # 重启服务
    restart_service
    
    # 健康检查
    sleep 30
    health_check
    
    log_success "服务更新完成"
}

# 清理资源
cleanup_resources() {
    log_info "清理资源..."
    
    # 清理停止的容器
    docker container prune -f
    
    # 清理未使用的镜像
    docker image prune -f
    
    # 清理未使用的卷
    docker volume prune -f
    
    # 清理未使用的网络
    docker network prune -f
    
    # 清理旧日志文件
    find logs -name "*.log" -mtime +30 -delete 2>/dev/null || true
    
    # 清理临时文件
    rm -rf tmp/* 2>/dev/null || true
    
    log_success "资源清理完成"
}

# 监控服务
monitor_service() {
    log_info "监控服务资源使用..."
    
    while true; do
        clear
        echo "=== Qwen Image API Service 监控 ==="
        echo "时间: $(date)"
        echo "按 Ctrl+C 退出监控"
        echo
        
        # 显示容器状态
        echo "=== 容器状态 ==="
        COMPOSE_FILE=$(get_compose_file)
        docker-compose -f "$COMPOSE_FILE" ps
        echo
        
        # 显示资源使用
        echo "=== 资源使用 ==="
        docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
        echo
        
        # 显示系统负载
        echo "=== 系统负载 ==="
        uptime
        echo
        
        # 显示磁盘使用
        echo "=== 磁盘使用 ==="
        df -h | head -5
        echo
        
        sleep 5
    done
}

# 解析命令行参数
parse_args() {
    local command=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            start|stop|restart|status|logs|health|backup|restore|update|cleanup|monitor)
                command="$1"
                shift
                ;;
            --env)
                ENVIRONMENT="$2"
                shift 2
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                # 传递给具体命令处理
                break
                ;;
        esac
    done
    
    case $command in
        start)
            start_service
            ;;
        stop)
            stop_service
            ;;
        restart)
            restart_service
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs "$@"
            ;;
        health)
            health_check
            ;;
        backup)
            backup_data
            ;;
        restore)
            restore_data "$1"
            ;;
        update)
            update_service
            ;;
        cleanup)
            cleanup_resources
            ;;
        monitor)
            monitor_service
            ;;
        "")
            log_error "请指定命令"
            show_help
            exit 1
            ;;
        *)
            log_error "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# 主函数
main() {
    parse_args "$@"
}

# 执行主函数
main "$@"