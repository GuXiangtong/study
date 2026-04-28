import json
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.question import get_question
from models.analysis import get_analysis
from services.analysis_service import AnalysisService

analysis_bp = Blueprint('analysis', __name__)


@analysis_bp.route('/analysis/question/<int:question_id>/run', methods=['POST'])
def run_analysis(question_id):
    question = get_question(question_id)
    if not question:
        flash('题目不存在', 'error')
        return redirect(request.referrer or url_for('questions.list_questions'))

    try:
        service = AnalysisService()
        result = service.run_full_analysis(question_id)
        mode_label = 'LLM 分析' if service.mode == 'llm' else '模板分析'
        flash(f'分析完成（{mode_label}）', 'success')
        return redirect(url_for('analysis.view_analysis', analysis_id=result['id']))
    except Exception as e:
        flash(f'分析失败：{e}', 'error')
        return redirect(request.referrer or url_for('questions.list_questions'))


@analysis_bp.route('/analysis/<int:analysis_id>')
def view_analysis(analysis_id):
    analysis = get_analysis(analysis_id)
    if not analysis:
        flash('分析记录不存在', 'error')
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
