"""
Tests for per-user data isolation at the model and route layers.

Covers:
  - Practice queries are filtered by user_id
  - Deleting a user cascades: DB records and file directories both removed
  - Deleting an exam only removes the owning user's directory
  - Deleting an analysis removes the file from the correct user's directory
  - Deleting a question removes the file from the correct user's directory
"""
import os

import pytest

from conftest import (
    insert_analysis,
    insert_exam,
    insert_practice,
    insert_question,
    login_as,
    make_dummy_file,
)


# ── Practice model: user_id filter ───────────────────────────────────

class TestPracticeModel:
    """get_practices_by_analysis() must honour the user_id filter."""

    SUBJECT = '语文'

    @pytest.fixture(scope='class')
    def practice_data(self, raw_db, users):
        """One analysis record with one practice owned by user_a."""
        exam_id = insert_exam(raw_db, self.SUBJECT, 'prac_test_exam', users['a']['id'])
        q_id    = insert_question(raw_db, exam_id,
                                  f'{self.SUBJECT}/prac_test_exam/q1.jpg',
                                  users['a']['id'])
        ar_id   = insert_analysis(raw_db, q_id,
                                  f'{self.SUBJECT}/prac_test.md',
                                  users['a']['id'])
        insert_practice(raw_db, ar_id, users['a']['id'])
        return ar_id

    def test_owner_receives_practices(self, app, practice_data, users):
        from models.practice import get_practices_by_analysis
        with app.app_context():
            rows = get_practices_by_analysis(practice_data, user_id=users['a']['id'])
        assert len(rows) >= 1

    def test_other_user_receives_empty_list(self, app, practice_data, users):
        from models.practice import get_practices_by_analysis
        with app.app_context():
            rows = get_practices_by_analysis(practice_data, user_id=users['b']['id'])
        assert rows == [] or len(rows) == 0


# ── User deletion ─────────────────────────────────────────────────────

class TestDeleteUser:
    """delete_user() must remove both DB records and file directories."""

    def _create_temp_user(self, raw_db, username):
        from werkzeug.security import generate_password_hash
        raw_db.execute(
            'INSERT OR IGNORE INTO users (username, password_hash, is_admin)'
            ' VALUES (?, ?, 0)',
            (username, generate_password_hash('tmppassword')),
        )
        raw_db.commit()
        return raw_db.execute(
            'SELECT id FROM users WHERE username = ?', (username,)
        ).fetchone()['id']

    def test_data_dirs_are_removed(self, app, raw_db, test_paths):
        uid = self._create_temp_user(raw_db, 'tmp_del_dirs')
        data_dir = os.path.join(test_paths['data'],     str(uid))
        ana_dir  = os.path.join(test_paths['analysis'], str(uid))
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(ana_dir,  exist_ok=True)

        from models.user import delete_user
        with app.app_context():
            delete_user(uid)

        assert not os.path.isdir(data_dir), 'DATA_DIR/{user_id} should be deleted'
        assert not os.path.isdir(ana_dir),  'ANALYSIS_DIR/{user_id} should be deleted'

    def test_db_records_are_cascaded(self, app, raw_db, test_paths):
        uid     = self._create_temp_user(raw_db, 'tmp_del_records')
        exam_id = insert_exam(raw_db, '英语', 'del_records_exam', uid)
        raw_db.execute(
            'INSERT INTO settings (user_id, key, value) VALUES (?, ?, ?)',
            (uid, 'method', 'deepseek'),
        )
        raw_db.commit()

        from models.user import delete_user
        with app.app_context():
            delete_user(uid)

        def count(table):
            return raw_db.execute(
                f'SELECT COUNT(*) FROM {table} WHERE user_id = ?', (uid,)
            ).fetchone()[0]

        assert raw_db.execute(
            'SELECT COUNT(*) FROM users WHERE id = ?', (uid,)
        ).fetchone()[0] == 0
        assert count('exams')    == 0
        assert count('settings') == 0


# ── Exam deletion: only the owner's directory is removed ─────────────

class TestExamDeletion:
    """Deleting an exam must not touch another user's directory."""

    SUBJECT = '物理'

    def test_only_owners_dir_is_removed(self, client, raw_db, test_paths, users):
        uid_a = users['a']['id']
        uid_b = users['b']['id']

        exam_a_id = insert_exam(raw_db, self.SUBJECT, 'exam_del_a', uid_a)
        insert_exam(raw_db, self.SUBJECT, 'exam_del_b', uid_b)

        dir_a = os.path.join(test_paths['data'], str(uid_a), self.SUBJECT, 'exam_del_a')
        dir_b = os.path.join(test_paths['data'], str(uid_b), self.SUBJECT, 'exam_del_b')
        os.makedirs(dir_a, exist_ok=True)
        os.makedirs(dir_b, exist_ok=True)

        login_as(client, users, 'a')
        client.post(f'/exams/{exam_a_id}/delete', follow_redirects=True)

        assert not os.path.isdir(dir_a), "Owner's exam dir should be deleted"
        assert os.path.isdir(dir_b),     "Other user's exam dir must not be touched"


# ── Analysis deletion: correct user directory ─────────────────────────

class TestAnalysisDeletion:
    """DELETE /analysis/<id>/delete must remove the file from ANALYSIS_DIR/{user_id}/."""

    SUBJECT = '化学'

    def test_analysis_file_removed_from_user_dir(
        self, client, raw_db, test_paths, users
    ):
        uid_a   = users['a']['id']
        exam_id = insert_exam(raw_db, self.SUBJECT, 'ana_del_exam', uid_a)
        q_id    = insert_question(raw_db, exam_id,
                                  f'{self.SUBJECT}/ana_del_exam/q1.jpg', uid_a)
        file_path = f'{self.SUBJECT}/ana_del.md'
        ar_id     = insert_analysis(raw_db, q_id, file_path, uid_a)

        ana_file = os.path.join(test_paths['analysis'], str(uid_a), file_path)
        make_dummy_file(ana_file)
        assert os.path.isfile(ana_file), 'pre-condition: file must exist before delete'

        login_as(client, users, 'a')
        client.post(f'/analysis/{ar_id}/delete', follow_redirects=True)

        assert not os.path.isfile(ana_file), 'Analysis file should be deleted'


# ── Question deletion: correct user directory ─────────────────────────

class TestQuestionDeletion:
    """DELETE /questions/<id>/delete must remove the image from DATA_DIR/{user_id}/."""

    SUBJECT = '生物'

    def test_question_image_removed_from_user_dir(
        self, client, raw_db, test_paths, users
    ):
        uid_a     = users['a']['id']
        exam_id   = insert_exam(raw_db, self.SUBJECT, 'q_del_exam', uid_a)
        img_rel   = f'{self.SUBJECT}/q_del_exam/q_del.jpg'
        q_id      = insert_question(raw_db, exam_id, img_rel, uid_a)

        img_file  = os.path.join(test_paths['data'], str(uid_a), img_rel)
        make_dummy_file(img_file)
        assert os.path.isfile(img_file), 'pre-condition: image must exist before delete'

        login_as(client, users, 'a')
        client.post(f'/questions/{q_id}/delete', follow_redirects=True)

        assert not os.path.isfile(img_file), 'Question image should be deleted'
