"""
OCR 提供商工厂。

本应用错题识别统一使用百度智能云 OCR（access_token 流程，高精度 accurate 接口）。
get_ocr_provider() 始终返回 BaiduOCRProvider，不再提供 EasyOCR / 腾讯云等
其他方式，也不再做失败回退。缺少百度凭证时 BaiduOCRProvider 初始化即抛错，
不会静默降级到本地引擎。
"""
import threading
from .base import OCRProvider
from .baidu_provider import BaiduOCRProvider


_PROVIDERS = {}
_LOCK = threading.Lock()


def get_ocr_provider(mode: str = None) -> OCRProvider:
    """获取 OCR 提供商（带模块级缓存，避免重复实例化）。

    当前仅支持百度智能云 OCR。参数 mode 仅为兼容旧调用而保留，会被忽略。
    缺少百度凭证时初始化即抛 RuntimeError。
    """
    with _LOCK:
        if 'baidu' in _PROVIDERS:
            return _PROVIDERS['baidu']
        provider = BaiduOCRProvider()
        _PROVIDERS['baidu'] = provider
        return provider
