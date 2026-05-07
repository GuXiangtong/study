# Gunicorn configuration for tong-study
# 部署路径: /opt/tong-study/gunicorn.conf.py

# 绑定地址（仅本地，由Nginx反向代理对外）
bind = "127.0.0.1:5001"

# 工作进程数（轻量服务器2核建议2个）
workers = 2

# 工作模式（sync适合IO密集型+OCR处理）
worker_class = "sync"

# 超时时间（秒）- OCR和LLM处理可能较慢
timeout = 300

# 优雅关闭超时
graceful_timeout = 30

# 每个worker处理指定数量请求后自动重启（防止内存泄漏）
max_requests = 500
max_requests_jitter = 50

# 日志配置（日志放在数据目录，不随代码更新）
accesslog = "/opt/tong-study-data/logs/access.log"
errorlog = "/opt/tong-study-data/logs/error.log"
loglevel = "info"

# 访问日志格式
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 进程名称
proc_name = "tong-study"

# 预加载应用（多个worker共享PaddleOCR模型，节省内存）
preload_app = True

# PID文件
pidfile = "/opt/tong-study-data/logs/gunicorn.pid"
