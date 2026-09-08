"""
Tests for concurrent question recognition in services.paper_service.

recognize_question_images fans out one API call per question across a bounded
thread pool. These tests verify (without hitting any real OCR/vision API):

  - output order matches input order,
  - each question is recognized in isolation (one failure doesn't abort others),
  - recognition actually runs concurrently rather than serially.
"""
import os
import threading
import time

import pytest

import services.paper_service as ps
from tests.conftest import make_dummy_file


def _setup_task_pages(test_paths, task_id, pages):
    """Create page image files for a task. `pages` is a list of page numbers."""
    pages_dir = os.path.join(test_paths['paper_temp'], task_id, 'pages')
    os.makedirs(pages_dir, exist_ok=True)
    for p in pages:
        make_dummy_file(os.path.join(pages_dir, f'page_{p:03d}.png'))


@pytest.fixture
def patched_recognition(app, monkeypatch):
    """Force doubao_seed method and stub crop + single-question recognition.

    Depends on `app` so conftest patches services.paper_service.PAPER_TEMP_DIR
    to the temp test directory before these tests run.
    """
    monkeypatch.setattr(ps, '_get_recognition_method_name', lambda user_id=None: 'doubao_seed')
    # Crop just creates the output file; skip real PIL work on dummy bytes.
    monkeypatch.setattr(ps, '_crop_question',
                        lambda *a, **k: make_dummy_file(a[3]))


def test_preserves_input_order(test_paths, patched_recognition, monkeypatch):
    task_id = 'order-task'
    _setup_task_pages(test_paths, task_id, [1])

    # Recognition returns the question id so we can assert ordering.
    monkeypatch.setattr(ps, '_recognize_single_question',
                        lambda img_path: os.path.splitext(os.path.basename(img_path))[0])

    questions = [{'id': i, 'page': 1} for i in range(10)]
    results = ps.recognize_question_images(task_id, questions, user_id=1)

    assert [r['id'] for r in results] == list(range(10))
    assert [r['content'] for r in results] == [str(i) for i in range(10)]


def test_one_failure_does_not_abort_others(test_paths, patched_recognition, monkeypatch):
    task_id = 'fail-task'
    _setup_task_pages(test_paths, task_id, [1])

    def flaky(img_path):
        q_id = os.path.splitext(os.path.basename(img_path))[0]
        if q_id == '2':
            raise RuntimeError('boom')
        return f'ok-{q_id}'

    monkeypatch.setattr(ps, '_recognize_single_question', flaky)

    questions = [{'id': i, 'page': 1} for i in range(4)]
    results = ps.recognize_question_images(task_id, questions, user_id=1)

    assert results[0] == {'id': 0, 'content': 'ok-0', 'image': '0.png'}
    assert results[2]['id'] == 2 and results[2]['error'] == 'boom' and 'content' not in results[2]
    assert results[3]['content'] == 'ok-3'


def test_missing_page_reported_per_question(test_paths, patched_recognition, monkeypatch):
    task_id = 'missing-page-task'
    _setup_task_pages(test_paths, task_id, [1])  # only page 1 exists
    monkeypatch.setattr(ps, '_recognize_single_question', lambda img_path: 'ok')

    questions = [{'id': 0, 'page': 1}, {'id': 1, 'page': 9}]
    results = ps.recognize_question_images(task_id, questions, user_id=1)

    assert results[0]['content'] == 'ok'
    assert '第9页图片不存在' in results[1]['error']


def test_runs_concurrently(test_paths, patched_recognition, monkeypatch):
    task_id = 'concurrent-task'
    _setup_task_pages(test_paths, task_id, [1])

    active = {'now': 0, 'max': 0}
    lock = threading.Lock()

    def slow(img_path):
        with lock:
            active['now'] += 1
            active['max'] = max(active['max'], active['now'])
        try:
            time.sleep(0.2)
            return 'ok'
        finally:
            with lock:
                active['now'] -= 1

    monkeypatch.setattr(ps, '_recognize_single_question', slow)

    n = ps._RECOGNIZE_MAX_WORKERS
    questions = [{'id': i, 'page': 1} for i in range(n)]

    start = time.perf_counter()
    results = ps.recognize_question_images(task_id, questions, user_id=1)
    elapsed = time.perf_counter() - start

    assert all(r['content'] == 'ok' for r in results)
    # More than one worker ran at once.
    assert active['max'] > 1
    # Serial would take n * 0.2s; concurrent collapses toward ~0.2s.
    assert elapsed < n * 0.2 * 0.7


def test_empty_input_returns_empty(test_paths, patched_recognition):
    assert ps.recognize_question_images('empty-task', [], user_id=1) == []
