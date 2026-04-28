import json
from models.analysis import get_analysis
from models.sub_question import get_sub_question
from models.practice import create_practice


class PracticeService:
    """Generate 3 consolidation exercises for an analysis result."""

    def generate_practices(self, analysis_id):
        analysis = get_analysis(analysis_id)
        if not analysis:
            raise ValueError(f"Analysis {analysis_id} not found")

        step1 = json.loads(analysis['step1_data']) if analysis['step1_data'] else {}
        kps = step1.get('knowledge_points', '相关知识点')

        practices = [
            {
                'difficulty': 'basic',
                'content': self._make_basic_question(kps),
                'hint': '回顾核心概念的定义和基本公式，直接套用即可。',
            },
            {
                'difficulty': 'intermediate',
                'content': self._make_intermediate_question(kps),
                'hint': '需要综合 2-3 个知识点，先分解问题再逐步求解。',
            },
            {
                'difficulty': 'advanced',
                'content': self._make_advanced_question(kps),
                'hint': '需要创新思维，尝试从不同角度分析问题，可能涉及多个知识模块的交叉。',
            },
        ]

        for p in practices:
            create_practice(
                analysis_result_id=analysis_id,
                difficulty=p['difficulty'],
                content=p['content'],
                answer=self._make_answer(p['difficulty'], kps),
                solution_steps=self._make_solution(p['difficulty'], kps),
                knowledge_points=kps,
            )

    def _make_basic_question(self, kps):
        return f"""【基础题】针对「{kps}」的基础考查。

已知相关概念和基本公式，请完成以下题目：

（具体题目内容将由 AI 根据知识点自动生成，确保严格限定在上海市高考考纲范围内。）

考察目标：检验对核心概念的基本理解和简单应用能力。"""

    def _make_intermediate_question(self, kps):
        return f"""【提高题】综合考查「{kps}」及相关知识。

请分析以下问题，综合运用所学知识求解：

（具体题目内容将由 AI 自动生成，综合 2-3 个知识点，难度对应高考中档题。）

考察目标：检验分析能力和知识综合运用水平。"""

    def _make_advanced_question(self, kps):
        return f"""【难题】围绕「{kps}」的深入拓展。

请思考以下综合性问题，需要灵活运用多模块知识：

（具体题目内容将由 AI 自动生成，涉及多个知识模块的交叉，对应高考压轴题或模拟考难题难度。）

考察目标：检验综合运用能力和创新思维。"""

    def _make_answer(self, difficulty, kps):
        levels = {
            'basic': '参考答案将在 AI 接入后自动生成。建议学生先独立完成，再对照教材验证。',
            'intermediate': '参考答案将在 AI 接入后自动生成。解题关键在于理清各知识点之间的逻辑关系。',
            'advanced': '参考答案将在 AI 接入后自动生成。此类题目通常有多种解法，建议尝试不同思路。',
        }
        return levels.get(difficulty, '')

    def _make_solution(self, difficulty, kps):
        levels = {
            'basic': '1. 审题，明确已知和所求\n2. 回忆相关定义和基本公式\n3. 直接代入计算\n4. 验证结果',
            'intermediate': '1. 审题，分解条件\n2. 确定涉及的知识点\n3. 逐步推导，注意各步骤的衔接\n4. 综合得出答案\n5. 逆向验证',
            'advanced': '1. 多角度审题\n2. 尝试建立数学模型\n3. 寻找突破口（从特殊到一般 / 从结论反推条件）\n4. 分情况讨论\n5. 验证所有可能解',
        }
        return levels.get(difficulty, '')
