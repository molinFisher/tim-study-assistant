"""
Tim 学习助手 - 应用配置
"""
import os

# 项目根目录（用于定位 .env、数据库、上传目录等）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 可选：从项目目录下的 .env 加载环境变量（不强制依赖；生产环境可直接注入环境变量）。
# 用显式路径，确保无论从哪个工作目录启动都能加载到本项目的 .env。
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, '.env'))
except Exception:
    pass


class Config:
    # 基础路径
    BASE_DIR = BASE_DIR

    # 数据库配置
    DATABASE_PATH = os.path.join(BASE_DIR, 'data', 'study_assistant.db')

    # 文件上传配置
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}

    # 图片存储阈值：小于此值存 BLOB，大于存文件
    IMAGE_BLOB_THRESHOLD = 100 * 1024  # 100KB
    SECONDS_PER_DAY = 86400

    # Flask 配置
    _raw_key = os.environ.get('SECRET_KEY', '')
    if not _raw_key:
        # 开发环境允许默认值，但打印警告
        _raw_key = 'tim-study-dev-key-not-for-production'
        print("⚠️  未设置 SECRET_KEY 环境变量，使用开发默认值（生产环境务必设置！）")
    SECRET_KEY = _raw_key
    TEMPLATES_AUTO_RELOAD = True

    # Cookie 配置
    COOKIE_NAME = 'tim_study_uuid'
    COOKIE_MAX_AGE = 365 * 24 * 60 * 60 * 10  # 10 年

    # 分页配置
    PAGE_SIZE = 20

    # 复习算法默认配置
    DEFAULT_REVIEW_ALGORITHM = 'sm2'
    DEFAULT_DAILY_REVIEW_LIMIT = 0   # 0 表示不限制

    # SM-2 间隔配置（阶段 → 天数）
    SM2_INTERVALS = {
        0: 1,
        1: 3,
        2: 7,
        3: 14,
        4: 30,
        5: 60,
    }

    # 艾宾浩斯遗忘曲线间隔（阶段 → 分钟）
    EBBINGHAUS_INTERVALS = {
        0: 5,       # 5 分钟
        1: 30,      # 30 分钟
        2: 720,     # 12 小时
        3: 1440,    # 1 天
        4: 2880,    # 2 天
        5: 5760,    # 4 天
        6: 10080,   # 7 天
        7: 21600,   # 15 天
    }

    # 学科列表
    SUBJECTS = ['数学', '物理', '道法', '语文', '英语', '生物', '化学', '信奥']

    # ---- 基础数据（从 base_data 表读取） ----
    @staticmethod
    def get_subjects():
        """从 base_data 表获取学科列表（带缓存）"""
        try:
            from database import query_db
            rows = query_db("SELECT name FROM base_data WHERE category='subject' ORDER BY sort_order")
            if rows:
                return [r['name'] for r in rows]
        except Exception:
            pass
        return Config.SUBJECTS

    @staticmethod
    def get_error_types():
        """从 base_data 表获取错误类型（含 keywords）"""
        try:
            from database import query_db
            rows = query_db("SELECT name, extra FROM base_data WHERE category='error_type' ORDER BY sort_order")
            if rows:
                import json
                result = []
                for r in rows:
                    kw = []
                    try:
                        kw = json.loads(r['extra'] or '[]')
                    except Exception:
                        pass
                    result.append((r['name'], kw))
                return result
        except Exception:
            pass
        return [('计算错误', ['计算','算错']), ('概念不清', ['概念']), ('审题失误', ['审题']),
                ('公式记忆错误', ['公式','记错']), ('方法不当', ['方法','思路']), ('其他', [])]

    # 错题状态
    STATUS_OPTIONS = {
        'active': '活跃',
        'archived': '已归档',
        'mastered': '已掌握',
        'deleted': '已删除',
    }

    # ========== OCR 配置 ==========
    OCR_TEMP_FOLDER = os.path.join(BASE_DIR, 'uploads', 'ocr_temp')
    OCR_MIN_CONFIDENCE = 0.3
    OCR_TASK_EXPIRE_SECONDS = 1800  # 30 分钟

    # ---- OCR 提供商 ----
    # 错题识别统一使用百度智能云 OCR（access_token 流程，高精度 accurate 接口）。
    # 凭证来自环境变量 BAIDU_OCR_API_KEY / BAIDU_OCR_SECRET_KEY，切勿在此硬编码。
    # 已移除本地 EasyOCR 与腾讯云等其他方式，不再提供回退/兜底。
    OCR_PROVIDER = os.environ.get('OCR_PROVIDER', 'baidu')

    # 百度智能云 OCR（access_token 流程，凭证来自环境变量，切勿在此硬编码）
    # 凭证为百度AI开放平台的 API Key(client_id) + Secret Key(client_secret)
    BAIDU_OCR_API_KEY = os.environ.get('BAIDU_OCR_API_KEY', '')
    BAIDU_OCR_SECRET_KEY = os.environ.get('BAIDU_OCR_SECRET_KEY', '')
    BAIDU_OCR_ENDPOINT = os.environ.get('BAIDU_OCR_ENDPOINT', 'https://aip.baidubce.com')
    # 默认使用「试卷分析与识别」(doc_analysis) 接口：原生支持版面分析与公式识别，
    # 开启 recg_formula 后返回文本已融合 LaTeX 公式。
    # 注意：需在百度控制台开通「试卷分析与识别/文档版面分析」服务。
    BAIDU_OCR_API = os.environ.get('BAIDU_OCR_API', '/rest/2.0/ocr/v1/doc_analysis')
    BAIDU_OCR_RECG_FORMULA = os.environ.get('BAIDU_OCR_RECG_FORMULA', 'true')  # 公式识别 on/off
    BAIDU_OCR_TIMEOUT = int(os.environ.get('BAIDU_OCR_TIMEOUT', '10'))

    # ========== 外部 API 配置 ==========
    API_RATE_LIMIT_DEFAULT = 60          # 默认每分钟 60 次请求
    API_RATE_LIMIT_BURST = 10            # 允许的突发请求数
    API_IMPORT_MAX_BATCH_SIZE = 200      # 单次最多导入 200 道错题
    API_TOKEN_PREFIX = 'tim_'            # Token 前缀，便于识别
