#!/usr/bin/env python3
"""
shared/simple_token_loader.py - Simple shared token loading
Save this as shared/simple_token_loader.py
"""

import threading
import time
from typing import List, Dict, Optional
from datetime import datetime, timedelta

class SimpleSharedTokenLoader:
    """Simple shared token loader - loads tokens once and shares across all bots"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the shared loader"""
        if hasattr(self, '_initialized'):
            return
            
        self._initialized = True
        self.tokens: List[Dict] = []
        self.last_loaded: Optional[datetime] = None
        self.refresh_interval = timedelta(minutes=30)  # Refresh every 30 minutes
        self.is_loading = False
        self.loading_event = threading.Event()
        
        # Contract references (set by first bot)
        self.factory_contract = None
        self.token_abi = None
        self.w3 = None
        self.factory_address = None
        
        # Statistics
        self.total_loads = 0
        self.bots_served = 0
        self.queries_saved = 0
        
        print("🌐 Simple Shared Token Loader initialized")
    
    def setup_contracts(self, factory_contract, token_abi, w3):
        """Setup contract references from the first bot"""
        with self._lock:
            if self.factory_contract is None:
                self.factory_contract = factory_contract
                self.token_abi = token_abi
                self.w3 = w3
                self.factory_address = factory_contract.address
                print(f"🌐 Shared loader: Factory set to {self.factory_address}")
            elif factory_contract.address != self.factory_address:
                print(f"⚠️  Warning: Different factory address detected!")
                print(f"   Current: {self.factory_address}")
                print(f"   New: {factory_contract.address}")
    
    def needs_refresh(self) -> bool:
        """Check if tokens need refreshing"""
        if self.last_loaded is None:
            return True
        return datetime.utcnow() - self.last_loaded > self.refresh_interval
    
    def get_tokens(self, bot_name: str) -> List[Dict]:
        """Get tokens for a bot - loads if needed, returns cached if fresh"""
        with self._lock:
            self.bots_served += 1
            
            # If tokens are fresh, return immediately
            if not self.needs_refresh() and self.tokens:
                self.queries_saved += 1
                print(f"🌐 {bot_name}: Using cached tokens ({len(self.tokens)} available)")
                return self.tokens.copy()
            
            # If someone else is loading, wait for them
            if self.is_loading:
                print(f"🌐 {bot_name}: Waiting for shared token load...")
                self._lock.release()  # Release lock while waiting
                loaded = self.loading_event.wait(timeout=60)  # Wait up to 60 seconds
                self._lock.acquire()  # Re-acquire lock
                
                if loaded and self.tokens:
                    self.queries_saved += 1
                    print(f"🌐 {bot_name}: Received shared tokens ({len(self.tokens)} available)")
                    return self.tokens.copy()
                else:
                    print(f"🌐 {bot_name}: Shared load timeout, loading independently")
            
            # This bot will load for everyone
            print(f"🌐 {bot_name}: Loading tokens for all bots...")
            return self._load_tokens()
    
    def _load_tokens(self) -> List[Dict]:
        """Internal method to actually load tokens"""
        if not self.factory_contract:
            print("❌ Shared loader: No factory contract available")
            return []
        
        self.is_loading = True
        self.loading_event.clear()
        start_time = time.time()
        
        try:
            # Get all token addresses
            token_addresses = self.factory_contract.functions.getAllTokens().call()
            print(f"🌐 Shared loader: Factory returned {len(token_addresses)} token addresses")
            
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
                        
                        # Only log every 5th token to reduce spam
                        if i % 5 == 0 or i == len(token_addresses):
                            print(f"🌐 ✅ {symbol} [{i}/{len(token_addresses)}]")
                    
                except Exception as e:
                    print(f"🌐 ❌ Error processing token {i}: {e}")
            
            # Update shared state
            self.tokens = tradeable_tokens
            self.last_loaded = datetime.utcnow()
            self.total_loads += 1
            
            elapsed = time.time() - start_time
            print(f"🌐 ✅ Shared load complete: {len(tradeable_tokens)} tradeable tokens in {elapsed:.2f}s")
            print(f"🌐 📊 Serving {self.bots_served} bots - saved {self.queries_saved} redundant queries!")
            
            return tradeable_tokens.copy()
            
        except Exception as e:
            print(f"🌐 ❌ Shared token load error: {e}")
            return []
        finally:
            self.is_loading = False
            self.loading_event.set()  # Signal that loading is complete
    
    def force_refresh(self):
        """Force a refresh of tokens"""
        with self._lock:
            self.last_loaded = None
            print("🌐 Forced token refresh requested")
    
    def get_stats(self) -> Dict:
        """Get loader statistics"""
        return {
            "total_tokens": len(self.tokens),
            "last_loaded": self.last_loaded.isoformat() + "Z" if self.last_loaded else None,
            "next_refresh_minutes": self._get_next_refresh_minutes(),
            "total_loads": self.total_loads,
            "bots_served": self.bots_served,
            "queries_saved": self.queries_saved,
            "factory_address": self.factory_address
        }
    
    def _get_next_refresh_minutes(self) -> float:
        """Get minutes until next refresh"""
        if self.last_loaded is None:
            return 0
        
        next_refresh = self.last_loaded + self.refresh_interval
        time_until = next_refresh - datetime.utcnow()
        return max(0, time_until.total_seconds() / 60)
    
    def print_stats(self):
        """Print statistics"""
        stats = self.get_stats()
        print(f"\n🌐 Shared Token Loader Stats:")
        print(f"  🎯 Total tokens: {stats['total_tokens']}")
        print(f"  🤖 Bots served: {stats['bots_served']}")
        print(f"  🚀 Queries saved: {stats['queries_saved']}")
        print(f"  🔄 Total loads: {stats['total_loads']}")
        print(f"  ⏰ Next refresh: {stats['next_refresh_minutes']:.1f} minutes")
        
        if stats['queries_saved'] > 0:
            efficiency = (stats['queries_saved'] / stats['bots_served']) * 100
            print(f"  📈 Efficiency: {efficiency:.1f}% reduction in factory calls")


# Global instance
_shared_loader = SimpleSharedTokenLoader()

def get_shared_tokens(bot_name: str, factory_contract, token_abi, w3) -> List[Dict]:
    """Simple function to get shared tokens"""
    # Setup contracts if needed
    _shared_loader.setup_contracts(factory_contract, token_abi, w3)
    
    # Get tokens
    return _shared_loader.get_tokens(bot_name)

def force_refresh_shared_tokens():
    """Force refresh of shared tokens"""
    _shared_loader.force_refresh()

def get_shared_loader_stats() -> Dict:
    """Get shared loader statistics"""
    return _shared_loader.get_stats()

def print_shared_loader_stats():
    """Print shared loader statistics"""
    _shared_loader.print_stats()


# Example usage
if __name__ == "__main__":
    print("🌐 Simple Shared Token Loader")
    print("✅ Ready to eliminate redundant token loading!")