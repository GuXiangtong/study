import sqlite3
import os
from flask import g
from werkzeug.security import generate_password_hash
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


def _column_exists(db, table, column):
    cursor = db.execute(f"PRAGMA table_info({table})")
    return any(row['name'] == column for row in cursor.fetchall())


def _run_migrations(db):
    """Add users table and user_id columns to existing databases."""

    # Users table
    db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    # Insert default user for existing data (id=1)
    default_hash = generate_password_hash('changeme123')
    db.execute(
        "INSERT OR IGNORE INTO users (id, username, password_hash) VALUES (?, ?, ?)",
        (1, 'default', default_hash)
    )

    # Add user_id to exams (SQLite ALTER TABLE cannot add REFERENCES with non-NULL default)
    if not _column_exists(db, 'exams', 'user_id'):
        db.execute("ALTER TABLE exams ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")

    if not _column_exists(db, 'questions', 'user_id'):
        db.execute("ALTER TABLE questions ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")

    if not _column_exists(db, 'analysis_results', 'user_id'):
        db.execute("ALTER TABLE analysis_results ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")

    if not _column_exists(db, 'practice_questions', 'user_id'):
        db.execute("ALTER TABLE practice_questions ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")

    if not _column_exists(db, 'sub_questions', 'user_id'):
        db.execute("ALTER TABLE sub_questions ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")

    # Rebuild settings table with (user_id, key) PK
    if not _column_exists(db, 'settings', 'user_id'):
        db.executescript('''
            CREATE TABLE settings_new (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL DEFAULT 1,
                key         TEXT    NOT NULL,
                value       TEXT    NOT NULL,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, key)
            );
            INSERT INTO settings_new (user_id, key, value, updated_at)
                SELECT 1, key, value, updated_at FROM settings;
            DROP TABLE settings;
            ALTER TABLE settings_new RENAME TO settings;
        ''')

    # Indexes
    db.execute("CREATE INDEX IF NOT EXISTS idx_exams_user_id ON exams(user_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_questions_user_id ON questions(user_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_analysis_user_id ON analysis_results(user_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_practice_user_id ON practice_questions(user_id)")

    db.commit()


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

    # Run migrations to add user_dimension
    _run_migrations(db)

    db.close()


def init_app(app):
    app.teardown_appcontext(close_db)
    if not os.path.exists(DATABASE_PATH):
        with app.app_context():
            init_db()
    else:
        with app.app_context():
            db = get_db()
            db.execute('''CREATE TABLE IF NOT EXISTS settings (
                key         TEXT PRIMARY KEY,
                value       TEXT    NOT NULL,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            db.commit()
            # Run migrations on existing databases
            _run_migrations(db)
            close_db(None)
