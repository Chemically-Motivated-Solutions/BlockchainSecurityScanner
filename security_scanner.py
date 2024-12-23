import re
from typing import Dict, List

def analyze_contract(source_code: str, network_id: int) -> Dict:
    from ai_analyzer import analyze_smart_contract
    from models import Network
    from app import get_web3_provider
    
    # Get network information
    network = Network.query.get(network_id)
    if not network:
        return {
            "error": "Invalid network specified",
            "vulnerabilities": [],
            "risk_score": 1.0
        }
        
    try:
        # Get network-specific Web3 provider with resilient connection
        w3, is_connected = get_web3_provider(network.chain_id)
        
        if not is_connected:
            # Try one more time with force_new=True
            w3, is_connected = get_web3_provider(network.chain_id, force_new=True)
            if not is_connected:
                return {
                    "error": f"Cannot establish reliable connection to {network.name}",
                    "vulnerabilities": [],
                    "risk_score": 1.0,
                    "recommendations": ["Try again later or switch to a different network"]
                }
        
        # Verify chain ID
        try:
            chain_id = w3.eth.chain_id
            if chain_id != network.chain_id:
                return {
                    "error": f"Chain ID mismatch on {network.name}. Expected {network.chain_id}, got {chain_id}",
                    "vulnerabilities": [],
                    "risk_score": 1.0,
                    "recommendations": ["Verify network configuration"]
                }
        except Exception as e:
            return {
                "error": f"Failed to verify chain ID for {network.name}: {str(e)}",
                "vulnerabilities": [],
                "risk_score": 1.0,
                "recommendations": ["Check network connectivity"]
            }
            
    except Exception as e:
        return {
            "error": f"Network error on {network.name}: {str(e)}",
            "vulnerabilities": [],
            "risk_score": 1.0,
            "recommendations": ["Verify network availability", "Check RPC endpoint status"]
        }
        
    # Network-specific vulnerability checks
    network_checks = {
        # Ethereum Mainnet
        1: {
            "patterns": [
                ("transfer.call", "high", "Potential ETH transfer vulnerability"),
                ("selfdestruct", "critical", "Self-destruct capability detected")
            ]
        },
        # BSC
        56: {
            "patterns": [
                ("SafeBEP20", "medium", "Missing SafeBEP20 usage"),
                ("BEP20", "info", "BEP20 token implementation")
            ]
        },
        # Polygon
        137: {
            "patterns": [
                ("checkpoint", "medium", "Checkpoint mechanism consideration needed"),
                ("ChildToken", "info", "Child token implementation")
            ]
        }
    }
    
    # Basic static analysis
    vulnerabilities = []
    risk_score = 0
    
    # Check for reentrancy vulnerabilities
    if "call.value" in source_code and not "ReentrancyGuard" in source_code:
        vulnerabilities.append({
            "type": "reentrancy",
            "severity": "high",
            "description": "Potential reentrancy vulnerability detected"
        })
        risk_score += 0.4
        
    # Check for unchecked return values
    if re.search(r'\.call\{.*\}\(".*"\)', source_code):
        if not re.search(r'require\(.*\.call', source_code):
            vulnerabilities.append({
                "type": "unchecked_return",
                "severity": "medium",
                "description": "Unchecked return value from low-level call"
            })
            risk_score += 0.3
            
    # Check for integer overflow
    if not "SafeMath" in source_code:
        vulnerabilities.append({
            "type": "integer_overflow",
            "severity": "medium",
            "description": "No SafeMath usage detected"
        })
        risk_score += 0.2
        
    # Check for tx.origin usage
    if "tx.origin" in source_code:
        vulnerabilities.append({
            "type": "tx_origin",
            "severity": "high",
            "description": "Dangerous tx.origin usage detected"
        })
        risk_score += 0.4
        
    # AI-powered analysis
    ai_analysis = analyze_smart_contract(source_code)
    if "error" not in ai_analysis:
        # Combine static and AI analysis results
        vulnerabilities.extend(ai_analysis.get("vulnerabilities", []))
        ai_risk_score = ai_analysis.get("risk_score", 0.5)
        # Weight the scores (60% AI, 40% static analysis)
        risk_score = (0.6 * ai_risk_score) + (0.4 * min(risk_score, 1.0))

    return {
        "vulnerabilities": vulnerabilities,
        "risk_score": min(risk_score, 1.0),
        "recommendations": generate_recommendations(vulnerabilities)
    }

def check_wallet_safety(address: str, network_id: int) -> Dict:
    from ai_analyzer import analyze_transaction_patterns, calculate_combined_risk_score
    
    flags = []
    risk_score = 0
    
    # Example transaction data - in production, this would fetch real blockchain data
    sample_transactions = [
        {
            "from": address,
            "to": f"0x{''.join(['0123456789abcdef'[i % 16] for i in range(40)])}",
            "value": "1000000000000000000",
            "timestamp": "2024-11-24T10:00:00Z"
        }
    ]
    
    # Check contract interaction history
    interaction_risk = check_contract_interactions(address)
    if interaction_risk > 0:
        flags.append({
            "type": "suspicious_interactions",
            "severity": interaction_risk,
            "description": "Suspicious smart contract interactions detected"
        })
        risk_score += interaction_risk
    
    # AI-powered transaction pattern analysis
    tx_analysis = analyze_transaction_patterns(sample_transactions)
    if "error" not in tx_analysis:
        suspicious_patterns = tx_analysis.get("suspicious_patterns", [])
        for pattern in suspicious_patterns:
            flags.append({
                "type": "ai_detected_pattern",
                "severity": pattern.get("severity", "medium"),
                "description": pattern.get("description", "Suspicious pattern detected by AI")
            })
        
        # Combine traditional and AI risk scores
        risk_score = calculate_combined_risk_score(
            {"risk_score": risk_score},
            tx_analysis,
            weights={"code_analysis": 0.4, "transaction_analysis": 0.6}
        )

    return {
        "address": address,
        "risk_score": min(risk_score, 1.0),
        "flags": flags
    }

def check_contract_interactions(address: str) -> float:
    # Placeholder for contract interaction analysis
    return 0.0

def analyze_transaction_patterns(address: str) -> float:
    # Placeholder for transaction pattern analysis
    return 0.0

def generate_recommendations(vulnerabilities: List[Dict]) -> List[str]:
    recommendations = []
    for vuln in vulnerabilities:
        if vuln["type"] == "reentrancy":
            recommendations.append("Implement ReentrancyGuard or checks-effects-interactions pattern")
        elif vuln["type"] == "unchecked_return":
            recommendations.append("Add require() statements to check return values")
        elif vuln["type"] == "integer_overflow":
            recommendations.append("Use SafeMath library for arithmetic operations")
        elif vuln["type"] == "tx_origin":
            recommendations.append("Replace tx.origin with msg.sender")
    return recommendations
