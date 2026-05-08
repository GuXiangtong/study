import os
from database import get_db
from werkzeug.security import generate_password_hash, check_password_hash


def create_user(username, password, is_admin=0, must_change_password=0):
    db = get_db()
    password_hash = generate_password_hash(password)
    try:
        db.execute(
            "INSERT INTO users (username, password_hash, is_admin, must_change_password) VALUES (?, ?, ?, ?)",
            (username, password_hash, is_admin, must_change_password)
        )
        db.commit()
        return db.execute("SELECT last_insert_rowid()").fetchone()[0]
    except Exception:
        return None


def get_user_by_id(user_id):
    db = get_db()
    row = db.execute(
        "SELECT id, username, is_admin, must_change_password, created_at FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    return dict(row) if row else None


def get_user_by_username(username):
    db = get_db()
    row = db.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    return dict(row) if row else None


def verify_user(username, password):
    user = get_user_by_username(username)
    if user and check_password_hash(user['password_hash'], password):
        return user
    return None


def list_all_users():
    db = get_db()
    rows = db.execute(
        "SELECT id, username, is_admin, must_change_password, created_at FROM users ORDER BY created_at"
    ).fetchall()
    return [dict(r) for r in rows]


def count_admins():
    db = get_db()
    return db.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1").fetchone()[0]


def update_password(user_id, new_password, must_change=False):
    db = get_db()
    password_hash = generate_password_hash(new_password)
    db.execute(
        "UPDATE users SET password_hash = ?, must_change_password = ? WHERE id = ?",
        (password_hash, 1 if must_change else 0, user_id)
    )
    db.commit()


def delete_user(user_id):
    import shutil
    from config import DATA_DIR, ANALYSIS_DIR

    db = get_db()
    db.execute("DELETE FROM analysis_results WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM exams WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM settings WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()

    for base_dir in (DATA_DIR, ANALYSIS_DIR):
        user_dir = os.path.join(base_dir, str(user_id))
        if os.path.isdir(user_dir):
            shutil.rmtree(user_dir, ignore_errors=True)
