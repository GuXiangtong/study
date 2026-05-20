"""
Tests for authentication routes (login, logout, change-password).
"""
import pytest
from werkzeug.security import generate_password_hash

from conftest import login_as


# ── TestLogin ─────────────────────────────────────────────────────────

class TestLogin:

    def test_login_success(self, client, users):
        resp = client.post(
            '/auth/login',
            data={'username': users['a']['username'], 'password': users['a']['password']},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        with client.session_transaction() as sess:
            assert 'user_id' in sess

    def test_login_wrong_password(self, client, users):
        resp = client.post(
            '/auth/login',
            data={'username': users['a']['username'], 'password': 'wrong_pw'},
            follow_redirects=False,
        )
        assert resp.status_code == 200
        with client.session_transaction() as sess:
            assert 'user_id' not in sess

    def test_login_unknown_user(self, client):
        resp = client.post(
            '/auth/login',
            data={'username': 'no_such_user', 'password': 'anything'},
            follow_redirects=False,
        )
        assert resp.status_code == 200
        with client.session_transaction() as sess:
            assert 'user_id' not in sess

    def test_login_empty_fields(self, client):
        resp = client.post(
            '/auth/login',
            data={'username': '', 'password': ''},
            follow_redirects=False,
        )
        assert resp.status_code == 200

    def test_login_must_change_password_redirects(self, client, raw_db, app):
        raw_db.execute(
            'INSERT OR IGNORE INTO users (username, password_hash, is_admin, must_change_password)'
            ' VALUES (?, ?, 0, 1)',
            ('must_change_user', generate_password_hash('mc_pass1')),
        )
        raw_db.commit()

        resp = client.post(
            '/auth/login',
            data={'username': 'must_change_user', 'password': 'mc_pass1'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert '/auth/change-password' in resp.headers['Location']


# ── TestLogout ────────────────────────────────────────────────────────

class TestLogout:

    def test_logout_clears_session(self, client, users):
        login_as(client, users, 'a')
        with client.session_transaction() as sess:
            assert 'user_id' in sess

        resp = client.get('/auth/logout', follow_redirects=False)
        assert resp.status_code == 302
        with client.session_transaction() as sess:
            assert 'user_id' not in sess


# ── TestChangePassword ────────────────────────────────────────────────

class TestChangePassword:

    SUBJECT = '数学'

    @pytest.fixture(autouse=True)
    def _login(self, client, users):
        login_as(client, users, 'a')

    def test_change_password_requires_login(self, app, client):
        client.get('/auth/logout')
        resp = client.get('/auth/change-password', follow_redirects=False)
        assert resp.status_code == 302

    def test_change_password_success(self, client, users, raw_db, app):
        resp = client.post(
            '/auth/change-password',
            data={
                'old_password': users['a']['password'],
                'new_password': 'new_valid_pw',
                'confirm_password': 'new_valid_pw',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        # Restore original password so other tests aren't broken
        with app.app_context():
            from models.user import update_password
            update_password(users['a']['id'], users['a']['password'], must_change=False)

    def test_change_password_clears_must_change_flag(self, client, users, raw_db, app):
        raw_db.execute(
            'UPDATE users SET must_change_password = 1 WHERE id = ?',
            (users['a']['id'],),
        )
        raw_db.commit()

        client.post(
            '/auth/change-password',
            data={
                'old_password': users['a']['password'],
                'new_password': 'new_valid_pw2',
                'confirm_password': 'new_valid_pw2',
            },
        )
        row = raw_db.execute(
            'SELECT must_change_password FROM users WHERE id = ?',
            (users['a']['id'],),
        ).fetchone()
        assert row['must_change_password'] == 0

        with app.app_context():
            from models.user import update_password
            update_password(users['a']['id'], users['a']['password'], must_change=False)

    def test_change_password_wrong_old(self, client, users):
        resp = client.post(
            '/auth/change-password',
            data={
                'old_password': 'wrong_current',
                'new_password': 'new_valid_pw',
                'confirm_password': 'new_valid_pw',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 200

    def test_change_password_too_short(self, client, users):
        resp = client.post(
            '/auth/change-password',
            data={
                'old_password': users['a']['password'],
                'new_password': 'abc',
                'confirm_password': 'abc',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 200

    def test_change_password_mismatch(self, client, users):
        resp = client.post(
            '/auth/change-password',
            data={
                'old_password': users['a']['password'],
                'new_password': 'new_valid_pw',
                'confirm_password': 'different_pw',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 200
