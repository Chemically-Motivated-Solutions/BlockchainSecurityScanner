import os
from typing import Dict, List, Optional, TypedDict, Union
from openai import OpenAI
import json
import time
from functools import wraps
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# The newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# Do not change this unless explicitly requested by the user
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

client = OpenAI(api_key=OPENAI_API_KEY)

class RateLimiter:
    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window  # in seconds
        self.requests = []

    def allow_request(self) -> bool:
        now = datetime.now()
        # Remove old requests outside the time window
        self.requests = [req_time for req_time in self.requests 
                        if now - req_time < timedelta(seconds=self.time_window)]
        
        if len(self.requests) >= self.max_requests:
            return False
            
        self.requests.append(now)
        return True

    def wait_time(self) -> float:
        if not self.requests:
            return 0
        
        now = datetime.now()
        oldest_request = min(self.requests)
        next_window = oldest_request + timedelta(seconds=self.time_window)
        
        if now >= next_window:
            return 0
        return (next_window - now).total_seconds()

# Global rate limiter instances
contract_limiter = RateLimiter(max_requests=50, time_window=60)  # 50 requests per minute
transaction_limiter = RateLimiter(max_requests=50, time_window=60)

def rate_limit(limiter: RateLimiter):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not limiter.allow_request():
                wait_time = limiter.wait_time()
                if wait_time > 0:
                    logger.info(f"Rate limit reached. Waiting {wait_time:.2f} seconds")
                    time.sleep(wait_time)
            return func(*args, **kwargs)
        return wrapper
    return decorator

@rate_limit(max_per_minute=50)
def analyze_smart_contract(source_code: str, network: Optional[Dict] = None) -> Dict:
    """Analyze smart contract code using AI for potential security risks."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": f"You are a blockchain security expert. Analyze the smart contract code for security vulnerabilities, specifically for the {network['name'] if network else 'Unknown'} network. Consider network-specific vulnerabilities and standards. Provide a detailed risk assessment including specific vulnerability types, severity levels, and confidence scores."
                },
                {"role": "user", "content": f"Analyze this smart contract code:\n\n{source_code}"}
            ],
            response_format={"type": "json_object"},
        )
        
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {
            "error": f"AI analysis failed: {str(e)}",
            "vulnerabilities": [],
            "risk_score": 1.0  # High risk score on failure
        }

@rate_limit(max_per_minute=50)
def analyze_transaction_patterns(transactions: List[Dict]) -> Dict:
    """Analyze transaction patterns for suspicious behavior."""
    try:
        transactions_str = json.dumps(transactions)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a blockchain transaction analysis expert. Analyze these transactions for suspicious patterns and provide a risk assessment with specific flags and confidence scores."
                },
                {"role": "user", "content": f"Analyze these transactions:\n\n{transactions_str}"}
            ],
            response_format={"type": "json_object"},
        )
        
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {
            "error": f"Transaction analysis failed: {str(e)}",
            "suspicious_patterns": [],
            "risk_score": 0.5  # Moderate risk score on failure
        }

def calculate_combined_risk_score(
    code_analysis: Dict,
    transaction_analysis: Dict,
    weights: Dict[str, float] = None
) -> float:
    """Calculate a combined risk score from multiple analyses."""
    if weights is None:
        weights = {
            "code_analysis": 0.6,
            "transaction_analysis": 0.4
        }
    
    try:
        code_score = code_analysis.get("risk_score", 0.5)
        transaction_score = transaction_analysis.get("risk_score", 0.5)
        
        combined_score = (
            code_score * weights["code_analysis"] +
            transaction_score * weights["transaction_analysis"]
        )
        
        return min(1.0, max(0.0, combined_score))
    except Exception:
        return 0.7  # Default to moderately high risk on calculation failure
