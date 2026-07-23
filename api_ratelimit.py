"""
内存级 API 速率限制器（Token Bucket 算法）
线程安全，无需外部依赖（Redis 等）。
"""
import time
import threading


class TokenBucket:
    """令牌桶 — 平滑限流"""

    def __init__(self, rate, burst):
        """
        rate:  每分钟允许的请求数（令牌补充速率）
        burst: 桶容量（允许的突发请求数）
        """
        self.rate = rate
        self.burst = burst
        self.tokens = float(burst)
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def consume(self, tokens=1):
        """尝试消耗 1 个令牌，返回 (allowed: bool, remaining: int, retry_after_sec: int)"""
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill

            # 按速率补充令牌
            refill = elapsed * (self.rate / 60.0)
            self.tokens = min(float(self.burst), self.tokens + refill)
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True, int(self.tokens), 0
            else:
                # 计算需等待的秒数
                wait = (tokens - self.tokens) * (60.0 / self.rate)
                return False, int(self.tokens), max(1, int(wait))


class RateLimiter:
    """全局速率限制器管理器"""

    def __init__(self):
        self.buckets = {}
        self.lock = threading.Lock()

    def get_bucket(self, token_id, rate=60, burst=10):
        """获取或创建指定 token 的令牌桶"""
        with self.lock:
            if token_id not in self.buckets:
                self.buckets[token_id] = TokenBucket(rate=rate, burst=burst)
            return self.buckets[token_id]

    def check(self, token_id, rate=60, burst=10):
        """检查是否允许请求，返回 (allowed: bool, retry_after_sec: int)"""
        bucket = self.get_bucket(token_id, rate, burst)
        allowed, _, retry_after = bucket.consume()
        return allowed, retry_after

    def remaining(self, token_id, rate=60, burst=10):
        """获取剩余令牌数（不消耗）"""
        bucket = self.get_bucket(token_id, rate, burst)
        with bucket.lock:
            now = time.monotonic()
            elapsed = now - bucket.last_refill
            refill = elapsed * (bucket.rate / 60.0)
            current = min(float(bucket.burst), bucket.tokens + refill)
            return max(0, int(current))


# 全局单例
limiter = RateLimiter()
