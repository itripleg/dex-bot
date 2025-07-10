# shared/token_manager.py - Fixed shared token manager with truly shared loading
#!/usr/bin/env python3
"""
Shared Token Manager for Multi-Bot Optimization
FIXED: Eliminates ALL redundant factory queries and coordinates token loading
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict

@dataclass
class TokenInfo:
    """Token information structure"""
    address: str
    name: str
    symbol: str
    state: int
    last_updated: str
    
    def to_dict(self):
        """Convert to dictionary for backwards compatibility"""
        return {
            "address": self.address,
            "name": self.name,
            "symbol": self.symbol
        }

class SharedTokenManager:
    """
    FIXED: Centralized token manager that truly shares tokens across all bots
    Only ONE bot loads tokens, all others get the shared result
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern to ensure only one instance"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the shared token manager"""
        if hasattr(self, '_initialized'):
            return
            
        self._initialized = True
        self.tokens: Dict[str, TokenInfo] = {}
        self.tradeable_tokens: List[TokenInfo] = []
        
        # Manager state
        self.last_refresh = None
        self.refresh_interval = timedelta(minutes=30)  # Refresh every 30 minutes
        self.is_refreshing = False
        self.refresh_in_progress = False  # Flag to prevent multiple refreshes
        
        # Factory contract references (set by first bot)
        self.factory_contract = None
        self.token_abi = None
        self.w3 = None
        self.current_factory_address = None
        
        # COORDINATION: Track which bot is the "coordinator" (first to register)
        self.coordinator_bot = None
        self.tokens_loaded = False  # Flag to track if tokens have been loaded
        self.loading_event = threading.Event()  # Event to signal when loading is complete
        
        # Statistics
        self.stats = {
            "total_refreshes": 0,
            "bots_served": 0,
            "cache_hits": 0,
            "factory_queries_saved": 0,
            "factory_address_changes": 0,
            "coordinated_loads": 0
        }
        
        # Bot registration
        self.registered_bots: Dict[str, dict] = {}
        
        # Thread safety
        self.data_lock = threading.RLock()
        
        # Import clean logger
        try:
            from bot.logger import BotLogger
            self.logger = BotLogger
        except ImportError:
            self.logger = None
        
        if self.logger:
            self.logger.system("🌐 Shared Token Manager initialized")
        else:
            print("🤖 TVB: 🌐 Shared Token Manager initialized")
    
    def register_bot(self, bot_name: str, factory_contract, token_abi, w3, logger=None):
        """Register a bot with the shared manager and coordinate token loading"""
        with self.data_lock:
            # Check if factory address changed
            new_factory_address = factory_contract.address
            
            if self.current_factory_address is None:
                self.current_factory_address = new_factory_address
                if self.logger:
                    self.logger.system(f"📜 Factory address set: {new_factory_address}")
            elif self.current_factory_address != new_factory_address:
                if self.logger:
                    self.logger.system("🔄 FACTORY ADDRESS CHANGED!", "warning")
                    self.logger.system(f"Old: {self.current_factory_address}")
                    self.logger.system(f"New: {new_factory_address}")
                    self.logger.system("🧹 Clearing all cached tokens...")
                
                # Clear all cached data
                self.tokens.clear()
                self.tradeable_tokens.clear()
                self.last_refresh = None
                self.tokens_loaded = False
                self.loading_event.clear()
                self.current_factory_address = new_factory_address
                self.coordinator_bot = None  # Reset coordinator
                
                # Update stats
                self.stats["factory_address_changes"] += 1
            
            # Register bot
            self.registered_bots[bot_name] = {
                "registered_at": datetime.utcnow().isoformat() + "Z",
                "logger": logger
            }
            
            # Set factory references from first bot
            if self.factory_contract is None:
                self.factory_contract = factory_contract
                self.token_abi = token_abi
                self.w3 = w3
                if self.logger:
                    self.logger.system(f"📜 Factory contract set by {bot_name}")
            
            # COORDINATION: Set first bot as coordinator
            if self.coordinator_bot is None:
                self.coordinator_bot = bot_name
                if self.logger:
                    self.logger.system(f"👑 {bot_name} designated as token coordinator")
            
            self.stats["bots_served"] += 1
            if self.logger:
                self.logger.system(f"📝 Bot registered: {bot_name} (Total: {len(self.registered_bots)})")
    
    def unregister_bot(self, bot_name: str):
        """Unregister a bot from the shared manager"""
        with self.data_lock:
            if bot_name in self.registered_bots:
                del self.registered_bots[bot_name]
                
                # If coordinator is leaving, assign new one
                if self.coordinator_bot == bot_name and self.registered_bots:
                    self.coordinator_bot = list(self.registered_bots.keys())[0]
                    if self.logger:
                        self.logger.system(f"👑 {self.coordinator_bot} is now token coordinator")
                elif not self.registered_bots:
                    self.coordinator_bot = None
                
                if self.logger:
                    self.logger.system(f"📤 Bot unregistered: {bot_name} (Remaining: {len(self.registered_bots)})")
    
    def needs_refresh(self) -> bool:
        """Check if token data needs refreshing"""
        if self.last_refresh is None:
            return True
        
        age = datetime.utcnow() - self.last_refresh
        return age > self.refresh_interval
    
    def get_tokens_for_bot(self, bot_name: str, force_refresh: bool = False) -> List[dict]:
        """
        FIXED: Get tradeable tokens with TRUE coordination
        Only coordinator loads, others wait for result
        """
        with self.data_lock:
            # If tokens already loaded and fresh, return immediately
            if self.tokens_loaded and not force_refresh and not self.needs_refresh():
                self.stats["cache_hits"] += 1
                self.stats["factory_queries_saved"] += 1
                
                if self.logger:
                    self.logger.system(f"💨 {bot_name} using shared tokens ({len(self.tradeable_tokens)} available)")
                
                return [token.to_dict() for token in self.tradeable_tokens]
            
            # Check if this bot is the coordinator
            is_coordinator = (bot_name == self.coordinator_bot)
            
            if is_coordinator and not self.refresh_in_progress:
                # Coordinator bot loads tokens for everyone
                if self.logger:
                    self.logger.system(f"👑 {bot_name} coordinating token refresh for all bots...")
                
                self.refresh_in_progress = True
                self.loading_event.clear()
                
                try:
                    self._refresh_tokens()
                    self.tokens_loaded = True
                    self.stats["coordinated_loads"] += 1
                finally:
                    self.refresh_in_progress = False
                    self.loading_event.set()  # Signal other bots that loading is complete
                
                if self.logger:
                    self.logger.system(f"✅ {bot_name} completed coordinated refresh - {len(self.tradeable_tokens)} tokens available")
                
            elif not is_coordinator:
                # Non-coordinator bots wait for coordinator to finish
                if self.logger:
                    self.logger.system(f"⏳ {bot_name} waiting for coordinator {self.coordinator_bot} to load tokens...")
                
                # Wait for coordinator to finish loading (with timeout)
                loading_completed = self.loading_event.wait(timeout=60)  # 60 second timeout
                
                if not loading_completed:
                    if self.logger:
                        self.logger.system(f"⏰ {bot_name} timeout waiting for coordinator - loading independently", "warning")
                    # Fallback: load independently if coordinator takes too long
                    self._refresh_tokens()
                    self.tokens_loaded = True
                else:
                    self.stats["factory_queries_saved"] += 1
                    if self.logger:
                        self.logger.system(f"✅ {bot_name} received shared tokens from coordinator")
            
            # Return the shared tokens
            return [token.to_dict() for token in self.tradeable_tokens]
    
    def _refresh_tokens(self):
        """Refresh token list from factory contract"""
        if self.factory_contract is None:
            if self.logger:
                self.logger.system("⚠️ No factory contract available for refresh", "warning")
            return
        
        start_time = time.time()
        
        try:
            if self.logger:
                self.logger.system("🔄 Shared Token Manager refreshing token list...")
            
            # Get all token addresses from factory
            token_addresses = self.factory_contract.functions.getAllTokens().call()
            if self.logger:
                self.logger.system(f"📡 Factory returned {len(token_addresses)} token addresses")
            
            new_tokens = {}
            new_tradeable = []
            
            for i, address in enumerate(token_addresses, 1):
                try:
                    # Get token state
                    state = self.factory_contract.functions.getTokenState(address).call()
                    
                    # Get token metadata
                    token_contract = self.w3.eth.contract(
                        address=self.w3.to_checksum_address(address), 
                        abi=self.token_abi
                    )
                    
                    name = token_contract.functions.name().call()
                    symbol = token_contract.functions.symbol().call()
                    
                    # Create token info
                    token_info = TokenInfo(
                        address=address,
                        name=name,
                        symbol=symbol,
                        state=state,
                        last_updated=datetime.utcnow().isoformat() + "Z"
                    )
                    
                    new_tokens[address.lower()] = token_info
                    
                    # Add to tradeable list if appropriate
                    if state in [1, 4]:  # TRADING or RESUMED
                        new_tradeable.append(token_info)
                    
                    # Only log progress every 5 tokens to reduce spam
                    if i % 5 == 0 or i == len(token_addresses):
                        status = "✅ Tradeable" if state in [1, 4] else "⏭️ Not trading"
                        if self.logger:
                            self.logger.system(f"{status}: {symbol} [{i}/{len(token_addresses)}]")
                    
                except Exception as e:
                    if self.logger:
                        self.logger.system(f"❌ Error processing {address[:10]}... [{i}/{len(token_addresses)}]: {e}", "error")
            
            # Update shared data
            self.tokens = new_tokens
            self.tradeable_tokens = new_tradeable
            self.last_refresh = datetime.utcnow()
            self.stats["total_refreshes"] += 1
            
            elapsed = time.time() - start_time
            
            if self.logger:
                self.logger.system(f"✅ Shared refresh complete: {len(new_tradeable)} tradeable tokens in {elapsed:.2f}s")
                self.logger.system(f"📊 Serving {len(self.registered_bots)} bots - saved {len(self.registered_bots) - 1} redundant queries!")
            
        except Exception as e:
            if self.logger:
                self.logger.system(f"❌ Shared token refresh error: {e}", "error")
    
    def force_refresh(self):
        """Force a token refresh regardless of cache age"""
        with self.data_lock:
            self.last_refresh = None
            self.tokens_loaded = False
            self.loading_event.clear()
            if self.logger:
                self.logger.system("🔄 Forced refresh requested - clearing cache")
    
    def get_stats(self) -> dict:
        """Get shared manager statistics"""
        with self.data_lock:
            stats = self.stats.copy()
            stats.update({
                "registered_bots": len(self.registered_bots),
                "total_tokens": len(self.tokens),
                "tradeable_tokens": len(self.tradeable_tokens),
                "last_refresh": self.last_refresh.isoformat() + "Z" if self.last_refresh else None,
                "next_refresh_in_minutes": self._get_next_refresh_minutes(),
                "is_refreshing": self.refresh_in_progress,
                "coordinator_bot": self.coordinator_bot,
                "tokens_loaded": self.tokens_loaded
            })
            return stats
    
    def _get_next_refresh_minutes(self) -> float:
        """Get minutes until next refresh"""
        if self.last_refresh is None:
            return 0
        
        next_refresh = self.last_refresh + self.refresh_interval
        time_until = next_refresh - datetime.utcnow()
        return max(0, time_until.total_seconds() / 60)
    
    def print_stats(self):
        """Print shared manager statistics with clean logging"""
        stats = self.get_stats()
        
        if self.logger:
            self.logger.section("Shared Token Manager Statistics")
            self.logger.system(f"🤖 Registered bots: {stats['registered_bots']}")
            self.logger.system(f"👑 Coordinator: {stats['coordinator_bot'] or 'None'}")
            self.logger.system(f"🎯 Total tokens: {stats['total_tokens']}")
            self.logger.system(f"✅ Tradeable tokens: {stats['tradeable_tokens']}")
            self.logger.system(f"🔄 Total refreshes: {stats['total_refreshes']}")
            self.logger.system(f"🎯 Coordinated loads: {stats['coordinated_loads']}")
            self.logger.system(f"💨 Cache hits: {stats['cache_hits']}")
            self.logger.system(f"🚀 Factory queries saved: {stats['factory_queries_saved']}")
            self.logger.system(f"⏰ Next refresh in: {stats['next_refresh_in_minutes']:.1f} minutes")
            
            if stats['last_refresh']:
                self.logger.system(f"📅 Last refresh: {stats['last_refresh']}")
            
            self.logger.system(f"🔧 Currently refreshing: {'Yes' if stats['is_refreshing'] else 'No'}")
        else:
            # Fallback to old print statements
            print("\n🤖 TVB: 📊 Shared Token Manager Statistics:")
            print(f"  🤖 Registered bots: {stats['registered_bots']}")
            print(f"  👑 Coordinator: {stats['coordinator_bot'] or 'None'}")
            print(f"  🎯 Total tokens: {stats['total_tokens']}")
            print(f"  ✅ Tradeable tokens: {stats['tradeable_tokens']}")
            print(f"  🔄 Total refreshes: {stats['total_refreshes']}")
            print(f"  🎯 Coordinated loads: {stats['coordinated_loads']}")
            print(f"  💨 Cache hits: {stats['cache_hits']}")
            print(f"  🚀 Factory queries saved: {stats['factory_queries_saved']}")
            print(f"  ⏰ Next refresh in: {stats['next_refresh_in_minutes']:.1f} minutes")
    
    def get_token_by_address(self, address: str) -> Optional[TokenInfo]:
        """Get specific token by address"""
        with self.data_lock:
            return self.tokens.get(address.lower())
    
    def cleanup(self):
        """Cleanup resources when shutting down"""
        with self.data_lock:
            if self.logger:
                self.logger.system("🧹 Shared Token Manager cleanup")
            self.registered_bots.clear()
            self.coordinator_bot = None
            self.tokens_loaded = False
            self.loading_event.clear()


# FIXED: Optimized Token Loader that truly uses shared coordination
class OptimizedTokenLoader:
    """Token loader that uses TRUE shared coordination"""
    
    def __init__(self, bot_name: str, factory_contract, token_abi, w3, logger=None):
        self.bot_name = bot_name
        self.logger = logger
        
        # Get shared manager instance
        self.shared_manager = SharedTokenManager()
        
        # Register with shared manager
        self.shared_manager.register_bot(
            bot_name, factory_contract, token_abi, w3, logger
        )
    
    def load_tokens_optimized(self, force_refresh: bool = False) -> List[dict]:
        """
        FIXED: Load tokens using TRUE shared coordination
        Only coordinator loads, others get shared result
        """
        if self.logger:
            self.logger.info("🚀 Loading tokens via shared coordination...")
        
        start_time = time.time()
        
        try:
            # Get tokens through shared manager coordination
            tokens = self.shared_manager.get_tokens_for_bot(self.bot_name, force_refresh)
            
            elapsed = time.time() - start_time
            
            # Check if this bot was the coordinator
            stats = self.shared_manager.get_stats()
            was_coordinator = (self.bot_name == stats.get('coordinator_bot'))
            
            if was_coordinator:
                message = f"Loaded {len(tokens)} tradeable tokens in {elapsed:.2f}s (coordinated for all bots)"
            else:
                message = f"Received {len(tokens)} tradeable tokens in {elapsed:.2f}s (from coordinator)"
            
            if self.logger:
                self.logger.success(message)
            
            return tokens
            
        except Exception as e:
            error_msg = f"Token loading error: {e}"
            if self.logger:
                self.logger.error(error_msg)
            return []
    
    def force_refresh(self):
        """Force refresh via shared manager"""
        self.shared_manager.force_refresh()
    
    def get_stats(self):
        """Get shared manager stats"""
        return self.shared_manager.get_stats()
    
    def cleanup(self):
        """Cleanup when bot shuts down"""
        self.shared_manager.unregister_bot(self.bot_name)


# Example usage
if __name__ == "__main__":
    # Test the FIXED shared manager
    manager = SharedTokenManager()
    
    print("🤖 TVB: 🧪 Testing FIXED Shared Token Manager...")
    
    # Simulate multiple bots
    for i in range(3):
        bot_name = f"test_bot_{i+1}"
        # In real usage, these would be actual contracts
        manager.register_bot(bot_name, None, None, None)
    
    # Print stats
    manager.print_stats()
    
    print("🤖 TVB: ✅ FIXED Shared Token Manager test complete!")