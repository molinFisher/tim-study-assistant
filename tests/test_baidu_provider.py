"""
百度智能云 OCR 提供商测试（不依赖真实网络/密钥）。

运行：
  python3.11 tests/test_baidu_provider.py
  python3.11 -m pytest tests/test_baidu_provider.py -q
"""
import os
import sys
import unittest
from unittest import mock

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 必须在设置环境变量后再 import provider（__init__ 读取 env）
os.environ.setdefault('BAIDU_OCR_API_KEY', 'test_api_key_0000000000000000')
os.environ.setdefault('BAIDU_OCR_SECRET_KEY', 'test_secret_key_0000000000000000')

from ocr_providers.baidu_provider import BaiduOCRProvider  # noqa: E402
from ocr_parser import create_ocr_parser  # noqa: E402


def _fake_token_resp():
    return {'access_token': '24.faketokenxxxx.yyyyyyyyyyyy.2592000.000000',
            'expires_in': 2592000, 'refresh_token': 'fake', 'scope': 'public'}


def _fake_ocr_resp():
    """模拟百度 doc_analysis 接口响应（words_result + 公式融合）。"""
    return {
        'words_result_num': 1,
        'words_result': [
            {
                'words': 'x^2 + 1 = 2',
                'location': {'left': 10, 'top': 20, 'width': 140, 'height': 20},
                'probability': {'average': 0.98, 'variance': 0.0, 'min': 0.98},
            }
        ],
    }


def _fake_formula_ocr_resp():
    """模拟 doc_analysis 返回 LaTeX 公式文本。"""
    return {
        'words_result': [
            {
                'words': 'x = \\frac{1}{2}',
                'location': {'left': 10, 'top': 20, 'width': 140, 'height': 30},
                'probability': {'average': 0.95, 'variance': 0.0, 'min': 0.95},
            }
        ],
    }


class TestBaiduProvider(unittest.TestCase):
    def setUp(self):
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        Image.fromarray(img).save('/tmp/_baidu_ocr_test.png')

    def test_token_cached(self):
        prov = BaiduOCRProvider()
        fake = mock.MagicMock()
        fake.json.return_value = _fake_token_resp()
        with mock.patch('requests.get', return_value=fake) as m_get:
            t1 = prov._get_token()
            t2 = prov._get_token()
        # 只请求一次 token（第二次命中缓存）
        self.assertEqual(m_get.call_count, 1)
        self.assertEqual(t1, '24.faketokenxxxx.yyyyyyyyyyyy.2592000.000000')
        # 请求 token 时携带 client_id/client_secret
        _, kwargs = m_get.call_args
        self.assertEqual(kwargs['params']['client_id'], 'test_api_key_0000000000000000')
        self.assertEqual(kwargs['params']['client_secret'], 'test_secret_key_0000000000000000')

    def test_normalize_and_parser(self):
        prov = BaiduOCRProvider()
        self.assertEqual(prov.api, '/rest/2.0/ocr/v1/doc_analysis')

        fake_get = mock.MagicMock()
        fake_get.json.return_value = _fake_token_resp()
        fake_post = mock.MagicMock()
        fake_post.json.return_value = _fake_ocr_resp()

        with mock.patch('requests.get', return_value=fake_get), \
             mock.patch('requests.post', return_value=fake_post) as m_post:
            res = prov.recognize('/tmp/_baidu_ocr_test.png')
            # OCR 请求确实带上了 access_token
            _, kwargs = m_post.call_args
            self.assertEqual(kwargs['params']['access_token'],
                             '24.faketokenxxxx.yyyyyyyyyyyy.2592000.000000')
            self.assertIn('image', kwargs['data'])
            self.assertEqual(kwargs['data']['probability'], 'true')
            self.assertEqual(kwargs['data']['recg_formula'], 'true')
            self.assertEqual(kwargs['data']['language_type'], 'CHN_ENG')
            self.assertEqual(kwargs['data']['line_probability'], 'true')

        # 归一化契约
        self.assertEqual(len(res), 1)
        r = res[0]
        self.assertSetEqual(
            set(r.keys()),
            {'text', 'bbox', 'confidence', 'center_y', 'center_x'},
        )
        self.assertAlmostEqual(r['confidence'], 0.98, places=4)
        self.assertTrue(all(0 <= c <= 1 for pt in r['bbox'] for c in pt))
        # 与下游 parser + formula_fixer 衔接
        qs = create_ocr_parser().parse(res)
        self.assertIsInstance(qs, list)
        self.assertEqual(qs[0].timu, 'x² + 1 = 2')

    def test_token_fetch_failure_raises(self):
        prov = BaiduOCRProvider()
        fake = mock.MagicMock()
        fake.json.return_value = {'error_description': 'invalid client_id'}
        with mock.patch('requests.get', return_value=fake):
            with self.assertRaises(RuntimeError):
                prov._get_token()

    def test_missing_credential_raises(self):
        ak = os.environ.pop('BAIDU_OCR_API_KEY', None)
        sk = os.environ.pop('BAIDU_OCR_SECRET_KEY', None)
        try:
            with self.assertRaises(RuntimeError):
                BaiduOCRProvider()
        finally:
            if ak is not None:
                os.environ['BAIDU_OCR_API_KEY'] = ak
            if sk is not None:
                os.environ['BAIDU_OCR_SECRET_KEY'] = sk


    def test_formula_tex_retained(self):
        """doc_analysis recg_formula=true 返回的 LaTeX 应原样保留，不被 formula_fixer 改坏。"""
        prov = BaiduOCRProvider()

        fake_get = mock.MagicMock()
        fake_get.json.return_value = _fake_token_resp()
        fake_post = mock.MagicMock()
        fake_post.json.return_value = _fake_formula_ocr_resp()

        with mock.patch('requests.get', return_value=fake_get), \
             mock.patch('requests.post', return_value=fake_post):
            res = prov.recognize('/tmp/_baidu_ocr_test.png')

        self.assertEqual(len(res), 1)
        self.assertIn('\\frac', res[0]['text'])
        self.assertEqual(res[0]['text'], 'x = \\frac{1}{2}')

        # FormulaFixer 不应改写已含 LaTeX 的文本
        from formula_fixer import create_formula_fixer
        fixer = create_formula_fixer()
        fixed = fixer.fix('x = \\frac{1}{2}')
        self.assertEqual(fixed, 'x = \\frac{1}{2}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
