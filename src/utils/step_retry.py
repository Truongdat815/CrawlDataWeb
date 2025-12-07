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
from src.scrapers import safe_print


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
        max_backoff: float = 60.0,
        backoff_multiplier: float = 2.0,
        jitter: bool = True,
        step_name: str = "API_CALL"
    ):
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter
        self.step_name = step_name
        self.metrics = RetryMetrics()
    
    def get_backoff_time(self, attempt: int) -> float:
        """Calculate backoff time with exponential increase and optional jitter"""
        backoff = self.initial_backoff * (self.backoff_multiplier ** attempt)
        backoff = min(backoff, self.max_backoff)
        
        if self.jitter:
            # Add random jitter: 0-25% of backoff time
            jitter_amount = backoff * random.uniform(0, 0.25)
            backoff += jitter_amount
        
        return backoff


def step_retry(
    max_retries: Optional[int] = None,
    initial_backoff: float = 1.0,
    max_backoff: float = 60.0,
    backoff_multiplier: float = 2.0,
    step_name: str = "STEP",
    retryable_exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    fatal_exceptions: Tuple[Type[BaseException], ...] = ()
):
    """
    Decorator for step-level retries
    
    Usage:
        @step_retry(
            max_retries=3,
            step_name="fetch_chapters",
            retryable_exceptions=(requests.Timeout, requests.ConnectionError),
            fatal_exceptions=(ValueError,)
        )
        def fetch_chapters(story_id):
            ...
    
    Args:
        max_retries: Number of retries (from config if None)
        initial_backoff: Initial backoff in seconds
        max_backoff: Maximum backoff time
        backoff_multiplier: Exponential backoff multiplier
        step_name: Name of the step (for logging)
        retryable_exceptions: Tuple of exceptions to retry on
        fatal_exceptions: Exceptions that should NOT be retried
    """
    max_retries = max_retries or config.MAX_CHAPTER_RETRIES
    
    def decorator(func: Callable) -> Callable:
        retry_config = StepRetryConfig(
            max_retries=max_retries,
            initial_backoff=initial_backoff,
            max_backoff=max_backoff,
            backoff_multiplier=backoff_multiplier,
            step_name=step_name
        )
        
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    retry_config.metrics.record_success()
                    
                    if attempt > 0:
                        safe_print(f"✅ [{step_name}] Succeeded after {attempt} retry/retries")
                    
                    return result
                
                except fatal_exceptions as e:
                    # Don't retry fatal exceptions
                    safe_print(f"❌ [{step_name}] Fatal error (no retry): {e}")
                    retry_config.metrics.record_failure(e)
                    raise
                
                except retryable_exceptions as e:
                    last_exception = e
                    retry_config.metrics.record_failure(e)
                    
                    if attempt < max_retries:
                        backoff_time = retry_config.get_backoff_time(attempt)
                        retry_config.metrics.total_retries += 1
                        
                        safe_print(
                            f"⚠️ [{step_name}] Attempt {attempt + 1}/{max_retries + 1} failed: {type(e).__name__}"
                        )
                        safe_print(
                            f"   ⏳ Retrying in {backoff_time:.1f}s... (backoff attempt {attempt})"
                        )
                        
                        time.sleep(backoff_time)
                    else:
                        safe_print(
                            f"❌ [{step_name}] All {max_retries + 1} attempts failed"
                        )
                        raise
                
                except Exception as e:
                    # Unexpected exception, don't retry
                    safe_print(f"❌ [{step_name}] Unexpected error (no retry): {type(e).__name__}: {e}")
                    retry_config.metrics.record_failure(e)
                    raise
            
            # Should not reach here
            if last_exception:
                raise last_exception
        
        # Attach metrics to function for introspection
        # Type: ignore because we're adding custom attributes to a function
        wrapper.retry_metrics = retry_config.metrics  # type: ignore
        wrapper.retry_config = retry_config  # type: ignore
        
        return cast(Callable, wrapper)
    
    return decorator


# Pre-defined step retry configurations
STEP_RETRIES = {
    "fetch_chapters": {
        "max_retries": 3,
        "initial_backoff": 1.0,
        "step_name": "fetch_chapters"
    },
    "scrape_chapter": {
        "max_retries": 3,
        "initial_backoff": 1.5,
        "step_name": "scrape_chapter"
    },
    "fetch_comments": {
        "max_retries": 3,
        "initial_backoff": 2.0,
        "step_name": "fetch_comments"
    },
    "fetch_user": {
        "max_retries": 2,
        "initial_backoff": 1.0,
        "step_name": "fetch_user"
    },
    "fetch_story_metadata": {
        "max_retries": 3,
        "initial_backoff": 1.0,
        "step_name": "fetch_story_metadata"
    }
}


def get_step_retry_decorator(step_type: str, max_retries: Optional[int] = None):
    """
    Get pre-configured retry decorator for common steps
    
    Args:
        step_type: One of 'fetch_chapters', 'scrape_chapter', 'fetch_comments', 'fetch_user'
        max_retries: Override max retries
    
    Returns:
        Configured step_retry decorator
    """
    if step_type not in STEP_RETRIES:
        raise ValueError(f"Unknown step type: {step_type}")
    
    config_dict = STEP_RETRIES[step_type].copy()
    if max_retries:
        config_dict["max_retries"] = max_retries
    
    return step_retry(**config_dict)


# Common retryable exceptions - Built dynamically to avoid type issues
def _build_retryable_exceptions() -> Tuple[Type[BaseException], ...]:
    """Build retryable exceptions tuple from available libraries"""
    exceptions: list[Type[BaseException]] = [
        TimeoutError,
        ConnectionError,
        ConnectionResetError,
        ConnectionAbortedError,
    ]
    
    # Try to import requests exceptions if available
    try:
        import requests
        exceptions.append(requests.Timeout)
        exceptions.append(requests.ConnectionError)
        # ChunkedEncodingError might not exist in all requests versions
        # Use getattr with default to safely access the attribute
        chunked_error = getattr(requests, 'ChunkedEncodingError', None)
        if chunked_error is not None:
            exceptions.append(chunked_error)  # type: ignore
    except (ImportError, AttributeError):
        pass
    
    # Try to import playwright exceptions if available
    try:
        from playwright._impl._errors import TimeoutError as PlaywrightTimeoutError
        exceptions.append(PlaywrightTimeoutError)
    except (ImportError, AttributeError):
        pass
    
    try:
        from playwright.async_api import Error as PlaywrightError
        exceptions.append(PlaywrightError)
    except (ImportError, AttributeError):
        pass
    
    return tuple(exceptions)


RETRYABLE_NETWORK_ERRORS: Tuple[Type[BaseException], ...] = _build_retryable_exceptions()
