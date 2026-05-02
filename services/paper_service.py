import base64
import json
import os
import re
import shutil

import requests
from PIL import Image

from config import (DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL,
                    DOUBAO_API_KEY, DOUBAO_API_URL, DOUBAO_BASE_URL,
                    DOUBAO_MODEL, DOUBAO_VISION_MODEL, PAPER_TEMP_DIR)

# ── Question number regex (Chinese exam papers) ────────────────────
_QUESTION_PATTERN = re.compile(
    r'^[\(\（]?\s*(\d+)[\)\）]?(?:\s|[\.\、\．])|'  # "1.", "1、", "(1)", "1 "
    r'^第\s*(\d+)\s*题|'                              # "第1题"
    r'^([一二三四五六七八九十]+)\s*[、\．]'            # "一、", "二、"
)

# Sub-question patterns to skip: bare (1), (2) without a following ./、
_SUB_QUESTION_RE = re.compile(r'^[\(\（]\s*\d+\s*[\)\）]')

LLM_REFINE_PROMPT = """你是一个试卷题目整理助手。请根据提供的页面原始文本和初步分题结果，优化题目的内容和格式。

## 要求
1. 保留题目的完整文字内容，不要遗漏任何条件
2. 数学公式使用 LaTeX 语法（$...$ 或 $$...$$）
3. 如果题目包含子问题如(1)(2)(3)，全部保留在 content 中
4. 如果原始分题有误（如将一道题拆成多道），合并为一道
5. 如果一道题被错误合并，拆分为多道

## 输出格式
严格输出 JSON：
```json
{
  "questions": [
    {"question_number": "1", "content": "完整题目文字..."},
    {"question_number": "2", "content": "完整题目文字..."}
  ]
}
```"""

_SINGLE_Q_PROMPT = """请识别图片中的题目内容，完整提取所有文字，并按照以下规则整理格式。

## 排版顺序（重要）
- 如果图片是左右两栏布局（左栏是各题选项编号，右栏是文章正文），必须按以下顺序输出：
  ① 先输出完整文章正文（含编号空格）
  ② 再逐题输出选项
  不得按左栏→右栏的视觉顺序原样输出。

## 格式要求
- 段落之间用空行分隔，还原原图中的段落结构，不要把多段拼成一段
- 每道子问题 (1)(2)(3) 另起一行
- 选择题选项 A. B. C. D.（或 A/ B/ C/ D/）各占一行，选项前保留两个空格缩进
- 阅读理解：文章部分与题目部分之间用两个空行明显分隔；题目之间用一个空行分隔
- 完形填空空格：无论原图用横线还是数字，一律用 __数字__ 表示（如 __1__、__2__）
- 其他填空横线用 ____ 表示（四个下划线）
- 数学公式使用 LaTeX 语法：行内用 $...$，行间用 $$...$$
- 如有图形或表格，标注 [图] 或 [表格]

## 输出格式
只输出 JSON，格式：{"content": "整理后的题目内容，段落间含空行"}"""

_REFINE_SINGLE_Q_PROMPT = """你是一个高考题目文字整理助手。请对以下 OCR 识别的原始文字进行格式整理。

## 整理规则
1. 段落之间插入空行，不要将多个段落连成一行
2. 每道子问题 (1)(2)(3) 另起一行
3. 选择题选项 A. B. C. D.（含 A/ B/ C/ D/、A、B、C、D 等变体）各占一行，选项前加两个空格缩进
4. 阅读理解：若能识别出文章和题目两部分，之间用两个空行分隔；各题之间用一个空行分隔
5. 填空题横线统一为 ____（四个下划线）
6. 数学公式转写为 LaTeX 语法：行内用 $...$，行间用 $$...$$
7. 保留所有原始文字，不得删减任何内容

只输出 JSON，格式：{"content": "整理后的题目内容..."}"""


def _extract_pdf_text(pdf_path):
    """Extract text blocks with positions from a PDF using pymupdf.

    Returns list of dicts: {page, y0, y1, text, page_height}
    """
    import fitz
    doc = fitz.open(pdf_path)
    all_blocks = []
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        blocks = page.get_text('blocks')
        for b in blocks:
            text = b[4].strip()
            if text:
                all_blocks.append({
                    'page': page_idx,
                    'y0': b[1],
                    'y1': b[3],
                    'text': text,
                    'page_height': page.rect.height,
                })
    doc.close()
    # Sort by page, then y-position
    all_blocks.sort(key=lambda b: (b['page'], b['y0']))
    return all_blocks


def _get_recognition_llm_config(user_id=None):
    """Return (api_key, api_url, model) for the configured recognition method."""
    try:
        from models.settings import get_recognition_method
        method = get_recognition_method(user_id=user_id)
    except Exception:
        method = 'paddleocr_deepseek'

    if method == 'doubao_seed':
        return DOUBAO_API_KEY, DOUBAO_API_URL, DOUBAO_MODEL
    return DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL


def _get_recognition_method_name(user_id=None):
    """Return the configured recognition method key."""
    try:
        from models.settings import get_recognition_method
        return get_recognition_method(user_id=user_id)
    except Exception:
        return 'paddleocr_deepseek'


def _sanitize_llm_json(text):
    """Fix LaTeX backslashes in LLM JSON output so they survive json.loads().

    Doubles backslashes that are NOT valid JSON string escapes.
    Preserves \\\" and \\\\ (JSON structural escapes) and \\n / \\t (JSON
    whitespace escapes that LLMs use for paragraph/line breaks).
    LaTeX commands like \\frac, \\alpha, \\sqrt start with characters not in
    the preserved set, so they are correctly doubled.
    """
    text = re.sub(
        r'\\(?!["\\nt])',
        r'\\\\', text
    )
    return text


# ── Doubao Seed vision recognition ──────────────────────────────────

DOUBAO_VISION_PROMPT = """你是一个试卷题目识别助手。你的任务是分析试卷图片，识别并提取每一道题目，并标注每道题在页面中的大致位置。

## 输出要求
请严格按照以下 JSON 格式输出（不要输出任何其他内容）：

```json
{
  "questions": [
    {
      "question_number": "17",
      "content": "题目的完整文字内容。数学公式使用 LaTeX 语法（$...$ 或 $$...$$）。如果题目中有图表或几何图形，标注 [图表]。",
      "position": {
        "y_start": 40,
        "y_end": 55
      }
    }
  ],
  "note": ""
}
```

## position 字段说明
- y_start: 题目在页面中的起始位置，用百分比表示（0-100，从页面顶部算起）
- y_end: 题目在页面中的结束位置，用百分比表示（0-100）
- 每道题之间留略微宽松的范围

## 注意事项
- 识别所有题目：选择题、填空题、解答题
- 不要将考场须知、考试说明、章节标题等非题目内容列为题目
- 题号格式统一为数字（去除"第"、"题"、"、"、"."等）
- 如果题目包含子问题如(1)(2)(3)，将所有子问题合并到一道题中
- 数学公式使用 $...$ 或 $$...$$ 语法（禁止使用 \\(...\\) 语法）
- 禁止在content中使用反斜杠后跟空格、下划线、括号等字符
- 不要遗漏任何题目"""

MAX_IMAGE_DIM = 2048  # Resize images to at most this width/height before sending

_doubao_client = None


def _get_doubao_client():
    """Return a cached Ark client for Doubao Seed API."""
    global _doubao_client
    if _doubao_client is None:
        from volcenginesdkarkruntime import Ark
        _doubao_client = Ark(
            base_url=DOUBAO_BASE_URL,
            api_key=DOUBAO_API_KEY,
        )
    return _doubao_client


def _encode_image_for_api(image_path):
    """Resize and encode an image to a base64 data URI suitable for vision API."""
    from io import BytesIO

    img = Image.open(image_path)
    w, h = img.size
    if max(w, h) > MAX_IMAGE_DIM:
        scale = MAX_IMAGE_DIM / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')

    buf = BytesIO()
    img.save(buf, format='JPEG', quality=85)
    img_bytes = buf.getvalue()
    img_b64 = base64.b64encode(img_bytes).decode('utf-8')
    return f'data:image/jpeg;base64,{img_b64}'


def _recognize_page_with_doubao(image_path, page_num, total_pages):
    """Use Doubao Seed vision model to recognize questions on a page image."""
    if not DOUBAO_API_KEY:
        return {'questions': [], 'note': 'Doubao API key not configured'}

    data_uri = _encode_image_for_api(image_path)

    client = _get_doubao_client()
    response = client.responses.create(
        model=DOUBAO_VISION_MODEL,
        input=[{
            'role': 'user',
            'content': [
                {
                    'type': 'input_text',
                    'text': DOUBAO_VISION_PROMPT,
                },
                {
                    'type': 'input_image',
                    'image_url': data_uri,
                },
                {
                    'type': 'input_text',
                    'text': (
                        f'请识别这张图片（第 {page_num}/{total_pages} 页）的所有题目。'
                        f'只输出JSON，不要任何其他文字。'
                    ),
                },
            ],
        }],
    )

    raw_text = ''
    for item in response.output:
        if getattr(item, 'type', '') == 'message':
            for content_block in item.content:
                if hasattr(content_block, 'text'):
                    raw_text += content_block.text

    if not raw_text:
        return {'questions': [], 'note': 'Empty response from Doubao Seed'}

    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw_text, re.DOTALL)
    if json_match:
        raw_text = json_match.group(1)

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        sanitized = _sanitize_llm_json(raw_text)
        try:
            return json.loads(sanitized)
        except json.JSONDecodeError:
            return {'questions': [], 'note': f'Failed to parse JSON: {raw_text[:200]}'}


def _recognize_single_question(image_path):
    """Recognize a single cropped question image using Doubao Seed vision API.

    Returns the recognized text content string.
    Raises RuntimeError if Doubao API key is not configured.
    """
    if not DOUBAO_API_KEY:
        raise RuntimeError('视觉识别需要配置 Doubao API Key，请在设置中配置。')

    data_uri = _encode_image_for_api(image_path)
    client = _get_doubao_client()

    response = client.responses.create(
        model=DOUBAO_VISION_MODEL,
        input=[{
            'role': 'user',
            'content': [
                {'type': 'input_text', 'text': _SINGLE_Q_PROMPT},
                {'type': 'input_image', 'image_url': data_uri},
            ],
        }],
    )

    raw_text = ''
    for item in response.output:
        if getattr(item, 'type', '') == 'message':
            for content_block in item.content:
                if hasattr(content_block, 'text'):
                    raw_text += content_block.text

    if not raw_text:
        return ''

    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw_text, re.DOTALL)
    if json_match:
        raw_text = json_match.group(1)

    try:
        return json.loads(raw_text).get('content', '')
    except json.JSONDecodeError:
        sanitized = _sanitize_llm_json(raw_text)
        try:
            return json.loads(sanitized).get('content', '')
        except json.JSONDecodeError:
            return raw_text.strip()


def _recognize_single_question_ocr(image_path, user_id=None):
    """Recognize a cropped question image via PaddleOCR + LLM text refinement.

    Used when the recognition method is paddleocr_deepseek. Runs OCR on the
    cropped region, then asks the text LLM to fix LaTeX and clean up formatting.
    Falls back to raw OCR text if the LLM call fails.
    """
    blocks = _extract_image_text(image_path)
    if not blocks:
        return ''

    raw_text = '\n'.join(b['text'] for b in blocks)

    api_key, api_url, model = _get_recognition_llm_config(user_id=user_id)
    if not api_key:
        return raw_text

    is_anthropic = '/anthropic/' in api_url
    try:
        if is_anthropic:
            resp = requests.post(
                api_url,
                headers={'x-api-key': api_key, 'Content-Type': 'application/json'},
                json={
                    'model': model,
                    'system': _REFINE_SINGLE_Q_PROMPT,
                    'messages': [{'role': 'user', 'content': raw_text}],
                    'temperature': 0.2,
                    'max_tokens': 2048,
                    'thinking': {'type': 'disabled'},
                },
                timeout=60,
            )
        else:
            resp = requests.post(
                api_url,
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': model,
                    'messages': [
                        {'role': 'system', 'content': _REFINE_SINGLE_Q_PROMPT},
                        {'role': 'user', 'content': raw_text},
                    ],
                    'temperature': 0.2,
                    'max_tokens': 2048,
                },
                timeout=60,
            )
        resp.raise_for_status()
        data = resp.json()

        if is_anthropic:
            content = ''.join(
                b.get('text', '') for b in data.get('content', [])
                if b.get('type') == 'text'
            )
        else:
            content = data['choices'][0]['message']['content']

        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)

        try:
            return json.loads(content).get('content', raw_text)
        except json.JSONDecodeError:
            sanitized = _sanitize_llm_json(content)
            try:
                return json.loads(sanitized).get('content', raw_text)
            except json.JSONDecodeError:
                return raw_text
    except Exception:
        return raw_text


# ── PaddleOCR lazy singleton ────────────────────────────────────────
_paddle_ocr = None
_paddle_formula = None


def _get_paddle_ocr():
    """Return a cached PaddleOCR instance (text detection + recognition).

    Disables unnecessary preprocessing models for speed.
    Uses PP-OCRv5_mobile (faster, lighter) instead of server models.
    Models are loaded once and reused across requests.
    """
    global _paddle_ocr
    if _paddle_ocr is None:
        import warnings
        warnings.filterwarnings('ignore')
        from paddleocr import PaddleOCR
        _paddle_ocr = PaddleOCR(
            lang='ch',
            ocr_version='PP-OCRv4',
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    return _paddle_ocr


def _get_paddle_formula():
    """Return a cached PaddleOCR FormulaRecognition instance."""
    global _paddle_formula
    if _paddle_formula is None:
        import warnings
        warnings.filterwarnings('ignore')
        from paddleocr import FormulaRecognition
        _paddle_formula = FormulaRecognition()
    return _paddle_formula


def _extract_image_text(image_path):
    """Extract text from an image using PaddleOCR.

    Returns list of dicts: {page: 0, y0, y1, text, page_height}
    Each dict represents a detected text line with its bounding box.
    """
    try:
        ocr = _get_paddle_ocr()
    except Exception:
        return None

    try:
        result = ocr.ocr(image_path)
        if not result:
            return None

        page = result[0]
        img = Image.open(image_path)
        _, h = img.size

        blocks = []
        # PaddleOCR v3 returns OCRResult (dict-like) with rec_polys + rec_texts
        if hasattr(page, 'keys'):
            polys = page.get('rec_polys', []) or []
            texts = page.get('rec_texts', []) or []
            scores = page.get('rec_scores', []) or []
        else:
            # Legacy list-of-lists format
            polys, texts, scores = [], [], []
            for line in page:
                if len(line) == 2:
                    poly, (text, score) = line[0], line[1]
                    polys.append(poly)
                    texts.append(text)
                    scores.append(score)

        for poly, text in zip(polys, texts):
            text = (text[0] if isinstance(text, tuple) else text).strip()
            if text:
                y0 = min(p[1] for p in poly)
                y1 = max(p[1] for p in poly)
                blocks.append({
                    'page': 0,
                    'y0': y0,
                    'y1': y1,
                    'text': text,
                    'page_height': h,
                })

        blocks.sort(key=lambda b: b['y0'])
        return blocks if blocks else None
    except Exception:
        return None


def _extract_formulas(image_path):
    """Use PaddleOCR FormulaRecognition to detect and convert math formulas.

    Returns dict: {region_index: latex_string} keyed by y-position range.
    """
    try:
        fr = _get_paddle_formula()
    except Exception:
        return {}

    try:
        result = fr.ocr(image_path)
        if not result:
            return {}

        page = result[0]
        formulas = {}
        if hasattr(page, 'keys'):
            polys = page.get('rec_polys', []) or []
            texts = page.get('rec_texts', []) or []
            for poly, text in zip(polys, texts):
                text = (text[0] if isinstance(text, tuple) else text).strip()
                if text:
                    y0 = min(p[1] for p in poly)
                    y1 = max(p[1] for p in poly)
                    formulas[(y0, y1)] = text
        return formulas
    except Exception:
        return {}


def _group_blocks_by_page(blocks):
    """Group text blocks by page number."""
    pages = {}
    for b in blocks:
        p = b['page']
        if p not in pages:
            pages[p] = {'blocks': [], 'page_height': b['page_height']}
        pages[p]['blocks'].append(b)
    return pages


def _is_question_start(text):
    """Check if a text block starts with a main question number pattern.

    Skips sub-question markers like bare (1) (2) (3).
    """
    t = text.strip()
    if not _QUESTION_PATTERN.match(t):
        return False
    # Skip bare parenthesized numbers: "(1)", "(2)" are sub-questions
    if _SUB_QUESTION_RE.match(t):
        return False
    return True


def _extract_question_number(text):
    """Extract the question number from text. Returns string or None."""
    text = text.strip()
    m = _QUESTION_PATTERN.match(text)
    if m:
        return m.group(1) or m.group(2)
    return None


def _split_into_questions(blocks, page_height):
    """Split a page's text blocks into individual questions based on patterns.

    Returns list of {question_number, content, y_start_pct, y_end_pct}
    """
    if not blocks:
        return []

    # Find all question start indices
    q_starts = []
    for i, b in enumerate(blocks):
        if _is_question_start(b['text']):
            q_starts.append(i)

    if not q_starts:
        return []

    questions = []
    for idx, start_i in enumerate(q_starts):
        end_i = q_starts[idx + 1] if idx + 1 < len(q_starts) else len(blocks)
        q_blocks = blocks[start_i:end_i]

        q_num = _extract_question_number(q_blocks[0]['text']) or str(idx + 1)
        content = '\n'.join(b['text'] for b in q_blocks)

        y_start = q_blocks[0]['y0'] / page_height * 100
        y_end = q_blocks[-1]['y1'] / page_height * 100

        questions.append({
            'question_number': q_num,
            'content': content,
            'y_start': round(y_start, 1),
            'y_end': round(y_end, 1),
        })

    return questions


def _refine_with_llm(questions, user_id=None):
    """Use LLM text API to refine question content and fix any
    mis-splits. Returns the refined question list."""
    api_key, api_url, model = _get_recognition_llm_config(user_id=user_id)
    if not api_key or not questions:
        return questions

    text_input = '\n---\n'.join(
        f"[题号 {q['question_number']}]\n{q['content']}"
        for q in questions
    )

    # Determine if using Anthropic-compatible endpoint
    is_anthropic = '/anthropic/' in api_url
    try:
        if is_anthropic:
            resp = requests.post(
                api_url,
                headers={
                    'x-api-key': api_key,
                    'Content-Type': 'application/json',
                },
                json={
                    'model': model,
                    'system': LLM_REFINE_PROMPT,
                    'messages': [
                        {'role': 'user', 'content': text_input},
                    ],
                    'temperature': 0.3,
                    'max_tokens': 4096,
                    'thinking': {'type': 'disabled'},
                },
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            content = ''
            for block in data.get('content', []):
                if block.get('type') == 'text':
                    content += block.get('text', '')
        else:
            resp = requests.post(
                api_url,
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': model,
                    'messages': [
                        {'role': 'system', 'content': LLM_REFINE_PROMPT},
                        {'role': 'user', 'content': text_input},
                    ],
                    'temperature': 0.3,
                    'max_tokens': 4096,
                },
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data['choices'][0]['message']['content']

        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)

        refined = json.loads(content)
        refined_questions = refined.get('questions', [])
        if refined_questions:
            # Match refined questions to originals by question number (not index),
            # because LLM may remove non-question items (exam headers, section titles).
            orig_by_num = {}
            for q in questions:
                orig_by_num[q['question_number']] = q

            for rq in refined_questions:
                rq_num = rq.get('question_number', '')
                orig = orig_by_num.get(rq_num)
                if orig:
                    rq['y_start'] = orig['y_start']
                    rq['y_end'] = orig['y_end']
                # If no match by number, copy position from an unmatched original
                # by finding the one with best text overlap
            return refined_questions
    except Exception:
        pass

    return questions


def _crop_question(page_img_path, y_start, y_end, output_path,
                   x_start=0, x_end=100):
    """Crop a question from a page image by percentage range."""
    img = Image.open(page_img_path)
    w, h = img.size
    left = max(0, int(w * x_start / 100))
    right = min(w, int(w * x_end / 100))
    top = max(0, int(h * y_start / 100))
    bottom = min(h, int(h * y_end / 100))
    cropped = img.crop((left, top, right, bottom))
    cropped.save(output_path, 'PNG')


def _match_questions_with_ocr(questions, ocr_blocks, image_height):
    """Use OCR text blocks to find precise Y positions for Doubao questions.

    Phase 1: match OCR question-number blocks to Doubao questions by actual
    number (e.g. OCR "6." block matches Q6, not the 6th question in order).
    Phase 2: unmatched questions interpolate between neighboring anchors.
    """

    def _clean_num(n):
        return str(n).strip().lstrip('0') or '0'

    # Find section boundary
    section_re = re.compile(r'^[一二三四五六七八九十]+[、\．]')
    section_y = 0
    for block in ocr_blocks:
        if section_re.match(block.get('text', '')):
            section_y = block['y0']
            break

    # Collect OCR question-number blocks, extract actual number
    ocr_by_num = {}  # {clean_number: y_top_px}
    for block in ocr_blocks:
        text = block.get('text', '')
        if block['y0'] <= section_y:
            continue
        if _SUB_QUESTION_RE.match(text):
            continue
        m = _QUESTION_PATTERN.match(text)
        if m:
            num = _clean_num(m.group(1) or m.group(2) or '')
            if num and num not in ocr_by_num:
                ocr_by_num[num] = block['y0']

    # Phase 1: exact number match
    anchors = []  # [(question_index, y_px)]
    for qi, q in enumerate(questions):
        q_num = _clean_num(q.get('question_number', ''))
        if q_num in ocr_by_num:
            q['y0_px'] = int(ocr_by_num[q_num])
            anchors.append((qi, q['y0_px']))
        else:
            q['y0_px'] = None  # mark as unmatched

    # Sort anchors by Y position
    anchors.sort(key=lambda x: x[1])

    # Phase 2: interpolate unmatched questions between anchors
    for qi, q in enumerate(questions):
        if q.get('y0_px') is not None:
            continue

        # Find nearest anchors above and below by question index
        above_qi, above_y = None, 0
        below_qi, below_y = None, image_height

        for a_qi, a_y in anchors:
            if a_qi < qi and (above_qi is None or a_qi > above_qi):
                above_qi, above_y = a_qi, a_y
            if a_qi > qi and (below_qi is None or a_qi < below_qi):
                below_qi, below_y = a_qi, a_y

        if above_qi is not None and below_qi is not None:
            # Interpolate: split the pixel gap proportionally by question count
            gap_questions = below_qi - above_qi
            gap_pixels = below_y - above_y
            q['y0_px'] = int(above_y + gap_pixels * (qi - above_qi) / gap_questions)
        elif above_qi is not None:
            # Extrapolate after last anchor
            q['y0_px'] = int(above_y + 80 * (qi - above_qi))
        elif below_qi is not None:
            # Before first anchor
            q['y0_px'] = max(0, int(below_y - 80 * (below_qi - qi)))
        else:
            # No anchors at all — fall back to LLM estimate
            q['y0_px'] = int(image_height * float(q.get('y_start', 0)) / 100)

    # y1_px set later by _crop_questions_for_page; set a placeholder
    for q in questions:
        q['y1_px'] = q['y0_px'] + 50


def _crop_question_px(page_img_path, y0_px, y1_px, output_path):
    """Crop a question from a page image using pixel coordinates."""
    img = Image.open(page_img_path)
    w, h = img.size
    padding = 15
    top = max(0, y0_px - padding)
    bottom = min(h, y1_px + padding)
    cropped = img.crop((0, top, w, bottom))
    cropped.save(output_path, 'PNG')


def _pdf_to_images(pdf_path, output_dir):
    """Convert PDF pages to PNG images at 200 DPI."""
    import fitz
    doc = fitz.open(pdf_path)
    paths = []
    for i in range(len(doc)):
        pix = doc[i].get_pixmap(dpi=200)
        p = os.path.join(output_dir, f"page_{i + 1:03d}.png")
        pix.save(p)
        paths.append(p)
    doc.close()
    return paths


def _crop_questions_for_page(questions, page_img, questions_dir, page_num):
    """Crop question images from a page image.

    Boundaries are seamless: Q(i+1).top == Q(i).bottom.  Only the first
    question has a small top offset to skip page headers.  The last question
    extends to the bottom of the page.
    """
    # Sort by y_start so we can walk top-to-bottom
    sorted_pairs = sorted(
        enumerate(questions), key=lambda x: float(x[1].get('y_start', 0))
    )
    q_count = len(sorted_pairs)
    pad_pct = 1.5

    for rank, (orig_i, q) in enumerate(sorted_pairs):
        text_y0 = float(q.get('y_start', 0))

        if rank == 0:
            crop_y0 = max(0, text_y0 - pad_pct)
        else:
            # Seamless: start exactly where previous question ended
            crop_y0 = prev_crop_y1

        if rank + 1 < q_count:
            # End at the next question's start position
            next_y0 = float(sorted_pairs[rank + 1][1].get('y_start', 100))
            crop_y1 = next_y0
        else:
            # Last question: extend to page bottom
            crop_y1 = 100

        if crop_y1 - crop_y0 < 5:
            mid = (crop_y0 + crop_y1) / 2
            crop_y0 = max(0, mid - 2.5)
            crop_y1 = min(100, mid + 2.5)

        prev_crop_y1 = crop_y1

        q_num = q.get('question_number', '')
        img_name = f'p{page_num + 1:02d}_{rank:02d}_q{q_num}.png'
        img_path = os.path.join(questions_dir, img_name)
        try:
            if page_img and os.path.isfile(page_img):
                _crop_question(page_img, crop_y0, crop_y1, img_path)
            q['image'] = img_name
        except Exception:
            if page_img:
                shutil.copy(page_img, img_path)
            q['image'] = img_name

        q['page'] = page_num + 1
        q['crop_y_start'] = round(crop_y0, 1)
        q['crop_y_end'] = round(crop_y1, 1)
        q['crop_x_start'] = 0.0
        q['crop_x_end'] = 100.0


def process_paper(file, task_id, user_id=None):
    """Process uploaded paper file: extract text, segment questions, crop images.

    Uses the configured recognition method (PaddleOCR+DeepSeek or Doubao Seed).
    """
    task_dir = os.path.join(PAPER_TEMP_DIR, task_id)
    pages_dir = os.path.join(task_dir, 'pages')
    questions_dir = os.path.join(task_dir, 'questions')
    os.makedirs(pages_dir, exist_ok=True)
    os.makedirs(questions_dir, exist_ok=True)

    ext = os.path.splitext(file.filename)[1].lower()
    original_path = os.path.join(task_dir, f'original{ext}')
    file.save(original_path)

    is_pdf = (ext == '.pdf')
    recognition_method = _get_recognition_method_name(user_id=user_id)

    # ── Prepare page images ──
    if is_pdf:
        page_images = _pdf_to_images(original_path, pages_dir)
    else:
        dest = os.path.join(pages_dir, f'page_001{ext}')
        shutil.copy(original_path, dest)
        page_images = [dest]

    page_image_names = [os.path.basename(p) for p in page_images]

    # ── Doubao Seed vision path ──
    if recognition_method == 'doubao_seed':
        all_questions = []
        errors = []
        total = len(page_images)
        for idx, page_img in enumerate(page_images):
            page_num = idx + 1
            try:
                result = _recognize_page_with_doubao(page_img, page_num, total)
            except Exception as e:
                errors.append(f'第{page_num}页 Doubao Seed 识别失败：{e}')
                continue

            questions = result.get('questions', [])
            # Keep LLM-estimated positions as fallback
            for q in questions:
                pos = q.pop('position', None) or {}
                q['y_start'] = float(pos.get('y_start', q.pop('y_start', 0)))
                q['y_end'] = float(pos.get('y_end', q.pop('y_end', 100)))

            # Use PaddleOCR for precise question positions
            ocr_blocks = _extract_image_text(page_img)
            if ocr_blocks:
                img = Image.open(page_img)
                _match_questions_with_ocr(questions, ocr_blocks, img.size[1])
                for q in questions:
                    if 'y0_px' in q:
                        y0 = q['y0_px']
                        y1 = q['y1_px']
                        img_h = img.size[1]
                        q['y_start'] = round(y0 / img_h * 100, 1)
                        q['y_end'] = round(y1 / img_h * 100, 1)
                    q.pop('y0_px', None)
                    q.pop('y1_px', None)

            _crop_questions_for_page(questions, page_img, questions_dir, idx)
            all_questions.extend(questions)

        result_data = {
            'task_id': task_id,
            'original_filename': file.filename,
            'page_count': total,
            'question_count': len(all_questions),
            'questions': all_questions,
            'errors': errors,
            'page_image_names': page_image_names,
        }
        with open(os.path.join(task_dir, 'result.json'), 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        return result_data

    # ── PaddleOCR + DeepSeek path (default) ──
    if is_pdf:
        blocks = _extract_pdf_text(original_path)
    else:
        blocks = _extract_image_text(original_path)
        if blocks is None:
            blocks = []

    if not blocks:
        errors = []
        if is_pdf:
            errors.append('未能从 PDF 中提取文字，PDF 可能为扫描图片格式。'
                          '请尝试将扫描件转为可搜索 PDF 后重试。')
        else:
            errors.append('PaddleOCR 未能识别图片中的文字，请检查图片清晰度。')
        result_data = {
            'task_id': task_id, 'original_filename': file.filename,
            'page_count': len(page_images), 'question_count': 0,
            'questions': [], 'errors': errors,
            'page_image_names': page_image_names,
        }
        with open(os.path.join(task_dir, 'result.json'), 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        return result_data

    pages = _group_blocks_by_page(blocks)
    all_questions = []
    errors = []

    for page_num in sorted(pages.keys()):
        page_data = pages[page_num]
        page_blocks = page_data['blocks']
        page_height = page_data['page_height']

        questions = _split_into_questions(page_blocks, page_height)
        if not questions:
            errors.append(f'第{page_num + 1}页未识别到题号，请手动检查。')
            continue

        try:
            questions = _refine_with_llm(questions, user_id=user_id)
        except Exception as e:
            errors.append(f'第{page_num + 1}页 LLM 优化失败：{e}')

        page_img = page_images[page_num] if page_num < len(page_images) else None
        _crop_questions_for_page(questions, page_img, questions_dir, page_num)
        all_questions.extend(questions)

    result_data = {
        'task_id': task_id, 'original_filename': file.filename,
        'page_count': len(page_images), 'question_count': len(all_questions),
        'questions': all_questions, 'errors': errors,
        'page_image_names': page_image_names,
    }
    with open(os.path.join(task_dir, 'result.json'), 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    return result_data


def prepare_paper(file, task_id):
    """Save uploaded file and render page images. No OCR or question detection.

    This is the entry point for the manual-selection workflow. After calling this,
    the user manually draws bounding boxes for each question on the review page,
    then calls recognize_question_images() to extract text content.
    """
    task_dir = os.path.join(PAPER_TEMP_DIR, task_id)
    pages_dir = os.path.join(task_dir, 'pages')
    questions_dir = os.path.join(task_dir, 'questions')
    os.makedirs(pages_dir, exist_ok=True)
    os.makedirs(questions_dir, exist_ok=True)

    ext = os.path.splitext(file.filename)[1].lower()
    original_path = os.path.join(task_dir, f'original{ext}')
    file.save(original_path)

    if ext == '.pdf':
        page_images = _pdf_to_images(original_path, pages_dir)
    else:
        dest = os.path.join(pages_dir, f'page_001{ext}')
        shutil.copy(original_path, dest)
        page_images = [dest]

    page_image_names = [os.path.basename(p) for p in page_images]

    result_data = {
        'task_id': task_id,
        'original_filename': file.filename,
        'page_count': len(page_images),
        'page_image_names': page_image_names,
        'questions': [],
    }
    with open(os.path.join(task_dir, 'result.json'), 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    return result_data


def crop_region(task_id, page, x_start, y_start, x_end, y_end, name):
    """Crop a rectangular region from a page image and save it as a PNG.

    Args:
        task_id: The processing task ID.
        page: 1-based page number.
        x_start, y_start, x_end, y_end: Crop boundaries as percentages (0-100).
        name: Base name for the output file (without extension).

    Returns:
        The filename of the saved crop (e.g. 'q_abc123.png'), or None on failure.
    """
    task_dir = os.path.join(PAPER_TEMP_DIR, task_id)
    pages_dir = os.path.join(task_dir, 'pages')
    questions_dir = os.path.join(task_dir, 'questions')
    os.makedirs(questions_dir, exist_ok=True)

    page_img = os.path.join(pages_dir, f'page_{page:03d}.png')
    if not os.path.isfile(page_img):
        for ext in ('.jpg', '.jpeg'):
            alt = os.path.join(pages_dir, f'page_{page:03d}{ext}')
            if os.path.isfile(alt):
                page_img = alt
                break
        else:
            return None

    img_name = f'{name}.png'
    img_path = os.path.join(questions_dir, img_name)
    try:
        _crop_question(page_img, y_start, y_end, img_path, x_start=x_start, x_end=x_end)
        return img_name
    except Exception:
        return None


def recognize_question_images(task_id, questions_data, user_id=None):
    """Crop question regions from page images and recognize their text content.

    Args:
        task_id: The processing task ID.
        questions_data: List of dicts with keys:
            id, page, x_start, y_start, x_end, y_end
        user_id: Used to select the configured recognition method.

    Returns:
        List of dicts: {id, content, image} on success, or {id, error} on failure.
    """
    task_dir = os.path.join(PAPER_TEMP_DIR, task_id)
    pages_dir = os.path.join(task_dir, 'pages')
    questions_dir = os.path.join(task_dir, 'questions')
    os.makedirs(questions_dir, exist_ok=True)

    recognition_method = _get_recognition_method_name(user_id=user_id)

    results = []
    for q in questions_data:
        q_id = q['id']
        page = int(q.get('page', 1))
        x_start = float(q.get('x_start', 0))
        y_start = float(q.get('y_start', 0))
        x_end = float(q.get('x_end', 100))
        y_end = float(q.get('y_end', 100))

        page_img = os.path.join(pages_dir, f'page_{page:03d}.png')
        if not os.path.isfile(page_img):
            for ext in ('.jpg', '.jpeg'):
                alt = os.path.join(pages_dir, f'page_{page:03d}{ext}')
                if os.path.isfile(alt):
                    page_img = alt
                    break
            else:
                results.append({'id': q_id, 'error': f'第{page}页图片不存在'})
                continue

        img_name = f'{q_id}.png'
        img_path = os.path.join(questions_dir, img_name)
        try:
            _crop_question(page_img, y_start, y_end, img_path, x_start=x_start, x_end=x_end)
        except Exception as e:
            results.append({'id': q_id, 'error': f'裁图失败: {e}'})
            continue

        try:
            if recognition_method == 'doubao_seed':
                content = _recognize_single_question(img_path)
            else:
                # paddleocr_deepseek: OCR the cropped image, then refine with text LLM
                content = _recognize_single_question_ocr(img_path, user_id=user_id)
            results.append({'id': q_id, 'content': content, 'image': img_name})
        except Exception as e:
            results.append({'id': q_id, 'error': str(e)})

    return results


def recrop_question(task_id, page_num, y_start, y_end, question_index,
                    x_start=0, x_end=100):
    """Re-crop a question with user-adjusted boundaries.

    Args:
        task_id: The processing task ID.
        page_num: 1-based page number.
        y_start: New top boundary in percentage (0-100).
        y_end: New bottom boundary in percentage (0-100).
        question_index: Index of the question (used for filename).
        x_start: New left boundary in percentage (0-100).
        x_end: New right boundary in percentage (0-100).

    Returns:
        New image filename, or None if re-crop failed.
    """
    task_dir = os.path.join(PAPER_TEMP_DIR, task_id)
    pages_dir = os.path.join(task_dir, 'pages')
    questions_dir = os.path.join(task_dir, 'questions')
    os.makedirs(questions_dir, exist_ok=True)

    page_img = os.path.join(pages_dir, f'page_{page_num:03d}.png')
    if not os.path.isfile(page_img):
        # Try original extension
        for ext in ('.jpg', '.jpeg', '.png'):
            alt = os.path.join(pages_dir, f'page_{page_num:03d}{ext}')
            if os.path.isfile(alt):
                page_img = alt
                break
        else:
            return None

    # Find existing cropped image to get the question number for filename
    result = load_result(task_id)
    q_num = str(question_index + 1)
    if result:
        for q in result.get('questions', []):
            if q.get('page') == page_num:
                q_num = q.get('question_number', q_num)
                break

    img_name = f'p{page_num:02d}_{question_index:02d}_q{q_num}.png'
    img_path = os.path.join(questions_dir, img_name)
    _crop_question(page_img, y_start, y_end, img_path,
                   x_start=x_start, x_end=x_end)
    return img_name


def load_result(task_id):
    """Load a saved processing result by task ID."""
    result_path = os.path.join(PAPER_TEMP_DIR, task_id, 'result.json')
    if not os.path.exists(result_path):
        return None
    with open(result_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_result(task_id, result):
    """Persist updated result data."""
    task_dir = os.path.join(PAPER_TEMP_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)
    with open(os.path.join(task_dir, 'result.json'), 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


def get_temp_image_path(task_id, subdir, filename):
    """Return the full path to a temporary image, or None."""
    path = os.path.join(PAPER_TEMP_DIR, task_id, subdir, filename)
    return path if os.path.isfile(path) else None


def cleanup_task(task_id):
    """Remove a single task directory after successful import."""
    task_dir = os.path.join(PAPER_TEMP_DIR, task_id)
    if os.path.isdir(task_dir):
        shutil.rmtree(task_dir, ignore_errors=True)


def cleanup_old_tasks(max_age_hours=24):
    """Remove task directories older than max_age_hours. Called on startup."""
    if not os.path.isdir(PAPER_TEMP_DIR):
        return
    import time
    now = time.time()
    cutoff = now - max_age_hours * 3600
    for name in os.listdir(PAPER_TEMP_DIR):
        task_dir = os.path.join(PAPER_TEMP_DIR, name)
        try:
            if os.path.isdir(task_dir) and os.path.getmtime(task_dir) < cutoff:
                shutil.rmtree(task_dir, ignore_errors=True)
        except OSError:
            pass
