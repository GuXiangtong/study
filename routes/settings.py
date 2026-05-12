import os

from flask import Blueprint, flash, redirect, render_template, request, url_for, session
from utils.decorators import login_required
from models.settings import (get_available_recognition_methods, get_available_analysis_methods,
                             get_all_settings, set_setting, get_setting,
                             get_subject_prompts, set_subject_prompts,
                             fix_user_model_settings)
from models.subject import get_all_subjects
from config import BASE_DIR


def _read_default_system_prompt():
    """Return admin's global system prompt, falling back to the file default."""
    admin_prompt = get_setting('system_prompt', '', user_id=0)
    if admin_prompt:
        return admin_prompt
    path = os.path.join(BASE_DIR, 'prompts', 'system_prompt.txt')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    from services.analysis_service import SYSTEM_PROMPT
    return SYSTEM_PROMPT

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def index():
    user_id = session['user_id']

    # Get admin-filtered available methods
    recognition_methods = get_available_recognition_methods()
    analysis_methods = get_available_analysis_methods()

    if request.method == 'POST':
        recognition = request.form.get('recognition_method', 'paddleocr_deepseek')
        analysis = request.form.get('analysis_method', 'deepseek')

        if recognition in recognition_methods:
            set_setting('recognition_method', recognition, user_id=user_id)
        if analysis in analysis_methods:
            set_setting('analysis_method', analysis, user_id=user_id)

        # Save subject-specific prompts
        subjects = get_all_subjects()
        prompts = {}
        for s in subjects:
            prompt = request.form.get(f'prompt_{s["name"]}', '')
            if prompt.strip():
                prompts[s['name']] = prompt.strip()
        set_subject_prompts(prompts, user_id=user_id)

        # Save system prompt
        system_prompt = request.form.get('system_prompt', '').strip()
        set_setting('system_prompt', system_prompt, user_id=user_id)

        flash('设置已保存', 'success')
        return redirect(url_for('settings.index'))

    # Auto-fix if user's current model was disabled by admin
    fix_user_model_settings(user_id)

    current = get_all_settings(user_id=user_id)
    subjects = get_all_subjects()
    subject_prompts = get_subject_prompts(user_id=user_id)
    return render_template('settings/index.html',
                           recognition_methods=recognition_methods,
                           analysis_methods=analysis_methods,
                           current=current,
                           subjects=subjects,
                           subject_prompts=subject_prompts,
                           default_system_prompt=_read_default_system_prompt())