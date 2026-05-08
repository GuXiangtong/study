"""
Tests for user-data isolation in file-serving routes.

/images/<subject>/<exam>/<filename>
    - owner gets 200
    - other user gets 403
    - unauthenticated redirects to login

/paper/temp/<task_id>/<subdir>/<filename>   (serve_temp)
/paper/temp/<task_id>/pages/<filename>      (serve_page_image)
    - owner gets 200
    - other user gets 403
    - unauthenticated redirects to login
    - non-existent task returns 404
"""
import os

import pytest

from conftest import insert_exam, login_as, make_dummy_file, make_temp_task


# ── /images/<subject>/<exam>/<filename> ──────────────────────────────

class TestServeImage:
    """Images are only served to the user who owns the exam."""

    SUBJECT = '数学'

    def _setup(self, raw_db, test_paths, user_id, exam_name):
        """Insert exam record in DB and place a dummy image on disk."""
        insert_exam(raw_db, self.SUBJECT, exam_name, user_id)
        img_path = os.path.join(
            test_paths['data'], str(user_id), self.SUBJECT, exam_name, 'q1.jpg'
        )
        make_dummy_file(img_path)

    def test_owner_gets_200(self, client, raw_db, test_paths, users):
        self._setup(raw_db, test_paths, users['a']['id'], 'img_owner')
        login_as(client, users, 'a')
        resp = client.get(f'/images/{self.SUBJECT}/img_owner/q1.jpg')
        assert resp.status_code == 200

    def test_other_user_gets_403(self, client, raw_db, test_paths, users):
        self._setup(raw_db, test_paths, users['a']['id'], 'img_403')
        login_as(client, users, 'b')
        resp = client.get(f'/images/{self.SUBJECT}/img_403/q1.jpg')
        assert resp.status_code == 403

    def test_unauthenticated_redirects(self, client, raw_db, test_paths, users):
        self._setup(raw_db, test_paths, users['a']['id'], 'img_unauth')
        resp = client.get(f'/images/{self.SUBJECT}/img_unauth/q1.jpg')
        assert resp.status_code in (302, 401)


# ── /paper/temp/<task_id>/<subdir>/<filename> ─────────────────────────

class TestServeTempFile:
    """Temp question-crop images are only accessible to the task owner."""

    def test_owner_gets_200(self, client, test_paths, users):
        make_temp_task(test_paths, 'tmp_owner', users['a']['id'])
        login_as(client, users, 'a')
        resp = client.get('/paper/temp/tmp_owner/questions/q1.jpg')
        assert resp.status_code == 200

    def test_other_user_gets_403(self, client, test_paths, users):
        make_temp_task(test_paths, 'tmp_403', users['a']['id'])
        login_as(client, users, 'b')
        resp = client.get('/paper/temp/tmp_403/questions/q1.jpg')
        assert resp.status_code == 403

    def test_unauthenticated_redirects(self, client, test_paths, users):
        make_temp_task(test_paths, 'tmp_unauth', users['a']['id'])
        resp = client.get('/paper/temp/tmp_unauth/questions/q1.jpg')
        assert resp.status_code in (302, 401)

    def test_nonexistent_task_returns_404(self, client, users):
        login_as(client, users, 'a')
        resp = client.get('/paper/temp/no_such_task_xyz/questions/q1.jpg')
        assert resp.status_code == 404


# ── /paper/temp/<task_id>/pages/<filename> ────────────────────────────

class TestServePageImage:
    """Temp page images are only accessible to the task owner."""

    def test_owner_gets_200(self, client, test_paths, users):
        make_temp_task(test_paths, 'page_owner', users['a']['id'],
                       subdir='pages', filename='p1.jpg')
        login_as(client, users, 'a')
        resp = client.get('/paper/temp/page_owner/pages/p1.jpg')
        assert resp.status_code == 200

    def test_other_user_gets_403(self, client, test_paths, users):
        make_temp_task(test_paths, 'page_403', users['a']['id'],
                       subdir='pages', filename='p1.jpg')
        login_as(client, users, 'b')
        resp = client.get('/paper/temp/page_403/pages/p1.jpg')
        assert resp.status_code == 403
