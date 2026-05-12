import json
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from utils.decorators import login_required
from models.question import get_question, update_question
from models.sub_question import get_sub_questions_by_question
from models.analysis import get_analysis, delete_analysis
from models.analysis_chat import get_chats, add_chat_messages
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
        student_answer = request.form.get('student_answer', '').strip() or None
        error_reason = request.form.get('error_reason', '').strip() or None
        update_question(question_id, student_answer=student_answer, error_reason=error_reason)

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
        full_path = os.path.join(ANALYSIS_DIR, str(user_id), file_path)
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
    from models.settings import get_analysis_method
    practices = get_practices_by_analysis(analysis_id, user_id=user_id)

    _MODE_LABELS = {
        'deepseek':    'DeepSeek',
        'anthropic':   'Claude',
        'doubao_seed': 'Doubao',
    }
    current_mode = get_analysis_method(user_id=user_id)
    chat_model = _MODE_LABELS.get(current_mode, current_mode)

    def safe_json(raw):
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    return render_template('analysis/result.html', analysis=analysis, practices=practices,
                           chats=get_chats(analysis_id, user_id),
                           chat_model=chat_model,
                           step1=safe_json(analysis['step1_data']),
                           step2=safe_json(analysis['step2_data']),
                           step3=safe_json(analysis['step3_data']),
                           step4=safe_json(analysis['step4_data']))


@analysis_bp.route('/analysis/<int:analysis_id>/prompts')
@login_required
def view_prompts(analysis_id):
    user_id = session['user_id']
    analysis = get_analysis(analysis_id, user_id=user_id)
    if not analysis:
        flash('分析记录不存在或无权访问', 'error')
        return redirect(url_for('questions.list_questions'))
    return render_template('analysis/prompts.html', analysis=analysis)


@analysis_bp.route('/analysis/<int:analysis_id>/chat', methods=['POST'])
@login_required
def chat_with_analysis(analysis_id):
    user_id = session['user_id']
    analysis = get_analysis(analysis_id, user_id=user_id)
    if not analysis:
        return jsonify({'error': '分析记录不存在'}), 404

    data = request.get_json() or {}
    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify({'error': '消息不能为空'}), 400

    def safe_json(raw):
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    step1 = safe_json(analysis['step1_data'])
    step2 = safe_json(analysis['step2_data'])
    step3 = safe_json(analysis['step3_data'])
    step4 = safe_json(analysis['step4_data'])
    chat_history = get_chats(analysis_id, user_id)

    question = None
    sub_questions = []
    if analysis.get('question_id'):
        q = get_question(analysis['question_id'])
        if q:
            question = dict(q)
            sub_questions = [dict(sq) for sq in get_sub_questions_by_question(analysis['question_id'])]

    try:
        service = AnalysisService(user_id=user_id)
        reply = service.chat(analysis, question, sub_questions, step1, step2, step3, step4, chat_history, user_message)
        add_chat_messages(analysis_id, user_id, user_message, reply)
        return jsonify({'reply': reply})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
