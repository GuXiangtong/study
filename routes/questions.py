import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from config import BASE_DIR, UPLOAD_EXTENSIONS
from utils.decorators import login_required
from models.subject import get_all_subjects
from models.exam import get_all_exams, get_exam, create_exam
from models.question import (
    create_question, get_question, get_questions_by_exam,
    get_questions_filtered, update_question, delete_question
)
from models.sub_question import (
    create_sub_question, get_sub_questions_by_question,
    update_sub_question, delete_sub_question, get_sub_question
)
from models.analysis import get_analyses_by_question

questions_bp = Blueprint('questions', __name__)


@questions_bp.route('/questions')
@login_required
def list_questions():
    user_id = session['user_id']
    subjects = get_all_subjects()
    subject_id = request.args.get('subject_id', type=int)
    exam_id = request.args.get('exam_id', type=int)
    search = request.args.get('search')
    exams = get_all_exams(user_id)
    questions = get_questions_filtered(subject_id=subject_id, exam_id=exam_id, search=search, user_id=user_id)
    return render_template('questions/list.html', subjects=subjects, exams=exams,
                           questions=questions, selected_subject=subject_id,
                           selected_exam=exam_id, search=search)


@questions_bp.route('/questions/create', methods=['GET', 'POST'])
@login_required
def create():
    user_id = session['user_id']

    if request.method == 'GET':
        subjects = get_all_subjects()
        exams = get_all_exams(user_id)
        return render_template('questions/create.html', subjects=subjects, exams=exams)

    subject_id = request.form.get('subject_id', type=int)
    exam_name = request.form.get('exam_name', '').strip()
    exam_id = request.form.get('exam_id', type=int)
    exam_date = request.form.get('exam_date') or None
    question_number = request.form.get('question_number', '').strip()
    stem = request.form.get('stem', '').strip() or None
    student_answer = request.form.get('student_answer', '').strip() or None
    error_reason = request.form.get('error_reason', '').strip() or None

    if not subject_id or not question_number:
        flash('请选择学科并输入题号', 'error')
        return redirect(url_for('questions.create'))

    if not exam_id and exam_name:
        exam = create_exam(subject_id, exam_name, exam_date, user_id=user_id)
        exam_id = exam['id'] if exam else None
    if not exam_id:
        flash('请选择或创建考试', 'error')
        return redirect(url_for('questions.create'))

    image_path = None
    file = request.files.get('image')
    if file and file.filename:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext in UPLOAD_EXTENSIONS:
            subject_name = next((s['name'] for s in get_all_subjects() if s['id'] == subject_id), None)
            if subject_name and exam_name:
                dir_path = os.path.join(BASE_DIR, subject_name, exam_name)
                os.makedirs(dir_path, exist_ok=True)
                filename = f"{question_number}{ext}"
                file.save(os.path.join(dir_path, filename))
                image_path = f"{subject_name}/{exam_name}/{filename}"

    question_id = create_question(exam_id, question_number, stem, image_path,
                                    student_answer=student_answer, error_reason=error_reason,
                                    user_id=user_id)

    labels = request.form.getlist('sq_label')
    contents = request.form.getlist('sq_content')
    correct_answers = request.form.getlist('sq_correct_answer')
    student_answers = request.form.getlist('sq_student_answer')
    error_reasons = request.form.getlist('sq_error_reason')
    error_types = request.form.getlist('sq_error_type')

    for i in range(len(labels)):
        if labels[i].strip():
            create_sub_question(
                question_id, labels[i].strip(),
                content=contents[i].strip() or None,
                correct_answer=correct_answers[i].strip() or None if i < len(correct_answers) else None,
                student_answer=student_answers[i].strip() or None if i < len(student_answers) else None,
                error_reason=error_reasons[i].strip() or None if i < len(error_reasons) else None,
                error_type=error_types[i].strip() or None if i < len(error_types) else None,
                user_id=user_id,
            )

    flash('题目创建成功', 'success')
    return redirect(url_for('questions.detail', question_id=question_id))


@questions_bp.route('/questions/<int:question_id>')
@login_required
def detail(question_id):
    user_id = session['user_id']
    question = get_question(question_id, user_id=user_id)
    if not question:
        flash('题目不存在或无权访问', 'error')
        return redirect(url_for('questions.list_questions'))
    sub_questions = get_sub_questions_by_question(question_id)
    analyses = get_analyses_by_question(question_id)
    return render_template('questions/detail.html', question=question,
                           sub_questions=sub_questions, analyses=analyses)


@questions_bp.route('/questions/<int:question_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(question_id):
    user_id = session['user_id']
    question = get_question(question_id, user_id=user_id)
    if not question:
        flash('题目不存在或无权访问', 'error')
        return redirect(url_for('questions.list_questions'))

    if request.method == 'GET':
        subjects = get_all_subjects()
        exams = get_all_exams(user_id)
        sub_questions = get_sub_questions_by_question(question_id)
        return render_template('questions/edit.html', question=question,
                               subjects=subjects, exams=exams,
                               sub_questions=sub_questions)

    question_number = request.form.get('question_number', '').strip()
    stem = request.form.get('stem', '').strip() or None
    student_answer = request.form.get('student_answer', '').strip() or None
    error_reason = request.form.get('error_reason', '').strip() or None
    update_question(question_id, question_number=question_number, stem=stem,
                    student_answer=student_answer, error_reason=error_reason)

    file = request.files.get('image')
    if file and file.filename:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext in UPLOAD_EXTENSIONS:
            subject_name = question['subject_name']
            exam_name = question['exam_name']
            dir_path = os.path.join(BASE_DIR, subject_name, exam_name)
            os.makedirs(dir_path, exist_ok=True)
            filename = f"{question_number}{ext}"
            file.save(os.path.join(dir_path, filename))
            image_path = f"{subject_name}/{exam_name}/{filename}"
            update_question(question_id, image_path=image_path)

    flash('题目更新成功', 'success')
    return redirect(url_for('questions.detail', question_id=question_id))


@questions_bp.route('/questions/<int:question_id>/delete', methods=['POST'])
@login_required
def delete(question_id):
    user_id = session['user_id']
    question = get_question(question_id, user_id=user_id)
    if not question:
        flash('题目不存在或无权访问', 'error')
    else:
        # Remove image file from disk
        image_path = question.get('image_path')
        if image_path:
            full_path = os.path.join(BASE_DIR, image_path)
            if os.path.isfile(full_path):
                os.remove(full_path)
        delete_question(question_id)
        flash('题目已删除', 'success')
    return redirect(url_for('questions.list_questions'))


@questions_bp.route('/questions/<int:question_id>/sub_questions', methods=['POST'])
@login_required
def add_sub_question(question_id):
    user_id = session['user_id']
    question = get_question(question_id, user_id=user_id)
    if not question:
        flash('题目不存在或无权访问', 'error')
        return redirect(url_for('questions.list_questions'))

    label = request.form.get('label', '').strip()
    if not label:
        flash('请输入子问题标号', 'error')
        return redirect(url_for('questions.detail', question_id=question_id))
    create_sub_question(
        question_id, label,
        content=request.form.get('content', '').strip() or None,
        correct_answer=request.form.get('correct_answer', '').strip() or None,
        student_answer=request.form.get('student_answer', '').strip() or None,
        error_reason=request.form.get('error_reason', '').strip() or None,
        error_type=request.form.get('error_type', '').strip() or None,
        user_id=user_id,
    )
    flash('子问题添加成功', 'success')
    return redirect(url_for('questions.detail', question_id=question_id))


@questions_bp.route('/sub_questions/<int:sub_question_id>/update', methods=['POST'])
@login_required
def update_sub(sub_question_id):
    user_id = session['user_id']
    sq = get_sub_question(sub_question_id, user_id=user_id)
    if not sq:
        flash('子问题不存在或无权访问', 'error')
        return redirect(url_for('questions.list_questions'))

    update_sub_question(
        sub_question_id,
        label=request.form.get('label', '').strip(),
        content=request.form.get('content', '').strip() or None,
        correct_answer=request.form.get('correct_answer', '').strip() or None,
        student_answer=request.form.get('student_answer', '').strip() or None,
        error_reason=request.form.get('error_reason', '').strip() or None,
        error_type=request.form.get('error_type', '').strip() or None,
    )
    flash('子问题更新成功', 'success')
    return redirect(url_for('questions.detail', question_id=sq['question_id']))


@questions_bp.route('/sub_questions/<int:sub_question_id>/delete', methods=['POST'])
@login_required
def delete_sub(sub_question_id):
    user_id = session['user_id']
    sq = get_sub_question(sub_question_id, user_id=user_id)
    if not sq:
        flash('子问题不存在或无权访问', 'error')
        return redirect(url_for('questions.list_questions'))

    delete_sub_question(sub_question_id)
    flash('子问题已删除', 'success')
    return redirect(url_for('questions.detail', question_id=sq['question_id']))
