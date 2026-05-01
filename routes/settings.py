from flask import Blueprint, flash, redirect, render_template, request, url_for, session
from utils.decorators import login_required
from models.settings import (ANALYSIS_METHODS, RECOGNITION_METHODS,
                             get_all_settings, set_setting,
                             get_subject_prompts, set_subject_prompts)
from models.subject import get_all_subjects
from services.analysis_service import SYSTEM_PROMPT as DEFAULT_SYSTEM_PROMPT

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def index():
    user_id = session['user_id']

    if request.method == 'POST':
        recognition = request.form.get('recognition_method', 'paddleocr_deepseek')
        analysis = request.form.get('analysis_method', 'deepseek')

        if recognition in RECOGNITION_METHODS:
            set_setting('recognition_method', recognition, user_id=user_id)
        if analysis in ANALYSIS_METHODS:
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

    current = get_all_settings(user_id=user_id)
    subjects = get_all_subjects()
    subject_prompts = get_subject_prompts(user_id=user_id)
    return render_template('settings/index.html',
                           recognition_methods=RECOGNITION_METHODS,
                           analysis_methods=ANALYSIS_METHODS,
                           current=current,
                           subjects=subjects,
                           subject_prompts=subject_prompts,
                           default_system_prompt=DEFAULT_SYSTEM_PROMPT)
