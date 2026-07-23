"""
百度智能云 OCR 提供商：「试卷分析与识别」(doc_analysis) 接口（access_token 流程）。

接口特点：
  - 路径：/rest/2.0/ocr/v1/doc_analysis
  - 原生支持版面分析，开启 recg_formula=true 后返回文本已融合 LaTeX 公式，
    对数学试卷/错题的公式识别质量远优于通用 accurate 接口。
  - 返回 words_result[]（每行：words + location{left,top,width,height}），
    下游按 center_y 排序/拆多题不受影响。

鉴权方式：
  1. 用 API Key(client_id) + Secret Key(client_secret) 调
     GET {endpoint}/oauth/2.0/token 换取 access_token（有效期 30 天）；
  2. 用 access_token 调 POST {endpoint}/rest/2.0/ocr/v1/doc_analysis，
    带上 recg_formula、language_type、line_probability 等参数。

access_token 内存缓存（提前 60s 刷新）。
密钥仅来自运行环境变量，不硬编码、不落库。
"""

import os
import time
import base64

from config import Config
from .base import OCRProvider, build_result


class BaiduOCRProvider(OCRProvider):
    """百度 AI 开放平台「试卷分析与识别」提供商，access_token 鉴权。"""

    def __init__(self):
        self.api_key = os.environ.get('BAIDU_OCR_API_KEY')
        self.secret_key = os.environ.get('BAIDU_OCR_SECRET_KEY')
        if not (self.api_key and self.secret_key):
            raise RuntimeError(
                '缺少百度OCR凭证：请在环境变量设置 '
                'BAIDU_OCR_API_KEY 与 BAIDU_OCR_SECRET_KEY')
        self.endpoint = getattr(
            Config, 'BAIDU_OCR_ENDPOINT', 'https://aip.baidubce.com').rstrip('/')
        self.api = getattr(
            Config, 'BAIDU_OCR_API', '/rest/2.0/ocr/v1/doc_analysis')
        self.timeout = int(getattr(Config, 'BAIDU_OCR_TIMEOUT', '10'))
        self.recg_formula = getattr(Config, 'BAIDU_OCR_RECG_FORMULA', 'true')
        # access_token 内存缓存
        self._token = None
        self._token_expire = 0.0

    # ---------- Token ----------
    def _get_token(self):
        import requests

        now = time.time()
        if self._token and now < self._token_expire - 60:
            return self._token
        try:
            resp = requests.get(
                self.endpoint + '/oauth/2.0/token',
                params={
                    'grant_type': 'client_credentials',
                    'client_id': self.api_key,
                    'client_secret': self.secret_key,
                },
                timeout=self.timeout,
            )
            data = resp.json()
        except Exception as e:
            raise RuntimeError('百度OCR获取token失败: %s' % e)
        if 'access_token' not in data:
            raise RuntimeError(
                '百度OCR获取token失败: %s' % data.get('error_description', data))
        self._token = data['access_token']
        self._token_expire = now + data.get('expires_in', 2592000)
        return self._token

    # ---------- 识别 ----------
    def recognize(self, image_path: str):
        """
        调用百度试卷分析与识别 (doc_analysis) 接口。
        开启 recg_formula 时，返回文本已融合 LaTeX 公式。
        """
        import requests
        from PIL import Image

        with Image.open(image_path) as im:
            w, h = im.size

        with open(image_path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('utf-8')

        token = self._get_token()

        try:
            resp = requests.post(
                self.endpoint + self.api,
                params={'access_token': token},
                data={
                    'image': b64,
                    'language_type': 'CHN_ENG',
                    'line_probability': 'true',
                    'probability': 'true',
                    'recg_formula': self.recg_formula,
                },
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'accept': 'application/json',
                },
                timeout=self.timeout,
            )
            data = resp.json()
        except Exception as e:
            raise RuntimeError('百度OCR调用失败: %s' % e)

        if data.get('error_code'):
            self._token = None
            self._token_expire = 0.0
            raise RuntimeError(
                '百度OCR错误 %s: %s'
                % (data.get('error_code'), data.get('error_msg')))

        results = []

        # 优先 words_result（recg_formula=true 时融合了文字与公式）
        wr = data.get('words_result')
        if wr and isinstance(wr, list):
            for item in wr:
                text = (item.get('words') or '').strip()
                loc = item.get('location') or {}
                left = loc.get('left', 0)
                top = loc.get('top', 0)
                ww = loc.get('width', 0)
                hh = loc.get('height', 0)
                norm_bbox = _normalize_bbox(left, top, ww, hh, w, h)
                conf = _pick_confidence(item)
                if text:
                    results.append(build_result(text, norm_bbox, conf))
        else:
            # 兜底：results[] 字段
            for r in (data.get('results') or []):
                words_list = r.get('words') or []
                lines = []
                for wd in words_list:
                    word_text = (wd.get('word') or '').strip()
                    lines.append(word_text)
                text = ' '.join(lines)
                loc = {}
                if words_list:
                    loc = words_list[0].get('words_location') or {}
                left = loc.get('left', 0)
                top = loc.get('top', 0)
                ww = loc.get('width', 0)
                hh = loc.get('height', 0)
                norm_bbox = _normalize_bbox(left, top, ww, hh, w, h)
                conf = _pick_confidence(r)
                if text:
                    results.append(build_result(text, norm_bbox, conf))

        results.sort(key=lambda r: r['center_y'])
        return results


def _normalize_bbox(left, top, ww, hh, img_w, img_h):
    if img_w <= 0 or img_h <= 0:
        return [[0, 0], [1, 0], [1, 1], [0, 1]]
    return [
        [left / img_w, top / img_h],
        [(left + ww) / img_w, top / img_h],
        [(left + ww) / img_w, (top + hh) / img_h],
        [left / img_w, (top + hh) / img_h],
    ]


def _pick_confidence(item):
    prob = item.get('probability')
    if isinstance(prob, dict):
        return float(prob.get('average', 1.0))
    lp = item.get('line_probability')
    if lp is not None:
        return float(lp)
    return 1.0
