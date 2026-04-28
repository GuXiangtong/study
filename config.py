import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'study.db')
ANALYSIS_DIR = os.path.join(BASE_DIR, '错题分析')

SUBJECTS = ['语文', '数学', '英语', '物理', '化学', '生物']

UPLOAD_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

SECRET_KEY = os.environ.get('SECRET_KEY', 'study-app-dev-key-gaokao')

# LLM API configuration
_apikey_path = os.path.join(BASE_DIR, '.claude', 'apikey')
if os.path.exists(_apikey_path):
    with open(_apikey_path) as f:
        LLM_API_KEY = f.read().strip()
else:
    LLM_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')

LLM_API_URL = 'https://api.deepseek.com/chat/completions'
LLM_MODEL = 'deepseek-chat'
