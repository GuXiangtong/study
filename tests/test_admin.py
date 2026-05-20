"""
Tests for admin user management routes.
"""
import pytest
from werkzeug.security import generate_password_hash

from conftest import login_as, login_as_admin


# ── TestUserCreation ──────────────────────────────────────────────────

class TestUserCreation:

    @pytest.fixture(autouse=True)
    def _login(self, client, admin_user):
        login_as_admin(client, admin_user)

    def test_create_user_success(self, client, raw_db, app):
        resp = client.post(
            '/admin/users/create',
            data={'username': 'new_test_user', 'password': 'valid_pw'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        row = raw_db.execute(
            'SELECT must_change_password FROM users WHERE username = ?',
            ('new_test_user',),
        ).fetchone()
        assert row is not None, 'user should be created'
        assert row['must_change_password'] == 1

    def test_create_user_duplicate_username(self, client, raw_db, users):
        existing_username = users['a']['username']
        before = raw_db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        client.post(
            '/admin/users/create',
            data={'username': existing_username, 'password': 'valid_pw'},
        )
        after = raw_db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        assert after == before, 'no new user should be created for duplicate username'

    def test_create_user_short_username(self, client, raw_db):
        before = raw_db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        resp = client.post(
            '/admin/users/create',
            data={'username': 'x', 'password': 'valid_pw'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        after = raw_db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        assert after == before

    def test_create_user_short_password(self, client, raw_db):
        before = raw_db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        resp = client.post(
            '/admin/users/create',
            data={'username': 'valid_name', 'password': 'abc'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        after = raw_db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        assert after == before

    def test_create_user_requires_admin(self, client, users):
        client.get('/auth/logout')
        login_as(client, users, 'a')
        resp = client.post(
            '/admin/users/create',
            data={'username': 'should_not_exist', 'password': 'valid_pw'},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 403)


# ── TestAdminProtection ───────────────────────────────────────────────

class TestAdminProtection:

    @pytest.fixture(autouse=True)
    def _login(self, client, admin_user):
        login_as_admin(client, admin_user)

    def test_cannot_delete_last_admin(self, client, raw_db, admin_user, app):
        # Ensure admin_user is the only admin
        raw_db.execute('UPDATE users SET is_admin = 0 WHERE id != ?', (admin_user['id'],))
        raw_db.commit()

        resp = client.post(
            f'/admin/users/{admin_user["id"]}/delete',
            follow_redirects=False,
        )
        assert resp.status_code == 302
        row = raw_db.execute(
            'SELECT id FROM users WHERE id = ?', (admin_user['id'],)
        ).fetchone()
        assert row is not None, 'last admin must not be deleted'

    def test_cannot_delete_self(self, client, admin_user, raw_db):
        resp = client.post(
            f'/admin/users/{admin_user["id"]}/delete',
            follow_redirects=False,
        )
        assert resp.status_code == 302
        row = raw_db.execute(
            'SELECT id FROM users WHERE id = ?', (admin_user['id'],)
        ).fetchone()
        assert row is not None, 'admin cannot delete their own account'


# ── TestPasswordReset ─────────────────────────────────────────────────

class TestPasswordReset:

    @pytest.fixture(scope='class')
    def reset_target(self, raw_db):
        """A disposable user whose password we'll reset."""
        raw_db.execute(
            'INSERT OR IGNORE INTO users (username, password_hash, is_admin, must_change_password)'
            ' VALUES (?, ?, 0, 0)',
            ('reset_target_user', generate_password_hash('original_pw')),
        )
        raw_db.commit()
        uid = raw_db.execute(
            'SELECT id FROM users WHERE username = ?', ('reset_target_user',)
        ).fetchone()['id']
        return uid

    @pytest.fixture(autouse=True)
    def _login(self, client, admin_user):
        login_as_admin(client, admin_user)

    def test_reset_password_sets_must_change_flag(self, client, raw_db, reset_target):
        raw_db.execute(
            'UPDATE users SET must_change_password = 0 WHERE id = ?', (reset_target,)
        )
        raw_db.commit()

        client.post(
            f'/admin/users/{reset_target}/reset-password',
            data={'new_password': 'new_valid_pw'},
        )
        row = raw_db.execute(
            'SELECT must_change_password FROM users WHERE id = ?', (reset_target,)
        ).fetchone()
        assert row['must_change_password'] == 1

    def test_reset_password_too_short(self, client, raw_db, reset_target):
        old_hash = raw_db.execute(
            'SELECT password_hash FROM users WHERE id = ?', (reset_target,)
        ).fetchone()['password_hash']

        resp = client.post(
            f'/admin/users/{reset_target}/reset-password',
            data={'new_password': 'abc'},
            follow_redirects=False,
        )
        assert resp.status_code == 302

        new_hash = raw_db.execute(
            'SELECT password_hash FROM users WHERE id = ?', (reset_target,)
        ).fetchone()['password_hash']
        assert new_hash == old_hash, 'password must not change when too short'
