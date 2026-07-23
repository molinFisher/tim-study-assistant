"""
文档导入模块轻量测试（不依赖真实文件/网络）。

运行：
  python3.11 tests/test_doc_import.py
  python3.11 -m pytest tests/test_doc_import.py -q
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from doc_import import check_doc_ext, lines_to_questions, ALLOWED_DOC_EXTENSIONS


class TestDocImport(unittest.TestCase):
    def test_check_ext_valid(self):
        self.assertEqual(check_doc_ext('test.pdf'), 'pdf')
        self.assertEqual(check_doc_ext('test.docx'), 'docx')
        self.assertEqual(check_doc_ext('test.doc'), 'doc')
        self.assertEqual(check_doc_ext('a.b.c.PDF'), 'pdf')

    def test_check_ext_invalid(self):
        self.assertEqual(check_doc_ext('test.txt'), '')
        self.assertEqual(check_doc_ext('test'), '')
        self.assertEqual(check_doc_ext('test.xlsx'), '')
        self.assertEqual(check_doc_ext(''), '')

    def test_allowed_set_contains_key_formats(self):
        self.assertIn('pdf', ALLOWED_DOC_EXTENSIONS)
        self.assertIn('docx', ALLOWED_DOC_EXTENSIONS)
        self.assertIn('doc', ALLOWED_DOC_EXTENSIONS)

    def test_lines_to_questions_empty(self):
        self.assertEqual(lines_to_questions([]), [])

    def test_lines_to_questions_single(self):
        lines = [
            {'text': '(1) 计算 2+3', 'center_y': 0, 'confidence': 1.0, 'center_x': 0,
             'bbox': [[0, 0], [1, 0], [1, 1], [0, 1]]},
            {'text': '答案：5', 'center_y': 1000, 'confidence': 1.0, 'center_x': 0,
             'bbox': [[0, 0], [1, 0], [1, 1], [0, 1]]},
        ]
        qs = lines_to_questions(lines)
        self.assertGreaterEqual(len(qs), 1)
        q = qs[0]
        for key in ('xueke', 'timu', 'xueshengdaan', 'zhengquedaan',
                     'cuowufenxi', 'zhishidian', 'confidence'):
            self.assertIn(key, q)
        self.assertIn('2', q['timu'])

    def test_lines_to_questions_multiple(self):
        # 模拟两道题的文本行
        lines = [
            {'text': '1. 解方程：x + 5 = 10', 'center_y': 0, 'confidence': 1.0, 'center_x': 0,
             'bbox': [[0, 0], [1, 0], [1, 1], [0, 1]]},
            {'text': '答案：x = 5', 'center_y': 1000, 'confidence': 1.0, 'center_x': 0,
             'bbox': [[0, 0], [1, 0], [1, 1], [0, 1]]},
            {'text': '2. 计算 3×4', 'center_y': 4000, 'confidence': 1.0, 'center_x': 0,
             'bbox': [[0, 0], [1, 0], [1, 1], [0, 1]]},
            {'text': '答案：12', 'center_y': 5000, 'confidence': 1.0, 'center_x': 0,
             'bbox': [[0, 0], [1, 0], [1, 1], [0, 1]]},
        ]
        qs = lines_to_questions(lines)
        # 至少应该拆出 1 道题（题号 + 大间距）
        self.assertGreaterEqual(len(qs), 1, f'应拆出至少1题，实际{len(qs)}')
        # 检查每题的 timu 不为空
        for q in qs:
            self.assertTrue(q['timu'].strip(), f'题目不应为空: {q}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
