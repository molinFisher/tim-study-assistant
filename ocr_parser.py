"""
Tim 学习助手 - OCR 文本解析模块
从 OCR 识别结果中智能提取学科、题目、答案、知识点等结构化信息
支持多题自动拆分和数学公式修复
"""
import re
from dataclasses import dataclass, field
from config import Config
from formula_fixer import create_formula_fixer


@dataclass
class ParsedQuestion:
    """OCR 解析出的结构化错题数据"""
    xueke: str = ''
    timu: str = ''
    xueshengdaan: str = ''
    zhengquedaan: str = ''
    cuowufenxi: str = ''
    zhishidian: str = ''
    confidence: float = 0.0
    field_confidences: dict = field(default_factory=dict)


class OCRParser:
    """OCR 文本结构化提取器"""

    # 学科关键词表
    SUBJECT_KEYWORDS = {
        '数学': [
            '数学', '代数', '几何', '函数', '方程', '计算', '证明',
            '三角形', '圆', '概率', '统计', '数列', '导数', '积分',
            '向量', '坐标', '不等式', '多项式', '因式分解',
        ],
        '物理': [
            '物理', '力学', '电学', '光学', '运动', '能量', '力',
            '速度', '加速度', '电阻', '电压', '电流', '功率',
            '牛顿', '磁场', '电场', '浮力', '压强', '功', '热量',
            '频率', '波长', '折射', '反射',
        ],
        '道法': [
            '道德', '法治', '宪法', '法律', '公民', '权利', '义务',
            '国家', '社会', '民主', '自由', '平等', '公正',
            '社会主义核心价值观', '政治', '制度', '人民',
        ],
        '语文': [
            '语文', '阅读', '作文', '古诗', '文言文', '修辞',
            '比喻', '拟人', '排比', '夸张', '描写', '叙述',
            '说明文', '议论文', '记叙文', '字词', '拼音', '成语',
            '作者', '诗人', '课文', '默写', '翻译',
        ],
    }

    # 标准答案匹配模式
    ANSWER_PATTERNS = [
        (re.compile(r'(?:标准|正确|参考)\s*答案\s*[：:]\s*(.+)', re.IGNORECASE), 'zhengquedaan'),
        (re.compile(r'答案\s*[：:]\s*(.+)', re.IGNORECASE), 'zhengquedaan'),
        (re.compile(r'【答案】\s*(.+)', re.IGNORECASE), 'zhengquedaan'),
        (re.compile(r'[（(]答案[）)]\s*(.+)', re.IGNORECASE), 'zhengquedaan'),
    ]

    # 学生答案匹配模式
    STUDENT_ANSWER_PATTERNS = [
        (re.compile(r'(?:学生|我的|你的|错误)\s*答案\s*[：:]\s*(.+)', re.IGNORECASE), 'xueshengdaan'),
        (re.compile(r'作答\s*[：:]\s*(.+)', re.IGNORECASE), 'xueshengdaan'),
        (re.compile(r'解\s*[：:]\s*(.+)', re.IGNORECASE), 'xueshengdaan'),
        (re.compile(r'错解\s*[：:]\s*(.+)', re.IGNORECASE), 'xueshengdaan'),
    ]

    # 错误分析匹配模式
    ERROR_ANALYSIS_PATTERNS = [
        re.compile(r'(?:错误分析|错因|原因)\s*[：:]\s*(.+)', re.IGNORECASE),
        re.compile(r'分析\s*[：:]\s*(.+)', re.IGNORECASE),
    ]

    # 知识点匹配模式
    KNOWLEDGE_PATTERNS = [
        re.compile(r'知识点\s*[：:]\s*(.+)', re.IGNORECASE),
        re.compile(r'考点\s*[：:]\s*(.+)', re.IGNORECASE),
        re.compile(r'第[一二三四五六七八九十\d]+章\s*(.+)', re.IGNORECASE),
        re.compile(r'§\d+[.\d]*\s*(.+)', re.IGNORECASE),
    ]

    # 数学特征符号（用于推断学科）
    MATH_SYMBOLS = set('=+-×÷<>≤≥∫∑√∏∞∂∇∈∉⊂⊃∪∩∧∨∴∵')
    PHYSICS_UNITS = {'N', 'm/s', 'km/h', 'kg', 'g', 'V', 'A', 'Ω', 'W', 'J', 'Pa', 'Hz', 'm/s²'}
    DAOFA_TERMS = {'宪法', '权利', '义务', '公民', '法律', '法治', '民主', '国家', '人民'}
    YUWEN_TERMS = {'比喻', '拟人', '排比', '夸张', '修辞', '文言文', '古诗', '作者', '描写'}

    def parse(self, ocr_lines: list) -> list:
        """
        从 OCR 识别结果中提取结构化错题信息
        支持多题自动拆分，返回 ParsedQuestion 列表
        """
        if not ocr_lines:
            return [ParsedQuestion(confidence=0.0)]

        # 按 Y 坐标排序
        ocr_lines = sorted(ocr_lines, key=lambda r: r['center_y'])

        # 步骤 1: 拆分为多道题
        groups = self.split_questions(ocr_lines)

        # 步骤 2: 每组独立解析
        results = []
        formula_fixer = create_formula_fixer()

        for group in groups:
            q = self._parse_single_group(group, formula_fixer)
            # 过滤掉空题目（无有效内容）
            if q.timu and q.timu.strip():
                results.append(q)

        # 如果拆分后没有有效题目，回退到整体解析
        if not results:
            q = self._parse_single_group(ocr_lines, formula_fixer)
            if q.timu and q.timu.strip():
                results.append(q)

        return results

    def split_questions(self, ocr_lines: list) -> list:
        """
        将 OCR 行按题号/位置拆分为题目组
        返回: [[line, line, ...], [line, ...], ...]
        """
        if len(ocr_lines) <= 1:
            return [ocr_lines]

        # 计算平均行间距作为分割阈值参考
        ys = sorted([l['center_y'] for l in ocr_lines])
        total_gap = ys[-1] - ys[0]
        avg_gap = total_gap / max(1, len(ys) - 1)
        # 大间距阈值：平均间距的 2.5 倍，且至少 40px
        big_gap_threshold = max(40, avg_gap * 2.5)

        groups = []
        current = []

        for i, line in enumerate(ocr_lines):
            text = line['text'].strip()

            # 题号检测：命中即开启新题（除非是第一行）
            is_new = self._is_question_start(text) and current

            # 大间距检测：与上一行间距过大
            if not is_new and current and i > 0:
                prev_y = ocr_lines[i - 1]['center_y']
                gap = line['center_y'] - prev_y
                if gap > big_gap_threshold and len(current) >= 2:
                    is_new = True

            if is_new:
                groups.append(current)
                current = [line]
            else:
                current.append(line)

        if current:
            groups.append(current)

        # 如果只有一组且无题号，尝试等距切分（兜底）
        if len(groups) == 1 and not self._has_question_number(ocr_lines):
            groups = self._split_by_equal_spacing(ocr_lines, avg_gap)

        # 优化：如果第一组是纯标题（1-2行且无题号、无答案标记），合并到第二组
        if len(groups) >= 2:
            first_group = groups[0]
            first_text = '\n'.join([l['text'] for l in first_group])
            is_title = (
                len(first_group) <= 2 and
                not self._has_question_number(first_group) and
                '答案' not in first_text and '解' not in first_text
            )
            if is_title and len(groups) > 1:
                groups[1] = first_group + groups[1]
                groups = groups[1:]

        return groups if groups else [ocr_lines]

    def _is_question_start(self, text):
        """判断文本是否题号起始行"""
        if not text:
            return False
        patterns = [
            r'^\d+[.。、)）]',              # 1. 2) 3、
            r'^[一二三四五六七八九十]+[、.．]',  # 一、 二．
            r'^[（(]\d+[)）]',               # (1) (2)
            r'^[①②③④⑤⑥⑦⑧⑨⑩]',          # ①②③
            r'^第\s*\d+\s*题',               # 第1题
            r'^\d+[、.．]',                  # 1、 2．
        ]
        return any(re.match(p, text.strip()) for p in patterns)

    def _has_question_number(self, ocr_lines):
        """检查是否包含题号"""
        return any(self._is_question_start(l['text']) for l in ocr_lines)

    def _split_by_equal_spacing(self, ocr_lines, avg_gap):
        """兜底：按等距切分（每 ~6 行一组）"""
        if len(ocr_lines) <= 3:
            return [ocr_lines]
        chunk_size = max(3, len(ocr_lines) // 3)
        groups = []
        for i in range(0, len(ocr_lines), chunk_size):
            chunk = ocr_lines[i:i + chunk_size]
            if chunk:
                groups.append(chunk)
        return groups if groups else [ocr_lines]

    def _parse_single_group(self, ocr_lines, formula_fixer) -> ParsedQuestion:
        """解析单组 OCR 行为结构化错题"""
        if not ocr_lines:
            return ParsedQuestion(confidence=0.0)

        # 合并所有文本行
        all_text = '\n'.join([line['text'] for line in ocr_lines])
        avg_confidence = sum(line['confidence'] for line in ocr_lines) / len(ocr_lines)

        result = ParsedQuestion()
        result.field_confidences = {}

        # 步骤 1: 提取学科
        result.xueke, subject_conf = self._extract_subject(all_text, ocr_lines)
        result.field_confidences['xueke'] = subject_conf

        # 步骤 2: 提取答案（标准答案 + 学生答案）
        result.zhengquedaan, result.xueshengdaan, answer_conf = self._extract_answers(all_text)
        result.field_confidences['answers'] = answer_conf

        # 步骤 3: 提取错误分析
        result.cuowufenxi = self._extract_error_analysis(all_text)

        # 步骤 4: 提取知识点
        result.zhishidian = self._extract_knowledge_point(all_text)

        # 步骤 5: 提取题目内容（排除答案和元数据行）
        result.timu = self._extract_question(
            all_text, ocr_lines,
            result.zhengquedaan, result.xueshengdaan,
            result.cuowufenxi, result.zhishidian
        )

        # 步骤 6: 数学公式修复
        fields = {
            'timu': result.timu,
            'xueshengdaan': result.xueshengdaan,
            'zhengquedaan': result.zhengquedaan,
            'cuowufenxi': result.cuowufenxi,
            'zhishidian': result.zhishidian,
        }
        fixed_fields, changed = formula_fixer.fix_batch(fields)
        result.timu = fixed_fields['timu']
        result.xueshengdaan = fixed_fields['xueshengdaan']
        result.zhengquedaan = fixed_fields['zhengquedaan']
        result.cuowufenxi = fixed_fields['cuowufenxi']
        result.zhishidian = fixed_fields['zhishidian']
        result.field_confidences['formula_fixed'] = any(changed.values())

        # 计算综合置信度
        completeness = sum([
            1 if result.xueke else 0,
            1 if result.timu else 0,
            1 if result.zhengquedaan else 0,
            1 if result.xueshengdaan else 0,
        ]) / 4.0

        result.confidence = round(
            0.3 * subject_conf +
            0.3 * answer_conf +
            0.2 * avg_confidence +
            0.2 * completeness,
            4
        )

        return result

    def _extract_subject(self, all_text, ocr_lines):
        """识别学科"""
        # 策略 1: 前几行关键词匹配
        first_lines = '\n'.join([l['text'] for l in ocr_lines[:5]])
        for subject, keywords in self.SUBJECT_KEYWORDS.items():
            for kw in keywords:
                if kw in first_lines:
                    return subject, 0.95

        # 策略 2: 全文关键词频次统计
        scores = {}
        for subject, keywords in self.SUBJECT_KEYWORDS.items():
            score = sum(all_text.count(kw) for kw in keywords)
            scores[subject] = score

        if scores:
            best_subject = max(scores, key=scores.get)
            if scores[best_subject] > 0:
                return best_subject, min(0.7, 0.3 + scores[best_subject] * 0.05)

        # 策略 3: 特征推断
        if any(c in all_text for c in self.MATH_SYMBOLS):
            return '数学', 0.4
        if any(unit in all_text for unit in self.PHYSICS_UNITS):
            return '物理', 0.4
        if any(term in all_text for term in self.DAOFA_TERMS):
            return '道法', 0.4
        if any(term in all_text for term in self.YUWEN_TERMS):
            return '语文', 0.4

        return '', 0.0

    def _extract_answers(self, all_text):
        """提取标准答案和学生答案"""
        zhengquedaan = ''
        xueshengdaan = ''
        confidence = 0.0

        # 先尝试带前缀的精确匹配
        for pattern, field in self.ANSWER_PATTERNS:
            match = pattern.search(all_text)
            if match:
                zhengquedaan = match.group(1).strip()
                confidence = 0.8
                break

        for pattern, field in self.STUDENT_ANSWER_PATTERNS:
            match = pattern.search(all_text)
            if match:
                xueshengdaan = match.group(1).strip()
                confidence = max(confidence, 0.7)
                break

        # 如果没有明确标签，尝试位置启发式
        # 通常答案在文本后部，以特定标记开头
        if not zhengquedaan:
            lines = all_text.split('\n')
            for i, line in enumerate(lines):
                line = line.strip()
                # 短行且包含数字/字母，可能是答案
                if len(line) < 50 and re.search(r'[A-Da-d0-9]', line):
                    if i > len(lines) * 0.5:  # 在后半部分
                        if not zhengquedaan:
                            zhengquedaan = line
                            confidence = 0.35

        return zhengquedaan, xueshengdaan, confidence

    def _extract_error_analysis(self, all_text):
        """提取错误分析"""
        for pattern in self.ERROR_ANALYSIS_PATTERNS:
            match = pattern.search(all_text)
            if match:
                return match.group(1).strip()
        return ''

    def _extract_knowledge_point(self, all_text):
        """提取知识点"""
        for pattern in self.KNOWLEDGE_PATTERNS:
            match = pattern.search(all_text)
            if match:
                text = match.group(1).strip() if match.lastindex else match.group(0).strip()
                # 截取合理长度
                return text[:30]
        return ''

    def _extract_question(self, all_text, ocr_lines, zhengquedaan, xueshengdaan, cuowufenxi, zhishidian):
        """提取题目主体内容"""
        # 收集需要排除的文本
        exclude_texts = set()
        for text in [zhengquedaan, xueshengdaan, cuowufenxi, zhishidian]:
            if text:
                exclude_texts.add(text.strip())

        # 标记答案标签行
        answer_label_patterns = [
            r'(?:标准|正确|参考|学生|我的|你的|错误)?\s*答案\s*[：:]',
            r'作答\s*[：:]',
            r'解\s*[：:]',
            r'错解\s*[：:]',
            r'知识点\s*[：:]',
            r'考点\s*[：:]',
            r'错误分析\s*[：:]',
            r'错因\s*[：:]',
        ]

        clean_lines = []
        for line in ocr_lines:
            text = line['text'].strip()

            # 跳过空行
            if not text:
                continue

            # 跳过已识别的答案内容
            if text in exclude_texts:
                continue

            # 跳过答案/知识点标签行
            is_label = False
            for pat in answer_label_patterns:
                if re.match(pat, text):
                    is_label = True
                    break
            if is_label:
                continue

            # 跳过过短的非中文行（可能是噪音）
            if len(text) < 3 and not re.search(r'[\u4e00-\u9fff]', text):
                continue

            clean_lines.append(text)

        # 合并清理后的文本
        question = '\n'.join(clean_lines)

        # 截取合理长度
        if len(question) > 800:
            question = question[:800] + '\n...(内容过长，已截断)'

        return question.strip()


def create_ocr_parser():
    """工厂函数：创建 OCRParser 实例"""
    return OCRParser()
