from extensions import db
from datetime import datetime

class Network(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    chain_id = db.Column(db.Integer, unique=True)
    is_testnet = db.Column(db.Boolean, default=False)
    rpc_url = db.Column(db.String(255), nullable=False)
    explorer_url = db.Column(db.String(255), nullable=False)
    currency_symbol = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    contracts = db.relationship('Contract', backref='network', lazy=True)
    wallet_checks = db.relationship('WalletCheck', backref='network', lazy=True)
    
    def __repr__(self):
        return f'<Network {self.name}>'
    
    @property
    def config(self):
        """Get network configuration"""
        from app import NETWORK_CONFIGS
        return NETWORK_CONFIGS.get(self.chain_id, {})

class Contract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), nullable=False)
    source_code = db.Column(db.Text, nullable=False)
    network_id = db.Column(db.Integer, db.ForeignKey('network.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    scan_results = db.relationship('ScanResult', backref='contract', lazy=True)

class ScanResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey('contract.id'))
    vulnerabilities = db.Column(db.JSON)
    risk_score = db.Column(db.Float)
    scan_date = db.Column(db.DateTime, default=datetime.utcnow)

class WalletCheck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(42), nullable=False)
    network_id = db.Column(db.Integer, db.ForeignKey('network.id'), nullable=False)
    risk_score = db.Column(db.Float)
    flags = db.Column(db.JSON)
    check_date = db.Column(db.DateTime, default=datetime.utcnow)
