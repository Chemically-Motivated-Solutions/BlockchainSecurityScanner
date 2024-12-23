import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
from flask import Flask, render_template, request, redirect, url_for, flash
import web3
from web3 import Web3
from extensions import db
from flask_migrate import Migrate
from mock_notifications import security_events

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blockchain_security.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit

# Network configurations with fallback RPC providers
NETWORK_CONFIGS = {
    1: {  # Ethereum Mainnet
        'rpc_urls': [
            'https://eth.drpc.org',
            'https://ethereum.publicnode.com',
            'https://cloudflare-eth.com',
            'https://eth-mainnet.public.blastapi.io'
        ],
        'explorer_url': 'https://etherscan.io',
        'currency_symbol': 'ETH',
        'timeout': 10,
        'retry_count': 3
    },
    5: {  # Goerli Testnet
        'rpc_urls': [
            'https://goerli.infura.io/v3/YOUR-PROJECT-ID',
            'https://ethereum-goerli.publicnode.com',
            'https://goerli.gateway.tenderly.co'
        ],
        'explorer_url': 'https://goerli.etherscan.io',
        'currency_symbol': 'gETH',
        'timeout': 10,
        'retry_count': 3
    },
    56: {  # BSC Mainnet
        'rpc_urls': [
            'https://bsc-dataseed.binance.org',
            'https://bsc-dataseed1.defibit.io',
            'https://bsc-dataseed1.ninicoin.io',
            'https://bsc.publicnode.com'
        ],
        'explorer_url': 'https://bscscan.com',
        'currency_symbol': 'BNB',
        'timeout': 10,
        'retry_count': 3
    },
    97: {  # BSC Testnet
        'rpc_urls': [
            'https://data-seed-prebsc-1-s1.binance.org:8545',
            'https://data-seed-prebsc-2-s1.binance.org:8545',
            'https://bsc-testnet.publicnode.com'
        ],
        'explorer_url': 'https://testnet.bscscan.com',
        'currency_symbol': 'tBNB',
        'timeout': 10,
        'retry_count': 3
    },
    137: {  # Polygon Mainnet
        'rpc_urls': [
            'https://polygon-rpc.com',
            'https://polygon.drpc.org',
            'https://polygon-bor.publicnode.com',
            'https://polygon.gateway.tenderly.co'
        ],
        'explorer_url': 'https://polygonscan.com',
        'currency_symbol': 'MATIC',
        'timeout': 10,
        'retry_count': 3
    },
    80001: {  # Mumbai Testnet
        'rpc_urls': [
            'https://rpc-mumbai.maticvigil.com',
            'https://polygon-mumbai.gateway.tenderly.co',
            'https://polygon-mumbai.blockpi.network/v1/rpc/public'
        ],
        'explorer_url': 'https://mumbai.polygonscan.com',
        'currency_symbol': 'tMATIC',
        'timeout': 10,
        'retry_count': 3
    }
}

# Initialize Web3 providers dictionary
web3_providers = {}

def get_web3_provider(network_id: int, force_new: bool = False) -> tuple[Web3, bool]:
    """Get or create Web3 provider for specific network and check its status with fallback support"""
    if network_id not in NETWORK_CONFIGS:
        raise ValueError(f"Unsupported network ID: {network_id}")
    
    config = NETWORK_CONFIGS[network_id]
    timeout = config.get('timeout', 10)
    retry_count = config.get('retry_count', 3)
    
    # Add network-specific middlewares
    def add_network_middlewares(w3: Web3):
        if network_id in [1, 5]:  # Ethereum networks
            w3.middleware_onion.inject(web3.middleware.geth_poa_middleware, layer=0)
        elif network_id in [56, 97]:  # BSC networks
            w3.middleware_onion.inject(web3.middleware.validation_middleware)
        elif network_id in [137, 80001]:  # Polygon networks
            w3.middleware_onion.inject(web3.middleware.geth_poa_middleware, layer=0)
            w3.middleware_onion.inject(web3.middleware.validation_middleware)
    
    # Return cached provider if available and working
    if not force_new and network_id in web3_providers:
        provider = web3_providers[network_id]
        try:
            if provider.is_connected():
                return provider, True
        except Exception:
            del web3_providers[network_id]
    
    # Try each RPC URL with retry logic and connection validation
    last_error = None
    for rpc_url in config['rpc_urls']:
        for attempt in range(retry_count):
            try:
                provider = Web3(Web3.HTTPProvider(
                    rpc_url,
                    request_kwargs={
                        'timeout': timeout,
                        'headers': {
                            'User-Agent': 'BlockchainSecurityScanner/1.0'
                        }
                    }
                ))
                
                # Basic connection test
                if not provider.is_connected():
                    raise ConnectionError("Basic connection test failed")
                
                # Additional health checks
                try:
                    # Test block retrieval
                    latest_block = provider.eth.get_block('latest')
                    if latest_block is None:
                        raise ConnectionError("Failed to retrieve latest block")
                        
                    # Verify chain ID
                    chain_id = provider.eth.chain_id
                    if chain_id != network_id:
                        raise ConnectionError(f"Chain ID mismatch. Expected {network_id}, got {chain_id}")
                except Exception as e:
                    logger.warning(f"Health check failed for {rpc_url}: {str(e)}")
                    raise ConnectionError(f"Health check failed: {str(e)}")
                
                # Verify connection
                if not provider.is_connected():
                    raise ConnectionError("Provider not connected")
                
                # Test basic API call
                _ = provider.eth.block_number
                
                # Check sync status if supported
                try:
                    if provider.eth.syncing:
                        raise ConnectionError("Node is still syncing")
                except Exception:
                    pass  # Skip sync check if not supported
                
                # Add network-specific middlewares
                add_network_middlewares(provider)
                
                # Cache successful provider
                web3_providers[network_id] = provider
                return provider, True
                
            except Exception as e:
                last_error = e
                if attempt < retry_count - 1:
                    import time
                    time.sleep(1 * (attempt + 1))  # Exponential backoff
                continue
            
    # All RPCs failed
    error_msg = f"Failed to connect to network {network_id} after trying all RPCs"
    if last_error:
        error_msg += f": {str(last_error)}"
    raise ConnectionError(error_msg)

def check_network_status(network_id: int) -> dict:
    """Check the status of a specific network with enhanced error reporting and timeout handling"""
    if network_id not in NETWORK_CONFIGS:
        return {
            'status': 'error',
            'message': f'Unsupported network ID: {network_id}',
            'error_type': 'configuration',
            'is_retryable': False
        }
    
    config = NETWORK_CONFIGS.get(network_id, {})
    network_name = config.get('name', f'Network {network_id}')
    
    if not config:
        return {
            'status': 'error',
            'message': 'Network configuration not found',
            'error_type': 'configuration',
            'is_retryable': False,
            'network': network_name
        }
        
    config = NETWORK_CONFIGS[network_id]
    
    try:
        # Try to get provider with fresh connection
        provider, is_active = get_web3_provider(network_id, force_new=True)
        
        if not is_active:
            return {
                'status': 'error',
                'message': 'Network is not responding or not synced',
                'error_type': 'connection',
                'is_retryable': True,
                'network': config.get('name', f'Network {network_id}')
            }
            
        try:
            # Get comprehensive network info with timeout
            block_number = provider.eth.block_number
            gas_price = provider.eth.gas_price
            
            # Get chain ID to verify network
            chain_id = provider.eth.chain_id
            if chain_id != network_id:
                return {
                    'status': 'error',
                    'message': f'Chain ID mismatch. Expected {network_id}, got {chain_id}',
                    'error_type': 'validation',
                    'is_retryable': False,
                    'network': config.get('name', f'Network {network_id}')
                }
            
            status = {
                'status': 'ok',
                'block_number': block_number,
                'gas_price': gas_price,
                'chain_id': chain_id,
                'is_connected': True,
                'currency_symbol': config['currency_symbol'],
                'network': config.get('name', f'Network {network_id}')
            }
            
            # Try to get additional network stats if available
            try:
                status['peer_count'] = provider.net.peer_count
            except Exception:
                pass
                
            return status
            
        except web3.exceptions.TimeoutError as te:
            return {
                'status': 'error',
                'message': 'Network request timed out. Please try again.',
                'error_type': 'timeout',
                'is_retryable': True,
                'network': config.get('name', f'Network {network_id}')
            }
        except web3.exceptions.ConnectionError as ce:
            return {
                'status': 'error',
                'message': 'Failed to connect to the network. Please check your internet connection.',
                'error_type': 'connection',
                'is_retryable': True,
                'network': config.get('name', f'Network {network_id}')
            }
        except web3.exceptions.ContractLogicError as cle:
            return {
                'status': 'error',
                'message': 'Contract interaction failed. Please try again.',
                'error_type': 'contract',
                'is_retryable': True,
                'network': config.get('name', f'Network {network_id}')
            }
            
    except Exception as e:
        error_message = str(e)
        error_type = 'unknown'
        is_retryable = True
        
        if 'timeout' in error_message.lower():
            error_type = 'timeout'
            error_message = 'Network request timed out. Please try again.'
        elif 'connection' in error_message.lower():
            error_type = 'connection'
            error_message = 'Failed to connect to the network. Please check your internet connection.'
        elif 'invalid json' in error_message.lower():
            error_type = 'response'
            error_message = 'Received invalid response from the network.'
        
        return {
            'status': 'error',
            'message': error_message,
            'error_type': error_type,
            'is_retryable': is_retryable,
            'network': config.get('name', f'Network {network_id}')
        }

# Initialize Web3 providers dict (providers will be initialized on demand)
def get_default_web3():
    """Get a default Web3 instance for basic operations like address validation"""
    try:
        return Web3(Web3.HTTPProvider('https://eth.drpc.org'))
    except Exception as e:
        logger.warning(f"Default Web3 initialization error: {str(e)}")
        return Web3()  # Fallback to local instance for basic operations

w3 = get_default_web3()
logger.info("Default Web3 provider initialized for basic operations")

# Import models
from models import Contract, ScanResult, WalletCheck, Network
from security_scanner import analyze_contract, check_wallet_safety
from utils import allowed_file, generate_report

# Initialize database
# Initialize Flask-Migrate
migrate = Migrate(app, db)
db.init_app(app)

# For development, we'll use SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blockchain_security.db'

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/analyze', methods=['GET', 'POST'])
def analyze():
    networks = Network.query.all()
    
    if request.method == 'POST':
        if 'contract' not in request.files:
            flash('No file uploaded', 'error')
            return redirect(request.url)
            
        file = request.files['contract']
        if not file or not isinstance(file.filename, str) or file.filename == '' or not allowed_file(file.filename):
            flash('Invalid file type or no file provided', 'error')
            return redirect(request.url)

        network_id = request.form.get('network_id')
        if not network_id:
            flash('Please select a network', 'error')
            return redirect(request.url)

        # Analyze contract
        source_code = file.read().decode('utf-8')
        scan_result = analyze_contract(source_code, int(network_id))
        
        if 'error' in scan_result:
            flash(scan_result['error'], 'error')
            return redirect(request.url)
            
        # Store results
        contract = Contract(
            name=file.filename,
            source_code=source_code,
            network_id=network_id
        )
        db.session.add(contract)
        db.session.commit()
        
        result = ScanResult()
        result.contract_id = contract.id
        result.vulnerabilities = scan_result['vulnerabilities']
        result.risk_score = scan_result['risk_score']
        db.session.add(result)
        db.session.commit()
        
        return redirect(url_for('results', scan_id=result.id))
        
    return render_template('analyze.html', networks=networks)

@app.route('/results/<int:scan_id>')
def results(scan_id):
    result = ScanResult.query.get_or_404(scan_id)
    report = generate_report(result)
    return render_template('results.html', result=result, report=report)

@app.route('/check_wallet', methods=['POST'])
def check_wallet():
    address = request.form.get('address')
    if not address or not isinstance(address, str):
        return {'error': 'Address is required and must be a string'}, 400
        
    network_id = request.form.get('network_id')
    if not network_id:
        return {'error': 'Network ID is required'}, 400
        
    try:
        if not w3.is_address(address):
            return {'error': 'Invalid wallet address format'}, 400
    except ValueError:
        return {'error': 'Invalid wallet address'}, 400
        
    if not network_id:
        return {'error': 'Please select a network'}, 400
        
    network = Network.query.get(network_id)
    if not network:
        return {'error': 'Invalid network selected'}, 400
        
    safety_result = check_wallet_safety(address, int(network_id))
    
    if address is None:
        return {'error': 'Address is required'}, 400
        
    check = WalletCheck()
    check.address = address
    check.network_id = network_id
    check.risk_score = safety_result['risk_score']
    check.flags = safety_result['flags']
    db.session.add(check)
    db.session.commit()
    

@app.route('/check_network_status/<int:network_id>')
def network_status(network_id):
    """Check and return the status of a specific network"""
    status = check_network_status(network_id)
    return status

@app.route('/trigger_mock_alert/<alert_type>', methods=['POST'])
def trigger_mock_alert(alert_type):
    if alert_type == 'contract':
        event = security_events.generate_contract_event()
    elif alert_type == 'wallet':
        event = security_events.generate_wallet_event()
    elif alert_type == 'transactions':
        event = security_events.generate_failed_transactions()
    else:
        return {'error': 'Invalid alert type'}, 400
        
    return event
    return safety_result

def init_networks():
    """Initialize supported blockchain networks"""
    from models import Network
    
    networks = [
        {
            "name": "Ethereum Mainnet",
            "chain_id": 1,
            "is_testnet": False,
            "rpc_url": NETWORK_CONFIGS[1]['rpc_urls'][0],
            "explorer_url": NETWORK_CONFIGS[1]['explorer_url'],
            "currency_symbol": NETWORK_CONFIGS[1]['currency_symbol']
        },
        {
            "name": "BSC Mainnet",
            "chain_id": 56,
            "is_testnet": False,
            "rpc_url": NETWORK_CONFIGS[56]['rpc_urls'][0],
            "explorer_url": NETWORK_CONFIGS[56]['explorer_url'],
            "currency_symbol": NETWORK_CONFIGS[56]['currency_symbol']
        },
        {
            "name": "Polygon",
            "chain_id": 137,
            "is_testnet": False,
            "rpc_url": NETWORK_CONFIGS[137]['rpc_urls'][0],
            "explorer_url": NETWORK_CONFIGS[137]['explorer_url'],
            "currency_symbol": NETWORK_CONFIGS[137]['currency_symbol']
        },
        {
            "name": "Ethereum Goerli",
            "chain_id": 5,
            "is_testnet": True,
            "rpc_url": NETWORK_CONFIGS[5]['rpc_urls'][0],
            "explorer_url": NETWORK_CONFIGS[5]['explorer_url'],
            "currency_symbol": NETWORK_CONFIGS[5]['currency_symbol']
        },
        {
            "name": "BSC Testnet",
            "chain_id": 97,
            "is_testnet": True,
            "rpc_url": NETWORK_CONFIGS[97]['rpc_urls'][0],
            "explorer_url": NETWORK_CONFIGS[97]['explorer_url'],
            "currency_symbol": NETWORK_CONFIGS[97]['currency_symbol']
        },
        {
            "name": "Mumbai (Polygon Testnet)",
            "chain_id": 80001,
            "is_testnet": True,
            "rpc_url": NETWORK_CONFIGS[80001]['rpc_urls'][0],
            "explorer_url": NETWORK_CONFIGS[80001]['explorer_url'],
            "currency_symbol": NETWORK_CONFIGS[80001]['currency_symbol']
        }
    ]
    
    for network_data in networks:
        network = Network.query.filter_by(chain_id=network_data["chain_id"]).first()
        if not network:
            network = Network(**network_data)
            db.session.add(network)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error initializing networks: {e}")

with app.app_context():
    db.create_all()
    init_networks()