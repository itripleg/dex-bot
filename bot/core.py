#!/usr/bin/env python3
"""
Core bot orchestration - the main TransparentVolumeBot class
Coordinates all bot components without doing the heavy lifting
Enhanced with real-time balance and token tracking
"""

import time
import random
from datetime import datetime
from web3 import Web3
from eth_account import Account

from bot.config import get_private_key, merge_config_with_defaults, print_config_summary
from bot.cache import TokenCache, TokenLoader
from bot.trader import TokenTrader
from bot.webhook import WebhookManager
from bot.logger import BotLogger
from contracts.factory import FactoryContract
from contracts.token import TokenContract

class TransparentVolumeBot:
    """
    Main bot orchestration class - coordinates all components
    Enhanced with real-time balance and token tracking
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
        
        # Initialize Web3 and account
        self._setup_web3_and_account(private_key_override)
        
        # Initialize contract interfaces
        self._setup_contracts()
        
        # Initialize cache system
        self._setup_cache(force_cache_refresh)
        
        # Initialize webhook manager with balance callback and bio
        self.webhook = WebhookManager(
            bot_name=self.bot_name,
            display_name=self.display_name,
            avatar_url=self.config.get('avatarUrl', ''),
            webhook_url=self.config.get('webhookUrl'),
            bot_secret=self.config.get('botSecret'),
            phrases=self._extract_personality_phrases(),
            bio=self.config.get('bio'),
            get_balance_callback=self.get_avax_balance
        )
        
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
        self.session_start_time = datetime.utcnow().isoformat() + "Z"
        self.starting_balance = self.get_avax_balance()
        
        # Load tokens
        self._load_tokens()
        
        # Send startup notification
        self._send_startup_notification()
        
        print(f"🤖 TVB: ✅ Bot '{self.display_name}' initialized successfully!")
    
    def _setup_web3_and_account(self, private_key_override):
        """Initialize Web3 connection and account"""
        self.logger.info("🌐 Setting up Web3 connection...")
        
        self.rpc_url = self.config['rpcUrl']
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to RPC: {self.rpc_url}")
        
        # Setup account - pass bot name for environment lookup
        private_key = get_private_key(self.config, private_key_override, self.bot_name)
        self.account = Account.from_key(private_key)
        
        self.logger.success(f"Account: {self.account.address}")
    
    def _setup_contracts(self):
        """Initialize contract interfaces"""
        self.logger.info("📜 Setting up contract interfaces...")
        
        self.factory_contract = FactoryContract(
            w3=self.w3,
            address=self.config['factoryAddress']
        )
        
        self.token_contract = TokenContract(w3=self.w3)
    
    def _setup_cache(self, force_refresh):
        """Initialize token cache system"""
        self.logger.info("💾 Setting up token cache...")
        
        cache_duration = self.config.get('cacheDurationHours', 6)
        self.cache = TokenCache(self.bot_name, cache_duration)
        
        if force_refresh:
            self.cache.force_refresh()
            self.logger.info("🔄 Forced cache refresh requested")
        
        self.token_loader = TokenLoader(
            factory_contract=self.factory_contract.contract,
            token_abi=self.token_contract.abi,
            w3=self.w3,
            cache=self.cache,
            logger=self.logger
        )
    
    def _extract_personality_phrases(self):
        """Extract personality phrases from config"""
        return {
            "buy": self.config.get("buyPhrases", []),
            "sell": self.config.get("sellPhrases", []),
            "create": self.config.get("createPhrases", []),
            "error": self.config.get("errorPhrases", [])
        }
    
    def _load_tokens(self):
        """Load tradeable tokens using cache system"""
        print("🤖 TVB: 🔍 Loading tradeable tokens...")
        self.tokens = self.token_loader.load_tokens_optimized()
        print(f"🤖 TVB: ✅ Loaded {len(self.tokens)} tradeable tokens")
    
    def _send_startup_notification(self):
        """Send enhanced startup notification"""
        startup_info = {
            "message": f"{self.display_name} is now online and ready to trade!",
            "startingBalance": self.starting_balance,
            "sessionStarted": self.session_start_time,
            "tokensFound": len(self.tokens),
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
    
    def refresh_tokens(self):
        """Refresh token list (public method for external calls)"""
        print("🤖 TVB: 🔄 Refreshing token list...")
        
        # Send webhook notification
        self.webhook.send_update("token_refresh_start", {
            "message": "Refreshing token list...",
            "previousTokenCount": len(self.tokens)
        })
        
        self.tokens = self.token_loader.load_tokens_optimized()
        
        # Send completion webhook
        self.webhook.send_update("token_refresh_complete", {
            "message": f"Token refresh complete: {len(self.tokens)} tokens available",
            "tokensFound": len(self.tokens)
        })
        
        print(f"🤖 TVB: ✅ Refreshed: {len(self.tokens)} tradeable tokens")
    
    def force_cache_refresh(self):
        """Force a complete cache refresh"""
        self.cache.force_refresh()
        self.refresh_tokens()
        self.cache.save()
    
    def get_cache_stats(self):
        """Get cache performance statistics"""
        return self.cache.get_stats()
    
    def execute_trade_cycle(self):
        """Execute one complete trading cycle with enhanced webhook reporting"""
        if self.verbose:
            print(f"\n🤖 TVB: --- Starting Trade Cycle ---")
        
        # Check if we should create a token
        create_chance = self.config.get('createTokenChance', 0.02)
        if random.random() < create_chance:
            self._attempt_token_creation()
            return
        
        # Check if we have tokens to trade
        if not self.tokens:
            print("🤖 TVB: ⏭️ No tradeable tokens, refreshing list...")
            self.webhook.send_update("token_refresh", {
                "message": "No tradeable tokens found, refreshing list...",
                "reason": "empty_token_list"
            })
            self.refresh_tokens()
            if not self.tokens:
                print("🤖 TVB: ⏭️ Still no tokens found, waiting...")
                self.webhook.send_update("no_tokens", {
                    "message": "Still no tradeable tokens found after refresh",
                    "tokensFound": 0
                })
                return
        
        # Select random token and execute trade
        token = random.choice(self.tokens)
        
        # Send cycle start webhook with selected token
        self.webhook.send_update("cycle_start", {
            "message": f"Starting trade cycle for {token['symbol']}",
            "selectedToken": {
                "address": token['address'],
                "symbol": token['symbol'],
                "name": token.get('name', token['symbol'])
            },
            "totalTokens": len(self.tokens)
        })
        
        success = self.trader.execute_trade_decision(token)
        
        if success and self.verbose:
            print(f"🤖 TVB: ✅ Trade cycle completed for {token['symbol']}")
        
        # Send cycle completion webhook
        self.webhook.send_update("cycle_complete", {
            "message": f"Trade cycle completed for {token['symbol']}",
            "success": success,
            "tokenSymbol": token['symbol'],
            "tokenAddress": token['address']
        })
    
    def _attempt_token_creation(self):
        """Attempt to create a new token with webhook updates"""
        print("🤖 TVB: 🎨 Considering token creation...")
        
        current_balance = self.get_avax_balance()
        min_creation_balance = 0.1  # Require at least 0.1 AVAX for token creation
        
        if current_balance < min_creation_balance:
            self.webhook.send_update("creation_cancelled", {
                "message": f"Insufficient AVAX for token creation ({current_balance:.4f} < {min_creation_balance})",
                "reason": "insufficient_balance",
                "currentBalance": current_balance,
                "requiredBalance": min_creation_balance
            })
            return
        
        # For now, just send webhook (token creation can be implemented later)
        self.webhook.send_update("create_token", {
            "message": "Considering creating a new token...",
            "status": "planned",
            "currentBalance": current_balance
        })
        
        # TODO: Implement actual token creation logic
        if self.verbose:
            print("🤖 TVB: 💡 Token creation logic not yet implemented")
    
    def send_heartbeat(self):
        """Send periodic heartbeat update with enhanced balance info"""
        current_balance = self.get_avax_balance()
        balance_change = current_balance - self.starting_balance
        cache_stats = self.get_cache_stats()
        
        # Check for low balance alert
        min_trade_amount = self.config.get('minTradeAmount', 0.005)
        if current_balance < min_trade_amount * 2:
            self.webhook.send_balance_alert(
                balance=current_balance,
                threshold=min_trade_amount * 2,
                alert_type="low"
            )
        
        # Calculate session duration
        session_start = datetime.fromisoformat(self.session_start_time.replace('Z', ''))
        session_duration_minutes = int((datetime.utcnow() - session_start).total_seconds() / 60)
        
        # Send enhanced heartbeat with detailed balance info
        self.webhook.send_heartbeat({
            "current": current_balance,
            "change": balance_change,
            "starting": self.starting_balance,
            "percentage_change": (balance_change / self.starting_balance * 100) if self.starting_balance > 0 else 0
        }, len(self.tokens), {
            "minTradeAmount": min_trade_amount,
            "cacheStats": {
                "cached_tokens": cache_stats["cached_tokens"],
                "hit_rate": f"{cache_stats.get('cache_hits', 0) / max(1, cache_stats.get('cache_hits', 0) + cache_stats.get('cache_misses', 0)) * 100:.1f}%"
            },
            "session_duration_minutes": session_duration_minutes
        })
    
    def run(self):
        """Main bot execution loop"""
        print(f"\n🤖 TVB: 🚀 Starting {self.display_name} trading loop...")
        print(f"🤖 TVB: Target webhook: {self.config.get('webhookUrl', 'None')}")
        
        cycle_count = 0
        last_heartbeat = time.time()
        last_token_refresh = time.time()
        
        try:
            while True:
                cycle_count += 1
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                if self.verbose:
                    print(f"\n🤖 TVB: [{timestamp}] 🔄 Cycle #{cycle_count}")
                
                # Execute trading cycle
                self.execute_trade_cycle()
                
                # Send heartbeat every 5 minutes
                if time.time() - last_heartbeat > 300:  # 5 minutes
                    self.send_heartbeat()
                    last_heartbeat = time.time()
                
                # Refresh token list every 30 minutes
                if time.time() - last_token_refresh > 1800:  # 30 minutes
                    self.refresh_tokens()
                    last_token_refresh = time.time()
                
                # Calculate delay based on personality
                min_interval = self.config.get('minInterval', 15)
                max_interval = self.config.get('maxInterval', 60)
                delay = random.randint(min_interval, max_interval)
                
                if self.verbose:
                    print(f"🤖 TVB: ⏳ Waiting {delay}s until next cycle...")
                
                time.sleep(delay)
                
        except KeyboardInterrupt:
            self._handle_shutdown(cycle_count, "user")
        except Exception as e:
            self._handle_shutdown(cycle_count, "crash", str(e))
        finally:
            print(f"🤖 TVB: 👋 Bot session ended after {cycle_count} cycles")
    
    def _handle_shutdown(self, cycle_count, reason, error_msg=None):
        """Handle bot shutdown gracefully with enhanced reporting"""
        final_balance = self.get_avax_balance()
        total_pnl = final_balance - self.starting_balance
        pnl_percentage = (total_pnl / self.starting_balance * 100) if self.starting_balance > 0 else 0
        
        # Calculate session duration
        session_start = datetime.fromisoformat(self.session_start_time.replace('Z', ''))
        session_duration = datetime.utcnow() - session_start
        session_hours = session_duration.total_seconds() / 3600
        
        shutdown_info = {
            "totalCycles": cycle_count,
            "finalBalance": final_balance,
            "startingBalance": self.starting_balance,
            "totalPnL": total_pnl,
            "pnlPercentage": pnl_percentage,
            "sessionDurationHours": session_hours,
            "sessionStarted": self.session_start_time
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
        
        # Save cache before shutdown
        self.cache.save()
        
        # Print final stats
        if self.verbose:
            print(f"🤖 TVB: 📊 Final Session Stats:")
            print(f"  💰 Starting Balance: {self.starting_balance:.6f} AVAX")
            print(f"  💰 Final Balance: {final_balance:.6f} AVAX") 
            print(f"  📈 Total P&L: {total_pnl:+.6f} AVAX ({pnl_percentage:+.2f}%)")
            print(f"  🔄 Total Cycles: {cycle_count}")
            print(f"  ⏰ Session Duration: {session_hours:.2f} hours")
            self.cache.print_stats()


# Example usage for testing
if __name__ == "__main__":
    # Test bot initialization (won't actually run without config)
    print("🤖 TVB: Core bot class loaded successfully!")
    print("Use main.py to run the bot with proper configuration.")