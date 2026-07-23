"""
Tim 学习助手 - 数学公式后处理修复模块
对 OCR 识别出的文本做规则修复，提升数学公式符号的准确率
"""
import re


class FormulaFixer:
    """OCR 数学公式文本修复器"""

    # 上标数字映射
    SUPERSCRIPT_MAP = {
        '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
        '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
    }

    # 下标数字映射
    SUBSCRIPT_MAP = {
        '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
        '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
    }

    # 常见分数映射（Unicode  vulgar fraction）
    FRACTION_MAP = {
        '1/2': '½', '1/3': '⅓', '1/4': '¼', '2/3': '⅔',
        '3/4': '¾', '1/5': '⅕', '2/5': '⅖', '3/5': '⅗',
        '4/5': '⅘', '1/6': '⅙', '5/6': '⅚', '1/7': '⅐',
        '1/8': '⅛', '3/8': '⅜', '5/8': '⅝', '7/8': '⅞',
        '1/9': '⅑', '1/10': '⅒',
    }

    # 希腊字母映射（英文 → 符号）
    GREEK_MAP = {
        'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'delta': 'δ',
        'epsilon': 'ε', 'zeta': 'ζ', 'eta': 'η', 'theta': 'θ',
        'iota': 'ι', 'kappa': 'κ', 'lambda': 'λ', 'mu': 'μ',
        'nu': 'ν', 'xi': 'ξ', 'omicron': 'ο', 'pi': 'π',
        'rho': 'ρ', 'sigma': 'σ', 'tau': 'τ', 'upsilon': 'υ',
        'phi': 'φ', 'chi': 'χ', 'psi': 'ψ', 'omega': 'ω',
        'Delta': 'Δ', 'Sigma': 'Σ', 'Pi': 'Π', 'Omega': 'Ω',
        'Theta': 'Θ', 'Lambda': 'Λ', 'Gamma': 'Γ',
    }

    # 关系/运算符号映射
    SYMBOL_MAP = {
        '>=': '≥', '<=': '≤', '!=': '≠', '~=': '≈', '+-': '±',
        '+-=': '±', 'infty': '∞', 'inf': '∞', 'sum': '∑',
        'int': '∫', 'lim': 'lim', 'sqrt': '√', 'squareroot': '√',
        'times': '×', 'div': '÷', 'cdot': '·', 'angle': '∠',
        'perp': '⊥', 'parallel': '∥', 'cong': '≅', 'sim': '∼',
        'propto': '∝', 'partial': '∂', 'nabla': '∇',
        'approx': '≈', 'equiv': '≡', 'neq': '≠',
    }

    # 常见 OCR 乱码修复（数学语境）
    TYPO_MAP = {
        'V': '√',      # 根号常被识别为 V
        'v': '√',      # 小写 v 也可能是根号
        'x2': 'x²', 'x3': 'x³', 'x4': 'x⁴', 'x5': 'x⁵',
        'y2': 'y²', 'y3': 'y³', 'n2': 'n²', 'a2': 'a²', 'b2': 'b²',
        'X2': 'X²', 'X3': 'X³',
    }

    # sqrt 系列误读（括号被读成 f / la 等）的兜底修复
    SQRT_TYPO = {
        'sqrtf': '√(',
        'sqrtla': '√(',
        'sqr': '√',
        'sart': '√',   # sqrt 常见误读
        'sgrt': '√',
        'squrt': '√',
    }

    def fix(self, text):
        """修复数学公式文本，返回修复后的文本"""
        if not text or not isinstance(text, str):
            return text

        # Baidu doc_analysis 返回的文本已含 LaTeX 公式，原样保留避免二次破坏
        if self._is_latex(text):
            return text

        original = text
        result = text

        # 1. 幂运算: x^2, x**2 → x²
        result = re.sub(r'([a-zA-Z0-9])\^(\d)', self._superscript_repl, result)
        result = re.sub(r'([a-zA-Z0-9])\*\*(\d)', self._superscript_repl, result)

        # 2. 下标: x_2 → x₂
        result = re.sub(r'([a-zA-Z])_(\d)', self._subscript_repl, result)

        # 3. 分数: 1/2 → ½
        for frac, sym in self.FRACTION_MAP.items():
            result = result.replace(frac, sym)

        # 4. 通用分数 a/b → 保留（不强行转换，避免误改）

        # 5. 希腊字母
        # 仅要求右侧非字母（避免误改 alphabet 等单词）；左侧可紧贴，
        # 因为 OCR 常把 "(" 误读为 "l"，导致 sin(alpha) 变成 sinlalpha
        for eng, sym in self.GREEK_MAP.items():
            result = re.sub(re.escape(eng) + r'(?![a-zA-Z])', sym, result)

        # 6. 关系/运算符号
        for eng, sym in self.SYMBOL_MAP.items():
            # 避免 sqrt 被当成 s×q×r×t 之类，仅替换独立词或特定模式
            if eng in ('times', 'div', 'cdot'):
                result = result.replace(eng, sym)
            else:
                result = re.sub(r'\b' + re.escape(eng) + r'\b', sym, result)

        # 7. 常见乱码（数学语境）
        # 仅在包含数学符号或变量的上下文中替换
        if self._looks_like_math(result):
            result = self._fix_sqrt_typos(result)
            result = self._fix_greek_typos(result)
            result = self._fix_multiplication(result)
            result = self._fix_typos(result)

        # 8. 修复 x2/x3 型上标（变量后跟单个数字）
        result = re.sub(r'([a-zA-Z])([2-9])(?![a-zA-Z0-9])', self._var_superscript_repl, result)

        return result

    def _superscript_repl(self, match):
        """幂运算替换回调"""
        base, exp = match.group(1), match.group(2)
        return base + self.SUPERSCRIPT_MAP.get(exp, exp)

    def _subscript_repl(self, match):
        """下标替换回调"""
        base, sub = match.group(1), match.group(2)
        return base + self.SUBSCRIPT_MAP.get(sub, sub)

    def _var_superscript_repl(self, match):
        """变量后上标替换回调：x2 → x²"""
        var, num = match.group(1), match.group(2)
        # 避免误改常见英文单词后缀（如 px, mx 等不在此列因为只匹配单个数字）
        if var in ('p', 'm', 'k', 'x', 'y', 'z', 'a', 'b', 'c', 'n', 't', 'i', 'j'):
            return var + self.SUPERSCRIPT_MAP.get(num, num)
        return match.group(0)

    def _looks_like_math(self, text):
        """判断文本是否像数学内容"""
        math_indicators = set('=+-×÷√∫∑≤≥≠≈±∂∇παβγδθλσ')
        has_symbol = any(c in text for c in math_indicators)
        has_var = bool(re.search(r'[a-zA-Z][0-9]|[0-9][a-zA-Z]', text))
        return has_symbol or has_var

    @staticmethod
    def _is_latex(text):
        """Baidu doc_analysis 返回的 LaTeX 公式：含反斜杠命令（如 \\frac）或 $。"""
        return bool(re.search(r'\\[a-zA-Z]+', text)) or '$' in text

    def _fix_greek_typos(self, text):
        """修复希腊字母相关误读（数学语境）"""
        result = text
        # pi/6 常被误读为 pil6（"/" 被读成 "l"）
        result = re.sub(r'pil(?=[0-9])', 'π/', result)
        result = re.sub(r'pil', 'π/', result)
        # theta 误读变体
        result = re.sub(r'theta', 'θ', result)
        return result

    def _fix_sqrt_typos(self, text):
        """修复 sqrt 系列误读为根号 √（括号被读成 f / la 等）"""
        result = text
        # f 紧跟真实括号：仅去掉 f，保留原括号（避免产生双括号）
        result = re.sub(r'sqrtf(?=\()', '√', result)
        # 其余 sqrtf / sqrtla 等：补一个左括号使 √ 表达式闭合
        result = re.sub(r'sqrtf', '√(', result)
        result = re.sub(r'sqrtla', '√(', result)
        result = re.sub(r'sart', '√', result)
        result = re.sub(r'sgrt', '√', result)
        result = re.sub(r'squrt', '√', result)
        result = re.sub(r'\bsqr\b', '√', result)
        return result

    def _fix_multiplication(self, text):
        """将数学乘号 X（大写，易与变量混淆）还原为 ×。
        仅在「数字/右括号」与「数字/左括号」之间判定为乘法，避免误改变量 X。"""
        return re.sub(
            r'(?<=[0-9)\]])[ \t]*X[ \t]*(?=[0-9(\[])',
            ' × ', text
        )

    def _fix_typos(self, text):
        """修复数学语境下的常见 OCR 乱码"""
        result = text

        # V/v 在根号语境（后面跟表达式）修复为 √
        # 匹配 V(  Vx  V2 等模式
        result = re.sub(r'\bV(?=[(a-zA-Z0-9])', '√', result)
        result = re.sub(r'(?<![a-zA-Z])v(?=[(a-zA-Z0-9])', '√', result)

        return result

    def fix_batch(self, fields):
        """修复多个字段，返回 {field: fixed_text} 和变更标记"""
        fixed = {}
        changed = {}
        for key, value in fields.items():
            if isinstance(value, str) and value:
                new_val = self.fix(value)
                fixed[key] = new_val
                changed[key] = (new_val != value)
            else:
                fixed[key] = value
                changed[key] = False
        return fixed, changed


def create_formula_fixer():
    """工厂函数"""
    return FormulaFixer()
