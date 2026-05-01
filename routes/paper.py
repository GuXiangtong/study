import json
import os
import shutil
import uuid

from flask import (Blueprint, flash, redirect, render_template, request,
                   send_from_directory, url_for, session)

from config import BASE_DIR, PAPER_TEMP_DIR
from utils.decorators import login_required
from models.exam import create_exam, get_exam, get_all_exams
from models.question import create_question
from models.subject import get_all_subjects
from services.paper_service import (cleanup_old_tasks, cleanup_task,
                                    load_result, process_paper, recrop_question,
                                    save_result)

paper_bp = Blueprint('paper', __name__)


@paper_bp.route('/paper/upload', methods=['GET', 'POST'])
@login_required
def upload():
    user_id = session['user_id']

    if request.method == 'GET':
        subjects = get_all_subjects()
        exams = get_all_exams(user_id)
        return render_template('paper/upload.html', subjects=subjects, exams=exams)

    subject_id = request.form.get('subject_id', type=int)
    exam_name = request.form.get('exam_name', '').strip()
    exam_id = request.form.get('exam_id', type=int)
    exam_date = request.form.get('exam_date') or None
    file = request.files.get('paper_file')

    if not subject_id:
        flash('请选择学科', 'error')
        return redirect(url_for('paper.upload'))
    if not file or not file.filename:
        flash('请选择要上传的试卷文件', 'error')
        return redirect(url_for('paper.upload'))

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in {'.pdf', '.jpg', '.jpeg', '.png'}:
        flash('不支持的文件格式，请上传 PDF 或图片文件（jpg/png）', 'error')
        return redirect(url_for('paper.upload'))

    if not exam_id and exam_name:
        exam = create_exam(subject_id, exam_name, exam_date, user_id=user_id)
        exam_id = exam['id'] if exam else None
    if not exam_id:
        flash('请选择或创建考试', 'error')
        return redirect(url_for('paper.upload'))

    task_id = str(uuid.uuid4())
    try:
        result = process_paper(file, task_id, user_id=user_id)
    except Exception as e:
        flash(f'试卷处理失败：{e}', 'error')
        return redirect(url_for('paper.upload'))

    result['subject_id'] = subject_id
    result['exam_id'] = exam_id
    save_result(task_id, result)

    if result.get('errors'):
        for err in result['errors']:
            flash(err, 'error')

    return redirect(url_for('paper.review', task_id=task_id))


@paper_bp.route('/paper/review/<task_id>')
@login_required
def review(task_id):
    result = load_result(task_id)
    if not result:
        flash('处理任务不存在或已过期', 'error')
        return redirect(url_for('paper.upload'))

    subjects = get_all_subjects()
    subject_name = ''
    exam_name = ''
    if result.get('subject_id'):
        subject_name = next(
            (s['name'] for s in subjects if s['id'] == result['subject_id']), '')
    if result.get('exam_id'):
        exam = get_exam(result['exam_id'])
        exam_name = exam['name'] if exam else ''

    return render_template('paper/review.html', result=result, subjects=subjects,
                           subject_name=subject_name, exam_name=exam_name,
                           task_id=task_id)


@paper_bp.route('/paper/review/<task_id>/confirm', methods=['POST'])
@login_required
def confirm(task_id):
    user_id = session['user_id']
    result = load_result(task_id)
    if not result:
        flash('处理任务不存在或已过期', 'error')
        return redirect(url_for('paper.upload'))

    selected_indices = request.form.getlist('selected')
    question_numbers = request.form.getlist('question_number')
    stems = request.form.getlist('stem')
    question_positions_raw = request.form.get('question_positions', '{}')

    try:
        question_positions = json.loads(question_positions_raw)
    except (json.JSONDecodeError, TypeError):
        question_positions = {}

    subject_id = result.get('subject_id')
    exam_id = result.get('exam_id')

    subjects = get_all_subjects()
    subject_name = next((s['name'] for s in subjects if s['id'] == subject_id), '')
    exam = get_exam(exam_id)
    exam_name = exam['name'] if exam else ''

    if not subject_name or not exam_name:
        flash('学科或考试信息缺失', 'error')
        return redirect(url_for('paper.review', task_id=task_id))

    questions = result.get('questions', [])
    task_dir = os.path.join(PAPER_TEMP_DIR, task_id)
    questions_dir = os.path.join(task_dir, 'questions')

    imported = 0
    for idx_str in selected_indices:
        idx = int(idx_str)
        if idx < 0 or idx >= len(questions):
            continue

        q = questions[idx]

        q_num = question_numbers[idx].strip() if idx < len(question_numbers) else ''
        if not q_num:
            q_num = q.get('question_number', str(idx + 1))

        stem = stems[idx].strip() if idx < len(stems) else ''

        # Apply user-adjusted crop positions if provided
        pos_key = str(idx)
        if pos_key in question_positions:
            pos = question_positions[pos_key]
            new_y_start = float(pos.get('y_start', q.get('crop_y_start', q.get('y_start', 0))))
            new_y_end = float(pos.get('y_end', q.get('crop_y_end', q.get('y_end', 100))))
            new_x_start = float(pos.get('x_start', q.get('crop_x_start', 0)))
            new_x_end = float(pos.get('x_end', q.get('crop_x_end', 100)))
            page_num = q.get('page', 1)
            new_img = recrop_question(task_id, page_num,
                                       new_y_start, new_y_end, idx,
                                       x_start=new_x_start, x_end=new_x_end)
            if new_img:
                q['image'] = new_img

        image_path = None
        q_img_name = q.get('image', '')
        if q_img_name:
            src = os.path.join(questions_dir, q_img_name)
            if os.path.isfile(src):
                dest_dir = os.path.join(BASE_DIR, subject_name, exam_name)
                os.makedirs(dest_dir, exist_ok=True)
                dest_file = f"{q_num}.png"
                shutil.copy(src, os.path.join(dest_dir, dest_file))
                image_path = f"{subject_name}/{exam_name}/{dest_file}"

        stem_value = stem if stem else q.get('content', '').strip()
        create_question(exam_id, q_num, stem=stem_value or None, image_path=image_path, user_id=user_id)
        imported += 1

    flash(f'成功导入 {imported} 道题目', 'success')
    cleanup_task(task_id)
    return redirect(url_for('questions.list_questions', exam_id=exam_id))


@paper_bp.route('/paper/temp/<task_id>/<subdir>/<filename>')
def serve_temp(task_id, subdir, filename):
    dir_path = os.path.join(PAPER_TEMP_DIR, task_id, subdir)
    return send_from_directory(dir_path, filename)


@paper_bp.route('/paper/temp/<task_id>/pages/<filename>')
def serve_page_image(task_id, filename):
    dir_path = os.path.join(PAPER_TEMP_DIR, task_id, 'pages')
    return send_from_directory(dir_path, filename)
