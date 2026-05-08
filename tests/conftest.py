"""
Shared fixtures and helpers for user-data-isolation tests.

Module-level path variables are patched at session scope so that all Flask
route handlers, services, and models read from the temporary test directories
for the entire pytest run.
"""
import json
import os
import shutil
import sqlite3
import tempfile

import pytest
from werkzeug.security import generate_password_hash


# ── Temp filesystem ──────────────────────────────────────────────────

def _cleanup_stale_test_dirs():
    """Remove any tong_study_test_* directories left by crashed previous runs."""
    tmp = tempfile.gettempdir()
    for name in os.listdir(tmp):
        if name.startswith('tong_study_test_'):
            shutil.rmtree(os.path.join(tmp, name), ignore_errors=True)


@pytest.fixture(scope='session')
def tmp_root():
    _cleanup_stale_test_dirs()
    d = tempfile.mkdtemp(prefix='tong_study_test_')
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(scope='session')
def test_paths(tmp_root):
    paths = {
        'data':       os.path.join(tmp_root, 'data'),
        'analysis':   os.path.join(tmp_root, '错题分析'),
        'paper_temp': os.path.join(tmp_root, '_tmp', 'papers'),
        'db':         os.path.join(tmp_root, 'test.db'),
    }
    for key in ('data', 'analysis', 'paper_temp'):
        os.makedirs(paths[key], exist_ok=True)
    return paths


# ── Flask app (session-scoped, all modules patched once) ─────────────

@pytest.fixture(scope='session')
def app(test_paths):
    # 1. Patch config module attributes before anything else imports them.
    import config
    config.DATA_DIR       = test_paths['data']
    config.DATABASE_PATH  = test_paths['db']
    config.ANALYSIS_DIR   = test_paths['analysis']
    config.PAPER_TEMP_DIR = test_paths['paper_temp']

    # 2. Patch module-level names that were captured via 'from config import X'.
    import database
    database.DATABASE_PATH = test_paths['db']

    import routes.questions
    import routes.exams
    import routes.analysis
    import routes.paper
    import services.paper_service

    routes.questions.DATA_DIR           = test_paths['data']
    routes.exams.DATA_DIR               = test_paths['data']
    routes.analysis.ANALYSIS_DIR        = test_paths['analysis']
    routes.paper.DATA_DIR               = test_paths['data']
    routes.paper.PAPER_TEMP_DIR         = test_paths['paper_temp']
    services.paper_service.PAPER_TEMP_DIR = test_paths['paper_temp']

    # 3. Initialise a fresh test database.
    from database import init_db
    init_db()

    # 4. Create and configure the Flask test app.
    from app import app as flask_app
    import app as app_module
    app_module.DATA_DIR = test_paths['data']  # used in serve_image route

    flask_app.config['TESTING'] = True
    flask_app.config['SECRET_KEY'] = 'test-secret'
    return flask_app


# ── Raw DB connection (for test-data setup, no Flask context needed) ──

@pytest.fixture(scope='session')
def raw_db(test_paths, app):
    conn = sqlite3.connect(test_paths['db'])
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    yield conn
    conn.close()


# ── Persistent test users ─────────────────────────────────────────────

@pytest.fixture(scope='session')
def users(raw_db):
    for username, password in [('test_user_a', 'pw_a'), ('test_user_b', 'pw_b')]:
        raw_db.execute(
            'INSERT OR IGNORE INTO users (username, password_hash, is_admin) VALUES (?, ?, 0)',
            (username, generate_password_hash(password)),
        )
    raw_db.commit()

    def uid(name):
        return raw_db.execute(
            'SELECT id FROM users WHERE username = ?', (name,)
        ).fetchone()['id']

    return {
        'a': {'id': uid('test_user_a'), 'username': 'test_user_a', 'password': 'pw_a'},
        'b': {'id': uid('test_user_b'), 'username': 'test_user_b', 'password': 'pw_b'},
    }


# ── Per-test HTTP client ──────────────────────────────────────────────

@pytest.fixture
def client(app):
    return app.test_client()


# ── Helpers (importable by test modules) ──────────────────────────────

def login_as(client, users, which='a'):
    """Log the test client in as user 'a' or 'b'."""
    u = users[which]
    client.post(
        '/auth/login',
        data={'username': u['username'], 'password': u['password']},
        follow_redirects=True,
    )


def make_dummy_file(path):
    """Create a 4-byte placeholder file, creating parent directories as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(b'test')


def insert_exam(raw_db, subject_name, exam_name, user_id):
    """Insert an exam row and return its id (raises on duplicate name)."""
    subject_id = raw_db.execute(
        'SELECT id FROM subjects WHERE name = ?', (subject_name,)
    ).fetchone()['id']
    raw_db.execute(
        'INSERT INTO exams (subject_id, name, user_id) VALUES (?, ?, ?)',
        (subject_id, exam_name, user_id),
    )
    raw_db.commit()
    return raw_db.execute(
        'SELECT id FROM exams WHERE subject_id = ? AND name = ?',
        (subject_id, exam_name),
    ).fetchone()['id']


def insert_question(raw_db, exam_id, image_path, user_id):
    """Insert a question row and return its id."""
    raw_db.execute(
        'INSERT INTO questions (exam_id, question_number, image_path, user_id)'
        ' VALUES (?, ?, ?, ?)',
        (exam_id, '1', image_path, user_id),
    )
    raw_db.commit()
    return raw_db.execute('SELECT last_insert_rowid()').fetchone()[0]


def insert_analysis(raw_db, question_id, file_path, user_id):
    """Insert an analysis_results row and return its id."""
    raw_db.execute(
        'INSERT INTO analysis_results (question_id, file_path, model, user_id)'
        ' VALUES (?, ?, ?, ?)',
        (question_id, file_path, 'test', user_id),
    )
    raw_db.commit()
    return raw_db.execute('SELECT last_insert_rowid()').fetchone()[0]


def insert_practice(raw_db, analysis_id, user_id):
    """Insert a practice_questions row and return its id."""
    raw_db.execute(
        'INSERT INTO practice_questions'
        ' (analysis_result_id, difficulty, content, user_id)'
        ' VALUES (?, ?, ?, ?)',
        (analysis_id, 'basic', '练习题内容', user_id),
    )
    raw_db.commit()
    return raw_db.execute('SELECT last_insert_rowid()').fetchone()[0]


def make_temp_task(test_paths, task_id, user_id, subdir='questions', filename='q1.jpg'):
    """Create a paper-processing task directory with result.json and a dummy image."""
    task_dir = os.path.join(test_paths['paper_temp'], task_id)
    os.makedirs(os.path.join(task_dir, subdir), exist_ok=True)
    with open(os.path.join(task_dir, 'result.json'), 'w', encoding='utf-8') as f:
        json.dump({'task_id': task_id, 'user_id': user_id, 'questions': []}, f)
    make_dummy_file(os.path.join(task_dir, subdir, filename))
