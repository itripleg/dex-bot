#!/usr/bin/env python3
"""
Core bot orchestration - the main TransparentVolumeBot class
Coordinates all bot components without doing the heavy lifting
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
from contracts.factory import FactoryContract
from contracts.token import TokenContract

class TransparentVolumeBot:
    """
    Main bot orchestration class - coordinates all components
    """
    
    def __init__(self, config, private_key_override=None, force_cache_refresh=False, verbose=False):
        """Initialize the bot with modular components"""
        print(f"🤖 TVB: 🚀 Initializing Transparent Volume Bot...")
        
        # Store configuration
        self.config = merge_config_with_defaults(config)
        self.verbose = verbose
        
        # Bot identity
        self.bot_name = self.config['name']
        self.display_name = self.config['displayName']
        
        print_config_summary(self.config)
        
        # Initialize Web3 and account
        self._setup_web3_and_account(private_key_override)
        
        # Initialize contract interfaces
        self._setup_contracts()
        
        # Initialize cache system
        self._setup_cache(force_cache_refresh)
        
        # Initialize trader
        self.trader = TokenTrader(
            w3=self.w3,
            account=self.account,
            factory_contract=self.factory_contract.contract,
            config=self.config,
            verbose=self.verbose
        )
        
        # Initialize webhook manager
        self.webhook = WebhookManager(
            bot_name=self.bot_name,
            display_name=self.display_name,
            avatar_url=self.config.get('avatarUrl', ''),
            webhook_url=self.config.get('webhookUrl'),
            bot_secret=self.config.get('botSecret'),
            phrases=self._extract_personality_phrases()
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
        print("🤖 TVB: 🌐 Setting up Web3 connection...")
        
        self.rpc_url = self.config['rpcUrl']
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to RPC: {self.rpc_url}")
        
        # Setup account
        private_key = get_private_key(self.config, private_key_override)
        self.account = Account.from_key(private_key)
        
        print(f"🤖 TVB: 💰 Account: {self.account.address}")
    
    def _setup_contracts(self):
        """Initialize contract interfaces"""
        print("🤖 TVB: 📜 Setting up contract interfaces...")
        
        self.factory_contract = FactoryContract(
            w3=self.w3,
            address=self.config['factoryAddress']
        )
        
        self.token_contract = TokenContract(w3=self.w3)
    
    def _setup_cache(self, force_refresh):
        """Initialize token cache system"""
        print("🤖 TVB: 💾 Setting up token cache...")
        
        cache_duration = self.config.get('cacheDurationHours', 6)
        self.cache = TokenCache(self.bot_name, cache_duration)
        
        if force_refresh:
            self.cache.force_refresh()
            print("🤖 TVB: 🔄 Forced cache refresh requested")
        
        self.token_loader = TokenLoader(
            factory_contract=self.factory_contract.contract,
            token_abi=self.token_contract.abi,
            w3=self.w3,
            cache=self.cache
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
        """Send initial startup webhook"""
        self.webhook.send_update("startup", {
            "message": f"{self.display_name} is now online and ready to trade!",
            "startingBalance": self.starting_balance,
            "sessionStarted": self.session_start_time,
            "tokensFound": len(self.tokens)
        })
    
    def get_avax_balance(self):
        """Get current AVAX balance"""
        balance_wei = self.w3.eth.get_balance(self.account.address)
        return float(self.w3.from_wei(balance_wei, 'ether'))
    
    def refresh_tokens(self):
        """Refresh token list (public method for external calls)"""
        print("🤖 TVB: 🔄 Refreshing token list...")
        self.tokens = self.token_loader.load_tokens_optimized()
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
        """Execute one complete trading cycle"""
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
            self.refresh_tokens()
            if not self.tokens:
                print("🤖 TVB: ⏭️ Still no tokens found, waiting...")
                return
        
        # Select random token and execute trade
        token = random.choice(self.tokens)
        success = self.trader.execute_trade_decision(token)
        
        if success and self.verbose:
            print(f"🤖 TVB: ✅ Trade cycle completed for {token['symbol']}")
    
    def _attempt_token_creation(self):
        """Attempt to create a new token"""
        print("🤖 TVB: 🎨 Considering token creation...")
        
        # For now, just send webhook (token creation can be implemented later)
        self.webhook.send_update("create_token", {
            "message": "Considering creating a new token...",
            "status": "planned"
        })
        
        # TODO: Implement actual token creation logic
        if self.verbose:
            print("🤖 TVB: 💡 Token creation logic not yet implemented")
    
    def send_heartbeat(self):
        """Send periodic heartbeat update"""
        current_balance = self.get_avax_balance()
        balance_change = current_balance - self.starting_balance
        cache_stats = self.get_cache_stats()
        
        self.webhook.send_update("heartbeat", {
            "message": f"{self.display_name} is active and trading",
            "currentBalance": current_balance,
            "balanceChange": balance_change,
            "tokensTracked": len(self.tokens),
            "cacheStats": {
                "cached_tokens": cache_stats["cached_tokens"],
                "hit_rate": f"{cache_stats.get('cache_hits', 0) / max(1, cache_stats.get('cache_hits', 0) + cache_stats.get('cache_misses', 0)) * 100:.1f}%"
            }
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
        """Handle bot shutdown gracefully"""
        if reason == "user":
            print(f"\n🤖 TVB: 🛑 Bot stopped by user")
            self.webhook.send_update("shutdown", {
                "message": f"{self.display_name} is going offline",
                "reason": "User initiated shutdown",
                "totalCycles": cycle_count,
                "finalBalance": self.get_avax_balance()
            })
        elif reason == "crash":
            print(f"\n🤖 TVB: 💥 Bot crashed: {error_msg}")
            self.webhook.send_update("error", {
                "message": f"Bot crashed: {error_msg}",
                "totalCycles": cycle_count,
                "finalBalance": self.get_avax_balance()
            })
        
        # Save cache before shutdown
        self.cache.save()
        
        # Print final stats
        if self.verbose:
            self.cache.print_stats()


# Example usage for testing
if __name__ == "__main__":
    # Test bot initialization (won't actually run without config)
    print("🤖 TVB: Core bot class loaded successfully!")
    print("Use main.py to run the bot with proper configuration.")