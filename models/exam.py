from database import get_db


def create_exam(subject_id, name, exam_date=None):
    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO exams (subject_id, name, exam_date) VALUES (?, ?, ?)",
        (subject_id, name, exam_date)
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


def get_all_exams():
    db = get_db()
    return db.execute(
        "SELECT e.*, s.name as subject_name FROM exams e "
        "JOIN subjects s ON e.subject_id = s.id ORDER BY e.exam_date DESC, e.id DESC"
    ).fetchall()


def get_exams_by_subject(subject_id):
    db = get_db()
    return db.execute(
        "SELECT * FROM exams WHERE subject_id = ? ORDER BY exam_date DESC, id DESC",
        (subject_id,)
    ).fetchall()


def delete_exam(exam_id):
    db = get_db()
    db.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
    db.commit()
