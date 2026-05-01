import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'study.db')
ANALYSIS_DIR = os.path.join(BASE_DIR, '错题分析')

SUBJECTS = ['语文', '数学', '英语', '物理', '化学', '生物']

UPLOAD_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
PAPER_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}
MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32 MB
PAPER_TEMP_DIR = os.path.join(BASE_DIR, '_tmp', 'papers')

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

# DeepSeek
DEEPSEEK_API_URL = 'https://api.deepseek.com/chat/completions'
DEEPSEEK_MODEL = 'deepseek-chat'

# Doubao Seed (ByteDance Ark)
DOUBAO_API_URL = 'https://ark.cn-beijing.volces.com/api/v3/chat/completions'
DOUBAO_BASE_URL = 'https://ark.cn-beijing.volces.com/api/v3'
DOUBAO_MODEL = 'doubao-seed-1-6'
DOUBAO_VISION_MODEL = 'doubao-seed-1-6-vision-250815'

# Legacy alias (used by existing code)
LLM_API_KEY = DEEPSEEK_API_KEY
LLM_API_URL = DEEPSEEK_API_URL
LLM_MODEL = DEEPSEEK_MODEL
