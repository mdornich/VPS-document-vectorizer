"""
API Rate Limiter for Document Vectorizer
Prevents runaway OpenAI API costs
"""
import os
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from pathlib import Path
import structlog

logger = structlog.get_logger()

class APIRateLimiter:
    """Rate limiter for OpenAI API calls with cost tracking"""
    
    def __init__(self):
        self.config = {
            'enabled': os.getenv('RATE_LIMIT_ENABLED', 'true').lower() == 'true',
            'max_requests_per_minute': int(os.getenv('MAX_REQUESTS_PER_MINUTE', '100')),
            'max_requests_per_hour': int(os.getenv('MAX_REQUESTS_PER_HOUR', '3000')),
            'max_requests_per_day': int(os.getenv('MAX_REQUESTS_PER_DAY', '100000')),
            'max_daily_cost_usd': float(os.getenv('MAX_DAILY_COST_USD', '10.00')),
            'estimated_cost_per_embedding': float(os.getenv('COST_PER_EMBEDDING', '0.000002')),
            'estimated_cost_per_completion': float(os.getenv('COST_PER_COMPLETION', '0.01'))
        }
        
        # Storage file for persistent tracking
        self.storage_file = Path('/tmp/rate_limit_tracker.json')
        self.usage_data = self._load_usage_data()
        
        logger.info("🛡️ API Rate Limiter initialized", config=self.config)
    
    def _load_usage_data(self) -> Dict:
        """Load usage data from file or create new"""
        if self.storage_file.exists():
            try:
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                    # Reset if it's a new day
                    if data.get('date') != datetime.now().strftime('%Y-%m-%d'):
                        return self._create_new_usage_data()
                    return data
            except:
                pass
        return self._create_new_usage_data()
    
    def _create_new_usage_data(self) -> Dict:
        """Create new usage tracking data"""
        return {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'requests': [],
            'daily_cost': 0.0,
            'daily_requests': 0
        }
    
    def _save_usage_data(self):
        """Save usage data to file"""
        try:
            with open(self.storage_file, 'w') as f:
                json.dump(self.usage_data, f)
        except Exception as e:
            logger.warning(f"Could not save usage data: {e}")
    
    def _clean_old_requests(self):
        """Remove requests older than 1 hour"""
        now = time.time()
        one_hour_ago = now - 3600
        self.usage_data['requests'] = [
            r for r in self.usage_data['requests'] 
            if r['timestamp'] > one_hour_ago
        ]
    
    def check_rate_limit(self, operation_type: str = 'embedding') -> Tuple[bool, Optional[str]]:
        """
        Check if operation is within rate limits
        
        Returns:
            (allowed, error_message)
        """
        if not self.config['enabled']:
            return True, None
        
        # Reset if new day
        if self.usage_data['date'] != datetime.now().strftime('%Y-%m-%d'):
            self.usage_data = self._create_new_usage_data()
        
        # Clean old requests
        self._clean_old_requests()
        
        # Check daily cost limit
        if self.usage_data['daily_cost'] >= self.config['max_daily_cost_usd']:
            logger.warning("💸 Daily cost limit reached", 
                         daily_cost=self.usage_data['daily_cost'],
                         limit=self.config['max_daily_cost_usd'])
            return False, f"Daily cost limit of ${self.config['max_daily_cost_usd']} reached. Service will resume tomorrow."
        
        # Check request counts
        now = time.time()
        one_minute_ago = now - 60
        one_hour_ago = now - 3600
        
        requests_last_minute = sum(1 for r in self.usage_data['requests'] 
                                   if r['timestamp'] > one_minute_ago)
        requests_last_hour = sum(1 for r in self.usage_data['requests'] 
                                 if r['timestamp'] > one_hour_ago)
        
        if requests_last_minute >= self.config['max_requests_per_minute']:
            return False, "Rate limit exceeded: Too many requests per minute. Please wait."
        
        if requests_last_hour >= self.config['max_requests_per_hour']:
            return False, "Rate limit exceeded: Hourly limit reached. Please try again later."
        
        if self.usage_data['daily_requests'] >= self.config['max_requests_per_day']:
            return False, "Rate limit exceeded: Daily request limit reached."
        
        # Warn if approaching limits
        if self.usage_data['daily_cost'] > self.config['max_daily_cost_usd'] * 0.8:
            logger.warning("⚠️ Approaching daily cost limit",
                         current_cost=f"${self.usage_data['daily_cost']:.2f}",
                         limit=f"${self.config['max_daily_cost_usd']:.2f}",
                         percent_used=f"{(self.usage_data['daily_cost'] / self.config['max_daily_cost_usd'] * 100):.1f}%")
        
        return True, None
    
    def record_usage(self, operation_type: str = 'embedding', count: int = 1, 
                     estimated_cost: Optional[float] = None):
        """Record API usage"""
        if not self.config['enabled']:
            return
        
        # Calculate cost if not provided
        if estimated_cost is None:
            if operation_type == 'embedding':
                estimated_cost = self.config['estimated_cost_per_embedding'] * count
            else:
                estimated_cost = self.config['estimated_cost_per_completion'] * count
        
        # Update usage data
        self.usage_data['requests'].append({
            'timestamp': time.time(),
            'type': operation_type,
            'count': count,
            'cost': estimated_cost
        })
        self.usage_data['daily_cost'] += estimated_cost
        self.usage_data['daily_requests'] += count
        
        # Save to file
        self._save_usage_data()
        
        logger.info(f"📊 API usage recorded",
                   operation=operation_type,
                   count=count,
                   cost=f"${estimated_cost:.4f}",
                   daily_total=f"${self.usage_data['daily_cost']:.2f}")
    
    def get_usage_stats(self) -> Dict:
        """Get current usage statistics"""
        self._clean_old_requests()
        
        return {
            'daily_cost': f"${self.usage_data['daily_cost']:.2f}",
            'daily_limit': f"${self.config['max_daily_cost_usd']:.2f}",
            'percent_used': f"{(self.usage_data['daily_cost'] / self.config['max_daily_cost_usd'] * 100):.1f}%",
            'requests_today': self.usage_data['daily_requests'],
            'requests_limit': self.config['max_requests_per_day'],
            'rate_limiting_enabled': self.config['enabled'],
            'reset_time': (datetime.now() + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            ).isoformat()
        }

# Singleton instance
rate_limiter = APIRateLimiter()