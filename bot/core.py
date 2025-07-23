# bot/core.py - Fixed core bot with improved error handling and stability
#!/usr/bin/env python3
"""
Core bot orchestration with improved error handling and connection stability
Fixed to prevent all bots from stopping due to unhandled exceptions
"""

import time
import random
import traceback
from datetime import datetime
from web3 import Web3
from web3.exceptions import (
    Web3Exception, 
    TimeExhausted, 
    TransactionNotFound, 
    BlockNotFound,
    ContractLogicError,
    Web3RPCError,
    ProviderConnectionError
)
from eth_account import Account
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

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
    Main bot orchestration class with enhanced error handling and stability
    """
    
    def __init__(self, config, private_key_override=None, force_cache_refresh=False, verbose=False):
        """Initialize the bot with modular components and robust error handling"""
        try:
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
            
            # Error tracking
            self.consecutive_errors = 0
            self.max_consecutive_errors = 5
            self.last_successful_action = time.time()
            self.connection_check_interval = 30  # Check connection every 30 seconds
            self.last_connection_check = 0
            
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
            self.is_running = False
            self.shutdown_requested = False
            
            # Load tokens using optimized system
            self._load_tokens()
            
            # Send startup notification (now includes wallet address automatically)
            self._send_startup_notification()
            
            print(f"🤖 TVB: ✅ Bot '{self.display_name}' initialized successfully!")
            print(f"🤖 TVB: 💼 Wallet Address: {self.account.address}")
            print(f"🤖 TVB: 💰 Starting session with {self.starting_balance:.6f} AVAX")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize bot: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def _setup_web3_and_account(self, private_key_override):
        """Initialize Web3 connection and account with auto key generation support"""
        try:
            self.logger.info("🌐 Setting up Web3 connection...")
            
            self.rpc_url = self.config['rpcUrl']
            self.w3 = Web3(Web3.HTTPProvider(self.rpc_url, request_kwargs={'timeout': 30}))
            
            # Test connection with retries
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    if self.w3.is_connected():
                        break
                    else:
                        if attempt == max_retries - 1:
                            raise ConnectionError(f"Failed to connect to RPC after {max_retries} attempts: {self.rpc_url}")
                        time.sleep(2 ** attempt)  # Exponential backoff
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise ConnectionError(f"Failed to connect to RPC: {self.rpc_url}, Error: {e}")
                    time.sleep(2 ** attempt)
            
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
            
        except Exception as e:
            self.logger.error(f"Failed to setup Web3/Account: {e}")
            raise
    
    def _check_connection_health(self):
        """Check if Web3 connection is still healthy"""
        try:
            # Simple connection test
            self.w3.eth.get_block_number()
            return True
        except Exception as e:
            self.logger.warning(f"Connection health check failed: {e}")
            return False
    
    def _reconnect_if_needed(self):
        """Attempt to reconnect if connection is unhealthy"""
        if not self._check_connection_health():
            try:
                self.logger.info("🔄 Attempting to reconnect to RPC...")
                self.w3 = Web3(Web3.HTTPProvider(self.rpc_url, request_kwargs={'timeout': 30}))
                
                if self.w3.is_connected():
                    self.logger.success("🔄 Reconnection successful")
                    return True
                else:
                    self.logger.error("🔄 Reconnection failed")
                    return False
            except Exception as e:
                self.logger.error(f"🔄 Reconnection error: {e}")
                return False
        return True
    
    def _setup_contracts(self):
        """Initialize contract interfaces with error handling"""
        try:
            self.logger.info("📜 Setting up contract interfaces...")
            
            self.factory_contract = FactoryContract(
                w3=self.w3,
                address=self.config['factoryAddress']
            )
            
            self.token_contract = TokenContract(w3=self.w3)
            
        except Exception as e:
            self.logger.error(f"Failed to setup contracts: {e}")
            raise
    
    def _setup_optimized_token_loader(self, force_refresh):
        """Initialize OPTIMIZED token loading system using shared manager"""
        try:
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
                
        except Exception as e:
            self.logger.error(f"Failed to setup token loader: {e}")
            raise
    
    def _extract_personality_phrases(self):
        """Extract personality phrases from config"""
        return {
            "buy": self.config.get("buyPhrases", []),
            "sell": self.config.get("sellPhrases", []),
            "create_token": self.config.get("createPhrases", []),
            "error": self.config.get("errorPhrases", [])
        }
    
    def _load_tokens(self):
        """Load tradeable tokens using OPTIMIZED shared system with error handling"""
        try:
            self.logger.info("🔍 Loading tradeable tokens via shared manager...")
            self.tokens = self.token_loader.load_tokens_optimized()
            self.logger.success(f"Loaded {len(self.tokens)} tradeable tokens")
        except Exception as e:
            self.logger.error(f"Failed to load tokens: {e}")
            self.tokens = []  # Continue with empty list rather than crash
    
    def _send_startup_notification(self):
        """Send enhanced startup notification with session balance and wallet address"""
        try:
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
            
        except Exception as e:
            self.logger.error(f"Failed to send startup notification: {e}")
            # Don't crash on webhook failure
    
    def _determine_bot_mood(self):
        """Determine bot mood based on config personality"""
        try:
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
        except:
            return "neutral"
    
    def get_avax_balance(self):
        """Get current AVAX balance with error handling and retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                balance_wei = self.w3.eth.get_balance(self.account.address)
                return float(self.w3.from_wei(balance_wei, 'ether'))
            except (Web3Exception, Web3RPCError, ProviderConnectionError) as e:
                if attempt == max_retries - 1:
                    self.logger.error(f"Failed to get balance after {max_retries} attempts: {e}")
                    return 0.0
                
                self.logger.warning(f"Balance fetch attempt {attempt + 1} failed: {e}")
                
                # Try to reconnect if connection issue
                if isinstance(e, ProviderConnectionError):
                    self._reconnect_if_needed()
                
                time.sleep(2 ** attempt)  # Exponential backoff
            except Exception as e:
                self.logger.error(f"Unexpected error getting balance: {e}")
                return 0.0
        
        return 0.0
    
    def get_session_metrics(self):
        """Get comprehensive session financial metrics"""
        try:
            return self.webhook.get_session_summary()
        except Exception as e:
            self.logger.error(f"Failed to get session metrics: {e}")
            return {}
    
    def refresh_tokens(self):
        """Refresh token list using optimized shared system with error handling"""
        try:
            self.logger.info("🔄 Refreshing token list via shared manager...")
            self.tokens = self.token_loader.load_tokens_optimized()
            self.logger.success(f"Refreshed: {len(self.tokens)} tradeable tokens")
        except Exception as e:
            self.logger.error(f"Failed to refresh tokens: {e}")
            # Keep existing tokens if refresh fails
    
    def force_cache_refresh(self):
        """Force a complete refresh via shared manager with error handling"""
        try:
            self.token_loader.force_refresh()
            self.refresh_tokens()
        except Exception as e:
            self.logger.error(f"Failed to force refresh: {e}")
    
    def get_cache_stats(self):
        """Get shared manager statistics with error handling"""
        try:
            return self.token_loader.get_stats()
        except Exception as e:
            self.logger.error(f"Failed to get cache stats: {e}")
            return {}
    
    def execute_trade_cycle(self):
        """Execute one complete trading cycle with comprehensive error handling"""
        try:
            if self.verbose:
                print(f"\n🤖 TVB: --- Starting Trade Cycle ---")
            
            # Check connection health before trading
            current_time = time.time()
            if current_time - self.last_connection_check > self.connection_check_interval:
                if not self._reconnect_if_needed():
                    self.logger.error("🔴 Connection unhealthy, skipping trade cycle")
                    return False
                self.last_connection_check = current_time
            
            # Check if we should create a token
            create_chance = self.config.get('createTokenChance', 0.02)
            if random.random() < create_chance:
                success = self._attempt_token_creation()
                if success:
                    self.last_successful_action = time.time()
                    self.consecutive_errors = 0
                return success
            
            # Check if we have tokens to trade
            if not self.tokens:
                self.logger.warning("⏭️ No tradeable tokens, refreshing list...")
                self.refresh_tokens()
                if not self.tokens:
                    self.logger.warning("⏭️ Still no tokens found, waiting...")
                    return False
            
            # Check balance before trading
            current_balance = self.get_avax_balance()
            min_trade_amount = self.config.get('minTradeAmount', 0.005)
            
            if current_balance < min_trade_amount:
                self.logger.warning(f"💸 Insufficient balance: {current_balance:.6f} AVAX < {min_trade_amount} AVAX")
                
                # Send balance alert only occasionally to avoid spam
                if hasattr(self, '_last_balance_alert'):
                    if time.time() - self._last_balance_alert > 300:  # 5 minutes
                        self.webhook.send_balance_alert(current_balance, min_trade_amount, "insufficient")
                        self._last_balance_alert = time.time()
                else:
                    self.webhook.send_balance_alert(current_balance, min_trade_amount, "insufficient")
                    self._last_balance_alert = time.time()
                
                return False
            
            # Select random token and execute trade
            token = random.choice(self.tokens)
            
            if self.verbose:
                self.logger.info(f"🎯 Selected token: {token['symbol']} ({token['address'][:10]}...)")
            
            success = self.trader.execute_trade_decision(token)
            
            if success:
                self.last_successful_action = time.time()
                self.consecutive_errors = 0
                if self.verbose:
                    self.logger.success(f"Trade cycle completed for {token['symbol']}")
            else:
                self.consecutive_errors += 1
                self.logger.warning(f"Trade cycle failed for {token['symbol']} (consecutive errors: {self.consecutive_errors})")
            
            return success
            
        except Web3Exception as e:
            self.logger.error(f"Web3 error in trade cycle: {e}")
            self.consecutive_errors += 1
            
            # Try to reconnect on Web3 errors
            self._reconnect_if_needed()
            
            # Send error webhook
            self.webhook.send_error_update(f"Web3 error: {str(e)}", "web3_error")
            return False
            
        except Exception as e:
            self.logger.error(f"Unexpected error in trade cycle: {e}")
            self.consecutive_errors += 1
            
            # Send error webhook
            self.webhook.send_error_update(str(e), "trade_cycle_error")
            return False
    
    def _attempt_token_creation(self):
        """Attempt to create a new token with personality-driven concept"""
        try:
            self.logger.info("🎨 Considering token creation...")
            
            # Use trader's token creation functionality
            success = self.trader.attempt_token_creation()
            
            if success:
                # Refresh token list to include the new token
                self.logger.info("🔄 Refreshing token list to include new creation...")
                self.refresh_tokens()
            
            return success
            
        except Exception as e:
            self.logger.error(f"Token creation failed: {e}")
            self.webhook.send_error_update(f"Token creation error: {str(e)}", "token_creation_error")
            return False
    
    def send_heartbeat(self):
        """Send periodic heartbeat update with session metrics and error handling"""
        try:
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
            success = self.webhook.send_heartbeat(
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
                    },
                    "connectionHealth": self._check_connection_health(),
                    "consecutiveErrors": self.consecutive_errors
                }
            )
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to send heartbeat: {e}")
            return False
    
    def print_session_summary(self):
        """Print comprehensive session summary with wallet address"""
        try:
            print(f"\n🤖 TVB: 📊 {self.display_name} Session Summary:")
            print(f"  👤 Account: {self.account.address}")
            
            # Get session metrics from webhook manager (includes wallet address)
            self.webhook.print_session_summary()
            
            # Additional bot-specific info
            print(f"  🎯 Tokens Tracked: {len(self.tokens)}")
            print(f"  ⚠️ Consecutive Errors: {self.consecutive_errors}")
            
            # Show shared manager stats
            shared_stats = self.get_cache_stats()
            print(f"  🌐 Shared Manager:")
            print(f"    🤖 Total bots: {shared_stats.get('registered_bots', 0)}")
            print(f"    🚀 Queries saved: {shared_stats.get('factory_queries_saved', 0)}")
            print(f"    ⏰ Next refresh: {shared_stats.get('next_refresh_in_minutes', 0):.1f}min")
            
        except Exception as e:
            self.logger.error(f"Failed to print session summary: {e}")

    def run(self):
        """Enhanced main trading loop with robust error handling and recovery"""
        try:
            self.is_running = True
            self.logger.info("🚀 Starting enhanced trading loop with improved error handling...")
            
            cycle_count = 0
            last_heartbeat = 0
            last_token_refresh = 0
            heartbeat_interval = 120  # 2 minutes
            token_refresh_interval = 300  # 5 minutes
            
            # Send initial heartbeat
            self.send_heartbeat()
            last_heartbeat = time.time()
            
            while self.is_running and not self.shutdown_requested:
                cycle_count += 1
                current_time = time.time()
                
                try:
                    # Check if we've had too many consecutive errors
                    if self.consecutive_errors >= self.max_consecutive_errors:
                        self.logger.error(f"🔴 Too many consecutive errors ({self.consecutive_errors}), pausing for recovery...")
                        
                        # Send error notification
                        self.webhook.send_error_update(
                            f"Bot paused due to {self.consecutive_errors} consecutive errors", 
                            "error_threshold_reached"
                        )
                        
                        # Wait longer and try to recover
                        time.sleep(60)  # Wait 1 minute
                        
                        # Try to reconnect and refresh
                        if self._reconnect_if_needed():
                            self.refresh_tokens()
                            self.consecutive_errors = 0  # Reset on successful recovery
                            self.logger.info("🟢 Recovery successful, resuming normal operation")
                        else:
                            self.logger.error("🔴 Recovery failed, continuing with limited operation")
                    
                    if self.verbose:
                        self.logger.cycle(cycle_count, "Starting trade cycle")
                    
                    # Execute trading logic with error handling
                    try:
                        self.execute_trade_cycle()
                    except KeyboardInterrupt:
                        raise  # Let keyboard interrupt bubble up
                    except Exception as e:
                        self.logger.error(f"Trade cycle error: {e}")
                        self.consecutive_errors += 1
                        
                        # Send error webhook but don't crash
                        self.webhook.send_error_update(str(e), "trade_cycle_error")
                    
                    # Send heartbeat every 2 minutes
                    if current_time - last_heartbeat >= heartbeat_interval:
                        success = self.send_heartbeat()
                        if success:
                            last_heartbeat = current_time
                        else:
                            self.logger.warning("Heartbeat failed, will retry sooner")
                    
                    # Refresh tokens every 5 minutes to pick up new ones
                    if current_time - last_token_refresh >= token_refresh_interval:
                        try:
                            self.refresh_tokens()
                            last_token_refresh = current_time
                        except Exception as e:
                            self.logger.warning(f"Token refresh failed: {e}")
                    
                    # Calculate sleep time based on personality and error state
                    min_interval = self.config.get('minInterval', 15)
                    max_interval = self.config.get('maxInterval', 60)
                    
                    # Increase intervals if we're having errors
                    if self.consecutive_errors > 0:
                        error_multiplier = min(3, 1 + (self.consecutive_errors * 0.5))
                        min_interval = int(min_interval * error_multiplier)
                        max_interval = int(max_interval * error_multiplier)
                    
                    sleep_time = random.uniform(min_interval, max_interval)
                    
                    if self.verbose:
                        error_status = f" (errors: {self.consecutive_errors})" if self.consecutive_errors > 0 else ""
                        self.logger.info(f"💤 Cycle {cycle_count} complete{error_status}, sleeping {sleep_time:.1f}s")
                    
                    # Sleep with interruption checking
                    sleep_interval = 0.5
                    total_sleep = 0
                    while total_sleep < sleep_time and self.is_running and not self.shutdown_requested:
                        time.sleep(min(sleep_interval, sleep_time - total_sleep))
                        total_sleep += sleep_interval
                    
                except KeyboardInterrupt:
                    self.logger.info("🛑 Keyboard interrupt received")
                    self.shutdown_requested = True
                    break
                except Exception as e:
                    self.logger.error(f"Outer loop error: {e}")
                    self.logger.error(f"Traceback: {traceback.format_exc()}")
                    
                    # Send error webhook
                    self.webhook.send_error_update(str(e), "outer_loop_error")
                    
                    # Don't increment consecutive errors for outer loop errors
                    # as they might be transient
                    
                    # Sleep a bit before retrying
                    time.sleep(30)
                    
        except KeyboardInterrupt:
            self._handle_shutdown(cycle_count, "user")
        except Exception as e:
            self._handle_shutdown(cycle_count, "crash", str(e))
        finally:
            self.is_running = False
        
        self.logger.info("👋 Bot trading loop ended")
    
    def _handle_shutdown(self, cycle_count, reason, error_msg=None):
        """Handle bot shutdown gracefully with enhanced reporting"""
        try:
            self.is_running = False
            self.shutdown_requested = True
            
            session_metrics = self.get_session_metrics()
            
            shutdown_info = {
                "totalCycles": cycle_count,
                "sessionMetrics": session_metrics,
                "walletAddress": self.account.address,  # Include wallet address in shutdown
                "consecutiveErrors": self.consecutive_errors
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
            
            # Send shutdown notification
            try:
                self.webhook.send_shutdown_notification(shutdown_info)
            except Exception as e:
                self.logger.error(f"Failed to send shutdown notification: {e}")
            
            # Cleanup shared resources
            try:
                if hasattr(self, 'token_loader'):
                    self.token_loader.cleanup()
            except Exception as e:
                self.logger.error(f"Failed to cleanup token loader: {e}")
            
            # Print final stats
            if self.verbose:
                self.print_session_summary()
                print(f"🤖 TVB: 🔄 Total Cycles: {cycle_count}")
                print(f"🤖 TVB: ⚠️ Final Error Count: {self.consecutive_errors}")
                
                # Print shared manager stats
                shared_stats = self.get_cache_stats()
                print(f"\n🤖 TVB: 🌐 Shared Manager Final Stats:")
                print(f"  🚀 Factory queries saved: {shared_stats.get('factory_queries_saved', 0)}")
                print(f"  🤖 Bots served: {shared_stats.get('registered_bots', 0)}")
                
        except Exception as e:
            print(f"🤖 TVB: ❌ Error during shutdown: {e}")
    
    def stop(self):
        """Gracefully stop the bot"""
        self.logger.info("🛑 Stop requested")
        self.shutdown_requested = True
        self.is_running = False


# Example usage for testing
if __name__ == "__main__":
    # Test bot initialization (won't actually run without config)
    print("🤖 TVB: Enhanced core bot class loaded successfully!")
    print("Use main.py to run the bot with proper configuration.")