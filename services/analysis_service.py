import json
import os
import re
import requests
from datetime import date
from config import ANALYSIS_DIR, LLM_API_KEY, LLM_API_URL, LLM_MODEL
from models.question import get_question
from models.sub_question import get_sub_questions_by_question
from models.analysis import create_analysis

SYSTEM_PROMPT = """你是一名上海市高三辅导老师，擅长分析学生错题。你需要严格按照以下四步流程输出分析结果。

## 核心原则
- 所有知识点严格限定在上海市高考考纲范围内
- 绝不直接给出答案，重点教授思考方式和解题路径
- 用苏格拉底式的提问引导学生自己找到答案
- 数学公式使用 LaTeX 语法（$...$ 行内，$$...$$ 行间）
- 用通俗的语言解释抽象概念

## 输出格式
请严格按照以下 JSON 格式输出（不要输出其他内容）：

```json
{
  "step1": {
    "knowledge_points": "具体的知识点（如：二次函数在闭区间上的最值问题）",
    "syllabus_section": "所属考纲板块",
    "ai_analysis": "详细分析：1)题目考察什么 2)学生错误根源 3)需要补齐的知识点"
  },
  "step2": {
    "weakness_analysis": "从概念层面、方法层面、思维层面分别诊断薄弱点，梳理前置知识→核心知识→拓展应用的知识链条",
    "knowledge_framework": "知识框架描述",
    "comparison_table": "易混淆概念对比（如有）"
  },
  "step3": {
    "steps": [
      {"name": "审题", "guidance": "引导学生审题的提问"},
      {"name": "切入点", "guidance": "帮助学生找到切入点的提问"},
      {"name": "路径推演", "guidance": "一步一步推导的思路框架"},
      {"name": "易错提醒", "guidance": "这类题的常见错误"},
      {"name": "验证方法", "guidance": "如何检查答案正确性"}
    ],
    "note": "以上每一步请学生先自己思考，再看提示"
  },
  "step4": {
    "exercises": [
      {
        "difficulty": "基础题",
        "content": "题目内容（含LaTeX公式）",
        "answer": "参考答案",
        "solution_steps": "解题步骤",
        "knowledge_points": "考察知识点"
      },
      {
        "difficulty": "提高题",
        "content": "题目内容（含LaTeX公式）",
        "answer": "参考答案",
        "solution_steps": "解题步骤",
        "knowledge_points": "考察知识点"
      },
      {
        "difficulty": "难题",
        "content": "题目内容（含LaTeX公式）",
        "answer": "参考答案",
        "solution_steps": "解题步骤",
        "knowledge_points": "考察知识点"
      }
    ]
  }
}
```"""


def _build_analysis_prompt(question, sub_questions):
    """Construct the user prompt for the LLM with all sub-question context."""
    prompt_parts = []

    prompt_parts.append(f"## 基本信息")
    prompt_parts.append(f"- 学科：{question.get('subject_name', '')}")
    prompt_parts.append(f"- 考试：{question.get('exam_name', '')}")
    prompt_parts.append(f"- 题号：第 {question.get('question_number', '')} 题")

    question_text = question.get('stem') or ''
    if question_text:
        prompt_parts.append(f"\n## 题目内容\n{question_text}")

    prompt_parts.append(f"\n## 子问题及学生作答情况")
    prompt_parts.append(f"本题共 {len(sub_questions)} 个子问题。\n")

    for sq in sub_questions:
        label = sq.get('label', '')
        prompt_parts.append(f"### 子问题 {label}")
        sq_content = sq.get('content') or ''
        if sq_content:
            prompt_parts.append(f"题目：{sq_content}")

        correct_answer = sq.get('correct_answer') or ''
        if correct_answer:
            prompt_parts.append(f"正确答案：{correct_answer}")

        student_answer = sq.get('student_answer') or '（未填写）'
        prompt_parts.append(f"学生错误答案：{student_answer}")

        error_type = sq.get('error_type') or '未分类'
        prompt_parts.append(f"错误类型：{error_type}")

        error_reason = sq.get('error_reason') or '（未填写）'
        prompt_parts.append(f"学生自述错误原因：{error_reason}")

        kp = sq.get('knowledge_points') or ''
        if kp:
            prompt_parts.append(f"已标注知识点：{kp}")
        prompt_parts.append("")

    prompt_parts.append("请综合所有子问题的错误情况，按照系统提示中的 JSON 格式输出完整的四步分析结果。")

    return '\n'.join(prompt_parts)


def _call_deepseek(system_prompt, user_prompt):
    """Call DeepSeek API and return parsed JSON."""
    resp = requests.post(
        LLM_API_URL,
        headers={
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 4096,
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]

    # Extract JSON from the response (may be wrapped in ```json ... ```)
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
    if json_match:
        content = json_match.group(1)
    return json.loads(content)


def _parse_llm_response(llm_data):
    """Convert LLM JSON response into the 4-step dicts the app expects."""
    step1 = {
        'title': '第一步：分析错题，定位知识点',
        'question_summary': llm_data.get('step1', {}).get('question_summary', ''),
        'student_error_reason': '',
        'ai_analysis': llm_data.get('step1', {}).get('ai_analysis', ''),
        'knowledge_points': llm_data.get('step1', {}).get('knowledge_points', ''),
        'syllabus_section': llm_data.get('step1', {}).get('syllabus_section', ''),
    }

    step2 = {
        'title': '第二步：诊断薄弱环节，梳理知识体系',
        'weakness_analysis': llm_data.get('step2', {}).get('weakness_analysis', ''),
        'knowledge_framework': llm_data.get('step2', {}).get('knowledge_framework', ''),
        'comparison_table': llm_data.get('step2', {}).get('comparison_table', ''),
    }

    step3 = {
        'title': '第三步：引导思考，给出解题路径',
        'steps': llm_data.get('step3', {}).get('steps', []),
        'note': llm_data.get('step3', {}).get('note', '以上每一步请学生先自己思考，再看提示。绝不直接给出答案。'),
    }

    step4_raw = llm_data.get('step4', {})
    exercises = step4_raw.get('exercises', [])
    step4 = {
        'title': '第四步：生成巩固练习',
        'description': '针对薄弱知识点生成三道变式练习题：',
        'levels': [
            {
                'difficulty': '基础题',
                'target': '直接考察核心知识点的理解和基本应用',
                'content': '',
                'answer': '',
                'solution_steps': '',
            },
            {
                'difficulty': '提高题',
                'target': '综合 2-3 个知识点，对应高考中档题难度',
                'content': '',
                'answer': '',
                'solution_steps': '',
            },
            {
                'difficulty': '难题',
                'target': '综合运用和创新思维，对应高考压轴题难度',
                'content': '',
                'answer': '',
                'solution_steps': '',
            },
        ],
        'exercises': exercises,
    }
    for i, lv in enumerate(step4['levels']):
        if i < len(exercises):
            lv['content'] = exercises[i].get('content', '')
            lv['answer'] = exercises[i].get('answer', '')
            lv['solution_steps'] = exercises[i].get('solution_steps', '')

    return step1, step2, step3, step4


class AnalysisService:
    """Execute the 4-step analysis workflow from CLAUDE.md."""

    def __init__(self, mode=None):
        # Auto-detect: use LLM if API key is available, otherwise template
        if mode is None:
            self.mode = 'llm' if LLM_API_KEY else 'template'
        else:
            self.mode = mode

    def run_full_analysis(self, question_id):
        question = dict(get_question(question_id))
        if not question:
            raise ValueError(f"Question {question_id} not found")

        sub_questions = [dict(sq) for sq in get_sub_questions_by_question(question_id)]

        if self.mode == 'llm':
            try:
                step1, step2, step3, step4 = self._run_llm_analysis(question, sub_questions)
            except Exception as e:
                print(f"[LLM Error] {e}, falling back to template mode")
                step1 = self._step1_template(question, sub_questions)
                step2 = self._step2_template(question, sub_questions, step1)
                step3 = self._step3_template(question, sub_questions, step1, step2)
                step4 = self._step4_template(question, sub_questions, step1, step2)
        else:
            step1 = self._step1_template(question, sub_questions)
            step2 = self._step2_template(question, sub_questions, step1)
            step3 = self._step3_template(question, sub_questions, step1, step2)
            step4 = self._step4_template(question, sub_questions, step1, step2)

        return self._save_analysis(question, step1, step2, step3, step4)

    def _run_llm_analysis(self, question, sub_questions):
        user_prompt = _build_analysis_prompt(question, sub_questions)
        llm_data = _call_deepseek(SYSTEM_PROMPT, user_prompt)
        return _parse_llm_response(llm_data)

    def _save_analysis(self, question, step1, step2, step3, step4):
        subject = question['subject_name']
        exam = question.get('exam_name', '')
        today = date.today().isoformat()
        filename = f"{today}_{exam}_第{question['question_number']}题.md"
        dir_path = os.path.join(ANALYSIS_DIR, subject)
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, filename)

        self._write_analysis_file(file_path, question, step1, step2, step3, step4)
        rel_path = f"{subject}/{filename}"

        analysis_id = create_analysis(
            sub_question_id=None,
            question_id=question['id'],
            file_path=rel_path,
            step1_data=json.dumps(step1, ensure_ascii=False),
            step2_data=json.dumps(step2, ensure_ascii=False),
            step3_data=json.dumps(step3, ensure_ascii=False),
            step4_data=json.dumps(step4, ensure_ascii=False),
        )
        return {'id': analysis_id}

    # ── Template fallback methods ──────────────────────────────────

    ERROR_TYPES = {
        '概念不清': '对核心概念的理解有偏差，需要回归教材定义',
        '计算失误': '解题思路正确但计算过程出错，需加强运算能力',
        '思路缺失': '无法找到正确的解题切入点，需训练思维路径',
        '粗心': '因审题不仔细或步骤跳跃导致的非知识性错误',
    }

    def _step1_template(self, question, sub_questions):
        error_types = set(sq.get('error_type') or '未分类' for sq in sub_questions)
        error_reasons = [f"子问题{sq.get('label','')}：{sq.get('error_reason') or '（未填写）'}" for sq in sub_questions]
        kps = set()
        for sq in sub_questions:
            kp = sq.get('knowledge_points', '')
            if kp:
                kps.add(kp)

        return {
            'title': '第一步：分析错题，定位知识点',
            'question_summary': question.get('stem') or '（无题目内容）',
            'student_error_reason': '\n'.join(error_reasons),
            'ai_analysis': (
                f"本题错误类型涉及：{'、'.join(error_types)}。\n\n"
                f"学生自述原因：\n" + '\n'.join(error_reasons) + "\n\n"
                f"结合题目内容和学生作答情况分析：\n"
                f"1. 需要确认学生对题目条件的理解是否到位\n"
                f"2. 检查解题步骤中是否存在跳跃或遗漏\n"
                f"3. 判断是知识性错误还是非知识性错误\n\n"
                f"建议学生重新审题，逐条列出已知条件和隐含条件，"
                f"再对照正确答案反思自己的解题路径。"
            ),
            'knowledge_points': '、'.join(kps) if kps else '（待补充）',
            'syllabus_section': '上海市高考考纲对应板块（待标注）',
        }

    def _step2_template(self, question, sub_questions, step1):
        return {
            'title': '第二步：诊断薄弱环节，梳理知识体系',
            'weakness_analysis': (
                f"综合本题 {len(sub_questions)} 个子问题的错误情况，学生的主要薄弱点可能在于：\n\n"
                f"**概念层面**：对相关知识点的理解是否停留在表面？\n"
                f"**方法层面**：是否掌握该类题型的通用解题模板？\n"
                f"**思维层面**：遇到变式题能否灵活迁移？\n\n"
                f"建议围绕以下脉络梳理知识体系：\n"
                f"**前置知识** → **核心知识** → **拓展应用**\n"
                f"（具体知识点链由 AI 根据题目内容生成）"
            ),
            'knowledge_framework': '（待生成知识框架思维导图）',
            'comparison_table': '（待生成易混淆概念对比表）',
        }

    def _step3_template(self, question, sub_questions, step1, step2):
        return {
            'title': '第三步：引导思考，给出解题路径',
            'steps': [
                {
                    'name': '审题',
                    'guidance': (
                        '看到题目条件，你应该联想到什么？\n'
                        '请用自己的话复述一遍题目，找出所有已知条件和求解目标。\n'
                        '关键信息在哪里？有没有隐含条件？'
                    ),
                },
                {
                    'name': '切入点',
                    'guidance': (
                        '从哪里下手？为什么选这个角度？\n'
                        '回顾相关知识点的基本方法，想一想这类题的常规切入点。'
                    ),
                },
                {
                    'name': '路径推演',
                    'guidance': (
                        '一步一步推导：\n'
                        '第一步做什么？为什么？\n'
                        '第二步基于什么结论？\n'
                        '每步都问自己"为什么这么想"。'
                    ),
                },
                {
                    'name': '易错提醒',
                    'guidance': (
                        '这类题最容易在哪里出错或卡住？\n'
                        '常见错误：\n'
                        '- 忽略定义域/隐含条件\n'
                        '- 计算跳步导致符号错误\n'
                        '- 未考虑多种情况（分类讨论不完整）'
                    ),
                },
                {
                    'name': '验证方法',
                    'guidance': (
                        '得出答案后如何检查？\n'
                        '- 代入验证法\n'
                        '- 量纲/量级检查\n'
                        '- 特殊值检验\n'
                        '- 是否满足所有约束条件？'
                    ),
                },
            ],
            'note': '以上每一步请学生先自己思考，再看提示。绝不直接给出答案。',
        }

    def _step4_template(self, question, sub_questions, step1, step2):
        return {
            'title': '第四步：生成巩固练习',
            'description': '针对薄弱知识点生成三道变式练习题：',
            'levels': [
                {'difficulty': '基础题', 'target': '直接考察核心知识点的理解和基本应用'},
                {'difficulty': '提高题', 'target': '综合 2-3 个知识点，对应高考中档题难度'},
                {'difficulty': '难题', 'target': '综合运用和创新思维，对应高考压轴题难度'},
            ],
            'exercises': [],
        }

    def _write_analysis_file(self, file_path, question, step1, step2, step3, step4):
        content = f"""# 错题分析报告

**学科**：{question.get('subject_name', '')}
**考试**：{question.get('exam_name', '')}
**题号**：第 {question.get('question_number', '')} 题

---

## {step1['title']}

**题目简述**：{step1.get('question_summary', '')}

**学生自述错误原因**：
{step1.get('student_error_reason', '')}

**AI 分析**：
{step1.get('ai_analysis', '')}

**关联知识点**：{step1.get('knowledge_points', '')}

**所属考纲板块**：{step1.get('syllabus_section', '')}

---

## {step2['title']}

{step2.get('weakness_analysis', '')}

{step2.get('knowledge_framework', '')}

{step2.get('comparison_table', '')}

---

## {step3['title']}

"""
        for s in step3.get('steps', []):
            content += f"### {s['name']}\n\n{s['guidance']}\n\n"

        content += f"""

{step3.get('note', '')}

---

## {step4['title']}

{step4.get('description', '')}

"""
        for lv in step4.get('levels', []):
            content += f"### {lv.get('difficulty', '')}\n"
            if lv.get('content'):
                content += f"\n{lv['content']}\n"
            if lv.get('solution_steps'):
                content += f"\n解题思路：{lv['solution_steps']}\n"
            if lv.get('answer'):
                content += f"\n参考答案：{lv['answer']}\n"
            content += "\n"

        content += "\n---\n*本报告由 DeepSeek AI 自动生成*\n"

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
