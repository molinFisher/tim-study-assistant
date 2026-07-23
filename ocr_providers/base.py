"""
OCR 提供商抽象基类与结果归一化工具。

所有提供商都需实现 recognize(image_path) -> List[dict]，返回结构统一为：
  - text:       识别文本
  - bbox:       归一化到 [0,1] 的 4 顶点多边形 [[x,y], ...]
  - confidence: 0~1 的置信度
  - center_y:   轴对齐包围盒纵向中点 *1000（仅用于排序，已升序）
  - center_x:   轴对齐包围盒横向中点 *1000
下游 ocr_parser / formula_fixer 仅依赖 text/center_y/confidence。
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List

OCRResult = Dict[str, Any]


class OCRProvider(ABC):
    """所有 OCR 提供商的抽象基类。"""

    @abstractmethod
    def recognize(self, image_path: str) -> List[OCRResult]:
        """识别图片，返回按 center_y 升序的结构化结果列表。"""
        raise NotImplementedError


def build_result(text: str, norm_bbox: List[List[float]], confidence: float) -> OCRResult:
    """
    将 (文本, 归一化4顶点bbox, 0-1置信度) 组装为统一 dict。
    center_y/center_x 用轴对齐包围盒中点 *1000 取整（与历史 OCREngine 语义一致）。
    """
    xs = [p[0] for p in norm_bbox]
    ys = [p[1] for p in norm_bbox]
    center_x = int((min(xs) + max(xs)) / 2 * 1000)
    center_y = int((min(ys) + max(ys)) / 2 * 1000)
    return {
        'text': (text or '').strip(),
        'bbox': [[round(float(x), 4), round(float(y), 4)] for x, y in norm_bbox],
        'confidence': round(float(confidence), 4),
        'center_y': center_y,
        'center_x': center_x,
    }
