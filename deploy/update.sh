#!/bin/bash
# =============================================================================
# tong-study 代码更新脚本
# 
# 使用方法：
#   cd /opt/tong-study && ./deploy/update.sh
#
# 功能：
#   1. 从GitHub拉取最新代码
#   2. 安装新增的Python依赖
#   3. 重启应用服务
# =============================================================================

set -e

# ─── 配置 ───────────────────────────────────────────────────
APP_DIR="/opt/tong-study"
VENV_DIR="$APP_DIR/venv"
SERVICE_NAME="tong-study"
BRANCH="main"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ─── 检查目录 ───────────────────────────────────────────────
if [ ! -f "$APP_DIR/app.py" ]; then
    echo_error "未找到 $APP_DIR/app.py，请确认项目路径正确"
    exit 1
fi

cd $APP_DIR

echo "=============================================="
echo "  tong-study 代码更新"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="
echo ""

# ─── Step 1: 拉取最新代码 ───────────────────────────────────
echo_info "Step 1/4: 拉取最新代码..."
git fetch origin $BRANCH
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/$BRANCH)

if [ "$LOCAL" = "$REMOTE" ]; then
    echo_warn "代码已是最新版本，无需更新"
    echo "  当前版本: $(git log --oneline -1)"
    exit 0
fi

echo "  更新前: $(git log --oneline -1)"
git pull origin $BRANCH
echo "  更新后: $(git log --oneline -1)"
echo ""

# ─── Step 2: 显示更新内容 ───────────────────────────────────
echo_info "Step 2/4: 本次更新的文件:"
git diff --stat $LOCAL $REMOTE
echo ""

# ─── Step 3: 安装新依赖（如果requirements.txt有变化）────────
echo_info "Step 3/4: 检查依赖更新..."
if git diff --name-only $LOCAL $REMOTE | grep -q "requirements.txt"; then
    echo_info "requirements.txt 有变化，安装新依赖..."
    source $VENV_DIR/bin/activate
    pip install -r requirements.txt -q
    echo_info "依赖安装完成"
else
    echo_warn "requirements.txt 未变化，跳过依赖安装"
fi
echo ""

# ─── Step 4: 重启服务 ───────────────────────────────────────
echo_info "Step 4/4: 重启服务..."
sudo systemctl restart $SERVICE_NAME

# 等待2秒检查状态
sleep 2
if sudo systemctl is-active --quiet $SERVICE_NAME; then
    echo_info "服务重启成功 ✓"
else
    echo_error "服务重启失败！查看日志："
    sudo journalctl -u $SERVICE_NAME --since "30 seconds ago" --no-pager
    exit 1
fi

echo ""
echo "=============================================="
echo -e "${GREEN}  更新完成！${NC}"
echo "=============================================="
echo "  当前版本: $(git log --oneline -1)"
echo "  服务状态: $(sudo systemctl is-active $SERVICE_NAME)"
echo "=============================================="