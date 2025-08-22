"""
Rate limiter for OpenAI API calls to prevent hitting rate limits.
"""

import time
import threading
from collections import deque
from typing import Optional
import structlog

logger = structlog.get_logger()


class RateLimiter:
    """
    Token bucket rate limiter for OpenAI API calls.
    Tracks both requests per minute (RPM) and tokens per minute (TPM).
    """
    
    def __init__(
        self,
        rpm_limit: int = 3000,  # Requests per minute
        tpm_limit: int = 1000000,  # Tokens per minute  
        window_seconds: int = 60
    ):
        self.rpm_limit = rpm_limit
        self.tpm_limit = tpm_limit
        self.window_seconds = window_seconds
        
        # Track request timestamps
        self.request_times = deque()
        # Track token usage with timestamps
        self.token_usage = deque()
        
        self.lock = threading.Lock()
        
        logger.info(f"Rate limiter initialized: {rpm_limit} RPM, {tpm_limit:,} TPM")
    
    def _clean_old_entries(self):
        """Remove entries older than the window."""
        current_time = time.time()
        cutoff_time = current_time - self.window_seconds
        
        # Clean request times
        while self.request_times and self.request_times[0] < cutoff_time:
            self.request_times.popleft()
        
        # Clean token usage
        while self.token_usage and self.token_usage[0][0] < cutoff_time:
            self.token_usage.popleft()
    
    def wait_if_needed(self, estimated_tokens: int = 0) -> float:
        """
        Check rate limits and wait if necessary.
        
        Args:
            estimated_tokens: Estimated tokens for the upcoming request
            
        Returns:
            Time waited in seconds
        """
        with self.lock:
            self._clean_old_entries()
            
            current_time = time.time()
            wait_time = 0.0
            
            # Check request rate limit
            if len(self.request_times) >= self.rpm_limit:
                # Need to wait until the oldest request is outside the window
                oldest_request = self.request_times[0]
                wait_time = max(wait_time, oldest_request + self.window_seconds - current_time)
            
            # Check token rate limit
            current_tokens = sum(tokens for _, tokens in self.token_usage)
            if current_tokens + estimated_tokens > self.tpm_limit:
                # Need to wait until we have token budget
                if self.token_usage:
                    oldest_token_time = self.token_usage[0][0]
                    wait_time = max(wait_time, oldest_token_time + self.window_seconds - current_time)
            
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.2f} seconds")
                time.sleep(wait_time)
            
            # Record this request
            self.request_times.append(time.time())
            if estimated_tokens > 0:
                self.token_usage.append((time.time(), estimated_tokens))
            
            return wait_time
    
    def record_usage(self, tokens_used: int):
        """
        Record actual token usage after a request.
        
        Args:
            tokens_used: Actual number of tokens used
        """
        with self.lock:
            # Update the last entry with actual usage if we have an estimate
            if self.token_usage and tokens_used > 0:
                # Replace estimated with actual
                timestamp = self.token_usage[-1][0]
                self.token_usage[-1] = (timestamp, tokens_used)
    
    def get_current_usage(self) -> dict:
        """Get current usage statistics."""
        with self.lock:
            self._clean_old_entries()
            
            current_tokens = sum(tokens for _, tokens in self.token_usage)
            
            return {
                'requests_in_window': len(self.request_times),
                'tokens_in_window': current_tokens,
                'rpm_usage': len(self.request_times) / self.rpm_limit * 100,
                'tpm_usage': current_tokens / self.tpm_limit * 100,
                'rpm_limit': self.rpm_limit,
                'tpm_limit': self.tpm_limit
            }


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        # Default limits for text-embedding-3-small model
        # Adjust based on your OpenAI tier
        _rate_limiter = RateLimiter(
            rpm_limit=3000,  # Tier 1 default
            tpm_limit=1000000  # Tier 1 default
        )
    return _rate_limiter


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for a text string.
    Rough estimate: ~4 characters per token for English text.
    """
    return len(text) // 4