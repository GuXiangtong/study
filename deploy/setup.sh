#!/bin/bash
# =============================================================================
# tong-study 阿里云轻量应用服务器一键部署脚本
# 
# 使用方法：
#   1. SSH连接到服务器（以root身份）
#   2. 上传此脚本或复制内容
#   3. chmod +x setup.sh && ./setup.sh
#
# 前提条件：
#   - Ubuntu 22.04 系统
#   - 已设置root密码
#   - 已记录服务器公网IP
# =============================================================================

set -e  # 遇到错误立即退出

# ─── 配置变量（根据需要修改）─────────────────────────────────
APP_NAME="tong-study"
APP_DIR="/opt/tong-study"
DEPLOY_USER="deploy"
REPO_URL="https://github.com/GuXiangtong/study.git"
BRANCH="main"
PYTHON_VERSION="python3"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ─── 检查是否为root ─────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    echo_error "请使用root用户运行此脚本: sudo ./setup.sh"
    exit 1
fi

echo "=============================================="
echo "  tong-study 部署脚本"
echo "  $(date)"
echo "=============================================="
echo ""

# ─── Step 1: 系统更新 ───────────────────────────────────────
echo_info "Step 1/10: 更新系统包..."
apt update && apt upgrade -y

# ─── Step 2: 安装系统依赖 ───────────────────────────────────
echo_info "Step 2/10: 安装系统依赖..."
apt install -y \
    git curl wget vim \
    python3 python3-pip python3-venv \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender1 \
    nginx \
    certbot python3-certbot-nginx \
    htop

# ─── Step 3: 创建部署用户 ───────────────────────────────────
echo_info "Step 3/10: 创建部署用户..."
if id "$DEPLOY_USER" &>/dev/null; then
    echo_warn "用户 $DEPLOY_USER 已存在，跳过创建"
else
    adduser --disabled-password --gecos "" $DEPLOY_USER
    usermod -aG sudo $DEPLOY_USER
    echo_info "已创建用户: $DEPLOY_USER"
fi

# ─── Step 4: 配置Swap（如果内存<4GB）─────────────────────────
echo_info "Step 4/10: 检查并配置Swap..."
TOTAL_MEM=$(free -m | awk '/^Mem:/{print $2}')
if [ "$TOTAL_MEM" -lt 4000 ] && [ ! -f /swapfile ]; then
    echo_info "内存 ${TOTAL_MEM}MB < 4GB，创建2GB Swap..."
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo_info "Swap已创建并启用"
else
    echo_warn "内存充足或Swap已存在，跳过"
fi

# ─── Step 5: 克隆项目代码 ───────────────────────────────────
echo_info "Step 5/10: 部署项目代码..."
if [ -d "$APP_DIR/.git" ]; then
    echo_warn "项目目录已存在，执行git pull..."
    cd $APP_DIR
    sudo -u $DEPLOY_USER git pull origin $BRANCH
else
    mkdir -p $APP_DIR
    chown $DEPLOY_USER:$DEPLOY_USER $APP_DIR
    sudo -u $DEPLOY_USER git clone -b $BRANCH $REPO_URL $APP_DIR
fi

# 创建必要目录
cd $APP_DIR
sudo -u $DEPLOY_USER mkdir -p _tmp/papers logs backup
sudo -u $DEPLOY_USER mkdir -p "错题分析/数学" "错题分析/物理" "错题分析/英语" "错题分析/语文"

# ─── Step 6: 安装Python依赖 ─────────────────────────────────
echo_info "Step 6/10: 安装Python依赖（这可能需要10-15分钟）..."
cd $APP_DIR

if [ ! -d "venv" ]; then
    sudo -u $DEPLOY_USER $PYTHON_VERSION -m venv venv
fi

# 使用deploy用户安装依赖
sudo -u $DEPLOY_USER bash -c "
    source $APP_DIR/venv/bin/activate
    pip install --upgrade pip setuptools wheel
    pip install gunicorn
    pip install flask>=3.0 requests>=2.31 pymupdf>=1.24.0 Pillow>=10.0.0
    pip install volcengine-python-sdk>=5.0.0
    pip install paddlepaddle==3.0.0
    pip install paddleocr>=3.5.0
"

# ─── Step 7: 配置Gunicorn ───────────────────────────────────
echo_info "Step 7/10: 配置Gunicorn..."
if [ -f "$APP_DIR/deploy/gunicorn.conf.py" ]; then
    cp $APP_DIR/deploy/gunicorn.conf.py $APP_DIR/gunicorn.conf.py
    chown $DEPLOY_USER:$DEPLOY_USER $APP_DIR/gunicorn.conf.py
    echo_info "Gunicorn配置已复制"
else
    echo_warn "未找到deploy/gunicorn.conf.py，请手动配置"
fi

# ─── Step 8: 配置Systemd服务 ────────────────────────────────
echo_info "Step 8/10: 配置Systemd服务..."

# 生成随机SECRET_KEY
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

if [ -f "$APP_DIR/deploy/tong-study.service" ]; then
    cp $APP_DIR/deploy/tong-study.service /etc/systemd/system/tong-study.service
    # 替换SECRET_KEY
    sed -i "s/change-this-to-a-random-secret-key/$SECRET_KEY/" /etc/systemd/system/tong-study.service
else
    cat > /etc/systemd/system/tong-study.service << EOF
[Unit]
Description=Tong Study Flask Application
After=network.target

[Service]
Type=notify
User=$DEPLOY_USER
Group=$DEPLOY_USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin:/usr/local/bin:/usr/bin"
Environment="SECRET_KEY=$SECRET_KEY"
ExecStart=$APP_DIR/venv/bin/gunicorn -c gunicorn.conf.py app:app
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=5
KillMode=mixed
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
fi

systemctl daemon-reload
systemctl enable tong-study

# ─── Step 9: 配置Nginx ──────────────────────────────────────
echo_info "Step 9/10: 配置Nginx..."
if [ -f "$APP_DIR/deploy/nginx.conf" ]; then
    cp $APP_DIR/deploy/nginx.conf /etc/nginx/sites-available/tong-study
else
    cat > /etc/nginx/sites-available/tong-study << 'EOF'
upstream tong_study {
    server 127.0.0.1:5001;
    keepalive 4;
}

server {
    listen 80;
    server_name _;
    client_max_body_size 32M;

    location /static/ {
        alias /opt/tong-study/static/;
        expires 7d;
    }

    location / {
        proxy_pass http://tong_study;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        proxy_http_version 1.1;
    }

    location ~ /\. { deny all; }
    location ~ \.py$ { deny all; }
    location ~ \.db$ { deny all; }
}
EOF
fi

# 启用站点
ln -sf /etc/nginx/sites-available/tong-study /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# 测试Nginx配置
nginx -t

systemctl restart nginx
systemctl enable nginx

# ─── Step 10: 配置API密钥提示 ───────────────────────────────
echo_info "Step 10/10: 最终配置..."

# 创建.claude目录
sudo -u $DEPLOY_USER mkdir -p $APP_DIR/.claude

if [ ! -f "$APP_DIR/.claude/apikey" ]; then
    sudo -u $DEPLOY_USER cat > $APP_DIR/.claude/apikey << 'EOF'
# 请填写真实的API密钥
DEEPSEEK_API_KEY=
DOUBAO_API_KEY=
MOONSHOT_API_KEY=
ANTHROPIC_API_KEY=
ANTHROPIC_BASE_URL=
EOF
    chmod 600 $APP_DIR/.claude/apikey
    chown $DEPLOY_USER:$DEPLOY_USER $APP_DIR/.claude/apikey
fi

# ─── 配置定时备份 ───────────────────────────────────────────
sudo -u $DEPLOY_USER mkdir -p $APP_DIR/backup
(sudo -u $DEPLOY_USER crontab -l 2>/dev/null; echo "0 2 * * * cp $APP_DIR/study.db $APP_DIR/backup/study_\$(date +\%Y\%m\%d).db") | sudo -u $DEPLOY_USER crontab - 2>/dev/null || true

# ─── 完成 ───────────────────────────────────────────────────
echo ""
echo "=============================================="
echo -e "${GREEN}  部署完成！${NC}"
echo "=============================================="
echo ""
echo "📋 后续步骤："
echo ""
echo "  1. 配置API密钥："
echo "     vim $APP_DIR/.claude/apikey"
echo ""
echo "  2. 启动应用："
echo "     sudo systemctl start tong-study"
echo ""
echo "  3. 检查状态："
echo "     sudo systemctl status tong-study"
echo ""
echo "  4. 访问应用："
echo "     http://$(curl -s ifconfig.me 2>/dev/null || echo '你的服务器IP')"
echo ""
echo "  5. (可选) 配置SSL证书："
echo "     sudo certbot --nginx -d your-domain.com"
echo ""
echo "  6. 查看日志："
echo "     tail -f $APP_DIR/logs/error.log"
echo ""
echo "⚠️  重要提醒："
echo "  - 记得在阿里云控制台防火墙中开放 80 和 443 端口"
echo "  - 如需域名访问，需先完成ICP备案（大陆服务器）"
echo "  - 修改 /etc/nginx/sites-available/tong-study 中的 server_name"
echo ""
echo "=============================================="