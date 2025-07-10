# bot/core.py - Fixed bot core with clean logging integration
#!/usr/bin/env python3
"""
Core bot orchestration with shared token management optimization and
CLEAN LOGGING SYSTEM - eliminates verbose spam
"""

import time
import random
import threading
from datetime import datetime
from web3 import Web3
from eth_account import Account

from bot.config import get_private_key, merge_config_with_defaults, print_config_summary
from bot.cache import TokenCache  # Keep for backwards compatibility if needed
from bot.trader import TokenTrader
from bot.webhook import WebhookManager
from bot.logger import BotLogger  # Import clean logger
from contracts.factory import FactoryContract
from contracts.token import TokenContract
from shared.token_manager import OptimizedTokenLoader

class TransparentVolumeBot:
    """
    Main bot orchestration class with optimized shared token management
    and CLEAN LOGGING SYSTEM
    """
    
    def __init__(self, config, private_key_override=None, force_cache_refresh=False, verbose=False):
        """Initialize the bot with modular components and clean logging"""
        # Store configuration
        self.config = merge_config_with_defaults(config)
        self.verbose = verbose
        
        # Bot identity
        self.bot_name = self.config['name']
        self.display_name = self.config['displayName']
        
        # Initialize CLEAN bot-specific logger
        self.logger = BotLogger(self.bot_name, self.display_name)
        self.logger.info("🚀 Initializing with enhanced reliability...")
        
        # Print config summary - but use clean logging
        self._print_clean_config_summary()
        
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
        
        # ENHANCED HEARTBEAT MANAGEMENT
        self.heartbeat_interval = 90  # Send heartbeat every 90 seconds (more frequent)
        self.last_heartbeat_time = 0
        self.heartbeat_failures = 0
        self.max_heartbeat_failures = 3
        self.force_heartbeat_on_error = True
        
        # Connection health tracking
        self.last_successful_action = time.time()
        self.connection_warnings_sent = 0
        
        # Load tokens using optimized system
        self._load_tokens()
        
        # Send startup notification (now includes wallet address automatically)
        self._send_startup_notification()
        
        # Clean success message
        self.logger.success(f"Bot '{self.display_name}' initialized successfully!")
        self.logger.info(f"💼 Wallet: {self.account.address}")
        self.logger.info(f"💰 Starting with {self.starting_balance:.6f} AVAX")
        self.logger.info(f"💓 Heartbeat: {self.heartbeat_interval}s interval")
    
    def _print_clean_config_summary(self):
        """Print configuration summary using clean logging"""
        self.logger.info(f"📊 Personality: Buy={self.config['buyBias']:.2f}, Risk={self.config['riskTolerance']:.2f}")
        self.logger.info(f"⏱️  Intervals: {self.config['minInterval']}-{self.config['maxInterval']}s")
        self.logger.info(f"💰 Trade Size: {self.config['minTradeAmount']:.4f}-{self.config['maxTradeAmount']:.4f} AVAX")
        
        # Network info (mask sensitive parts)
        rpc_url = self.config.get('rpcUrl', 'Not configured')
        if 'alchemy.com' in rpc_url or 'infura.io' in rpc_url:
            import re
            rpc_url = re.sub(r'/v2/[a-zA-Z0-9_-]+', '/v2/***API_KEY***', rpc_url)
        self.logger.info(f"🌐 Network: {rpc_url}")
        
        webhook_status = "✅ Enabled" if self.config.get('webhookUrl') else "❌ Disabled"
        self.logger.info(f"📡 Webhooks: {webhook_status}")
    
    def _setup_web3_and_account(self, private_key_override):
        """Initialize Web3 connection and account with clean logging"""
        self.logger.info("🌐 Setting up Web3 connection...")
        
        self.rpc_url = self.config['rpcUrl']
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to RPC: {self.rpc_url}")
        
        # Setup account - pass bot name for environment lookup
        private_key = get_private_key(self.config, private_key_override, self.bot_name)
        
        self.account = Account.from_key(private_key)
        
        # Clean wallet address logging
        BotLogger.system(f"💼 {self.display_name} Wallet: {self.account.address}")
        
        # Check balance and show funding instructions if needed
        current_balance = self.get_avax_balance()
        if current_balance == 0:
            BotLogger.system(f"⚠️  {self.display_name} wallet needs funding!", "warning")
            BotLogger.system(f"📍 Send AVAX to: {self.account.address}")
            BotLogger.system("🌐 Faucet: https://faucet.avax.network/")
            BotLogger.system("⏳ Bot will continue but cannot trade without AVAX")
        
        self.logger.success(f"Account connected: {self.account.address}")
        self.logger.info(f"Balance: {current_balance:.6f} AVAX")
    
    def _setup_contracts(self):
        """Initialize contract interfaces with clean logging"""
        self.logger.info("📜 Setting up contracts...")
        
        self.factory_contract = FactoryContract(
            w3=self.w3,
            address=self.config['factoryAddress']
        )
        
        self.token_contract = TokenContract(w3=self.w3)
        
        # Clean factory address logging
        BotLogger.system(f"📜 Factory: {self.config['factoryAddress']}")
    
    def _setup_optimized_token_loader(self, force_refresh):
        """Initialize OPTIMIZED token loading system with clean logging"""
        self.logger.info("🚀 Setting up shared token manager...")
        
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
        """Load tradeable tokens using OPTIMIZED shared system with clean logging"""
        self.logger.info("🔍 Loading tokens via shared manager...")
        self.tokens = self.token_loader.load_tokens_optimized()
        self.logger.success(f"Loaded {len(self.tokens)} tradeable tokens")
    
    def _send_startup_notification(self):
        """Send enhanced startup notification with clean logging"""
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
                "intervalRange": f"{self.config.get('minInterval', 15)}-{self.config.get('maxInterval', 60)}s",
                "heartbeatInterval": self.heartbeat_interval
            },
            "character": {
                "mood": self._determine_bot_mood(),
                "personality": self.config.get('name', '').replace('_', ' ').title()
            }
        }
        
        success = self.webhook.send_startup_notification(startup_info)
        if success:
            self.last_successful_action = time.time()
        else:
            self.logger.warning("Startup notification failed - bot may appear offline")
    
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
        """Refresh token list using optimized shared system with clean logging"""
        if self.verbose:
            self.logger.info("🔄 Refreshing token list...")
        self.tokens = self.token_loader.load_tokens_optimized()
        if self.verbose:
            self.logger.success(f"Refreshed: {len(self.tokens)} tradeable tokens")
    
    def force_cache_refresh(self):
        """Force a complete refresh via shared manager"""
        self.token_loader.force_refresh()
        self.refresh_tokens()
    
    def get_cache_stats(self):
        """Get shared manager statistics"""
        return self.token_loader.get_stats()
    
    def execute_trade_cycle(self):
        """Execute one complete trading cycle with clean logging"""
        if self.verbose:
            self.logger.cycle(1, "Starting trade cycle")
        
        trade_success = False
        
        try:
            # Check if we should create a token
            create_chance = self.config.get('createTokenChance', 0.02)
            if random.random() < create_chance:
                trade_success = self._attempt_token_creation()
                return trade_success
            
            # Check if we have tokens to trade
            if not self.tokens:
                if self.verbose:
                    self.logger.warning("⏭️ No tradeable tokens, refreshing...")
                self.refresh_tokens()
                if not self.tokens:
                    if self.verbose:
                        self.logger.warning("⏭️ Still no tokens found")
                    return False
            
            # Select random token and execute trade
            token = random.choice(self.tokens)
            
            if self.verbose:
                self.logger.info(f"🎯 Selected: {token['symbol']}")
            
            trade_success = self.trader.execute_trade_decision(token)
            
            if trade_success:
                self.last_successful_action = time.time()
            
        except Exception as e:
            self.logger.error(f"Trade cycle error: {e}")
            
            # Send error webhook but don't let it block the cycle
            try:
                if self.webhook:
                    self.webhook.send_error_update(str(e), "trade_cycle_error")
            except:
                pass  # Don't let webhook errors break the bot
            
            trade_success = False
        
        return trade_success
    
    def _attempt_token_creation(self):
        """Attempt to create a new token with clean logging"""
        if self.verbose:
            self.logger.info("🎨 Considering token creation...")
        
        try:
            # Use trader's token creation functionality
            success = self.trader.attempt_token_creation()
            
            if success:
                self.last_successful_action = time.time()
                # Refresh token list to include the new token
                if self.verbose:
                    self.logger.info("🔄 Refreshing tokens for new creation...")
                self.refresh_tokens()
            
            return success
            
        except Exception as e:
            self.logger.error(f"Token creation error: {e}")
            return False
    
    def send_heartbeat(self):
        """Send reliable heartbeat update with clean logging"""
        try:
            shared_stats = self.get_cache_stats()
            
            # Check for low balance alert (but don't spam)
            current_balance = self.get_avax_balance()
            min_trade_amount = self.config.get('minTradeAmount', 0.005)
            
            # Send heartbeat with enhanced data
            success = self.webhook.send_heartbeat(
                balance_info={}, # Not needed anymore, webhook calculates it
                token_count=len(self.tokens),
                extra_data={
                    "minTradeAmount": min_trade_amount,
                    "walletAddress": self.account.address,
                    "connectionHealth": {
                        "lastSuccessfulAction": self.last_successful_action,
                        "timeSinceLastSuccess": time.time() - self.last_successful_action,
                        "heartbeatFailures": self.heartbeat_failures,
                        "botRunning": self.is_running
                    },
                    "sharedManagerStats": {
                        "total_tokens": shared_stats.get("total_tokens", 0),
                        "registered_bots": shared_stats.get("registered_bots", 0),
                        "factory_queries_saved": shared_stats.get("factory_queries_saved", 0),
                        "next_refresh_minutes": shared_stats.get("next_refresh_in_minutes", 0)
                    }
                }
            )
            
            if success:
                self.heartbeat_failures = 0
                self.last_successful_action = time.time()
                self.last_heartbeat_time = time.time()
                
                # Send low balance alert if needed (separate from heartbeat)
                if current_balance < min_trade_amount * 2:
                    self.webhook.send_balance_alert(
                        balance=current_balance,
                        threshold=min_trade_amount * 2,
                        alert_type="low"
                    )
                
                return True
            else:
                self.heartbeat_failures += 1
                if self.verbose:
                    self.logger.warning(f"Heartbeat failed ({self.heartbeat_failures}/{self.max_heartbeat_failures})")
                return False
                
        except Exception as e:
            self.heartbeat_failures += 1
            self.logger.error(f"Heartbeat error: {e} ({self.heartbeat_failures}/{self.max_heartbeat_failures})")
            return False
    
    def _should_send_heartbeat(self, current_time):
        """Check if it's time to send a heartbeat"""
        return (current_time - self.last_heartbeat_time) >= self.heartbeat_interval
    
    def _handle_heartbeat_failure(self):
        """Handle persistent heartbeat failures with clean logging"""
        if self.heartbeat_failures >= self.max_heartbeat_failures:
            self.logger.warning("🚨 Multiple heartbeat failures - attempting recovery...")
            
            # Try force heartbeat
            if self.webhook and hasattr(self.webhook, 'force_heartbeat'):
                recovery_success = self.webhook.force_heartbeat()
                if recovery_success:
                    self.logger.success("✅ Heartbeat recovery successful!")
                    self.heartbeat_failures = 0
                    self.last_successful_action = time.time()
                    return True
                else:
                    self.logger.error("❌ Heartbeat recovery failed - bot may appear offline")
                    
                    # Send connection warning (limited frequency)
                    if self.connection_warnings_sent < 3:
                        self.connection_warnings_sent += 1
                        self.logger.warning("🔌 Connection health degraded")
            
            return False
        return True
    
    def print_session_summary(self):
        """Print comprehensive session summary with clean logging"""
        BotLogger.section(f"{self.display_name} Session Summary")
        BotLogger.system(f"👤 Account: {self.account.address}")
        
        # Get session metrics from webhook manager
        self.webhook.print_session_summary()
        
        # Additional bot-specific info
        BotLogger.system(f"🎯 Tokens Tracked: {len(self.tokens)}")
        BotLogger.system(f"💓 Heartbeat Failures: {self.heartbeat_failures}")
        BotLogger.system(f"🔌 Connection Warnings: {self.connection_warnings_sent}")
        
        # Show shared manager stats
        shared_stats = self.get_cache_stats()
        BotLogger.system(f"🌐 Shared Manager:")
        BotLogger.system(f"  🤖 Total bots: {shared_stats.get('registered_bots', 0)}")
        BotLogger.system(f"  🚀 Queries saved: {shared_stats.get('factory_queries_saved', 0)}")
        BotLogger.system(f"  ⏰ Next refresh: {shared_stats.get('next_refresh_in_minutes', 0):.1f}min")
    
    def run(self):
        """ENHANCED main trading loop with clean logging and reliable heartbeat"""
        try:
            self.is_running = True
            self.logger.success("🚀 Starting enhanced trading loop...")
            
            cycle_count = 0
            last_keepalive = 0
            keepalive_interval = 30   # Send keepalive every 30 seconds
            
            # Send initial heartbeat
            initial_heartbeat_success = self.send_heartbeat()
            if not initial_heartbeat_success:
                self.logger.warning("Initial heartbeat failed - bot may appear offline")
            
            while self.is_running:
                cycle_count += 1
                current_time = time.time()
                
                try:
                    # PRIORITY 1: Check and send heartbeat (time-based, not cycle-based)
                    if self._should_send_heartbeat(current_time):
                        heartbeat_success = self.send_heartbeat()
                        if not heartbeat_success:
                            self._handle_heartbeat_failure()
                    
                    # PRIORITY 2: Send keepalive if no recent heartbeat (backup connection)
                    elif (current_time - last_keepalive) >= keepalive_interval:
                        if hasattr(self.webhook, 'send_keepalive'):
                            keepalive_success = self.webhook.send_keepalive()
                            if keepalive_success:
                                last_keepalive = current_time
                    
                    # PRIORITY 3: Execute trading logic (don't let this block heartbeats)
                    trade_success = self.execute_trade_cycle()
                    
                    # Calculate sleep time based on personality
                    min_interval = self.config.get('minInterval', 15)
                    max_interval = self.config.get('maxInterval', 60)
                    sleep_time = random.uniform(min_interval, max_interval)
                    
                    if self.verbose:
                        self.logger.info(f"💤 Cycle {cycle_count} complete, sleeping {sleep_time:.1f}s")
                    
                    # Sleep with heartbeat monitoring
                    self._sleep_with_heartbeat_monitoring(sleep_time)
                    
                except KeyboardInterrupt:
                    self._handle_shutdown(cycle_count, "user")
                    break
                except Exception as e:
                    self.logger.error(f"Trade cycle error: {e}")
                    
                    # Send SPECIFIC error webhook with actual error details
                    try:
                        if self.webhook:
                            # Categorize the error type for better logging
                            error_str = str(e).lower()
                            if 'insufficient' in error_str or 'balance' in error_str:
                                error_type = "insufficient_funds"
                            elif 'timeout' in error_str or 'connection' in error_str:
                                error_type = "connection_error"
                            elif 'transaction' in error_str or 'gas' in error_str:
                                error_type = "transaction_error"
                            elif 'token' in error_str or 'contract' in error_str:
                                error_type = "contract_error"
                            else:
                                error_type = "trade_cycle_error"
                            
                            self.webhook.send_error_update(str(e), error_type)
                    except:
                        pass  # Don't let webhook errors break the bot
                    
                    trade_success = False
                    
        except KeyboardInterrupt:
            self._handle_shutdown(cycle_count, "user")
        except Exception as e:
            self._handle_shutdown(cycle_count, "crash", str(e))
        finally:
            self.is_running = False
        
        self.logger.info("👋 Trading loop ended")
    
    def _sleep_with_heartbeat_monitoring(self, total_sleep_time):
        """Sleep while monitoring for heartbeat needs"""
        start_sleep = time.time()
        check_interval = min(10, self.heartbeat_interval / 4)  # Check every 10s or 1/4 heartbeat interval
        
        while (time.time() - start_sleep) < total_sleep_time:
            # Sleep in small chunks
            remaining_sleep = total_sleep_time - (time.time() - start_sleep)
            actual_sleep = min(check_interval, remaining_sleep)
            
            if actual_sleep > 0:
                time.sleep(actual_sleep)
            
            # Check if heartbeat is needed during sleep
            if self._should_send_heartbeat(time.time()):
                heartbeat_success = self.send_heartbeat()
                if not heartbeat_success:
                    self._handle_heartbeat_failure()
                break
    
    def _handle_shutdown(self, cycle_count, reason, error_msg=None):
        """Handle bot shutdown gracefully with clean logging"""
        self.is_running = False
        session_metrics = self.get_session_metrics()
        
        shutdown_info = {
            "totalCycles": cycle_count,
            "sessionMetrics": session_metrics,
            "walletAddress": self.account.address,
            "heartbeatFailures": self.heartbeat_failures,
            "connectionWarnings": self.connection_warnings_sent
        }
        
        if reason == "user":
            BotLogger.system(f"🛑 {self.display_name} stopped by user", "shutdown")
            shutdown_info.update({
                "message": f"{self.display_name} is going offline (user requested)",
                "reason": "User initiated shutdown"
            })
        elif reason == "crash":
            BotLogger.system(f"💥 {self.display_name} crashed: {error_msg}", "error")
            shutdown_info.update({
                "message": f"Bot crashed: {error_msg}",
                "reason": "System error",
                "error": error_msg
            })
        
        # Send shutdown notification (with retries)
        shutdown_attempts = 0
        max_shutdown_attempts = 3
        
        while shutdown_attempts < max_shutdown_attempts:
            try:
                success = self.webhook.send_shutdown_notification(shutdown_info)
                if success:
                    break
                shutdown_attempts += 1
                if shutdown_attempts < max_shutdown_attempts:
                    time.sleep(2)  # Wait before retry
            except:
                shutdown_attempts += 1
                if shutdown_attempts < max_shutdown_attempts:
                    time.sleep(2)
        
        if shutdown_attempts >= max_shutdown_attempts:
            self.logger.warning("Failed to send shutdown notification")
        
        # Cleanup shared resources
        self.token_loader.cleanup()
        
        # Print final stats
        if self.verbose:
            self.print_session_summary()
            BotLogger.system(f"🔄 {self.display_name} Total Cycles: {cycle_count}")
            BotLogger.system(f"💓 {self.display_name} Heartbeat Failures: {self.heartbeat_failures}")


# Example usage for testing
if __name__ == "__main__":
    # Test bot initialization (won't actually run without config)
    BotLogger.system("Enhanced core bot class with clean logging loaded!", "success")
    BotLogger.system("Use main.py to run the bot with proper configuration.")