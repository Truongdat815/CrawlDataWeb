# -*- coding: utf-8 -*-
"""
Dynamic Concurrency Manager
✅ Adaptive thread pool sizing based on rate limit feedback
- Monitor rate limit status
- Automatically reduce workers on rate limit
- Automatically increase workers when recovered
- Per-story or global configuration
"""

import time
import threading
from enum import Enum
from collections import deque
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict
from src import config
from src.scrapers import safe_print


class ConcurrencyState(Enum):
    """Concurrency state machine"""
    OPTIMAL = "optimal"          # Normal operations (full workers)
    THROTTLED = "throttled"      # Rate limit detected (reduced workers)
    RECOVERING = "recovering"    # Recovery phase (gradually increase)
    MINIMUM = "minimum"          # All workers at minimum (1 worker)


class DynamicConcurrencyMetrics:
    """Track concurrency metrics"""
    
    def __init__(self):
        self.state = ConcurrencyState.OPTIMAL
        self.current_workers = 1
        self.max_workers = 1
        self.min_workers = 1
        
        # Rate limit tracking
        self.rate_limit_events = deque(maxlen=100)  # Last 100 events
        self.last_rate_limit_time = None
        self.consecutive_rate_limits = 0
        
        # Performance tracking
        self.total_chapters_processed = 0
        self.total_api_calls = 0
        self.rate_limit_count = 0
        self.timeout_count = 0
        self.success_count = 0
        
        # Timeline
        self.created_at = datetime.now()
        self.last_state_change = datetime.now()
        self.last_metric_update = datetime.now()
    
    def record_rate_limit(self):
        """Record rate limit event"""
        self.rate_limit_count += 1
        self.last_rate_limit_time = datetime.now()
        self.consecutive_rate_limits += 1
        self.rate_limit_events.append({
            "timestamp": datetime.now().isoformat(),
            "workers": self.current_workers,
            "state": self.state.value
        })
    
    def record_timeout(self):
        """Record timeout event"""
        self.timeout_count += 1
    
    def record_success(self):
        """Record successful chapter"""
        self.success_count += 1
        self.total_chapters_processed += 1
        # Reset consecutive rate limits on success
        if self.state != ConcurrencyState.THROTTLED:
            self.consecutive_rate_limits = 0
    
    def to_dict(self) -> Dict:
        """Convert to dict for logging"""
        return {
            "state": self.state.value,
            "current_workers": self.current_workers,
            "max_workers": self.max_workers,
            "rate_limit_events": len(self.rate_limit_events),
            "consecutive_rate_limits": self.consecutive_rate_limits,
            "rate_limit_count": self.rate_limit_count,
            "timeout_count": self.timeout_count,
            "success_count": self.success_count,
            "total_chapters": self.total_chapters_processed,
            "uptime": (datetime.now() - self.created_at).total_seconds()
        }


class DynamicConcurrencyManager:
    """
    Dynamically adjust thread pool size based on rate limit feedback
    
    Algorithm:
    1. Start with max_workers threads
    2. On rate limit:
       - Reduce workers by 1
       - Move to THROTTLED state
       - Wait before recovery
    3. On success:
       - Stay in OPTIMAL state
    4. After recovery delay:
       - Gradually increase workers back to max
       - Move to RECOVERING state
    5. If many consecutive rate limits:
       - Go to MINIMUM state (1 worker only)
    """
    
    def __init__(
        self,
        max_workers: Optional[int] = None,
        min_workers: int = 1,
        recovery_delay: float = 30.0,
        recovery_increase_step: int = 1,
        rate_limit_threshold: int = 3
    ):
        """
        Args:
            max_workers: Maximum workers (from config if None)
            min_workers: Minimum workers (default: 1)
            recovery_delay: Seconds to wait before recovering
            recovery_increase_step: How many workers to add on recovery
            rate_limit_threshold: How many rate limits before going to MINIMUM
        """
        self.max_workers = max_workers or config.MAX_CHAPTER_WORKERS
        self.min_workers = min_workers
        self.recovery_delay = recovery_delay
        self.recovery_increase_step = recovery_increase_step
        self.rate_limit_threshold = rate_limit_threshold
        
        self.metrics = DynamicConcurrencyMetrics()
        self.metrics.max_workers = self.max_workers
        self.metrics.min_workers = self.min_workers
        self.metrics.current_workers = self.max_workers
        
        self.lock = threading.Lock()
        self.recovery_timer = None
        self.last_state_change_time = datetime.now()
        
        safe_print(f"✨ DynamicConcurrencyManager initialized")
        safe_print(f"   Max workers: {self.max_workers}")
        safe_print(f"   Min workers: {self.min_workers}")
        safe_print(f"   Recovery delay: {self.recovery_delay}s")
    
    def get_current_workers(self) -> int:
        """Get current worker count (thread-safe)"""
        with self.lock:
            return self.metrics.current_workers
    
    def on_rate_limit(self) -> int:
        """
        Called when rate limit detected
        Returns: New worker count (or same if already at minimum)
        """
        with self.lock:
            self.metrics.record_rate_limit()
            old_workers = self.metrics.current_workers
            
            # If at minimum, stay there
            if self.metrics.current_workers <= self.min_workers:
                self.metrics.state = ConcurrencyState.MINIMUM
                safe_print(
                    f"⚠️ Rate limit detected - Already at MINIMUM ({self.min_workers} worker)"
                )
                return self.metrics.current_workers
            
            # Reduce by 1
            self.metrics.current_workers = max(
                self.min_workers,
                self.metrics.current_workers - 1
            )
            self.metrics.state = ConcurrencyState.THROTTLED
            self.metrics.last_state_change = datetime.now()
            self.last_state_change_time = datetime.now()
            
            safe_print(
                f"⚠️ Rate limit detected - Reducing workers: {old_workers} → {self.metrics.current_workers}"
            )
            
            # Schedule recovery
            self._schedule_recovery()
            
            return self.metrics.current_workers
    
    def on_timeout(self) -> int:
        """
        Called when timeout detected
        Similar to rate limit but less aggressive
        """
        with self.lock:
            self.metrics.record_timeout()
            old_workers = self.metrics.current_workers
            
            # Only reduce if we have headroom (not aggressive like rate limit)
            if self.metrics.current_workers > self.min_workers:
                self.metrics.current_workers = max(
                    self.min_workers,
                    self.metrics.current_workers - 1
                )
                self.metrics.state = ConcurrencyState.THROTTLED
                
                safe_print(
                    f"⏱️ Timeout detected - Reducing workers: {old_workers} → {self.metrics.current_workers}"
                )
                
                self._schedule_recovery()
            
            return self.metrics.current_workers
    
    def on_success(self):
        """Called when chapter successfully crawled"""
        with self.lock:
            self.metrics.record_success()
            
            # If in MINIMUM state, don't mark as optimal yet
            if self.metrics.state == ConcurrencyState.MINIMUM:
                return
            
            # If was throttled, stay in throttled (recovery timer will promote)
            if self.metrics.state == ConcurrencyState.THROTTLED:
                return
            
            # Mark as optimal
            if self.metrics.state != ConcurrencyState.OPTIMAL:
                self.metrics.state = ConcurrencyState.OPTIMAL
    
    def _schedule_recovery(self):
        """Schedule automatic recovery after delay"""
        # Cancel existing timer if any
        if self.recovery_timer:
            self.recovery_timer.cancel()
        
        # Schedule new recovery
        self.recovery_timer = threading.Timer(
            self.recovery_delay,
            self._attempt_recovery
        )
        self.recovery_timer.daemon = True
        self.recovery_timer.start()
        
        safe_print(
            f"⏳ Recovery scheduled in {self.recovery_delay}s - "
            f"Will attempt to increase workers"
        )
    
    def _attempt_recovery(self):
        """Attempt to recover (increase workers)"""
        with self.lock:
            # Only recover if we're below max
            if self.metrics.current_workers >= self.max_workers:
                self.metrics.state = ConcurrencyState.OPTIMAL
                safe_print(f"✅ Fully recovered to {self.max_workers} workers (OPTIMAL)")
                return
            
            # Increase by step
            old_workers = self.metrics.current_workers
            self.metrics.current_workers = min(
                self.max_workers,
                self.metrics.current_workers + self.recovery_increase_step
            )
            self.metrics.state = ConcurrencyState.RECOVERING
            self.metrics.last_state_change = datetime.now()
            
            safe_print(
                f"📈 Recovery phase - Increasing workers: {old_workers} → {self.metrics.current_workers}"
            )
            
            # If not fully recovered, schedule another attempt
            if self.metrics.current_workers < self.max_workers:
                self._schedule_recovery()
            else:
                self.metrics.state = ConcurrencyState.OPTIMAL
                safe_print(f"✅ Fully recovered to {self.max_workers} workers")
    
    def get_metrics(self) -> Dict:
        """Get current metrics (thread-safe)"""
        with self.lock:
            return self.metrics.to_dict()
    
    def get_status_string(self) -> str:
        """Get human-readable status"""
        with self.lock:
            uptime = (datetime.now() - self.metrics.created_at).total_seconds()
            
            emoji = {
                ConcurrencyState.OPTIMAL: "✅",
                ConcurrencyState.THROTTLED: "⚠️",
                ConcurrencyState.RECOVERING: "📈",
                ConcurrencyState.MINIMUM: "🔴"
            }[self.metrics.state]
            
            return (
                f"{emoji} Workers: {self.metrics.current_workers}/{self.max_workers} | "
                f"State: {self.metrics.state.value} | "
                f"Rate limits: {self.metrics.rate_limit_count} | "
                f"Success: {self.metrics.success_count} | "
                f"Uptime: {uptime:.0f}s"
            )
    
    def reset(self):
        """Reset to initial state"""
        with self.lock:
            if self.recovery_timer:
                self.recovery_timer.cancel()
            
            self.metrics = DynamicConcurrencyMetrics()
            self.metrics.max_workers = self.max_workers
            self.metrics.min_workers = self.min_workers
            self.metrics.current_workers = self.max_workers
            
            safe_print("🔄 DynamicConcurrencyManager reset to initial state")


# Pre-configured instances for different scenarios
CONCURRENCY_PRESETS = {
    "aggressive": {
        "max_workers": 5,
        "min_workers": 1,
        "recovery_delay": 15.0,
        "recovery_increase_step": 1,
        "rate_limit_threshold": 5
    },
    "balanced": {
        "max_workers": 3,
        "min_workers": 1,
        "recovery_delay": 30.0,
        "recovery_increase_step": 1,
        "rate_limit_threshold": 3
    },
    "conservative": {
        "max_workers": 2,
        "min_workers": 1,
        "recovery_delay": 60.0,
        "recovery_increase_step": 1,
        "rate_limit_threshold": 2
    }
}


def get_concurrency_manager(preset: str = "balanced") -> DynamicConcurrencyManager:
    """
    Get pre-configured concurrency manager
    
    Args:
        preset: One of 'aggressive', 'balanced', 'conservative'
    
    Returns:
        Configured DynamicConcurrencyManager
    """
    if preset not in CONCURRENCY_PRESETS:
        raise ValueError(f"Unknown preset: {preset}")
    
    config_dict = CONCURRENCY_PRESETS[preset].copy()
    return DynamicConcurrencyManager(**config_dict)
