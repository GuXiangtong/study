"""App-wide configuration stored per user in the database."""

from database import get_db

RECOGNITION_METHODS = {
    'paddleocr_deepseek': 'PaddleOCR + DeepSeek',
    'doubao_seed': 'Doubao Seed',
}

ANALYSIS_METHODS = {
    'deepseek': 'DeepSeek',
    'doubao_seed': 'Doubao Seed',
}


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
