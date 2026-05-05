from database import get_db


def get_chats(analysis_id, user_id):
    db = get_db()
    rows = db.execute(
        "SELECT role, content, created_at FROM analysis_chats "
        "WHERE analysis_id = ? AND user_id = ? ORDER BY created_at",
        (analysis_id, user_id)
    ).fetchall()
    return [dict(r) for r in rows]


def add_chat_messages(analysis_id, user_id, user_content, assistant_content):
    db = get_db()
    db.execute(
        "INSERT INTO analysis_chats (analysis_id, user_id, role, content) VALUES (?, ?, 'user', ?)",
        (analysis_id, user_id, user_content)
    )
    db.execute(
        "INSERT INTO analysis_chats (analysis_id, user_id, role, content) VALUES (?, ?, 'assistant', ?)",
        (analysis_id, user_id, assistant_content)
    )
    db.commit()
