# limits.py - a daily counter shared by all visitors. No Streamlit in here.

import threading
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


class DailyCounter:
    """Thread-safe counter that allows `limit` uses per IST day."""

    def __init__(self, limit):
        self.limit = limit
        self._lock = threading.Lock()
        self._day = None
        self._count = 0

    def try_take(self, now=None):
        """Use one slot. Returns True if allowed, False if today's limit is used up."""
        today = (now or datetime.now(IST)).date()
        with self._lock:
            if self._day != today:
                self._day, self._count = today, 0
            if self._count >= self.limit:
                return False
            self._count += 1
            return True