# -*- coding: utf-8 -*-
"""
Step-Level Retry Logic
✅ Retry from API calls, not entire stories
- Per-step retry: fetch_chapters, scrape_chapter, fetch_comments
- Exponential backoff with jitter
- Tracks retry metrics
"""

import time
import random
import traceback
from functools import wraps
from typing import Callable, Any, Optional, Dict, Tuple, Type, cast
from datetime import datetime, timedelta
from src import config
from ..scrapers import safe_print

class RetryMetrics:
    """Track retry statistics"""
    
    def __init__(self):
        self.total_attempts = 0
        self.successful_attempts = 0
        self.failed_attempts = 0
        self.total_retries = 0
        self.last_error = None
        self.last_error_time = None
    
    def record_success(self):
        self.total_attempts += 1
        self.successful_attempts += 1
    
    def record_failure(self, error: Optional[BaseException] = None):
        self.total_attempts += 1
        self.failed_attempts += 1
        if error:
            self.last_error = str(error)
            self.last_error_time = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "total_attempts": self.total_attempts,
            "successful": self.successful_attempts,
            "failed": self.failed_attempts,
            "total_retries": self.total_retries,
            "success_rate": (self.successful_attempts / self.total_attempts * 100) if self.total_attempts > 0 else 0,
            "last_error": self.last_error,
            "last_error_time": self.last_error_time
        }

class StepRetryConfig:
    """Configuration for step-level retries"""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
        backoff_multiplier: float = 2.0,
        max_backoff: float = 10.0,
        jitter: float = 0.1,
        retryable_exceptions: Tuple[Type[BaseException], ...] = (Exception,),
        non_retryable_errors: Tuple[str, ...] = ()
    ):
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.backoff_multiplier = backoff_multiplier
        self.max_backoff = max_backoff
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions
        self.non_retryable_errors = non_retryable_errors

def step_retry(config: StepRetryConfig = StepRetryConfig()):
    """Retry decorator for step-level functions"""
    
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            metrics = RetryMetrics()
            attempt = 0
            backoff = config.initial_backoff
            
            while attempt < config.max_retries:
                try:
                    result = func(*args, **kwargs)
                    metrics.record_success()
                    return result
                except Exception as e:
                    metrics.record_failure(e)
                    # Sửa lỗi: isinstance chỉ dùng cho type, không phải tuple str
                    if type(e).__name__ in config.non_retryable_errors:
                        break
                    attempt += 1
                    backoff = min(backoff * config.backoff_multiplier, config.max_backoff)
                    time.sleep(backoff + random.uniform(0, config.jitter))
            
            safe_print(f"Retries exhausted. Metrics: {metrics.to_dict()}")
            raise Exception(f"Failed after {config.max_retries} attempts")
        
        return wrapper
    return decorator
