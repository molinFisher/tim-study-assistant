"""
可插拔 OCR 提供商包。

对外主要导出：
  - OCRProvider     : 抽象基类
  - get_ocr_provider : 工厂函数（始终返回百度 OCR）
  - BaiduOCRProvider : 百度智能云 OCR 实现
  - build_result    : 结果归一化工具
  - create_ocr_engine : 兼容旧 ocr_engine 的别名
"""
from .base import OCRProvider, build_result
from .factory import get_ocr_provider
from .baidu_provider import BaiduOCRProvider

# 向后兼容：历史代码 from ocr_engine import create_ocr_engine
create_ocr_engine = get_ocr_provider

__all__ = [
    'OCRProvider',
    'build_result',
    'get_ocr_provider',
    'BaiduOCRProvider',
    'create_ocr_engine',
]
