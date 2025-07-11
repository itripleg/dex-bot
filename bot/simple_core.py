#!/usr/bin/env python3
"""
SIMPLIFIED Bot Core - Clean integration of all components
Removes complexity and ensures consistent behavior
"""

import time
import random
import threading
from datetime import datetime
from web3 import Web3
from eth_account import Account

class SimpleTVBBot:
    """Simplified TVB Bot with clean, consistent behavior"""
    
    # Color codes for different bots
    BOT_COLORS = {
        'bullish_billy': '\033[94m',      # Blue
        'companion_cube': '\033[92m',     # Green  
        'jackpot_jax': '\033[93m',        # Yellow
        'melancholy_mort': '\033[95m',    # Purple
        'default': '\033[96m'             # Cyan
    }
    RESET_COLOR = '\033[0m'
    BOLD = '\033[1m'
    
    def __init__(self, config, private_key_override=None):
        self.config = config
        self.bot_name = config['name']
        self.display_name = config['displayName']
        
        # Set color for this bot
        self.color = self.BOT_COLORS.get(self.bot_name, self.BOT_COLORS['default'])
        
        self.log(f"🤖 Initializing {self.display_name}...")
        
        # Initialize Web3 and account
        self._setup_web3_and_account(private_key_override)
        
        # Initialize contracts
        self._setup_contracts()
        
        # Initialize webhook
        self._setup_webhook()
        
        # Initialize trader
        self._setup_trader()
        
        # Bot state
        self.tokens = []
        self.is_running = False
        self.cycle_count = 0
        self.last_heartbeat = 0
        self.heartbeat_interval = 90  # seconds
        
        # Load tokens
        self._load_tokens()
        
        # Send startup notification
        self._send_startup()
        
        self.log(f"✅ {self.display_name} initialized successfully!")
        self.log(f"💼 Wallet: {self.account.address}")
        self.log(f"💰 Balance: {self.get_avax_balance():.6f} AVAX")
        self.log(f"🎯 Tokens: {len(self.tokens)}")
    
    def log(self, message: str):
        """Log message with bot-specific color coding"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        colored_prefix = f"{self.color}{self.BOLD}[{timestamp}] {self.display_name}{self.RESET_COLOR}"
        print(f"{colored_prefix}: {message}")
    
    def _setup_web3_and_account(self, private_key_override):
        """Setup Web3 connection and account"""
        self.log(f"🌐 Connecting to network...")
        
        self.rpc_url = self.config['rpcUrl']
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to RPC: {self.rpc_url}")
        
        # Get private key
        if private_key_override:
            private_key = private_key_override
        else:
            private_key = self.config.get('privateKey')
            if not private_key or private_key == "SET_IN_ENV_LOCAL":
                # Auto-generate key if none provided
                account = Account.create()
                private_key = account.key.hex()
                self.log(f"🔑 Auto-generated wallet: {account.address}")
                self.log(f"🔐 Private key: {private_key}")
                self.log("⚠️  Fund this wallet with AVAX to start trading!")
        
        if not private_key.startswith('0x'):
            private_key = f"0x{private_key}"
        
        self.account = Account.from_key(private_key)
        self.log(f"💼 Wallet loaded: {self.account.address}")
    
    def _setup_contracts(self):
        """Setup contract interfaces"""
        self.log(f"📜 Setting up contracts...")
        
        factory_address = self.config['factoryAddress']
        
        # Factory ABI (simplified - only what we need)
        factory_abi = [
            {
                "inputs": [],
                "name": "getAllTokens",
                "outputs": [{"internalType": "address[]", "name": "", "type": "address[]"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [{"internalType": "address", "name": "tokenAddress", "type": "address"}],
                "name": "getTokenState",
                "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "address", "name": "tokenAddress", "type": "address"},
                    {"internalType": "uint256", "name": "minTokensOut", "type": "uint256"}
                ],
                "name": "buy",
                "outputs": [],
                "stateMutability": "payable",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "address", "name": "tokenAddress", "type": "address"},
                    {"internalType": "uint256", "name": "tokenAmount", "type": "uint256"},
                    {"internalType": "uint256", "name": "minEthOut", "type": "uint256"}
                ],
                "name": "sell",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
        
        self.factory_contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(factory_address),
            abi=factory_abi
        )
        
        # Token ABI (simplified)
        self.token_abi = [
            {
                "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "name",
                "outputs": [{"internalType": "string", "name": "", "type": "string"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "symbol",
                "outputs": [{"internalType": "string", "name": "", "type": "string"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
        
        self.log(f"📜 Factory: {factory_address}")
    
    def _setup_webhook(self):
        """Setup webhook manager"""
        # Import the simplified webhook manager
        try:
            from bot.simple_webhook import SimpleWebhookManager
        except ImportError:
            # Fallback - create a dummy webhook manager
            class DummyWebhook:
                def __init__(self, *args, **kwargs):
                    self.enabled = False
                def __getattr__(self, name):
                    return lambda *args, **kwargs: False
            
            print("⚠️  Webhook manager not found, using dummy")
            self.webhook = DummyWebhook()
            return
        
        webhook_url = self.config.get('webhookUrl')
        bot_secret = self.config.get('botSecret', 'dev')
        
        if webhook_url and webhook_url != "SET_IN_ENV_LOCAL":
            self.webhook = SimpleWebhookManager(
                bot_name=self.bot_name,
                display_name=self.display_name,
                avatar_url=self.config.get('avatarUrl', ''),
                webhook_url=webhook_url,
                bot_secret=bot_secret,
                bio=self.config.get('bio'),
                wallet_address=self.account.address
            )
        else:
            self.log("⚠️  No webhook URL configured")
            self.webhook = DummyWebhook()
    
    def _setup_trader(self):
        """Setup trader"""
        try:
            from bot.simple_trader import SimpleTrader
        except ImportError:
            # Fallback - create a dummy trader
            class DummyTrader:
                def execute_trade_decision(self, token):
                    self.log(f"📊 Would trade {token['symbol']} (dummy mode)")
                    return True
                def attempt_token_creation(self):
                    return False
            
            self.log("⚠️  Trader not found, using dummy")
            self.trader = DummyTrader()
            return
        
        self.trader = SimpleTrader(
            w3=self.w3,
            account=self.account,
            factory_contract=self.factory_contract,
            config=self.config,
            webhook_manager=self.webhook,
            bot_logger=self  # Pass self for colored logging
        )
    
    def _load_tokens(self):
        """Load tradeable tokens using shared loader"""
        self.log(f"🔍 Loading tokens via shared loader...")
        
        try:
            # Import and use the shared token loader
            from shared.simple_token_loader import get_shared_tokens
            
            self.tokens = get_shared_tokens(
                bot_name=self.display_name,
                factory_contract=self.factory_contract,
                token_abi=self.token_abi,
                w3=self.w3
            )
            
            self.log(f"✅ Loaded {len(self.tokens)} tradeable tokens")
            
        except ImportError:
            # Fallback to individual loading if shared loader not available
            self.log("⚠️  Shared loader not found, loading individually...")
            self._load_tokens_individually()
        except Exception as e:
            self.log(f"❌ Error with shared loader: {e}")
            self._load_tokens_individually()
    
    def _load_tokens_individually(self):
        """Fallback method to load tokens individually"""
        try:
            # Get all token addresses
            token_addresses = self.factory_contract.functions.getAllTokens().call()
            self.log(f"📡 Found {len(token_addresses)} total tokens")
            
            tradeable_tokens = []
            
            for i, address in enumerate(token_addresses, 1):
                try:
                    # Check if token is tradeable
                    state = self.factory_contract.functions.getTokenState(address).call()
                    
                    if state in [1, 4]:  # TRADING or RESUMED
                        # Get token info
                        token_contract = self.w3.eth.contract(
                            address=self.w3.to_checksum_address(address),
                            abi=self.token_abi
                        )
                        
                        name = token_contract.functions.name().call()
                        symbol = token_contract.functions.symbol().call()
                        
                        tradeable_tokens.append({
                            "address": address,
                            "name": name,
                            "symbol": symbol
                        })
                        
                        self.log(f"✅ {symbol} ({name}) [{i}/{len(token_addresses)}]")
                    else:
                        self.log(f"⏭️  Token {i} not tradeable (state: {state})")
                        
                except Exception as e:
                    self.log(f"❌ Error processing token {i}: {e}")
            
            self.tokens = tradeable_tokens
            self.log(f"✅ Loaded {len(self.tokens)} tradeable tokens")
            
        except Exception as e:
            self.log(f"❌ Error loading tokens individually: {e}")
            self.tokens = []
    
    def _send_startup(self):
        """Send startup notification"""
        if self.webhook.enabled:
            starting_balance = self.get_avax_balance()
            self.webhook.set_session_start(starting_balance)
            
            config_summary = {
                "buyBias": self.config.get('buyBias', 0.6),
                "riskTolerance": self.config.get('riskTolerance', 0.5),
                "minTradeAmount": self.config.get('minTradeAmount', 0.005),
                "maxTradeAmount": self.config.get('maxTradeAmount', 0.02),
                "createTokenChance": self.config.get('createTokenChance', 0.02)
            }
            
            self.webhook.send_startup(starting_balance, len(self.tokens), config_summary)
    
    def get_avax_balance(self) -> float:
        """Get current AVAX balance"""
        try:
            balance_wei = self.w3.eth.get_balance(self.account.address)
            return float(self.w3.from_wei(balance_wei, 'ether'))
        except Exception as e:
            print(f"❌ Error getting AVAX balance: {e}")
            return 0.0
    
    def execute_trade_cycle(self) -> bool:
        """Execute one trade cycle"""
        try:
            self.cycle_count += 1
            self.log(f"🔄 Cycle #{self.cycle_count}")
            
            # Check if we should create a token
            create_chance = self.config.get('createTokenChance', 0.02)
            if random.random() < create_chance:
                return self.trader.attempt_token_creation()
            
            # Check if we have tokens to trade
            if not self.tokens:
                self.log("⚠️  No tokens available, reloading via shared loader...")
                self._load_tokens()
                if not self.tokens:
                    self.log("❌ Still no tokens found")
                    return False
            
            # Select random token and trade
            token = random.choice(self.tokens)
            self.log(f"🎯 Selected: {token['symbol']}")
            
            return self.trader.execute_trade_decision(token)
            
        except Exception as e:
            error_msg = f"Trade cycle error: {e}"
            self.log(f"❌ {error_msg}")
            if self.webhook.enabled:
                self.webhook.send_error(error_msg, "trade_cycle")
            return False
    
    def send_heartbeat_if_needed(self):
        """Send heartbeat if enough time has passed"""
        current_time = time.time()
        
        if current_time - self.last_heartbeat >= self.heartbeat_interval:
            if self.webhook.enabled:
                current_balance = self.get_avax_balance()
                self.webhook.send_heartbeat(current_balance, len(self.tokens))
            
            self.last_heartbeat = current_time
    
    def run(self):
        """Main trading loop"""
        try:
            self.is_running = True
            self.log(f"🚀 Starting {self.display_name} trading loop...")
            
            while self.is_running:
                # Send heartbeat if needed
                self.send_heartbeat_if_needed()
                
                # Execute trade cycle
                self.execute_trade_cycle()
                
                # Calculate sleep time
                min_interval = self.config.get('minInterval', 15)
                max_interval = self.config.get('maxInterval', 60)
                sleep_time = random.uniform(min_interval, max_interval)
                
                self.log(f"💤 Sleeping {sleep_time:.1f}s...")
                time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            self.log(f"🛑 {self.display_name} stopped by user")
            self._shutdown("user_stop")
        except Exception as e:
            self.log(f"💥 {self.display_name} crashed: {e}")
            self._shutdown("crash")
        finally:
            self.is_running = False
    
    def _shutdown(self, reason: str):
        """Handle bot shutdown"""
        current_balance = self.get_avax_balance()
        
        if self.webhook.enabled:
            # Send both shutdown and offline notifications
            self.webhook.send_shutdown(self.cycle_count, current_balance, reason)
            self.webhook.send_offline(self.cycle_count, current_balance, reason)
        
        self.log(f"👋 {self.display_name} shutdown complete")
        self.log(f"🔄 Total cycles: {self.cycle_count}")
        self.log(f"💰 Final balance: {current_balance:.6f} AVAX")
        
        if self.webhook.enabled:
            self.webhook.print_stats()


# Example usage
if __name__ == "__main__":
    # Test configuration
    test_config = {
        "name": "test_bot",
        "displayName": "Test Bot",
        "bio": "A test bot for development",
        "avatarUrl": "/test.png",
        "rpcUrl": "https://avax-fuji.g.alchemy.com/v2/YOUR_API_KEY",
        "factoryAddress": "0x20BC84B00406cd0cc6B467569553E5f46A990f3C",
        "webhookUrl": "http://localhost:3000/api/tvb/webhook",
        "botSecret": "dev",
        "buyBias": 0.6,
        "riskTolerance": 0.5,
        "minInterval": 5,
        "maxInterval": 15,
        "minTradeAmount": 0.005,
        "maxTradeAmount": 0.02,
        "createTokenChance": 0.01
    }
    
    print("🤖 Testing Simplified TVB Bot...")
    
    try:
        bot = SimpleTVBBot(test_config)
        print("✅ Bot initialization test passed!")
        print("🤖 Use bot.run() to start trading")
    except Exception as e:
        print(f"❌ Bot test failed: {e}")