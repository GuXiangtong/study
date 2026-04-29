"""App-wide configuration stored in the database."""

from database import get_db

# ── Available methods ──────────────────────────────────────────────
RECOGNITION_METHODS = {
    'paddleocr_deepseek': 'PaddleOCR + DeepSeek',
    'doubao_seed': 'Doubao Seed',
}

ANALYSIS_METHODS = {
    'deepseek': 'DeepSeek',
    'doubao_seed': 'Doubao Seed',
}


def get_setting(key, default=None):
    """Get a single setting value."""
    db = get_db()
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row['value'] if row else default


def set_setting(key, value):
    """Set a single setting value."""
    db = get_db()
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = CURRENT_TIMESTAMP",
        (key, value, value),
    )
    db.commit()


def get_all_settings():
    """Return all settings as a dict."""
    db = get_db()
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    return {r['key']: r['value'] for r in rows}


def get_recognition_method():
    """Get the currently configured question recognition method."""
    return get_setting('recognition_method', 'paddleocr_deepseek')


def get_analysis_method():
    """Get the currently configured question analysis method."""
    return get_setting('analysis_method', 'deepseek')
