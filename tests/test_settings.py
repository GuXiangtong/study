"""
Tests for the settings model: model enablement, fix_user_model_settings, subject prompts.
"""
import pytest


# ── TestModelEnablement ───────────────────────────────────────────────

class TestModelEnablement:
    """Admin-controlled enable/disable of analysis methods."""

    @pytest.fixture(autouse=True)
    def _restore_enabled_methods(self, app):
        """Reset enabled analysis methods after each test to avoid cross-test pollution."""
        yield
        with app.app_context():
            from models.settings import set_enabled_analysis_methods, ANALYSIS_METHODS
            set_enabled_analysis_methods(list(ANALYSIS_METHODS.keys()))

    def test_default_returns_all_methods(self, app, raw_db):
        with app.app_context():
            from models.settings import get_enabled_analysis_methods, ANALYSIS_METHODS
            # Remove stored config so we exercise the code-default branch
            raw_db.execute(
                'DELETE FROM settings WHERE user_id = 0 AND key = ?',
                ('enabled_analysis_methods',),
            )
            raw_db.commit()
            enabled = get_enabled_analysis_methods()
        assert set(enabled) == set(ANALYSIS_METHODS.keys())

    def test_admin_can_disable_method(self, app):
        with app.app_context():
            from models.settings import (set_enabled_analysis_methods,
                                         get_available_analysis_methods)
            set_enabled_analysis_methods(['deepseek'])
            available = get_available_analysis_methods()
        assert list(available.keys()) == ['deepseek']

    def test_set_empty_list_falls_back_to_all(self, app):
        with app.app_context():
            from models.settings import (set_enabled_analysis_methods,
                                         get_enabled_analysis_methods, ANALYSIS_METHODS)
            set_enabled_analysis_methods([])
            enabled = get_enabled_analysis_methods()
        assert len(enabled) > 0, 'at least one method must remain enabled'
        assert set(enabled) == set(ANALYSIS_METHODS.keys())


# ── TestFixUserModelSettings ──────────────────────────────────────────

class TestFixUserModelSettings:

    @pytest.fixture(autouse=True)
    def _restore(self, app, users):
        """Reset analysis method settings after each test."""
        yield
        with app.app_context():
            from models.settings import set_setting, set_enabled_analysis_methods, ANALYSIS_METHODS
            set_setting('analysis_method', 'deepseek', user_id=users['a']['id'])
            set_enabled_analysis_methods(list(ANALYSIS_METHODS.keys()))

    def test_fix_switches_disabled_analysis_method(self, app, users):
        with app.app_context():
            from models.settings import (set_setting, set_enabled_analysis_methods,
                                         fix_user_model_settings, get_analysis_method)
            # User picks 'kimi', then admin disables it
            set_setting('analysis_method', 'kimi', user_id=users['a']['id'])
            set_enabled_analysis_methods(['deepseek'])

            changed = fix_user_model_settings(users['a']['id'])
            new_method = get_analysis_method(users['a']['id'])

        assert changed is True
        assert new_method != 'kimi', 'method should be switched away from disabled kimi'
        assert new_method == 'deepseek'

    def test_fix_noop_when_method_still_enabled(self, app, users):
        with app.app_context():
            from models.settings import (set_setting, set_enabled_analysis_methods,
                                         fix_user_model_settings, get_analysis_method,
                                         ANALYSIS_METHODS)
            set_setting('analysis_method', 'deepseek', user_id=users['a']['id'])
            set_enabled_analysis_methods(list(ANALYSIS_METHODS.keys()))

            changed = fix_user_model_settings(users['a']['id'])
            method = get_analysis_method(users['a']['id'])

        assert changed is False
        assert method == 'deepseek'


# ── TestSubjectPrompts ────────────────────────────────────────────────

class TestSubjectPrompts:

    def test_set_and_get_subject_prompts(self, app, users):
        with app.app_context():
            from models.settings import set_subject_prompts, get_subject_prompts
            data = {'数学': '注重解题步骤', '物理': '结合公式推导'}
            set_subject_prompts(data, user_id=users['a']['id'])
            result = get_subject_prompts(user_id=users['a']['id'])
        assert result == data

    def test_empty_prompt_excluded_by_route_layer(self, app, users, client):
        """The settings route skips blank prompts before saving."""
        from conftest import login_as
        login_as(client, users, 'a')

        client.post('/settings', data={
            'recognition_method': 'paddleocr_deepseek',
            'analysis_method': 'deepseek',
            'prompt_数学': '',
            'prompt_物理': '多用图示',
        })

        with app.app_context():
            from models.settings import get_subject_prompts
            prompts = get_subject_prompts(user_id=users['a']['id'])

        assert '数学' not in prompts, 'blank prompt should not be saved'
        assert prompts.get('物理') == '多用图示'
