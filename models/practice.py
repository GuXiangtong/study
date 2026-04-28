from database import get_db


def create_practice(analysis_result_id, difficulty, content, answer=None,
                    solution_steps=None, knowledge_points=None):
    db = get_db()
    db.execute(
        "INSERT INTO practice_questions (analysis_result_id, difficulty, content, "
        "answer, solution_steps, knowledge_points) VALUES (?, ?, ?, ?, ?, ?)",
        (analysis_result_id, difficulty, content, answer, solution_steps, knowledge_points)
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_practices_by_analysis(analysis_result_id):
    db = get_db()
    return db.execute(
        "SELECT * FROM practice_questions WHERE analysis_result_id = ? "
        "ORDER BY CASE difficulty WHEN 'basic' THEN 1 WHEN 'intermediate' THEN 2 WHEN 'advanced' THEN 3 END",
        (analysis_result_id,)
    ).fetchall()


def update_practice(practice_id, **fields):
    db = get_db()
    allowed = {'content', 'answer', 'solution_steps', 'knowledge_points'}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())
    db.execute(
        f"UPDATE practice_questions SET {set_clause} WHERE id = ?",
        values + [practice_id]
    )
    db.commit()


def delete_practices_by_analysis(analysis_result_id):
    db = get_db()
    db.execute("DELETE FROM practice_questions WHERE analysis_result_id = ?", (analysis_result_id,))
    db.commit()
