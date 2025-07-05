# shared/token_manager.py
#!/usr/bin/env python3
"""
Shared Token Manager for Multi-Bot Optimization
Centralizes token list management to avoid redundant factory queries
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
    Centralized token manager that multiple bots can share
    Reduces redundant factory contract calls
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
        
        # Factory contract references (set by first bot)
        self.factory_contract = None
        self.token_abi = None
        self.w3 = None
        
        # Statistics
        self.stats = {
            "total_refreshes": 0,
            "bots_served": 0,
            "cache_hits": 0,
            "factory_queries_saved": 0
        }
        
        # Bot registration
        self.registered_bots: Dict[str, dict] = {}
        
        # Thread safety
        self.data_lock = threading.RLock()
        
        print("🤖 TVB: 🌐 Shared Token Manager initialized")
    
    def register_bot(self, bot_name: str, factory_contract, token_abi, w3, logger=None):
        """Register a bot with the shared manager"""
        with self.data_lock:
            self.registered_bots[bot_name] = {
                "registered_at": datetime.utcnow().isoformat() + "Z",
                "logger": logger
            }
            
            # Set factory references from first bot
            if self.factory_contract is None:
                self.factory_contract = factory_contract
                self.token_abi = token_abi
                self.w3 = w3
                print(f"🤖 TVB: 📜 Factory contract set by {bot_name}")
            
            self.stats["bots_served"] += 1
            print(f"🤖 TVB: 📝 Bot registered: {bot_name} (Total: {len(self.registered_bots)})")
    
    def unregister_bot(self, bot_name: str):
        """Unregister a bot from the shared manager"""
        with self.data_lock:
            if bot_name in self.registered_bots:
                del self.registered_bots[bot_name]
                print(f"🤖 TVB: 📤 Bot unregistered: {bot_name} (Remaining: {len(self.registered_bots)})")
    
    def needs_refresh(self) -> bool:
        """Check if token data needs refreshing"""
        if self.last_refresh is None:
            return True
        
        age = datetime.utcnow() - self.last_refresh
        return age > self.refresh_interval
    
    def get_tokens_for_bot(self, bot_name: str, force_refresh: bool = False) -> List[dict]:
        """Get tradeable tokens for a specific bot"""
        with self.data_lock:
            # Check if refresh needed
            if force_refresh or self.needs_refresh():
                if not self.is_refreshing:
                    self._refresh_tokens()
                else:
                    # Wait for ongoing refresh to complete
                    self._wait_for_refresh()
            else:
                self.stats["cache_hits"] += 1
                self.stats["factory_queries_saved"] += 1
                print(f"🤖 TVB: 💨 {bot_name} using cached tokens ({len(self.tradeable_tokens)} available)")
            
            # Return tradeable tokens as dict for backwards compatibility
            return [token.to_dict() for token in self.tradeable_tokens]
    
    def _refresh_tokens(self):
        """Refresh token list from factory contract"""
        if self.factory_contract is None:
            print("🤖 TVB: ⚠️ No factory contract available for refresh")
            return
        
        self.is_refreshing = True
        start_time = time.time()
        
        try:
            print("🤖 TVB: 🔄 Shared Token Manager refreshing token list...")
            
            # Get all token addresses from factory
            token_addresses = self.factory_contract.functions.getAllTokens().call()
            print(f"🤖 TVB: 📡 Factory returned {len(token_addresses)} token addresses")
            
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
                        status = "✅ Tradeable"
                    else:
                        status = "⏭️ Not trading"
                    
                    if i % 10 == 0 or i == len(token_addresses):
                        print(f"🤖 TVB: {status}: {symbol} ({name}) [{i}/{len(token_addresses)}]")
                    
                except Exception as e:
                    print(f"🤖 TVB: ❌ Error processing {address[:10]}... [{i}/{len(token_addresses)}]: {e}")
            
            # Update shared data
            self.tokens = new_tokens
            self.tradeable_tokens = new_tradeable
            self.last_refresh = datetime.utcnow()
            self.stats["total_refreshes"] += 1
            
            elapsed = time.time() - start_time
            print(f"🤖 TVB: ✅ Shared refresh complete: {len(new_tradeable)} tradeable tokens in {elapsed:.2f}s")
            print(f"🤖 TVB: 📊 Serving {len(self.registered_bots)} bots - saved {len(self.registered_bots) - 1} redundant queries!")
            
        except Exception as e:
            print(f"🤖 TVB: ❌ Shared token refresh error: {e}")
        finally:
            self.is_refreshing = False
    
    def _wait_for_refresh(self, timeout: int = 30):
        """Wait for ongoing refresh to complete"""
        start_time = time.time()
        while self.is_refreshing and (time.time() - start_time) < timeout:
            time.sleep(0.5)
        
        if self.is_refreshing:
            print("🤖 TVB: ⏰ Timeout waiting for token refresh")
    
    def force_refresh(self):
        """Force a token refresh regardless of cache age"""
        with self.data_lock:
            self.last_refresh = None
            self._refresh_tokens()
    
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
                "is_refreshing": self.is_refreshing
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
        """Print shared manager statistics"""
        stats = self.get_stats()
        
        print("\n🤖 TVB: 📊 Shared Token Manager Statistics:")
        print(f"  🤖 Registered bots: {stats['registered_bots']}")
        print(f"  🎯 Total tokens: {stats['total_tokens']}")
        print(f"  ✅ Tradeable tokens: {stats['tradeable_tokens']}")
        print(f"  🔄 Total refreshes: {stats['total_refreshes']}")
        print(f"  💨 Cache hits: {stats['cache_hits']}")
        print(f"  🚀 Factory queries saved: {stats['factory_queries_saved']}")
        print(f"  ⏰ Next refresh in: {stats['next_refresh_in_minutes']:.1f} minutes")
        
        if stats['last_refresh']:
            print(f"  📅 Last refresh: {stats['last_refresh']}")
        
        print(f"  🔧 Currently refreshing: {'Yes' if stats['is_refreshing'] else 'No'}")
    
    def get_token_by_address(self, address: str) -> Optional[TokenInfo]:
        """Get specific token by address"""
        with self.data_lock:
            return self.tokens.get(address.lower())
    
    def cleanup(self):
        """Cleanup resources when shutting down"""
        with self.data_lock:
            print("🤖 TVB: 🧹 Shared Token Manager cleanup")
            self.registered_bots.clear()


# Optimized Token Loader that uses shared manager
class OptimizedTokenLoader:
    """Token loader that uses the shared token manager"""
    
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
        """Load tokens using shared manager"""
        if self.logger:
            self.logger.info("🚀 Loading tokens via shared manager...")
        else:
            print(f"🤖 TVB: 🚀 {self.bot_name} loading tokens via shared manager...")
        
        start_time = time.time()
        
        try:
            tokens = self.shared_manager.get_tokens_for_bot(self.bot_name, force_refresh)
            
            elapsed = time.time() - start_time
            message = f"Loaded {len(tokens)} tradeable tokens in {elapsed:.2f}s (shared cache)"
            
            if self.logger:
                self.logger.success(message)
            else:
                print(f"🤖 TVB: ✅ {self.bot_name}: {message}")
            
            return tokens
            
        except Exception as e:
            error_msg = f"Token loading error: {e}"
            if self.logger:
                self.logger.error(error_msg)
            else:
                print(f"🤖 TVB: ❌ {self.bot_name}: {error_msg}")
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
    # Test the shared manager
    manager = SharedTokenManager()
    
    print("🤖 TVB: 🧪 Testing Shared Token Manager...")
    
    # Simulate multiple bots
    for i in range(3):
        bot_name = f"test_bot_{i+1}"
        # In real usage, these would be actual contracts
        manager.register_bot(bot_name, None, None, None)
    
    # Print stats
    manager.print_stats()
    
    print("🤖 TVB: ✅ Shared Token Manager test complete!")