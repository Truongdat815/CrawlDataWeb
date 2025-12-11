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
from ..scrapers import safe_print

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
            "event": "rate_limit"
        })
