import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# 数据目录：用户数据（数据库、图片、分析结果）存放位置
# 生产环境通过环境变量 DATA_DIR 指定独立数据目录（如 /opt/tong-study-data）
# 开发环境不设置则默认与代码同目录
DATA_DIR = os.environ.get('DATA_DIR', BASE_DIR)

DATABASE_PATH = os.path.join(DATA_DIR, 'study.db')
ANALYSIS_DIR = os.path.join(DATA_DIR, '错题分析')

SUBJECTS = ['语文', '数学', '英语', '物理', '化学', '生物', '日语']

UPLOAD_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
PAPER_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}
MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32 MB
PAPER_TEMP_DIR = os.path.join(DATA_DIR, '_tmp', 'papers')
LOG_DIR = os.path.join(DATA_DIR, '_tmp')

SECRET_KEY = os.environ.get('SECRET_KEY', 'study-app-dev-key-gaokao')

# LLM API configuration
_apikey_path = os.path.join(BASE_DIR, '.claude', 'apikey')
_apikeys = {}
if os.path.exists(_apikey_path):
    with open(_apikey_path) as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                key, val = line.split('=', 1)
                _apikeys[key.strip()] = val.strip()

DEEPSEEK_API_KEY = _apikeys.get('DEEPSEEK_API_KEY', os.environ.get('DEEPSEEK_API_KEY', ''))
DOUBAO_API_KEY = _apikeys.get('DOUBAO_API_KEY', os.environ.get('DOUBAO_API_KEY', ''))
MOONSHOT_API_KEY = _apikeys.get('MOONSHOT_API_KEY', os.environ.get('MOONSHOT_API_KEY', ''))

# DeepSeek (Anthropic-compatible endpoint)
DEEPSEEK_API_URL = 'https://api.deepseek.com/anthropic/v1/messages'
DEEPSEEK_MODEL = 'deepseek-v4-pro'

# Anthropic (Claude) — supports proxy via ANTHROPIC_BASE_URL
ANTHROPIC_API_KEY = _apikeys.get('ANTHROPIC_API_KEY', os.environ.get('ANTHROPIC_API_KEY', ''))
_anthropic_base = _apikeys.get('ANTHROPIC_BASE_URL', os.environ.get('ANTHROPIC_BASE_URL', '')).rstrip('/')
ANTHROPIC_API_URL = f'{_anthropic_base}/v1/messages' if _anthropic_base else 'https://api.anthropic.com/v1/messages'
ANTHROPIC_MODEL = 'claude-opus-4-6'

# Doubao Seed (ByteDance Ark)
DOUBAO_API_URL = 'https://ark.cn-beijing.volces.com/api/v3/chat/completions'
DOUBAO_BASE_URL = 'https://ark.cn-beijing.volces.com/api/v3'
DOUBAO_MODEL = 'doubao-seed-2-1-pro-260628'
DOUBAO_VISION_MODEL = 'doubao-seed-2-1-pro-260628'

# Kimi (Moonshot AI) — OpenAI-compatible, supports vision
KIMI_API_URL = 'https://api.moonshot.cn/v1/chat/completions'
KIMI_MODEL = 'kimi-k2.6'
