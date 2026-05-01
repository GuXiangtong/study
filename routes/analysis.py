import json
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from utils.decorators import login_required
from models.question import get_question
from models.analysis import get_analysis, delete_analysis
from services.analysis_service import AnalysisService
from config import ANALYSIS_DIR

analysis_bp = Blueprint('analysis', __name__)


@analysis_bp.route('/analysis/question/<int:question_id>/run', methods=['POST'])
@login_required
def run_analysis(question_id):
    user_id = session['user_id']
    question = get_question(question_id, user_id=user_id)
    if not question:
        flash('题目不存在或无权访问', 'error')
        return redirect(request.referrer or url_for('questions.list_questions'))

    try:
        service = AnalysisService(user_id=user_id)
        result = service.run_full_analysis(question_id)
        if result.get('llm_error'):
            flash(f'AI 调用失败，使用模板回退。错误：{result["llm_error"]}', 'warning')
        else:
            mode_label = {
                'deepseek': 'DeepSeek AI',
                'anthropic': 'Anthropic (Claude)',
                'doubao_seed': 'Doubao Seed AI',
            }.get(service.mode, service.mode)
            flash(f'分析完成（{mode_label}）', 'success')
        return redirect(url_for('analysis.view_analysis', analysis_id=result['id']))
    except Exception as e:
        flash(f'分析失败：{e}', 'error')
        return redirect(request.referrer or url_for('questions.list_questions'))


@analysis_bp.route('/analysis/<int:analysis_id>/delete', methods=['POST'])
@login_required
def delete_analysis_route(analysis_id):
    user_id = session['user_id']
    analysis = get_analysis(analysis_id, user_id=user_id)
    if not analysis:
        flash('分析记录不存在或无权访问', 'error')
        return redirect(url_for('questions.list_questions'))

    question_id = analysis.get('question_id')

    file_path = delete_analysis(analysis_id, user_id=user_id)
    if file_path:
        full_path = os.path.join(ANALYSIS_DIR, file_path)
        if os.path.exists(full_path):
            os.remove(full_path)

    flash('分析记录已删除', 'success')
    if question_id:
        return redirect(url_for('questions.detail', question_id=question_id))
    return redirect(url_for('questions.list_questions'))


@analysis_bp.route('/analysis/<int:analysis_id>')
@login_required
def view_analysis(analysis_id):
    user_id = session['user_id']
    analysis = get_analysis(analysis_id, user_id=user_id)
    if not analysis:
        flash('分析记录不存在或无权访问', 'error')
        return redirect(url_for('questions.list_questions'))

    from models.practice import get_practices_by_analysis
    practices = get_practices_by_analysis(analysis_id)

    def safe_json(raw):
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    return render_template('analysis/result.html', analysis=analysis, practices=practices,
                           step1=safe_json(analysis['step1_data']),
                           step2=safe_json(analysis['step2_data']),
                           step3=safe_json(analysis['step3_data']),
                           step4=safe_json(analysis['step4_data']))
