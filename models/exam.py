from database import get_db


def create_exam(subject_id, name, exam_date=None, user_id=None):
    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO exams (subject_id, name, exam_date, user_id) VALUES (?, ?, ?, ?)",
        (subject_id, name, exam_date, user_id)
    )
    db.commit()
    row = db.execute(
        "SELECT * FROM exams WHERE subject_id = ? AND name = ?", (subject_id, name)
    ).fetchone()
    return dict(row) if row else None


def get_exam(exam_id):
    db = get_db()
    row = db.execute("SELECT * FROM exams WHERE id = ?", (exam_id,)).fetchone()
    return dict(row) if row else None


def get_all_exams(user_id=None):
    db = get_db()
    query = (
        "SELECT e.*, s.name as subject_name FROM exams e "
        "JOIN subjects s ON e.subject_id = s.id WHERE 1=1"
    )
    params = []
    if user_id is not None:
        query += " AND e.user_id = ?"
        params.append(user_id)
    query += " ORDER BY e.exam_date DESC, e.id DESC"
    return db.execute(query, params).fetchall()


def get_exams_by_subject(subject_id, user_id=None):
    db = get_db()
    query = "SELECT * FROM exams WHERE subject_id = ?"
    params = [subject_id]
    if user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)
    query += " ORDER BY exam_date DESC, id DESC"
    return db.execute(query, params).fetchall()


def delete_exam(exam_id):
    db = get_db()
    db.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
    db.commit()
