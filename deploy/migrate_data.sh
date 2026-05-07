#!/bin/bash
# =============================================================================
# tong-study 数据迁移脚本
# 
# 将用户数据从代码目录迁移到独立数据目录
# 运行前提：已部署在 /opt/tong-study，数据和代码混在一起
#
# 使用方法：
#   cd /opt/tong-study && sudo ./deploy/migrate_data.sh
# =============================================================================

set -e

# ─── 配置 ───────────────────────────────────────────────────
APP_DIR="/opt/tong-study"
DATA_DIR="/opt/tong-study-data"
DEPLOY_USER="deploy"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ─── 检查 ───────────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    echo_error "请使用root运行: sudo ./deploy/migrate_data.sh"
    exit 1
fi

if [ ! -f "$APP_DIR/app.py" ]; then
    echo_error "未找到 $APP_DIR/app.py，请确认项目路径正确"
    exit 1
fi

echo "=============================================="
echo "  tong-study 数据迁移"
echo "  代码目录: $APP_DIR"
echo "  数据目录: $DATA_DIR"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="
echo ""

# ─── Step 1: 创建数据目录 ───────────────────────────────────
echo_info "Step 1/5: 创建数据目录..."
mkdir -p "$DATA_DIR"
chown $DEPLOY_USER:$DEPLOY_USER "$DATA_DIR"

# 创建子目录
sudo -u $DEPLOY_USER mkdir -p "$DATA_DIR/logs"
sudo -u $DEPLOY_USER mkdir -p "$DATA_DIR/backup"
sudo -u $DEPLOY_USER mkdir -p "$DATA_DIR/_tmp/papers"
sudo -u $DEPLOY_USER mkdir -p "$DATA_DIR/错题分析/数学"
sudo -u $DEPLOY_USER mkdir -p "$DATA_DIR/错题分析/物理"
sudo -u $DEPLOY_USER mkdir -p "$DATA_DIR/错题分析/英语"
sudo -u $DEPLOY_USER mkdir -p "$DATA_DIR/错题分析/语文"
sudo -u $DEPLOY_USER mkdir -p "$DATA_DIR/错题分析/化学"
sudo -u $DEPLOY_USER mkdir -p "$DATA_DIR/错题分析/生物"

echo_info "数据目录已创建: $DATA_DIR"

# ─── Step 2: 迁移数据库 ────────────────────────────────────
echo_info "Step 2/5: 迁移数据库..."
if [ -f "$APP_DIR/study.db" ]; then
    cp -p "$APP_DIR/study.db" "$DATA_DIR/study.db"
    chown $DEPLOY_USER:$DEPLOY_USER "$DATA_DIR/study.db"
    echo_info "数据库已迁移: study.db"
else
    echo_warn "未找到 study.db，跳过（首次启动会自动创建）"
fi

# ─── Step 3: 迁移试卷图片 ──────────────────────────────────
echo_info "Step 3/5: 迁移试卷图片..."
SUBJECTS=("数学" "物理" "英语" "语文" "化学" "生物")
for subj in "${SUBJECTS[@]}"; do
    if [ -d "$APP_DIR/$subj" ]; then
        echo_info "  迁移 $subj/ ..."
        cp -rp "$APP_DIR/$subj" "$DATA_DIR/"
        chown -R $DEPLOY_USER:$DEPLOY_USER "$DATA_DIR/$subj"
    fi
done

# ─── Step 4: 迁移错题分析 ──────────────────────────────────
echo_info "Step 4/5: 迁移错题分析..."
if [ -d "$APP_DIR/错题分析" ]; then
    # 合并而非覆盖（目标目录已创建）
    cp -rp "$APP_DIR/错题分析/"* "$DATA_DIR/错题分析/" 2>/dev/null || true
    chown -R $DEPLOY_USER:$DEPLOY_USER "$DATA_DIR/错题分析"
    echo_info "错题分析已迁移"
else
    echo_warn "未找到错题分析目录，跳过"
fi

# 迁移临时文件（可选）
if [ -d "$APP_DIR/_tmp" ]; then
    cp -rp "$APP_DIR/_tmp/"* "$DATA_DIR/_tmp/" 2>/dev/null || true
    chown -R $DEPLOY_USER:$DEPLOY_USER "$DATA_DIR/_tmp"
fi

# 迁移日志
if [ -d "$APP_DIR/logs" ]; then
    cp -rp "$APP_DIR/logs/"* "$DATA_DIR/logs/" 2>/dev/null || true
    chown -R $DEPLOY_USER:$DEPLOY_USER "$DATA_DIR/logs"
fi

# ─── Step 5: 更新systemd配置 ──────────────────────────────
echo_info "Step 5/5: 更新服务配置..."

# 检查service文件中是否已有DATA_DIR
if grep -q "DATA_DIR" /etc/systemd/system/tong-study.service; then
    # 更新DATA_DIR路径
    sed -i 's|Environment="DATA_DIR=.*"|Environment="DATA_DIR=/opt/tong-study-data"|' /etc/systemd/system/tong-study.service
    echo_info "已更新 systemd 中的 DATA_DIR"
else
    # 在SECRET_KEY行后添加DATA_DIR
    sed -i '/SECRET_KEY/a Environment="DATA_DIR=/opt/tong-study-data"' /etc/systemd/system/tong-study.service
    echo_info "已添加 DATA_DIR 到 systemd 配置"
fi

systemctl daemon-reload

# ─── 完成 ───────────────────────────────────────────────────
echo ""
echo "=============================================="
echo -e "${GREEN}  数据迁移完成！${NC}"
echo "=============================================="
echo ""
echo "📁 数据目录结构："
echo "  $DATA_DIR/"
echo "  ├── study.db          (数据库)"
echo "  ├── logs/             (运行日志)"
echo "  ├── backup/           (备份)"
echo "  ├── _tmp/papers/      (临时文件)"
echo "  ├── 数学/             (试卷图片)"
echo "  ├── 物理/"
echo "  ├── 英语/"
echo "  ├── 语文/"
echo "  └── 错题分析/         (分析结果)"
echo ""
echo "📋 后续步骤："
echo ""
echo "  1. 重启服务："
echo "     sudo systemctl restart tong-study"
echo ""
echo "  2. 验证服务正常："
echo "     sudo systemctl status tong-study"
echo "     curl http://127.0.0.1:5001"
echo ""
echo "  3. 确认无误后，可删除代码目录中的旧数据（可选）："
echo "     cd $APP_DIR"
echo "     rm -f study.db"
echo "     rm -rf 数学 物理 英语 语文 化学 生物"
echo "     rm -rf 错题分析"
echo "     rm -rf _tmp"
echo "     rm -rf logs"
echo ""
echo "⚠️  注意：在确认服务正常运行后再删除旧数据！"
echo "=============================================="