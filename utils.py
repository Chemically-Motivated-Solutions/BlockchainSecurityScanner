from typing import Dict, Set
import json

ALLOWED_EXTENSIONS = {'sol', 'txt'}

def allowed_file(filename: str) -> bool:
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_report(scan_result) -> Dict:
    vulnerabilities = scan_result.vulnerabilities
    
    # Calculate severity statistics
    severity_counts = {
        "high": 0,
        "medium": 0,
        "low": 0
    }
    
    for vuln in vulnerabilities:
        severity_counts[vuln['severity']] += 1
        
    # Generate summary
    summary = {
        "total_vulnerabilities": len(vulnerabilities),
        "risk_score": scan_result.risk_score,
        "severity_breakdown": severity_counts,
        "critical_findings": [v for v in vulnerabilities if v['severity'] == 'high']
    }
    
    return {
        "summary": summary,
        "details": vulnerabilities,
        "timestamp": scan_result.scan_date.isoformat()
    }

def format_vulnerability(vuln: Dict) -> str:
    return f"{vuln['type']} ({vuln['severity']}): {vuln['description']}"
