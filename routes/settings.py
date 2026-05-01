from flask import Blueprint, flash, redirect, render_template, request, url_for, session
from utils.decorators import login_required
from models.settings import (ANALYSIS_METHODS, RECOGNITION_METHODS,
                             get_all_settings, set_setting)

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

        flash('设置已保存', 'success')
        return redirect(url_for('settings.index'))

    current = get_all_settings(user_id=user_id)
    return render_template('settings/index.html',
                           recognition_methods=RECOGNITION_METHODS,
                           analysis_methods=ANALYSIS_METHODS,
                           current=current)
