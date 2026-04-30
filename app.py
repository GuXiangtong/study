from flask import Flask, render_template, send_from_directory, session, g
from config import SECRET_KEY, BASE_DIR, SUBJECTS
from database import init_app as init_db
from utils.decorators import login_required
from models.user import get_user_by_id
from models.subject import get_all_subjects
from models.exam import get_all_exams
from models.question import get_questions_filtered

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
init_db(app)

from services.paper_service import cleanup_old_tasks
cleanup_old_tasks()


@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.current_user = get_user_by_id(user_id) if user_id else None


@app.context_processor
def inject_global_template_vars():
    return {
        'current_user': g.get('current_user'),
    }


@app.route('/')
@login_required
def index():
    user_id = session['user_id']
    subjects = get_all_subjects()
    exams = get_all_exams(user_id)
    recent_questions = get_questions_filtered(user_id=user_id)[:10]
    return render_template('index.html', subjects=subjects, exams=exams,
                           recent_questions=recent_questions)


@app.route('/images/<subject>/<exam>/<filename>')
@login_required
def serve_image(subject, exam, filename):
    import os
    dir_path = os.path.join(BASE_DIR, subject, exam)
    return send_from_directory(dir_path, filename)


# Register blueprints
from routes.auth import auth_bp
from routes.exams import exams_bp
from routes.questions import questions_bp
from routes.analysis import analysis_bp
from routes.practice import practice_bp
from routes.paper import paper_bp
from routes.settings import settings_bp

app.register_blueprint(auth_bp)
app.register_blueprint(exams_bp)
app.register_blueprint(questions_bp)
app.register_blueprint(analysis_bp)
app.register_blueprint(practice_bp)
app.register_blueprint(paper_bp)
app.register_blueprint(settings_bp)

if __name__ == '__main__':
    app.run(debug=True, port=5001)
