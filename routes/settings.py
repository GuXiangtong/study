from flask import Blueprint, flash, redirect, render_template, request, url_for

from models.settings import (ANALYSIS_METHODS, RECOGNITION_METHODS,
                             get_all_settings, set_setting)

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/settings', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        recognition = request.form.get('recognition_method', 'paddleocr_deepseek')
        analysis = request.form.get('analysis_method', 'deepseek')

        if recognition in RECOGNITION_METHODS:
            set_setting('recognition_method', recognition)
        if analysis in ANALYSIS_METHODS:
            set_setting('analysis_method', analysis)

        flash('设置已保存', 'success')
        return redirect(url_for('settings.index'))

    current = get_all_settings()
    return render_template('settings/index.html',
                           recognition_methods=RECOGNITION_METHODS,
                           analysis_methods=ANALYSIS_METHODS,
                           current=current)
