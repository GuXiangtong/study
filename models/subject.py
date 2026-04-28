from database import get_db


def get_all_subjects():
    db = get_db()
    return db.execute("SELECT * FROM subjects ORDER BY id").fetchall()


def get_subject(subject_id):
    db = get_db()
    return db.execute("SELECT * FROM subjects WHERE id = ?", (subject_id,)).fetchone()


def get_subject_by_name(name):
    db = get_db()
    return db.execute("SELECT * FROM subjects WHERE name = ?", (name,)).fetchone()
