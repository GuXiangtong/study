import json
import os
import re

# --- JSON repair helpers ---
# Regex matching ASCII " used as Chinese quotation marks inside JSON string values.
_INNER_QUOTE_RE = re.compile(
    r'(?<=[一-鿿　-〿＀-￯\w)）\]】])'
    r'"'
    r'(?=[一-鿿　-〿＀-￯\w(（\[【])'
)


def _fix_backslashes(text):
    """Double lone backslashes that are not already part of valid JSON escapes."""
    PH_BS = ''
    PH_QT = ''
    fixed = text.replace('\\\\', PH_BS)
    fixed = fixed.replace('\\"', PH_QT)
    fixed = fixed.replace('\\', '\\\\')
    fixed = fixed.replace(PH_BS, '\\\\')
    fixed = fixed.replace(PH_QT, '\\"')
    return fixed


def _fix_inner_quotes(text):
    """Escape ASCII double-quotes used as Chinese quotation marks inside JSON strings."""
    return _INNER_QUOTE_RE.sub('\\"', text)


def _safe_json_parse(text):
    """Parse JSON, applying incremental fixes for common LLM output issues."""
    # 1. Try as-is
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Fix inner quotes only
    try:
        return json.loads(_fix_inner_quotes(text))
    except json.JSONDecodeError:
        pass

    # 3. Fix backslashes only
    try:
        return json.loads(_fix_backslashes(text))
    except json.JSONDecodeError:
        pass

    # 4. Fix both: backslashes first, then inner quotes
    fixed = _fix_inner_quotes(_fix_backslashes(text))
    try:
        return json.loads(fixed)
    except json.JSONDecodeError as e:
        import datetime
        log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '_tmp', 'llm_debug.log')
        pos = e.pos or 0
        snippet = fixed[max(0, pos - 50):pos + 50]
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.datetime.now().isoformat()}] JSON PARSE FAIL at pos {pos}: ...{repr(snippet)}...\n")
        raise
