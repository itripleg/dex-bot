# bot/core.py - Complete updated __init__ method with wallet address
#!/usr/bin/env python3
"""
Core bot orchestration with shared token management optimization
Updated to pass wallet address to webhook manager
"""

import time
import random
from datetime import datetime
from web3 import Web3
from eth_account import Account

from bot.config import get_private_key, merge_config_with_defaults, print_config_summary
from bot.cache import TokenCache  # Keep for backwards compatibility if needed
from bot.trader import TokenTrader
from bot.webhook import WebhookManager
from bot.logger import BotLogger
from contracts.factory import FactoryContract
from contracts.token import TokenContract
from shared.token_manager import OptimizedTokenLoader

class TransparentVolumeBot:
    """
    Main bot orchestration class with optimized shared token management
    """
    
    def __init__(self, config, private_key_override=None, force_cache_refresh=False, verbose=False):
        """Initialize the bot with modular components"""
        # Store configuration
        self.config = merge_config_with_defaults(config)
        self.verbose = verbose
        
        # Bot identity
        self.bot_name = self.config['name']
        self.display_name = self.config['displayName']
        
        # Initialize bot-specific logger
        self.logger = BotLogger(self.bot_name, self.display_name)
        self.logger.info("🚀 Initializing Transparent Volume Bot...")
        
        print_config_summary(self.config)
        
        # Initialize Web3 and account FIRST (we need the wallet address)
        self._setup_web3_and_account(private_key_override)
        
        # Initialize contract interfaces
        self._setup_contracts()
        
        # Initialize OPTIMIZED token loading system
        self._setup_optimized_token_loader(force_cache_refresh)
        
        # Session tracking
        self.session_start_time = datetime.utcnow().isoformat() + "Z"
        self.starting_balance = self.get_avax_balance()
        
        # Initialize webhook manager with balance callback, bio, AND WALLET ADDRESS
        self.webhook = WebhookManager(
            bot_name=self.bot_name,
            display_name=self.display_name,
            avatar_url=self.config.get('avatarUrl', ''),
            webhook_url=self.config.get('webhookUrl'),
            bot_secret=self.config.get('botSecret'),
            phrases=self._extract_personality_phrases(),
            bio=self.config.get('bio'),
            get_balance_callback=self.get_avax_balance,
            wallet_address=self.account.address  # PASS WALLET ADDRESS HERE
        )
        
        # Set session start in webhook manager
        self.webhook.set_session_start(self.starting_balance, self.session_start_time)
        
        # Initialize trader with webhook manager
        self.trader = TokenTrader(
            w3=self.w3,
            account=self.account,
            factory_contract=self.factory_contract.contract,
            config=self.config,
            webhook_manager=self.webhook,
            verbose=self.verbose,
            logger=self.logger
        )
        
        # Bot state
        self.tokens = []
        
        # Load tokens using optimized system
        self._load_tokens()
        
        # Send startup notification (now includes wallet address automatically)
        self._send_startup_notification()
        
        print(f"🤖 TVB: ✅ Bot '{self.display_name}' initialized successfully!")
        print(f"🤖 TVB: 💼 Wallet Address: {self.account.address}")
        print(f"🤖 TVB: 💰 Starting session with {self.starting_balance:.6f} AVAX")
    
    def _setup_web3_and_account(self, private_key_override):
        """Initialize Web3 connection and account with auto key generation support"""
        self.logger.info("🌐 Setting up Web3 connection...")
        
        self.rpc_url = self.config['rpcUrl']
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to RPC: {self.rpc_url}")
        
        # Setup account - pass bot name for environment lookup
        private_key = get_private_key(self.config, private_key_override, self.bot_name)
        
        self.account = Account.from_key(private_key)
        
        # Log wallet address prominently
        print(f"🤖 TVB: 💼 Bot Wallet Address: {self.account.address}")
        
        # If the balance is 0 and we just generated a key, show funding instructions
        current_balance = self.get_avax_balance()
        if current_balance == 0:
            print("\n🤖 TVB: ⚠️  WALLET NEEDS FUNDING!")
            print("🤖 TVB: " + "="*60)
            print(f"🤖 TVB: 📍 Send AVAX to: {self.account.address}")
            print("🤖 TVB: 🏦 Recommended minimum: 0.1 AVAX for testing")
            print("🤖 TVB: 🌐 Avalanche Fuji Testnet Faucet:")
            print("🤖 TVB:    https://faucet.avax.network/")
            print("🤖 TVB: " + "="*60)
            print("🤖 TVB: ⏳ The bot will continue but cannot trade without AVAX\n")
        
        self.logger.success(f"Account: {self.account.address}")
        self.logger.info(f"Balance: {current_balance:.6f} AVAX")
    
    def _setup_contracts(self):
        """Initialize contract interfaces"""
        self.logger.info("📜 Setting up contract interfaces...")
        
        self.factory_contract = FactoryContract(
            w3=self.w3,
            address=self.config['factoryAddress']
        )
        
        self.token_contract = TokenContract(w3=self.w3)
    
    def _setup_optimized_token_loader(self, force_refresh):
        """Initialize OPTIMIZED token loading system using shared manager"""
        self.logger.info("🚀 Setting up optimized token loading (shared manager)...")
        
        # Use optimized loader instead of old cache system
        self.token_loader = OptimizedTokenLoader(
            bot_name=self.bot_name,
            factory_contract=self.factory_contract.contract,
            token_abi=self.token_contract.abi,
            w3=self.w3,
            logger=self.logger
        )
        
        if force_refresh:
            self.logger.info("🔄 Forced refresh requested")
            self.token_loader.force_refresh()
    
    def _extract_personality_phrases(self):
        """Extract personality phrases from config"""
        return {
            "buy": self.config.get("buyPhrases", []),
            "sell": self.config.get("sellPhrases", []),
            "create_token": self.config.get("createPhrases", []),
            "error": self.config.get("errorPhrases", [])
        }
    
    def _load_tokens(self):
        """Load tradeable tokens using OPTIMIZED shared system"""
        self.logger.info("🔍 Loading tradeable tokens via shared manager...")
        self.tokens = self.token_loader.load_tokens_optimized()
        self.logger.success(f"Loaded {len(self.tokens)} tradeable tokens")
    
    def _send_startup_notification(self):
        """Send enhanced startup notification with session balance and wallet address"""
        startup_info = {
            "message": f"{self.display_name} is now online and ready to trade!",
            "sessionStarted": self.session_start_time,
            "tokensFound": len(self.tokens),
            "walletAddress": self.account.address,  # Include wallet address in startup
            "config": {
                "buyBias": self.config.get('buyBias', 0.6),
                "riskTolerance": self.config.get('riskTolerance', 0.5),
                "minTradeAmount": self.config.get('minTradeAmount', 0.005),
                "maxTradeAmount": self.config.get('maxTradeAmount', 0.02),
                "tradingRange": f"{self.config.get('minTradeAmount', 0.005):.4f}-{self.config.get('maxTradeAmount', 0.02):.4f} AVAX",
                "intervalRange": f"{self.config.get('minInterval', 15)}-{self.config.get('maxInterval', 60)}s"
            },
            "character": {
                "mood": self._determine_bot_mood(),
                "personality": self.config.get('name', '').replace('_', ' ').title()
            }
        }
        
        self.webhook.send_startup_notification(startup_info)
    
    def _determine_bot_mood(self):
        """Determine bot mood based on config personality"""
        buy_bias = self.config.get('buyBias', 0.6)
        risk_tolerance = self.config.get('riskTolerance', 0.5)
        
        if buy_bias > 0.7:
            return "bullish"
        elif risk_tolerance > 0.8:
            return "aggressive"
        elif buy_bias < 0.3:
            return "bearish"
        elif risk_tolerance < 0.3:
            return "cautious"
        else:
            return "neutral"
    
    def get_avax_balance(self):
        """Get current AVAX balance"""
        balance_wei = self.w3.eth.get_balance(self.account.address)
        return float(self.w3.from_wei(balance_wei, 'ether'))
    
    def get_session_metrics(self):
        """Get comprehensive session financial metrics"""
        return self.webhook.get_session_summary()
    
    def refresh_tokens(self):
        """Refresh token list using optimized shared system"""
        self.logger.info("🔄 Refreshing token list via shared manager...")
        self.tokens = self.token_loader.load_tokens_optimized()
        self.logger.success(f"Refreshed: {len(self.tokens)} tradeable tokens")
    
    def force_cache_refresh(self):
        """Force a complete refresh via shared manager"""
        self.token_loader.force_refresh()
        self.refresh_tokens()
    
    def get_cache_stats(self):
        """Get shared manager statistics"""
        return self.token_loader.get_stats()
    
    def execute_trade_cycle(self):
        """Execute one complete trading cycle with minimal webhook noise"""
        if self.verbose:
            print(f"\n🤖 TVB: --- Starting Trade Cycle ---")
        
        # Check if we should create a token
        create_chance = self.config.get('createTokenChance', 0.02)
        if random.random() < create_chance:
            self._attempt_token_creation()
            return
        
        # Check if we have tokens to trade
        if not self.tokens:
            self.logger.warning("⏭️ No tradeable tokens, refreshing list...")
            self.refresh_tokens()
            if not self.tokens:
                self.logger.warning("⏭️ Still no tokens found, waiting...")
                return
        
        # Select random token and execute trade
        token = random.choice(self.tokens)
        
        if self.verbose:
            self.logger.info(f"🎯 Selected token: {token['symbol']} ({token['address'][:10]}...)")
        
        success = self.trader.execute_trade_decision(token)
        
        if success and self.verbose:
            self.logger.success(f"Trade cycle completed for {token['symbol']}")
    
    def _attempt_token_creation(self):
        """Attempt to create a new token with personality-driven concept"""
        self.logger.info("🎨 Considering token creation...")
        
        # Use trader's token creation functionality
        success = self.trader.attempt_token_creation()
        
        if success:
            # Refresh token list to include the new token
            self.logger.info("🔄 Refreshing token list to include new creation...")
            self.refresh_tokens()
        
        return success
    
    def send_heartbeat(self):
        """Send periodic heartbeat update with session metrics"""
        shared_stats = self.get_cache_stats()
        
        # Check for low balance alert (but don't spam)
        current_balance = self.get_avax_balance()
        min_trade_amount = self.config.get('minTradeAmount', 0.005)
        if current_balance < min_trade_amount * 2:
            self.webhook.send_balance_alert(
                balance=current_balance,
                threshold=min_trade_amount * 2,
                alert_type="low"
            )
        
        # Send enhanced heartbeat with session metrics
        self.webhook.send_heartbeat(
            balance_info={}, # Not needed anymore, webhook calculates it
            token_count=len(self.tokens),
            extra_data={
                "minTradeAmount": min_trade_amount,
                "walletAddress": self.account.address,  # Include wallet address
                "sharedManagerStats": {
                    "total_tokens": shared_stats.get("total_tokens", 0),
                    "registered_bots": shared_stats.get("registered_bots", 0),
                    "factory_queries_saved": shared_stats.get("factory_queries_saved", 0),
                    "next_refresh_minutes": shared_stats.get("next_refresh_in_minutes", 0)
                }
            }
        )
    
    def print_session_summary(self):
        """Print comprehensive session summary with wallet address"""
        print(f"\n🤖 TVB: 📊 {self.display_name} Session Summary:")
        print(f"  👤 Account: {self.account.address}")
        
        # Get session metrics from webhook manager (includes wallet address)
        self.webhook.print_session_summary()
        
        # Additional bot-specific info
        print(f"  🎯 Tokens Tracked: {len(self.tokens)}")
        
        # Show shared manager stats
        shared_stats = self.get_cache_stats()
        print(f"  🌐 Shared Manager:")
        print(f"    🤖 Total bots: {shared_stats.get('registered_bots', 0)}")
        print(f"    🚀 Queries saved: {shared_stats.get('factory_queries_saved', 0)}")
        print(f"    ⏰ Next refresh: {shared_stats.get('next_refresh_in_minutes', 0):.1f}min")
    
# Enhanced bot core with better heartbeat management
    def run(self):
        """Enhanced main trading loop with better heartbeat management"""
        try:
            self.logger.info("🚀 Starting enhanced trading loop with improved heartbeat...")
            
            cycle_count = 0
            last_heartbeat = 0
            last_keepalive = 0
            heartbeat_interval = 120  # 2 minutes
            keepalive_interval = 60   # 1 minute
            
            # Send initial heartbeat
            self.send_heartbeat()
            last_heartbeat = time.time()
            
            while True:
                cycle_count += 1
                current_time = time.time()
                
                try:
                    if self.verbose:
                        self.logger.cycle(cycle_count, "Starting trade cycle")
                    
                    # Execute trading logic
                    self.execute_trade_cycle()
                    
                    # Send heartbeat every 2 minutes
                    if current_time - last_heartbeat >= heartbeat_interval:
                        success = self.send_heartbeat()
                        if success:
                            last_heartbeat = current_time
                        else:
                            # If heartbeat fails, try again sooner
                            self.logger.warning("Heartbeat failed, will retry sooner")
                    
                    # Send keepalive every minute if no recent heartbeat
                    elif current_time - last_keepalive >= keepalive_interval:
                        if hasattr(self.webhook, 'send_keepalive'):
                            self.webhook.send_keepalive()
                            last_keepalive = current_time
                    
                    # Calculate sleep time based on personality
                    min_interval = self.config.get('minInterval', 15)
                    max_interval = self.config.get('maxInterval', 60)
                    sleep_time = random.uniform(min_interval, max_interval)
                    
                    if self.verbose:
                        self.logger.info(f"💤 Cycle {cycle_count} complete, sleeping {sleep_time:.1f}s")
                    
                    time.sleep(sleep_time)
                    
                except KeyboardInterrupt:
                    self._handle_shutdown(cycle_count, "user")
                    break
                except Exception as e:
                    self.logger.error(f"Trade cycle error: {e}")
                    
                    # Send error webhook
                    if self.webhook:
                        self.webhook.send_error_update(str(e), "trade_cycle_error")
                    
                    # Force heartbeat after error to maintain connection
                    if hasattr(self.webhook, 'force_heartbeat'):
                        self.webhook.force_heartbeat()
                    
                    # Sleep a bit before retrying
                    time.sleep(10)
                    
        except KeyboardInterrupt:
            self._handle_shutdown(cycle_count, "user")
        except Exception as e:
            self._handle_shutdown(cycle_count, "crash", str(e))
        
        self.logger.info("👋 Bot trading loop ended")

    
    def _handle_shutdown(self, cycle_count, reason, error_msg=None):
        """Handle bot shutdown gracefully with enhanced reporting"""
        session_metrics = self.get_session_metrics()
        
        shutdown_info = {
            "totalCycles": cycle_count,
            "sessionMetrics": session_metrics,
            "walletAddress": self.account.address  # Include wallet address in shutdown
        }
        
        if reason == "user":
            print(f"\n🤖 TVB: 🛑 Bot stopped by user")
            shutdown_info.update({
                "message": f"{self.display_name} is going offline (user requested)",
                "reason": "User initiated shutdown"
            })
        elif reason == "crash":
            print(f"\n🤖 TVB: 💥 Bot crashed: {error_msg}")
            shutdown_info.update({
                "message": f"Bot crashed: {error_msg}",
                "reason": "System error",
                "error": error_msg
            })
        
        self.webhook.send_shutdown_notification(shutdown_info)
        
        # Cleanup shared resources
        self.token_loader.cleanup()
        
        # Print final stats
        if self.verbose:
            self.print_session_summary()
            print(f"🤖 TVB: 🔄 Total Cycles: {cycle_count}")
            
            # Print shared manager stats
            shared_stats = self.get_cache_stats()
            print(f"\n🤖 TVB: 🌐 Shared Manager Final Stats:")
            print(f"  🚀 Factory queries saved: {shared_stats.get('factory_queries_saved', 0)}")
            print(f"  🤖 Bots served: {shared_stats.get('registered_bots', 0)}")


# Example usage for testing
if __name__ == "__main__":
    # Test bot initialization (won't actually run without config)
    print("🤖 TVB: Optimized core bot class loaded successfully!")
    print("Use main.py to run the bot with proper configuration.")