"""
Tests for multi-image upload and optional merge in services.paper_service
and the /paper/upload route.

prepare_paper() accepts one or more uploaded files. With merge=True all pages
are concatenated vertically into a single page (so a question spanning a page
break can be selected in one box); with merge=False each image becomes its own
page. These tests use real (tiny) PNGs because merging exercises PIL.
"""
import io
import os

from PIL import Image
from werkzeug.datastructures import FileStorage

import services.paper_service as ps
from services.paper_service import prepare_paper, load_result
from tests.conftest import login_as, insert_exam


def _png_filestorage(filename, size=(100, 60), color=(200, 200, 200)):
    """Build a FileStorage wrapping a real in-memory PNG."""
    buf = io.BytesIO()
    Image.new('RGB', size, color).save(buf, 'PNG')
    buf.seek(0)
    return FileStorage(stream=buf, filename=filename, content_type='image/png')


def _pages_dir(test_paths, task_id):
    return os.path.join(test_paths['paper_temp'], task_id, 'pages')


def test_multi_image_no_merge_makes_multiple_pages(app, test_paths):
    task_id = 'multi-nomerge'
    files = [_png_filestorage(f'p{i}.png') for i in range(3)]

    result = prepare_paper(files, task_id, user_id=1, merge=False)

    assert result['page_count'] == 3
    assert result['merged'] is False
    assert result['page_image_names'] == ['page_001.png', 'page_002.png', 'page_003.png']
    for name in result['page_image_names']:
        assert os.path.isfile(os.path.join(_pages_dir(test_paths, task_id), name))


def test_multi_image_merge_makes_single_tall_page(app, test_paths):
    task_id = 'multi-merge'
    files = [
        _png_filestorage('a.png', size=(100, 60)),
        _png_filestorage('b.png', size=(100, 40)),
    ]

    result = prepare_paper(files, task_id, user_id=1, merge=True)

    assert result['page_count'] == 1
    assert result['merged'] is True
    assert result['page_image_names'] == ['page_001.png']

    merged_path = os.path.join(_pages_dir(test_paths, task_id), 'page_001.png')
    assert os.path.isfile(merged_path)
    with Image.open(merged_path) as img:
        assert img.width == 100
        assert img.height == 100  # 60 + 40, same width so no rescale


def test_merge_scales_to_widest_width(app, test_paths):
    task_id = 'multi-merge-scale'
    files = [
        _png_filestorage('wide.png', size=(200, 50)),
        _png_filestorage('narrow.png', size=(100, 50)),
    ]

    result = prepare_paper(files, task_id, user_id=1, merge=True)

    merged_path = os.path.join(_pages_dir(test_paths, task_id), 'page_001.png')
    with Image.open(merged_path) as img:
        assert img.width == 200
        # narrow (100x50) scaled to width 200 -> height 100; plus wide's 50
        assert img.height == 150


def test_single_file_still_works(app, test_paths):
    """Passing a single FileStorage (not a list) stays backward compatible."""
    task_id = 'single-file'
    result = prepare_paper(_png_filestorage('one.png'), task_id, user_id=1)

    assert result['page_count'] == 1
    assert result['merged'] is False
    assert result['page_image_names'] == ['page_001.png']
    assert os.path.isfile(os.path.join(_pages_dir(test_paths, task_id), 'page_001.png'))


def test_merge_single_image_is_noop(app, test_paths):
    """merge=True with only one source page produces a normal single page."""
    task_id = 'merge-one'
    result = prepare_paper([_png_filestorage('only.png')], task_id,
                           user_id=1, merge=True)

    assert result['page_count'] == 1
    assert result['merged'] is False  # merge needs >1 source images


def test_upload_route_multi_image_merge(client, app, raw_db, users, monkeypatch):
    """POST /paper/upload with several images + merge lands on the review page
    with a single merged page owned by the uploader."""
    login_as(client, users, 'a')
    exam_id = insert_exam(raw_db, '数学', '多图合并测试', users['a']['id'])

    captured = {}
    real_prepare = ps.prepare_paper

    def _spy(files, task_id, user_id=None, merge=False):
        captured['task_id'] = task_id
        return real_prepare(files, task_id, user_id=user_id, merge=merge)

    monkeypatch.setattr('routes.paper.prepare_paper', _spy)

    data = {
        'subject_id': raw_db.execute(
            'SELECT subject_id FROM exams WHERE id = ?', (exam_id,)
        ).fetchone()[0],
        'exam_id': str(exam_id),
        'merge_images': '1',
        'paper_file': [
            (io.BytesIO(_png_bytes()), 'p1.png'),
            (io.BytesIO(_png_bytes()), 'p2.png'),
        ],
    }
    resp = client.post('/paper/upload', data=data,
                       content_type='multipart/form-data')

    assert resp.status_code == 302
    assert f"/paper/review/{captured['task_id']}" in resp.headers['Location']

    result = load_result(captured['task_id'])
    assert result['merged'] is True
    assert result['page_count'] == 1
    assert result['user_id'] == users['a']['id']


def test_invalid_pdf_raises_friendly_error(app, test_paths):
    """A file with a .pdf name but non-PDF content gives an actionable message."""
    import pytest
    bogus = FileStorage(stream=io.BytesIO(b'{"error":"not a pdf"}'),
                        filename='broken.pdf', content_type='application/pdf')
    with pytest.raises(ValueError, match='broken.pdf'):
        prepare_paper([bogus], 'bad-pdf', user_id=1)


def test_invalid_image_raises_friendly_error(app, test_paths):
    """A file with a .png name but non-image content gives an actionable message."""
    import pytest
    bogus = FileStorage(stream=io.BytesIO(b'not really an image'),
                        filename='broken.png', content_type='image/png')
    with pytest.raises(ValueError, match='broken.png'):
        prepare_paper([bogus], 'bad-img', user_id=1)


def test_upload_route_bad_file_preserves_selection(client, app, raw_db, users):
    """A failed upload redirects back with the subject/exam kept as query args,
    and the reloaded form pre-selects them."""
    login_as(client, users, 'a')
    exam_id = insert_exam(raw_db, '物理', '选择保留测试', users['a']['id'])
    subject_id = raw_db.execute(
        'SELECT subject_id FROM exams WHERE id = ?', (exam_id,)
    ).fetchone()[0]

    # Bad file (not a valid image) -> processing fails -> redirect back.
    resp = client.post('/paper/upload', data={
        'subject_id': str(subject_id),
        'exam_id': str(exam_id),
        'paper_file': [(io.BytesIO(b'garbage'), 'oops.png')],
    }, content_type='multipart/form-data')

    assert resp.status_code == 302
    loc = resp.headers['Location']
    assert f'subject_id={subject_id}' in loc
    assert f'exam_id={exam_id}' in loc

    # Following the redirect, the form should mark the exam option selected.
    page = client.get(loc)
    assert page.status_code == 200
    assert 'selected' in page.get_data(as_text=True)


def _png_bytes(size=(80, 50), color=(180, 180, 180)):
    buf = io.BytesIO()
    Image.new('RGB', size, color).save(buf, 'PNG')
    return buf.getvalue()
