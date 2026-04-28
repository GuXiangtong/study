import json
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.analysis import get_analysis
from models.practice import get_practices_by_analysis, delete_practices_by_analysis
from services.practice_service import PracticeService

practice_bp = Blueprint('practice', __name__)


@practice_bp.route('/practice/<int:analysis_id>/generate', methods=['POST'])
def generate_practice(analysis_id):
    analysis = get_analysis(analysis_id)
    if not analysis:
        flash('分析记录不存在', 'error')
        return redirect(request.referrer or url_for('questions.list_questions'))

    # Remove old practice questions
    delete_practices_by_analysis(analysis_id)

    service = PracticeService()
    service.generate_practices(analysis_id)

    flash('巩固练习已生成', 'success')
    return redirect(url_for('analysis.view_analysis', analysis_id=analysis_id))
