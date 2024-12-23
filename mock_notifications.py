import logging
from typing import Dict, List
from datetime import datetime
import random

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MockTelegramNotifier:
    def __init__(self):
        self.enabled = True
        
    def send_notification(self, message: str, severity: str = "info"):
        """Simulate sending a Telegram notification"""
        severity_emoji = {
            "critical": "🚨",
            "high": "⚠️",
            "medium": "⚡",
            "low": "ℹ️",
            "info": "📢"
        }
        emoji = severity_emoji.get(severity, "📢")
        formatted_message = f"{emoji} {message}"
        logger.info(f"[TELEGRAM NOTIFICATION] {formatted_message}")
        return True

class SecurityEventGenerator:
    def __init__(self):
        self.notifier = MockTelegramNotifier()
        
    def generate_contract_event(self) -> Dict:
        """Generate a mock high-risk contract deployment event"""
        risk_factors = [
            "Unverified source code",
            "Similar to known scam contract",
            "Unusual token distribution",
            "Missing security features"
        ]
        
        event = {
            "type": "contract_deployment",
            "severity": "high",
            "timestamp": datetime.utcnow().isoformat(),
            "contract_address": f"0x{''.join(random.choices('0123456789abcdef', k=40))}",
            "risk_factors": random.sample(risk_factors, k=2),
            "risk_score": round(random.uniform(0.7, 1.0), 2)
        }
        
        message = (
            f"🚨 High-Risk Contract Deployment Detected!\n"
            f"Address: {event['contract_address']}\n"
            f"Risk Score: {event['risk_score']}\n"
            f"Risk Factors: {', '.join(event['risk_factors'])}"
        )
        self.notifier.send_notification(message, "critical")
        return event
        
    def generate_wallet_event(self) -> Dict:
        """Generate a mock suspicious wallet activity event"""
        suspicious_activities = [
            "Multiple rapid transfers to unknown addresses",
            "Interaction with flagged contracts",
            "Unusual transaction patterns",
            "Connection to known scam addresses"
        ]
        
        event = {
            "type": "suspicious_wallet",
            "severity": "medium",
            "timestamp": datetime.utcnow().isoformat(),
            "wallet_address": f"0x{''.join(random.choices('0123456789abcdef', k=40))}",
            "suspicious_activity": random.choice(suspicious_activities),
            "risk_score": round(random.uniform(0.4, 0.7), 2)
        }
        
        message = (
            f"⚠️ Suspicious Wallet Activity Detected!\n"
            f"Address: {event['wallet_address']}\n"
            f"Activity: {event['suspicious_activity']}\n"
            f"Risk Score: {event['risk_score']}"
        )
        self.notifier.send_notification(message, "high")
        return event
        
    def generate_failed_transactions(self) -> Dict:
        """Generate a mock multiple failed transactions event"""
        failure_reasons = [
            "Insufficient gas",
            "Contract execution revert",
            "Front-running attempt",
            "Invalid function parameters"
        ]
        
        num_failures = random.randint(3, 8)
        event = {
            "type": "failed_transactions",
            "severity": "medium",
            "timestamp": datetime.utcnow().isoformat(),
            "address": f"0x{''.join(random.choices('0123456789abcdef', k=40))}",
            "failure_count": num_failures,
            "failure_reason": random.choice(failure_reasons),
            "time_window": "5 minutes"
        }
        
        message = (
            f"⚡ Multiple Failed Transactions Detected!\n"
            f"Address: {event['address']}\n"
            f"Failed Attempts: {event['failure_count']}\n"
            f"Reason: {event['failure_reason']}\n"
            f"Time Window: {event['time_window']}"
        )
        self.notifier.send_notification(message, "medium")
        return event

# Global instance for easy access
security_events = SecurityEventGenerator()
