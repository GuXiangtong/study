from database import get_db


def create_question(exam_id, question_number, stem=None, image_path=None, user_id=None):
    db = get_db()
    db.execute(
        "INSERT INTO questions (exam_id, question_number, stem, image_path, user_id) VALUES (?, ?, ?, ?, ?)",
        (exam_id, question_number, stem, image_path, user_id)
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_question(question_id, user_id=None):
    db = get_db()
    query = (
        "SELECT q.*, e.name as exam_name, e.subject_id, e.user_id, s.name as subject_name "
        "FROM questions q JOIN exams e ON q.exam_id = e.id "
        "JOIN subjects s ON e.subject_id = s.id WHERE q.id = ?"
    )
    params = [question_id]
    if user_id is not None:
        query += " AND e.user_id = ?"
        params.append(user_id)
    row = db.execute(query, params).fetchone()
    return dict(row) if row else None


def get_questions_by_exam(exam_id):
    db = get_db()
    return db.execute(
        "SELECT * FROM questions WHERE exam_id = ? ORDER BY question_number", (exam_id,)
    ).fetchall()


def get_questions_filtered(subject_id=None, exam_id=None, search=None, user_id=None):
    db = get_db()
    query = (
        "SELECT q.*, e.name as exam_name, e.subject_id, s.name as subject_name "
        "FROM questions q JOIN exams e ON q.exam_id = e.id "
        "JOIN subjects s ON e.subject_id = s.id WHERE 1=1"
    )
    params = []
    if user_id is not None:
        query += " AND e.user_id = ?"
        params.append(user_id)
    if subject_id:
        query += " AND e.subject_id = ?"
        params.append(subject_id)
    if exam_id:
        query += " AND q.exam_id = ?"
        params.append(exam_id)
    if search:
        query += " AND (q.stem LIKE ? OR q.question_number LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    query += " ORDER BY q.created_at DESC"
    return db.execute(query, params).fetchall()


def update_question(question_id, **fields):
    db = get_db()
    allowed = {'question_number', 'stem', 'image_path'}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())
    db.execute(
        f"UPDATE questions SET updated_at = CURRENT_TIMESTAMP, {set_clause} WHERE id = ?",
        values + [question_id]
    )
    db.commit()


def delete_question(question_id):
    db = get_db()
    db.execute("DELETE FROM questions WHERE id = ?", (question_id,))
    db.commit()
