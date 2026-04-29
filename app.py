from flask import Flask, render_template, send_from_directory
from config import SECRET_KEY, BASE_DIR, SUBJECTS
from database import init_app as init_db
from models.subject import get_all_subjects
from models.exam import get_all_exams
from models.question import get_questions_filtered

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
init_db(app)

from services.paper_service import cleanup_old_tasks
cleanup_old_tasks()


@app.route('/')
def index():
    subjects = get_all_subjects()
    exams = get_all_exams()
    recent_questions = get_questions_filtered()[:10]
    return render_template('index.html', subjects=subjects, exams=exams,
                           recent_questions=recent_questions)


@app.route('/images/<subject>/<exam>/<filename>')
def serve_image(subject, exam, filename):
    import os
    dir_path = os.path.join(BASE_DIR, subject, exam)
    return send_from_directory(dir_path, filename)


# Register blueprints
from routes.exams import exams_bp
from routes.questions import questions_bp
from routes.analysis import analysis_bp
from routes.practice import practice_bp
from routes.paper import paper_bp
from routes.settings import settings_bp

app.register_blueprint(exams_bp)
app.register_blueprint(questions_bp)
app.register_blueprint(analysis_bp)
app.register_blueprint(practice_bp)
app.register_blueprint(paper_bp)
app.register_blueprint(settings_bp)

if __name__ == '__main__':
    app.run(debug=True, port=5001)
