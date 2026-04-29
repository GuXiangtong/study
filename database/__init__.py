import sqlite3
import os
from flask import g
from config import DATABASE_PATH, SUBJECTS


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE_PATH)
    db.executescript('''
        CREATE TABLE IF NOT EXISTS subjects (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS exams (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id  INTEGER NOT NULL REFERENCES subjects(id),
            name        TEXT    NOT NULL,
            exam_date   DATE,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(subject_id, name)
        );

        CREATE TABLE IF NOT EXISTS questions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id         INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
            question_number TEXT    NOT NULL,
            stem            TEXT,
            image_path      TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sub_questions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id     INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            label           TEXT    NOT NULL,
            content         TEXT,
            correct_answer  TEXT,
            student_answer  TEXT,
            error_reason    TEXT,
            error_type      TEXT,
            knowledge_points TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS analysis_results (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sub_question_id INTEGER REFERENCES sub_questions(id) ON DELETE SET NULL,
            question_id     INTEGER REFERENCES questions(id) ON DELETE SET NULL,
            file_path       TEXT,
            step1_data      TEXT,
            step2_data      TEXT,
            step3_data      TEXT,
            step4_data      TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS practice_questions (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_result_id  INTEGER NOT NULL REFERENCES analysis_results(id) ON DELETE CASCADE,
            difficulty          TEXT    NOT NULL,
            content             TEXT    NOT NULL,
            answer              TEXT,
            solution_steps      TEXT,
            knowledge_points    TEXT,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS settings (
            key         TEXT PRIMARY KEY,
            value       TEXT    NOT NULL,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    for subj in SUBJECTS:
        db.execute("INSERT OR IGNORE INTO subjects (name) VALUES (?)", (subj,))

    db.commit()
    db.close()


def init_app(app):
    app.teardown_appcontext(close_db)
    if not os.path.exists(DATABASE_PATH):
        with app.app_context():
            init_db()
    else:
        # Ensure new tables exist on existing databases
        with app.app_context():
            db = get_db()
            db.execute('''CREATE TABLE IF NOT EXISTS settings (
                key         TEXT PRIMARY KEY,
                value       TEXT    NOT NULL,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            db.commit()
