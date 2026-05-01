from database import get_db
from werkzeug.security import generate_password_hash, check_password_hash


def create_user(username, password):
    db = get_db()
    password_hash = generate_password_hash(password)
    try:
        db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash)
        )
        db.commit()
        return db.execute("SELECT last_insert_rowid()").fetchone()[0]
    except db.IntegrityError:
        return None


def get_user_by_id(user_id):
    db = get_db()
    row = db.execute(
        "SELECT id, username, created_at FROM users WHERE id = ?", (user_id,)
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
