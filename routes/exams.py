import os, shutil
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from config import DATA_DIR
from utils.decorators import login_required
from models.subject import get_all_subjects
from models.exam import create_exam, get_all_exams, get_exam, delete_exam
from models.analysis import get_tts_paths_by_exam

exams_bp = Blueprint('exams', __name__)


@exams_bp.route('/exams')
@login_required
def list_exams():
    user_id = session['user_id']
    subjects = get_all_subjects()
    exams = get_all_exams(user_id)
    return render_template('exams/list.html', subjects=subjects, exams=exams)


@exams_bp.route('/exams/create', methods=['POST'])
@login_required
def create():
    user_id = session['user_id']
    subject_id = request.form.get('subject_id')
    name = request.form.get('name')
    exam_date = request.form.get('exam_date') or None
    if not subject_id or not name:
        flash('请选择学科并输入考试名称', 'error')
        return redirect(url_for('exams.list_exams'))
    create_exam(int(subject_id), name.strip(), exam_date, user_id=user_id)
    flash('考试创建成功', 'success')
    return redirect(url_for('exams.list_exams'))


@exams_bp.route('/exams/<int:exam_id>/delete', methods=['POST'])
@login_required
def delete(exam_id):
    user_id = session['user_id']
    exam = get_exam(exam_id)
    if not exam or exam['user_id'] != user_id:
        flash('无权删除此考试', 'error')
        return redirect(url_for('exams.list_exams'))

    # Collect TTS paths before cascade-delete removes the DB rows
    tts_paths = get_tts_paths_by_exam(exam_id)

    # Delete image files from disk
    subject = next((s for s in get_all_subjects() if s['id'] == exam['subject_id']), None)
    if subject:
        exam_dir = os.path.join(DATA_DIR, str(user_id), subject['name'], exam['name'])
        if os.path.isdir(exam_dir):
            shutil.rmtree(exam_dir)

    # Delete TTS audio files
    for rel_path in tts_paths:
        full_path = os.path.join(DATA_DIR, rel_path)
        if os.path.isfile(full_path):
            os.remove(full_path)

    delete_exam(exam_id)
    flash(f'已删除考试「{exam["name"]}」', 'success')
    return redirect(url_for('exams.list_exams'))
