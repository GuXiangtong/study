import os
from config import BASE_DIR, UPLOAD_EXTENSIONS
from models.subject import get_all_subjects


def save_uploaded_image(file, subject_name, exam_name, question_number):
    """Save uploaded image to subject/exam directory. Returns relative path."""
    if not file or not file.filename:
        return None
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in UPLOAD_EXTENSIONS:
        return None
    dir_path = os.path.join(BASE_DIR, subject_name, exam_name)
    os.makedirs(dir_path, exist_ok=True)
    filename = f"{question_number}{ext}"
    file.save(os.path.join(dir_path, filename))
    return f"{subject_name}/{exam_name}/{filename}"
