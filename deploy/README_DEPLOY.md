# tong-study 阿里云轻量应用服务器部署指南

## 目录
1. [购买服务器](#1-购买服务器)
2. [服务器初始化](#2-服务器初始化)
3. [安装系统依赖](#3-安装系统依赖)
4. [部署项目代码](#4-部署项目代码)
5. [安装Python依赖](#5-安装python依赖)
6. [配置API密钥](#6-配置api密钥)
7. [配置Gunicorn](#7-配置gunicorn)
8. [配置Systemd服务](#8-配置systemd服务)
9. [配置Nginx反向代理](#9-配置nginx反向代理)
10. [配置SSL证书（HTTPS）](#10-配置ssl证书https)
11. [防火墙配置](#11-防火墙配置)
12. [日常运维](#12-日常运维)

---

## 1. 购买服务器

### 登录阿里云控制台
1. 访问 https://www.aliyun.com/ 并登录
2. 搜索"轻量应用服务器"或直接访问 https://swas.console.aliyun.com/

### 选择配置

| 配置项 | 推荐选择 | 说明 |
|--------|----------|------|
| 地域 | 华东1（杭州）或华东2（上海） | 国内访问快 |
| 镜像 | 系统镜像 → Ubuntu 22.04 | 稳定，软件源丰富 |
| 套餐 | **2核4GB内存 + 60GB SSD + 4Mbps** | PaddleOCR需要较大内存 |
| 购买时长 | 按需（月/年） | 年付更优惠 |

> ⚠️ **关键**：如果不使用PaddleOCR（仅用豆包/Kimi视觉API），可选择2核2GB的套餐

### 完成购买
- 设置服务器密码（root密码）
- 记录分配的公网IP地址

---

## 2. 服务器初始化

### 2.1 SSH连接服务器

```bash
# Windows用户可用PowerShell或PuTTY
ssh root@你的服务器IP

# 首次连接会提示确认指纹，输入yes
```

### 2.2 创建部署用户（推荐，不直接用root）

```bash
# 创建用户
adduser deploy
# 按提示设置密码

# 赋予sudo权限
usermod -aG sudo deploy

# 切换到deploy用户
su - deploy
```

### 2.3 更新系统

```bash
sudo apt update && sudo apt upgrade -y
```

### 2.4 配置Swap空间（如果内存为2GB）

```bash
# 创建2GB swap文件
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 永久生效
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 3. 安装系统依赖

```bash
# 基础工具
sudo apt install -y git curl wget vim

# Python 3.10+ (Ubuntu 22.04自带3.10)
sudo apt install -y python3 python3-pip python3-venv

# PaddleOCR需要的系统库
sudo apt install -y libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender1

# Nginx（反向代理）
sudo apt install -y nginx

# Certbot（SSL证书，可选）
sudo apt install -y certbot python3-certbot-nginx
```

---

## 4. 部署项目代码

### 4.1 创建项目目录

```bash
sudo mkdir -p /opt/tong-study
sudo chown deploy:deploy /opt/tong-study
cd /opt/tong-study
```

### 4.2 从GitHub克隆代码

```bash
git clone https://github.com/GuXiangtong/study.git .
```

> 如果是私有仓库，需要配置SSH Key或使用Personal Access Token：
> ```bash
> git clone https://用户名:token@github.com/GuXiangtong/study.git .
> ```

### 4.3 创建必要目录

```bash
mkdir -p _tmp/papers
mkdir -p 错题分析/{数学,物理,英语,语文}
```

---

## 5. 安装Python依赖

### 5.1 创建虚拟环境

```bash
cd /opt/tong-study
python3 -m venv venv
source venv/bin/activate
```

### 5.2 升级pip

```bash
pip install --upgrade pip setuptools wheel
```

### 5.3 安装项目依赖

```bash
# 安装PaddlePaddle（CPU版，适合服务器）
pip install paddlepaddle==3.0.0 -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

# 安装其他依赖
pip install flask>=3.0 requests>=2.31 pymupdf>=1.24.0 Pillow>=10.0.0
pip install paddleocr>=3.5.0
pip install volcengine-python-sdk>=5.0.0

# 安装Gunicorn（生产WSGI服务器）
pip install gunicorn
```

> ⚠️ PaddlePaddle安装较慢，约需5-10分钟，安装包约2GB

### 5.4 验证安装

```bash
python -c "import flask; print('Flask OK')"
python -c "import paddle; print('PaddlePaddle OK')"
python -c "from paddleocr import PaddleOCR; print('PaddleOCR OK')"
```

---

## 6. 配置API密钥

```bash
mkdir -p /opt/tong-study/.claude
vim /opt/tong-study/.claude/apikey
```

写入以下内容（替换为真实密钥）：

```
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
DOUBAO_API_KEY=xxxxxxxxxxxxxxxx
MOONSHOT_API_KEY=sk-xxxxxxxxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
ANTHROPIC_BASE_URL=https://api.anthropic.com
```

设置文件权限：

```bash
chmod 600 /opt/tong-study/.claude/apikey
```

---

## 7. 配置Gunicorn

### 7.1 创建Gunicorn配置文件

```bash
vim /opt/tong-study/gunicorn.conf.py
```

写入以下内容（也可使用本目录下的 `gunicorn.conf.py`）：

```python
# Gunicorn configuration for tong-study
import multiprocessing

# 绑定地址
bind = "127.0.0.1:5001"

# 工作进程数（轻量服务器2核建议2-3个）
workers = 2

# 工作模式
worker_class = "sync"

# 超时（OCR处理可能较慢）
timeout = 300

# 最大请求数后重启worker（防止内存泄漏）
max_requests = 500
max_requests_jitter = 50

# 日志
accesslog = "/opt/tong-study/logs/access.log"
errorlog = "/opt/tong-study/logs/error.log"
loglevel = "info"

# 进程名
proc_name = "tong-study"

# 预加载应用（共享PaddleOCR模型内存）
preload_app = True
```

### 7.2 创建日志目录

```bash
mkdir -p /opt/tong-study/logs
```

### 7.3 测试启动

```bash
cd /opt/tong-study
source venv/bin/activate
gunicorn -c gunicorn.conf.py app:app
```

如果正常启动，按 `Ctrl+C` 停止。

---

## 8. 配置Systemd服务

创建服务文件，让应用开机自启并在后台运行：

```bash
sudo vim /etc/systemd/system/tong-study.service
```

写入以下内容（也可使用本目录下的 `tong-study.service`）：

```ini
[Unit]
Description=Tong Study Flask Application
After=network.target

[Service]
Type=notify
User=deploy
Group=deploy
WorkingDirectory=/opt/tong-study
Environment="PATH=/opt/tong-study/venv/bin:/usr/bin"
Environment="SECRET_KEY=your-production-secret-key-change-this"
ExecStart=/opt/tong-study/venv/bin/gunicorn -c gunicorn.conf.py app:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=5
KillMode=mixed
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

启用并启动服务：

```bash
# 重新加载systemd配置
sudo systemctl daemon-reload

# 设置开机自启
sudo systemctl enable tong-study

# 启动服务
sudo systemctl start tong-study

# 查看状态
sudo systemctl status tong-study

# 查看日志
sudo journalctl -u tong-study -f
```

---

## 9. 配置Nginx反向代理

### 9.1 创建Nginx配置

```bash
sudo vim /etc/nginx/sites-available/tong-study
```

写入以下内容（也可使用本目录下的 `nginx.conf`）：

```nginx
server {
    listen 80;
    server_name 你的域名或IP;  # 替换为实际域名或IP

    # 上传文件大小限制
    client_max_body_size 32M;

    # 静态文件（CSS/JS）
    location /static/ {
        alias /opt/tong-study/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # 题目图片
    location /images/ {
        alias /opt/tong-study/;
        expires 1d;
    }

    # 反向代理到Gunicorn
    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 超时设置（OCR处理可能较慢）
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
}
```

### 9.2 启用站点

```bash
# 创建软链接
sudo ln -s /etc/nginx/sites-available/tong-study /etc/nginx/sites-enabled/

# 删除默认站点（可选）
sudo rm /etc/nginx/sites-enabled/default

# 测试配置
sudo nginx -t

# 重启Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

---

## 10. 配置SSL证书（HTTPS）

### 方法A：使用Let's Encrypt免费证书（需要域名）

```bash
# 确保域名已解析到服务器IP
sudo certbot --nginx -d 你的域名.com

# 按提示操作，证书会自动配置到Nginx
# 自动续期测试
sudo certbot renew --dry-run
```

### 方法B：仅使用IP访问（HTTP）

如果暂时不用域名，直接用 `http://你的服务器IP` 访问即可。

> ⚠️ 如果要绑定域名且服务器在中国大陆，需要先完成ICP备案

---

## 11. 防火墙配置

### 阿里云控制台防火墙

1. 登录 [轻量应用服务器控制台](https://swas.console.aliyun.com/)
2. 进入你的服务器实例 → **防火墙**
3. 添加规则：

| 协议 | 端口 | 说明 |
|------|------|------|
| TCP | 80 | HTTP |
| TCP | 443 | HTTPS（如果使用SSL） |
| TCP | 22 | SSH（默认已开放） |

> ❌ 不要开放5001端口，Gunicorn只监听127.0.0.1

### 服务器内部防火墙（可选）

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

## 12. 日常运维

### 查看应用状态

```bash
sudo systemctl status tong-study
```

### 查看日志

```bash
# 应用日志
tail -f /opt/tong-study/logs/error.log
tail -f /opt/tong-study/logs/access.log

# systemd日志
sudo journalctl -u tong-study --since "1 hour ago"
```

### 更新代码

```bash
cd /opt/tong-study
git pull origin main
source venv/bin/activate
pip install -r requirements.txt  # 如有新依赖
sudo systemctl restart tong-study
```

### 备份数据库

```bash
# 手动备份
cp /opt/tong-study/study.db /opt/tong-study/backup/study_$(date +%Y%m%d).db

# 定时备份（crontab）
crontab -e
# 添加：每天凌晨2点备份
0 2 * * * cp /opt/tong-study/study.db /opt/tong-study/backup/study_$(date +\%Y\%m\%d).db
```

### 重启服务

```bash
sudo systemctl restart tong-study  # 重启应用
sudo systemctl restart nginx       # 重启Nginx
```

### 查看资源使用

```bash
htop          # CPU和内存
df -h         # 磁盘空间
free -h       # 内存使用
```

---

## 快速部署脚本

如果想一键执行上述步骤，可以使用 `deploy/setup.sh` 脚本。

---

## 常见问题

### Q: PaddleOCR安装失败
```bash
# 确保安装系统依赖
sudo apt install -y libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender1

# 尝试指定CPU版本（使用百度镜像源更快）
pip install paddlepaddle==3.0.0 -i https://mirror.baidu.com/pypi/simple
pip install paddleocr -i https://mirror.baidu.com/pypi/simple
```

### Q: 内存不足(OOM)导致进程被kill
```bash
# 1. 检查内存使用
free -h

# 2. 增加Swap
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 3. 减少Gunicorn worker数量（编辑gunicorn.conf.py）
workers = 1  # 改为1个worker
```

### Q: 502 Bad Gateway
```bash
# 检查Gunicorn是否在运行
sudo systemctl status tong-study

# 查看错误日志
tail -50 /opt/tong-study/logs/error.log

# 检查端口是否监听
ss -tlnp | grep 5001
```

### Q: 上传文件失败（413 Request Entity Too Large）
```bash
# 检查Nginx配置中的client_max_body_size
# 确保设置为 32M 或更大
sudo vim /etc/nginx/sites-available/tong-study
sudo systemctl restart nginx
```

### Q: pip安装太慢
```bash
# 使用国内镜像源
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或永久配置
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q: 数据库被锁(database is locked)
```bash
# SQLite在多进程写入时可能出现锁
# 解决方案1：将Gunicorn worker数设为1
# gunicorn.conf.py 中设置：
workers = 1

# 解决方案2：考虑未来迁移到PostgreSQL
```

### Q: 如何查看实时访问情况
```bash
# 查看Nginx访问日志
tail -f /var/log/nginx/access.log

# 查看应用日志
tail -f /opt/tong-study/logs/access.log

# 查看实时连接数
ss -s
```

---

## 架构图

```
                    ┌─────────────────────────────────┐
                    │         Internet (用户)           │
                    └────────────────┬────────────────┘
                                     │
                              ┌──────┴──────┐
                              │ 阿里云防火墙  │
                              │  (80/443)   │
                              └──────┬──────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │     Nginx (反向代理 + 静态文件)    │
                    │         :80 / :443               │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │     Gunicorn (WSGI Server)       │
                    │       127.0.0.1:5001             │
                    │       2 workers                  │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │      Flask App (app.py)          │
                    ├─────────────────────────────────┤
                    │  PaddleOCR    │  SQLite DB       │
                    │  (本地OCR)    │  (study.db)      │
                    ├─────────────────────────────────┤
                    │        外部 LLM API 调用          │
                    │  DeepSeek / 豆包 / Kimi / Claude  │
                    └─────────────────────────────────┘
```
