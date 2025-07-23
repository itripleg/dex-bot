# bot/core.py - OPTIMIZED core bot with reduced webhook calls and better stability
#!/usr/bin/env python3
"""
OPTIMIZED Core bot orchestration with minimal webhook overhead and improved stability
Dramatically reduced webhook traffic while maintaining full functionality
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
from bot.trader import TokenTrader
from bot.webhook import OptimizedWebhookManager  # Use optimized webhook manager
from bot.logger import BotLogger
from contracts.factory import FactoryContract
from contracts.token import TokenContract
from shared.token_manager import OptimizedTokenLoader

class OptimizedTransparentVolumeBot:
    """
    OPTIMIZED main bot orchestration class with minimal webhook overhead
    """
    
    def __init__(self, config, private_key_override=None, force_cache_refresh=False, verbose=False):
        """Initialize the bot with optimized webhook and reduced API calls"""
        try:
            # Store configuration
            self.config = merge_config_with_defaults(config)
            self.verbose = verbose
            
            # Bot identity
            self.bot_name = self.config['name']
            self.display_name = self.config['displayName']
            
            # Initialize bot-specific logger
            self.logger = BotLogger(self.bot_name, self.display_name)
            self.logger.info("🚀 Initializing OPTIMIZED Transparent Volume Bot...")
            
            print_config_summary(self.config)
            
            # OPTIMIZATION: Enhanced error tracking with adaptive behavior
            self.consecutive_errors = 0
            self.max_consecutive_errors = 5
            self.last_successful_action = time.time()
            self.connection_check_interval = 60  # Reduced frequency: every 60 seconds
            self.last_connection_check = 0
            self.error_backoff_multiplier = 1.0  # Adaptive error handling
            
            # OPTIMIZATION: Cycle timing with adaptive intervals
            self.base_min_interval = self.config.get('minInterval', 15)
            self.base_max_interval = self.config.get('maxInterval', 60)
            self.current_min_interval = self.base_min_interval
            self.current_max_interval = self.base_max_interval
            self.last_successful_trade_time = time.time()
            
            # Initialize Web3 and account FIRST
            self._setup_web3_and_account(private_key_override)
            
            # Initialize contract interfaces
            self._setup_contracts()
            
            # Initialize OPTIMIZED token loading system
            self._setup_optimized_token_loader(force_cache_refresh)
            
            # Session tracking
            self.session_start_time = datetime.utcnow().isoformat() + "Z"
            self.starting_balance = self.get_avax_balance()
            
            # OPTIMIZATION: Initialize OPTIMIZED webhook manager
            self.webhook = OptimizedWebhookManager(
                bot_name=self.bot_name,
                display_name=self.display_name,
                avatar_url=self.config.get('avatarUrl', ''),
                webhook_url=self.config.get('webhookUrl'),
                bot_secret=self.config.get('botSecret'),
                phrases=self._extract_personality_phrases(),
                bio=self.config.get('bio'),
                get_balance_callback=self.get_avax_balance,
                wallet_address=self.account.address
            )
            
            # Set session start in webhook manager
            self.webhook.set_session_start(self.starting_balance, self.session_start_time)
            
            # Initialize trader with optimized webhook manager
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
            
            # OPTIMIZATION: Performance tracking
            self.cycle_count = 0
            self.successful_trades = 0
            self.failed_trades = 0
            self.tokens_refreshed = 0
            
            # Load tokens using optimized system
            self._load_tokens()
            
            # OPTIMIZATION: Send startup notification (automatic heartbeats will start)
            self._send_startup_notification()
            
            print(f"🤖 TVB: ✅ OPTIMIZED Bot '{self.display_name}' initialized successfully!")
            print(f"🤖 TVB: 💼 Wallet Address: {self.account.address}")
            print(f"🤖 TVB: 💰 Starting session with {self.starting_balance:.6f} AVAX")
            print(f"🤖 TVB: 🚀 Optimization features: Smart heartbeats, Request batching, Adaptive intervals")
            
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
                        time.sleep(2 ** attempt)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise ConnectionError(f"Failed to connect to RPC: {self.rpc_url}, Error: {e}")
                    time.sleep(2 ** attempt)
            
            # Setup account
            private_key = get_private_key(self.config, private_key_override, self.bot_name)
            self.account = Account.from_key(private_key)
            
            # Check balance and show funding instructions if needed
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
            self.tokens_refreshed += 1
            self.logger.success(f"Loaded {len(self.tokens)} tradeable tokens")
        except Exception as e:
            self.logger.error(f"Failed to load tokens: {e}")
            self.tokens = []
    
    def _send_startup_notification(self):
        """Send startup notification with session info"""
        try:
            startup_info = {
                "message": f"{self.display_name} is now online and ready to trade!",
                "sessionStarted": self.session_start_time,
                "tokensFound": len(self.tokens),
                "walletAddress": self.account.address,
                "config": {
                    "buyBias": self.config.get('buyBias', 0.6),
                    "riskTolerance": self.config.get('riskTolerance', 0.5),
                    "minTradeAmount": self.config.get('minTradeAmount', 0.005),
                    "maxTradeAmount": self.config.get('maxTradeAmount', 0.02),
                    "tradingRange": f"{self.config.get('minTradeAmount', 0.005):.4f}-{self.config.get('maxTradeAmount', 0.02):.4f} AVAX",
                    "intervalRange": f"{self.current_min_interval}-{self.current_max_interval}s"
                },
                "character": {
                    "mood": self._determine_bot_mood(),
                    "personality": self.config.get('name', '').replace('_', ' ').title()
                },
                "optimizationFeatures": {
                    "smartHeartbeats": True,
                    "requestBatching": True,
                    "adaptiveIntervals": True,
                    "sharedTokenManager": True
                }
            }
            
            self.webhook.send_startup_notification(startup_info)
            
        except Exception as e:
            self.logger.error(f"Failed to send startup notification: {e}")
    
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
                
                if isinstance(e, ProviderConnectionError):
                    self._reconnect_if_needed()
                
                time.sleep(2 ** attempt)
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
        """Refresh token list using optimized shared system"""
        try:
            self.logger.info("🔄 Refreshing token list via shared manager...")
            self.tokens = self.token_loader.load_tokens_optimized()
            self.tokens_refreshed += 1
            self.logger.success(f"Refreshed: {len(self.tokens)} tradeable tokens")
        except Exception as e:
            self.logger.error(f"Failed to refresh tokens: {e}")
    
    def force_cache_refresh(self):
        """Force a complete refresh via shared manager"""
        try:
            self.token_loader.force_refresh()
            self.refresh_tokens()
        except Exception as e:
            self.logger.error(f"Failed to force refresh: {e}")
    
    def get_cache_stats(self):
        """Get shared manager statistics"""
        try:
            return self.token_loader.get_stats()
        except Exception as e:
            self.logger.error(f"Failed to get cache stats: {e}")
            return {}
    
    def execute_trade_cycle(self):
        """OPTIMIZED trade cycle with adaptive intervals and reduced overhead"""
        try:
            self.cycle_count += 1
            
            if self.verbose:
                print(f"\n🤖 TVB: --- Cycle #{self.cycle_count} ---")
            
            # OPTIMIZATION: Less frequent connection checks
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
                    self.last_successful_trade_time = time.time()
                    self.consecutive_errors = 0
                    self.successful_trades += 1
                    self._adapt_intervals_on_success()
                else:
                    self.failed_trades += 1
                    self._adapt_intervals_on_failure()
                return success
            
            # Check tokens and balance
            if not self.tokens:
                self.logger.warning("⏭️ No tradeable tokens, refreshing list...")
                self.refresh_tokens()
                if not self.tokens:
                    self.logger.warning("⏭️ Still no tokens found, waiting...")
                    return False
            
            current_balance = self.get_avax_balance()
            min_trade_amount = self.config.get('minTradeAmount', 0.005)
            
            if current_balance < min_trade_amount:
                self.logger.warning(f"💸 Insufficient balance: {current_balance:.6f} AVAX < {min_trade_amount} AVAX")
                
                # OPTIMIZATION: Send balance alert less frequently
                if not hasattr(self, '_last_balance_alert') or time.time() - self._last_balance_alert > 300:
                    self.webhook.send_balance_alert(current_balance, min_trade_amount, "insufficient")
                    self._last_balance_alert = time.time()
                
                return False
            
            # Execute trade
            token = random.choice(self.tokens)
            
            if self.verbose:
                self.logger.info(f"🎯 Selected token: {token['symbol']} ({token['address'][:10]}...)")
            
            success = self.trader.execute_trade_decision(token)
            
            if success:
                self.last_successful_action = time.time()
                self.last_successful_trade_time = time.time()
                self.consecutive_errors = 0
                self.successful_trades += 1
                self._adapt_intervals_on_success()
                
                if self.verbose:
                    self.logger.success(f"Trade cycle completed for {token['symbol']}")
            else:
                self.consecutive_errors += 1
                self.failed_trades += 1
                self._adapt_intervals_on_failure()
                self.logger.warning(f"Trade cycle failed for {token['symbol']} (consecutive errors: {self.consecutive_errors})")
            
            return success
            
        except Exception as e:
            error_msg = f"Trade cycle error: {e}"
            self.logger.error(error_msg)
            self.consecutive_errors += 1
            self.failed_trades += 1
            self._adapt_intervals_on_failure()
            
            # Send error webhook (will be batched automatically)
            self.webhook.send_error_update(error_msg, "trade_cycle_error")
            return False
    
    def _adapt_intervals_on_success(self):
        """OPTIMIZATION: Adapt trading intervals on successful trades"""
        # Gradually reduce intervals on success (more aggressive trading)
        self.error_backoff_multiplier = max(0.5, self.error_backoff_multiplier * 0.95)
        
        self.current_min_interval = max(
            self.base_min_interval,
            int(self.base_min_interval * self.error_backoff_multiplier)
        )
        self.current_max_interval = max(
            self.base_max_interval,
            int(self.base_max_interval * self.error_backoff_multiplier)
        )
    
    def _adapt_intervals_on_failure(self):
        """OPTIMIZATION: Adapt trading intervals on failed trades"""
        # Gradually increase intervals on failure (less aggressive trading)
        self.error_backoff_multiplier = min(3.0, self.error_backoff_multiplier * 1.1)
        
        self.current_min_interval = int(self.base_min_interval * self.error_backoff_multiplier)
        self.current_max_interval = int(self.base_max_interval * self.error_backoff_multiplier)
    
    def _attempt_token_creation(self):
        """Attempt to create a new token"""
        try:
            self.logger.info("🎨 Considering token creation...")
            
            success = self.trader.attempt_token_creation()
            
            if success:
                self.logger.info("🔄 Refreshing token list to include new creation...")
                self.refresh_tokens()
            
            return success
            
        except Exception as e:
            self.logger.error(f"Token creation failed: {e}")
            self.webhook.send_error_update(f"Token creation error: {str(e)}", "token_creation_error")
            return False
    
    def print_session_summary(self):
        """Print comprehensive session summary with optimization stats"""
        try:
            print(f"\n🤖 TVB: 📊 {self.display_name} OPTIMIZED Session Summary:")
            print(f"  👤 Account: {self.account.address}")
            
            # Get session metrics from webhook manager
            self.webhook.print_session_summary()
            
            # Bot-specific performance stats
            print(f"\n🤖 TVB: 🎯 Trading Performance:")
            print(f"  🔄 Total cycles: {self.cycle_count}")
            print(f"  ✅ Successful trades: {self.successful_trades}")
            print(f"  ❌ Failed trades: {self.failed_trades}")
            if self.cycle_count > 0:
                success_rate = (self.successful_trades / self.cycle_count) * 100
                print(f"  📊 Success rate: {success_rate:.1f}%")
            print(f"  🎯 Tokens tracked: {len(self.tokens)}")
            print(f"  🔄 Token refreshes: {self.tokens_refreshed}")
            print(f"  ⚠️ Consecutive errors: {self.consecutive_errors}")
            
            # Optimization stats
            print(f"\n🤖 TVB: 🚀 Optimization Stats:")
            print(f"  ⚡ Current intervals: {self.current_min_interval}-{self.current_max_interval}s (base: {self.base_min_interval}-{self.base_max_interval}s)")
            print(f"  📉 Error backoff: {self.error_backoff_multiplier:.2f}x")
            
            # Shared manager stats
            shared_stats = self.get_cache_stats()
            print(f"  🌐 Shared Manager:")
            print(f"    🤖 Total bots: {shared_stats.get('registered_bots', 0)}")
            print(f"    🚀 Queries saved: {shared_stats.get('factory_queries_saved', 0)}")
            print(f"    ⏰ Next refresh: {shared_stats.get('next_refresh_in_minutes', 0):.1f}min")
            
        except Exception as e:
            self.logger.error(f"Failed to print session summary: {e}")

    def run(self):
        """OPTIMIZED main trading loop with reduced webhook overhead"""
        try:
            self.is_running = True
            self.logger.info("🚀 Starting OPTIMIZED trading loop...")
            
            last_token_refresh = 0
            token_refresh_interval = 300  # 5 minutes
            
            # NOTE: No manual heartbeat sending needed - OptimizedWebhookManager handles this automatically
            
            while self.is_running and not self.shutdown_requested:
                current_time = time.time()
                
                try:
                    # Check if we've had too many consecutive errors
                    if self.consecutive_errors >= self.max_consecutive_errors:
                        self.logger.error(f"🔴 Too many consecutive errors ({self.consecutive_errors}), pausing for recovery...")
                        
                        # Send error notification (will be sent immediately as it's critical)
                        self.webhook.send_error_update(
                            f"Bot paused due to {self.consecutive_errors} consecutive errors", 
                            "error_threshold_reached"
                        )
                        
                        # Wait longer and try to recover
                        time.sleep(60)
                        
                        if self._reconnect_if_needed():
                            self.refresh_tokens()
                            self.consecutive_errors = 0
                            self.logger.info("🟢 Recovery successful, resuming normal operation")
                        else:
                            self.logger.error("🔴 Recovery failed, continuing with limited operation")
                    
                    if self.verbose:
                        self.logger.cycle(self.cycle_count + 1, "Starting trade cycle")
                    
                    # Execute trading logic
                    try:
                        self.execute_trade_cycle()
                    except KeyboardInterrupt:
                        raise
                    except Exception as e:
                        self.logger.error(f"Trade cycle error: {e}")
                        self.consecutive_errors += 1
                        self.failed_trades += 1
                        self._adapt_intervals_on_failure()
                        
                        # Send error webhook (will be batched automatically)
                        self.webhook.send_error_update(str(e), "trade_cycle_error")
                    
                    # OPTIMIZATION: Less frequent token refreshes
                    if current_time - last_token_refresh >= token_refresh_interval:
                        try:
                            self.refresh_tokens()
                            last_token_refresh = current_time
                        except Exception as e:
                            self.logger.warning(f"Token refresh failed: {e}")
                    
                    # OPTIMIZATION: Adaptive sleep time based on performance
                    sleep_time = random.uniform(self.current_min_interval, self.current_max_interval)
                    
                    if self.verbose:
                        error_status = f" (errors: {self.consecutive_errors})" if self.consecutive_errors > 0 else ""
                        performance_info = f" (success: {self.successful_trades}, failed: {self.failed_trades})"
                        self.logger.info(f"💤 Cycle {self.cycle_count} complete{error_status}{performance_info}, sleeping {sleep_time:.1f}s")
                    
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
                    
                    # Send error webhook (will be sent immediately as it's critical)
                    self.webhook.send_error_update(str(e), "outer_loop_error")
                    
                    # Sleep before retrying
                    time.sleep(30)
                    
        except KeyboardInterrupt:
            self._handle_shutdown("user")
        except Exception as e:
            self._handle_shutdown("crash", str(e))
        finally:
            self.is_running = False
        
        self.logger.info("👋 OPTIMIZED bot trading loop ended")
    
    def _handle_shutdown(self, reason, error_msg=None):
        """Handle bot shutdown gracefully with enhanced reporting"""
        try:
            self.is_running = False
            self.shutdown_requested = True
            
            session_metrics = self.get_session_metrics()
            
            shutdown_info = {
                "totalCycles": self.cycle_count,
                "successfulTrades": self.successful_trades,
                "failedTrades": self.failed_trades,
                "sessionMetrics": session_metrics,
                "walletAddress": self.account.address,
                "consecutiveErrors": self.consecutive_errors,
                "optimizationStats": {
                    "tokensRefreshed": self.tokens_refreshed,
                    "finalIntervals": f"{self.current_min_interval}-{self.current_max_interval}s",
                    "errorBackoffMultiplier": self.error_backoff_multiplier,
                }
            }
            
            if reason == "user":
                print(f"\n🤖 TVB: 🛑 OPTIMIZED Bot stopped by user")
                shutdown_info.update({
                    "message": f"{self.display_name} is going offline (user requested)",
                    "reason": "User initiated shutdown"
                })
            elif reason == "crash":
                print(f"\n🤖 TVB: 💥 OPTIMIZED Bot crashed: {error_msg}")
                shutdown_info.update({
                    "message": f"Bot crashed: {error_msg}",
                    "reason": "System error",
                    "error": error_msg
                })
            
            # Send shutdown notification (will flush any pending batched requests)
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
                
        except Exception as e:
            print(f"🤖 TVB: ❌ Error during shutdown: {e}")
    
    def stop(self):
        """Gracefully stop the bot"""
        self.logger.info("🛑 Stop requested")
        self.shutdown_requested = True
        self.is_running = False


# Backward compatibility alias
TransparentVolumeBot = OptimizedTransparentVolumeBot


# Example usage for testing
if __name__ == "__main__":
    print("🤖 TVB: OPTIMIZED core bot class loaded successfully!")
    print("Use main.py to run the bot with proper configuration.")