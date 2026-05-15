"""App-wide configuration stored per user in the database."""

import json

from database import get_db

RECOGNITION_METHODS = {
    'paddleocr_deepseek': 'PaddleOCR + DeepSeek',
    'doubao_seed': 'Doubao Seed',
    'kimi': 'Kimi k2.6',
}

ANALYSIS_METHODS = {
    'deepseek': 'DeepSeek',
    'anthropic': 'Anthropic (Claude)',
    'doubao_seed': 'Doubao Seed',
    'kimi': 'Kimi k2.6',
}

# Default: all models enabled
_ALL_RECOGNITION_KEYS = list(RECOGNITION_METHODS.keys())
_ALL_ANALYSIS_KEYS = list(ANALYSIS_METHODS.keys())


def get_setting(key, default=None, user_id=None):
    db = get_db()
    row = db.execute(
        "SELECT value FROM settings WHERE user_id = ? AND key = ?",
        (user_id, key)
    ).fetchone()
    return row['value'] if row else default


def set_setting(key, value, user_id=None):
    db = get_db()
    db.execute(
        "INSERT INTO settings (user_id, key, value) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, key) DO UPDATE SET value = ?, updated_at = CURRENT_TIMESTAMP",
        (user_id, key, value, value),
    )
    db.commit()


def get_all_settings(user_id=None):
    db = get_db()
    rows = db.execute(
        "SELECT key, value FROM settings WHERE user_id = ?", (user_id,)
    ).fetchall()
    return {r['key']: r['value'] for r in rows}


def get_recognition_method(user_id=None):
    return get_setting('recognition_method', 'paddleocr_deepseek', user_id)


def get_analysis_method(user_id=None):
    return get_setting('analysis_method', 'deepseek', user_id)


def get_subject_prompts(user_id=None):
    """返回 {学科名: 个性化分析提示词} 字典"""
    val = get_setting('subject_prompts', '{}', user_id)
    return json.loads(val)


def set_subject_prompts(prompts_dict, user_id=None):
    """保存 {学科名: 个性化分析提示词} 字典"""
    set_setting('subject_prompts', json.dumps(prompts_dict, ensure_ascii=False), user_id)


def get_subject_tts_prompts(user_id=None):
    """返回 {学科名: 语音讲解提示词} 字典"""
    val = get_setting('subject_tts_prompts', '{}', user_id)
    return json.loads(val)


def set_subject_tts_prompts(prompts_dict, user_id=None):
    """保存 {学科名: 语音讲解提示词} 字典"""
    set_setting('subject_tts_prompts', json.dumps(prompts_dict, ensure_ascii=False), user_id)


# ── Global model enablement (admin-only, stored with user_id=0) ──────

_ADMIN_SETTINGS_USER_ID = 0  # Global settings use user_id=0


def get_enabled_recognition_methods():
    """获取管理员启用的题目识别模型列表。返回 key 列表。"""
    val = get_setting('enabled_recognition_methods', None, user_id=_ADMIN_SETTINGS_USER_ID)
    if val is None:
        return list(_ALL_RECOGNITION_KEYS)
    try:
        enabled = json.loads(val)
        # Filter to valid keys only
        return [k for k in enabled if k in RECOGNITION_METHODS]
    except (json.JSONDecodeError, TypeError):
        return list(_ALL_RECOGNITION_KEYS)


def set_enabled_recognition_methods(keys):
    """设置管理员启用的题目识别模型列表。"""
    valid = [k for k in keys if k in RECOGNITION_METHODS]
    if not valid:
        valid = list(_ALL_RECOGNITION_KEYS)  # At least one must be enabled
    set_setting('enabled_recognition_methods',
                json.dumps(valid, ensure_ascii=False),
                user_id=_ADMIN_SETTINGS_USER_ID)


def get_enabled_analysis_methods():
    """获取管理员启用的题目分析模型列表。返回 key 列表。"""
    val = get_setting('enabled_analysis_methods', None, user_id=_ADMIN_SETTINGS_USER_ID)
    if val is None:
        return list(_ALL_ANALYSIS_KEYS)
    try:
        enabled = json.loads(val)
        return [k for k in enabled if k in ANALYSIS_METHODS]
    except (json.JSONDecodeError, TypeError):
        return list(_ALL_ANALYSIS_KEYS)


def set_enabled_analysis_methods(keys):
    """设置管理员启用的题目分析模型列表。"""
    valid = [k for k in keys if k in ANALYSIS_METHODS]
    if not valid:
        valid = list(_ALL_ANALYSIS_KEYS)  # At least one must be enabled
    set_setting('enabled_analysis_methods',
                json.dumps(valid, ensure_ascii=False),
                user_id=_ADMIN_SETTINGS_USER_ID)


def get_available_recognition_methods():
    """获取用户可选的题目识别方法（已被管理员启用的）。返回 {key: label} 字典。"""
    enabled = get_enabled_recognition_methods()
    return {k: v for k, v in RECOGNITION_METHODS.items() if k in enabled}


def get_available_analysis_methods():
    """获取用户可选的题目分析方法（已被管理员启用的）。返回 {key: label} 字典。"""
    enabled = get_enabled_analysis_methods()
    return {k: v for k, v in ANALYSIS_METHODS.items() if k in enabled}


def fix_user_model_settings(user_id):
    """检查用户当前选择的模型是否仍被启用，若已禁用则自动切换到第一个可用模型。
    
    在用户登录时调用。返回是否有修改。
    """
    changed = False
    
    # Check recognition method
    current_recognition = get_recognition_method(user_id)
    enabled_recognition = get_enabled_recognition_methods()
    if current_recognition not in enabled_recognition:
        new_method = enabled_recognition[0] if enabled_recognition else 'paddleocr_deepseek'
        set_setting('recognition_method', new_method, user_id=user_id)
        changed = True
    
    # Check analysis method
    current_analysis = get_analysis_method(user_id)
    enabled_analysis = get_enabled_analysis_methods()
    if current_analysis not in enabled_analysis:
        new_method = enabled_analysis[0] if enabled_analysis else 'deepseek'
        set_setting('analysis_method', new_method, user_id=user_id)
        changed = True
    
    return changed