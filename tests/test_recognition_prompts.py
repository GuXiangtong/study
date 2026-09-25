"""
Guard tests for recognition prompt wording.

The user reported the vision model sometimes *supplements* content that isn't in
the image (hallucination). The recognition prompts must explicitly forbid
inferring or completing content that isn't visible. These tests lock that intent
in place so a future prompt edit doesn't silently drop the constraint.
"""
import services.paper_service as ps


def test_single_question_prompt_forbids_hallucination():
    p = ps._SINGLE_Q_PROMPT
    assert '严禁' in p
    assert '补全' in p
    assert '推断' in p


def test_page_vision_prompt_forbids_hallucination():
    p = ps.DOUBAO_VISION_PROMPT
    assert '严禁' in p
    assert '补全' in p


def test_refine_prompts_forbid_adding_content():
    for p in (ps._REFINE_SINGLE_Q_PROMPT, ps.LLM_REFINE_PROMPT):
        assert '补全' in p
        assert '推断' in p
