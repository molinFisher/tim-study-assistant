"""
错误类型自动归类模块测试（不依赖 DB / 网络）。

运行：
  python3.11 tests/test_error_classifier.py
  python3.11 -m pytest tests/test_error_classifier.py -q
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from error_classifier import (
    classify_error, classify_batch, ERROR_TYPES, _ERROR_KEYWORDS
)


class TestClassifyError(unittest.TestCase):
    def test_compute_error(self):
        self.assertEqual(classify_error('计算时粗心，符号弄错了'), '计算错误')

    def test_concept_error(self):
        self.assertEqual(classify_error('对这个概念理解不清，混淆了定义'), '概念不清')

    def test_review_error(self):
        self.assertEqual(classify_error('没有看清题目条件，审题失误'), '审题失误')

    def test_formula_error(self):
        self.assertEqual(classify_error('公式记错，用错了公式'), '公式记忆错误')

    def test_method_error(self):
        self.assertEqual(classify_error('解题思路不对，方法步骤有问题'), '方法不当')

    def test_empty_falls_to_other(self):
        self.assertEqual(classify_error(''), '其他')
        self.assertEqual(classify_error('这道题做错了'), '其他')

    def test_timu_weak_signal_only(self):
        # 题目含关键词但错误分析为空，弱信号不足以覆盖阈值（权重0.3*1 < 1）
        self.assertEqual(classify_error('', timu='请计算这道题'), '其他')

    def test_priority_order_on_tie(self):
        # 同时命中两类且次数相同：ERROR_TYPES 靠前者优先
        # “概念” 命中 概念不清；“公式” 命中 公式记忆错误
        res = classify_error('概念 公式')
        self.assertIn(res, ERROR_TYPES)
        self.assertEqual(res, '概念不清')

    def test_error_types_complete(self):
        self.assertEqual(ERROR_TYPES[-1], '其他')
        for et in ERROR_TYPES:
            if et != '其他':
                self.assertIn(et, _ERROR_KEYWORDS)


class TestClassifyBatch(unittest.TestCase):
    def _rec(self, cuowufenxi):
        return {'cuowufenxi': cuowufenxi, 'timu': '', 'zhishidian': ''}

    def test_batch_counts(self):
        records = [
            self._rec('计算粗心符号错'),
            self._rec('计算粗心符号错'),
            self._rec('概念理解不清'),
            self._rec(''),
        ]
        counts = classify_batch(records)
        self.assertEqual(counts['计算错误'], 2)
        self.assertEqual(counts['概念不清'], 1)
        self.assertEqual(counts['其他'], 1)
        # 总计数等于记录数
        self.assertEqual(sum(counts.values()), 4)
        # 未命中的类型保持 0
        self.assertEqual(counts['审题失误'], 0)

    def test_batch_empty(self):
        counts = classify_batch([])
        self.assertEqual(sum(counts.values()), 0)
        for et in ERROR_TYPES:
            self.assertIn(et, counts)


if __name__ == '__main__':
    unittest.main(verbosity=2)
