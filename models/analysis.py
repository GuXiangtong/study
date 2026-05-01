from database import get_db


def create_analysis(sub_question_id=None, question_id=None, file_path=None,
                    step1_data=None, step2_data=None, step3_data=None, step4_data=None,
                    user_id=None):
    db = get_db()
    db.execute(
        "INSERT INTO analysis_results (sub_question_id, question_id, file_path, "
        "step1_data, step2_data, step3_data, step4_data, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (sub_question_id, question_id, file_path, step1_data, step2_data, step3_data, step4_data, user_id)
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_analysis(analysis_id, user_id=None):
    db = get_db()
    query = (
        "SELECT ar.*, sq.label as sub_label, q.question_number, e.name as exam_name, "
        "s.name as subject_name FROM analysis_results ar "
        "LEFT JOIN sub_questions sq ON ar.sub_question_id = sq.id "
        "LEFT JOIN questions q ON ar.question_id = q.id OR sq.question_id = q.id "
        "LEFT JOIN exams e ON q.exam_id = e.id "
        "LEFT JOIN subjects s ON e.subject_id = s.id "
        "WHERE ar.id = ?"
    )
    params = [analysis_id]
    if user_id is not None:
        query += " AND ar.user_id = ?"
        params.append(user_id)
    row = db.execute(query, params).fetchone()
    return dict(row) if row else None


def get_analyses_by_sub_question(sub_question_id):
    db = get_db()
    return db.execute(
        "SELECT * FROM analysis_results WHERE sub_question_id = ? ORDER BY created_at DESC",
        (sub_question_id,)
    ).fetchall()


def get_analyses_by_question(question_id):
    db = get_db()
    return db.execute(
        "SELECT * FROM analysis_results WHERE question_id = ? ORDER BY created_at DESC",
        (question_id,)
    ).fetchall()
