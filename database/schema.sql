-- 参考建表语句，实际由 database/__init__.py 的 init_db() 自动创建

CREATE TABLE subjects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE exams (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id  INTEGER NOT NULL REFERENCES subjects(id),
    name        TEXT    NOT NULL,
    exam_date   DATE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(subject_id, name)
);

CREATE TABLE questions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id         INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    question_number TEXT    NOT NULL,
    stem            TEXT,
    image_path      TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sub_questions (
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

CREATE TABLE analysis_results (
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

CREATE TABLE practice_questions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_result_id  INTEGER NOT NULL REFERENCES analysis_results(id) ON DELETE CASCADE,
    difficulty          TEXT    NOT NULL,
    content             TEXT    NOT NULL,
    answer              TEXT,
    solution_steps      TEXT,
    knowledge_points    TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
