"""
Tests for exam management routes (creation, deletion authorization).
"""
import pytest

from conftest import insert_exam, login_as


# ── TestExamCreation ──────────────────────────────────────────────────

class TestExamCreation:

    @pytest.fixture(autouse=True)
    def _login(self, client, users):
        login_as(client, users, 'a')

    def _subject_id(self, raw_db, name='数学'):
        return raw_db.execute(
            'SELECT id FROM subjects WHERE name = ?', (name,)
        ).fetchone()['id']

    def test_create_exam_success(self, client, raw_db, users):
        subject_id = self._subject_id(raw_db)
        before = raw_db.execute(
            'SELECT COUNT(*) FROM exams WHERE user_id = ?', (users['a']['id'],)
        ).fetchone()[0]

        resp = client.post(
            '/exams/create',
            data={'subject_id': subject_id, 'name': '2024期中考试'},
            follow_redirects=False,
        )
        assert resp.status_code == 302

        after = raw_db.execute(
            'SELECT COUNT(*) FROM exams WHERE user_id = ?', (users['a']['id'],)
        ).fetchone()[0]
        assert after == before + 1

    def test_create_exam_missing_name(self, client, raw_db, users):
        subject_id = self._subject_id(raw_db)
        before = raw_db.execute('SELECT COUNT(*) FROM exams').fetchone()[0]

        resp = client.post(
            '/exams/create',
            data={'subject_id': subject_id, 'name': ''},
            follow_redirects=False,
        )
        assert resp.status_code == 302

        after = raw_db.execute('SELECT COUNT(*) FROM exams').fetchone()[0]
        assert after == before, 'no exam should be created without a name'

    def test_create_exam_missing_subject(self, client, raw_db, users):
        before = raw_db.execute('SELECT COUNT(*) FROM exams').fetchone()[0]

        resp = client.post(
            '/exams/create',
            data={'name': '无学科考试'},
            follow_redirects=False,
        )
        assert resp.status_code == 302

        after = raw_db.execute('SELECT COUNT(*) FROM exams').fetchone()[0]
        assert after == before, 'no exam should be created without a subject'


# ── TestExamDeletionAuth ──────────────────────────────────────────────

class TestExamDeletionAuth:

    SUBJECT = '英语'

    def test_cannot_delete_others_exam(self, client, raw_db, test_paths, users):
        exam_id = insert_exam(raw_db, self.SUBJECT, 'auth_del_exam', users['a']['id'])

        login_as(client, users, 'b')
        resp = client.post(f'/exams/{exam_id}/delete', follow_redirects=False)
        assert resp.status_code == 302

        row = raw_db.execute(
            'SELECT id FROM exams WHERE id = ?', (exam_id,)
        ).fetchone()
        assert row is not None, "user B must not be able to delete user A's exam"
