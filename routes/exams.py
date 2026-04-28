from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.subject import get_all_subjects
from models.exam import create_exam, get_all_exams, get_exam, delete_exam

exams_bp = Blueprint('exams', __name__)


@exams_bp.route('/exams')
def list_exams():
    subjects = get_all_subjects()
    exams = get_all_exams()
    return render_template('exams/list.html', subjects=subjects, exams=exams)


@exams_bp.route('/exams/create', methods=['POST'])
def create():
    subject_id = request.form.get('subject_id')
    name = request.form.get('name')
    exam_date = request.form.get('exam_date') or None
    if not subject_id or not name:
        flash('请选择学科并输入考试名称', 'error')
        return redirect(url_for('exams.list_exams'))
    create_exam(int(subject_id), name.strip(), exam_date)
    flash('考试创建成功', 'success')
    return redirect(url_for('exams.list_exams'))


@exams_bp.route('/exams/<int:exam_id>/delete', methods=['POST'])
def delete(exam_id):
    exam = get_exam(exam_id)
    if exam:
        delete_exam(exam_id)
        flash(f'已删除考试「{exam["name"]}」', 'success')
    return redirect(url_for('exams.list_exams'))
