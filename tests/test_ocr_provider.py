"""
OCR 工厂测试（不依赖真实网络/密钥）。

运行：
  python3.11 tests/test_ocr_provider.py
  python3.11 -m pytest tests/test_ocr_provider.py -q
"""
import os
import sys
import unittest

# 确保项目根目录在 path 中
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ocr_providers.factory import get_ocr_provider


class TestFactoryBaiduOnly(unittest.TestCase):
    def test_returns_baidu_provider(self):
        # 无论传入何种 mode，均返回百度 OCR（其他方式已移除）
        import ocr_providers.factory as fmod
        cases = [None, 'auto', 'baidu']
        for mode in cases:
            fmod._PROVIDERS.clear()
            self.assertEqual(
                type(get_ocr_provider(mode)).__name__, 'BaiduOCRProvider',
                msg='mode=%r 应返回 BaiduOCRProvider' % mode,
            )

    def test_missing_credential_raises(self):
        # 缺少百度凭证时不再静默回退，应直接抛错
        ak = os.environ.pop('BAIDU_OCR_API_KEY', None)
        sk = os.environ.pop('BAIDU_OCR_SECRET_KEY', None)
        import ocr_providers.factory as fmod
        fmod._PROVIDERS.clear()
        try:
            with self.assertRaises(RuntimeError):
                get_ocr_provider()
        finally:
            fmod._PROVIDERS.clear()
            if ak is not None:
                os.environ['BAIDU_OCR_API_KEY'] = ak
            if sk is not None:
                os.environ['BAIDU_OCR_SECRET_KEY'] = sk


if __name__ == '__main__':
    unittest.main(verbosity=2)
