from database import get_db


def create_sub_question(question_id, label, content=None, correct_answer=None,
                        student_answer=None, error_reason=None, error_type=None,
                        knowledge_points=None, user_id=None):
    db = get_db()
    db.execute(
        "INSERT INTO sub_questions (question_id, label, content, correct_answer, "
        "student_answer, error_reason, error_type, knowledge_points, user_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (question_id, label, content, correct_answer, student_answer,
         error_reason, error_type, knowledge_points, user_id)
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_sub_question(sub_question_id, user_id=None):
    db = get_db()
    query = (
        "SELECT sq.*, q.question_number, q.stem as question_stem, q.image_path, "
        "e.name as exam_name, s.name as subject_name "
        "FROM sub_questions sq JOIN questions q ON sq.question_id = q.id "
        "JOIN exams e ON q.exam_id = e.id JOIN subjects s ON e.subject_id = s.id "
        "WHERE sq.id = ?"
    )
    params = [sub_question_id]
    if user_id is not None:
        query += " AND sq.user_id = ?"
        params.append(user_id)
    row = db.execute(query, params).fetchone()
    return dict(row) if row else None


def get_sub_questions_by_question(question_id):
    db = get_db()
    return db.execute(
        "SELECT * FROM sub_questions WHERE question_id = ? ORDER BY label", (question_id,)
    ).fetchall()


def update_sub_question(sub_question_id, **fields):
    db = get_db()
    allowed = {'label', 'content', 'correct_answer', 'student_answer',
               'error_reason', 'error_type', 'knowledge_points'}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())
    db.execute(
        f"UPDATE sub_questions SET updated_at = CURRENT_TIMESTAMP, {set_clause} WHERE id = ?",
        values + [sub_question_id]
    )
    db.commit()


def delete_sub_question(sub_question_id):
    db = get_db()
    db.execute("DELETE FROM sub_questions WHERE id = ?", (sub_question_id,))
    db.commit()
