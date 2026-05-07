#!/bin/bash
# =============================================================================
# tong-study 服务重启脚本
# 
# 使用方法：
#   cd /opt/tong-study && ./deploy/restart.sh
#
# 可选参数：
#   ./deploy/restart.sh          重启应用服务
#   ./deploy/restart.sh all      重启应用 + Nginx
#   ./deploy/restart.sh status   仅查看状态
#   ./deploy/restart.sh stop     停止服务
#   ./deploy/restart.sh start    启动服务
#   ./deploy/restart.sh logs     查看最近日志
# =============================================================================

SERVICE_NAME="tong-study"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

show_status() {
    echo ""
    echo "── 服务状态 ──────────────────────────────────"
    if sudo systemctl is-active --quiet $SERVICE_NAME; then
        echo -e "  tong-study:  ${GREEN}运行中 ✓${NC}"
    else
        echo -e "  tong-study:  ${RED}已停止 ✗${NC}"
    fi
    if sudo systemctl is-active --quiet nginx; then
        echo -e "  nginx:       ${GREEN}运行中 ✓${NC}"
    else
        echo -e "  nginx:       ${RED}已停止 ✗${NC}"
    fi
    echo ""
    echo "── 资源使用 ──────────────────────────────────"
    echo "  内存: $(free -h | awk '/^Mem:/{print $3 "/" $2}')"
    echo "  磁盘: $(df -h / | awk 'NR==2{print $3 "/" $2 " (" $5 ")"}')"
    echo ""
}

case "${1:-restart}" in
    restart)
        echo_info "重启 $SERVICE_NAME 服务..."
        sudo systemctl restart $SERVICE_NAME
        sleep 2
        if sudo systemctl is-active --quiet $SERVICE_NAME; then
            echo_info "重启成功 ✓"
        else
            echo_error "重启失败！"
            sudo journalctl -u $SERVICE_NAME --since "30 seconds ago" --no-pager
            exit 1
        fi
        show_status
        ;;
    all)
        echo_info "重启 $SERVICE_NAME + Nginx..."
        sudo systemctl restart $SERVICE_NAME
        sudo systemctl restart nginx
        sleep 2
        show_status
        ;;
    stop)
        echo_warn "停止 $SERVICE_NAME 服务..."
        sudo systemctl stop $SERVICE_NAME
        echo_info "服务已停止"
        show_status
        ;;
    start)
        echo_info "启动 $SERVICE_NAME 服务..."
        sudo systemctl start $SERVICE_NAME
        sleep 2
        if sudo systemctl is-active --quiet $SERVICE_NAME; then
            echo_info "启动成功 ✓"
        else
            echo_error "启动失败！"
            sudo journalctl -u $SERVICE_NAME --since "30 seconds ago" --no-pager
            exit 1
        fi
        show_status
        ;;
    status)
        show_status
        echo "── 最近日志 ──────────────────────────────────"
        sudo journalctl -u $SERVICE_NAME --since "10 minutes ago" --no-pager | tail -20
        ;;
    logs)
        echo_info "查看实时日志（Ctrl+C退出）..."
        sudo journalctl -u $SERVICE_NAME -f
        ;;
    *)
        echo "用法: $0 {restart|all|stop|start|status|logs}"
        echo ""
        echo "  restart  - 重启应用服务（默认）"
        echo "  all      - 重启应用 + Nginx"
        echo "  stop     - 停止服务"
        echo "  start    - 启动服务"
        echo "  status   - 查看状态"
        echo "  logs     - 查看实时日志"
        exit 1
        ;;
esac