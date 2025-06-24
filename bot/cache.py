#!/usr/bin/env python3
"""
Token cache management for fast bot startup
Maintains local JSON cache of token metadata
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

class TokenCache:
    """Manages local token metadata cache for fast startup"""
    
    def __init__(self, bot_name, cache_duration_hours=6):
        self.bot_name = bot_name
        self.cache_duration = timedelta(hours=cache_duration_hours)
        self.cache_file = f"{bot_name}_token_cache.json"
        self.cache_data = self._load_cache()
        
    def _load_cache(self):
        """Load existing cache from file"""
        cache_path = Path(self.cache_file)
        
        if cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    cache = json.load(f)
                    token_count = len(cache.get('tokens', {}))
                    print(f"🤖 TVB: 💾 Loaded cache with {token_count} tokens from {self.cache_file}")
                    return cache
            except (json.JSONDecodeError, IOError) as e:
                print(f"🤖 TVB: ⚠️  Cache file corrupt, creating new one: {e}")
        
        # Create new cache structure
        return {
            "version": "1.0",
            "bot_name": self.bot_name,
            "created": datetime.utcnow().isoformat() + "Z",
            "last_updated": None,
            "tokens": {},
            "stats": {
                "total_refreshes": 0,
                "last_full_refresh": None,
                "cache_hits": 0,
                "cache_misses": 0
            }
        }
    
    def save(self):
        """Save current cache to file"""
        try:
            self.cache_data["last_updated"] = datetime.utcnow().isoformat() + "Z"
            self.cache_data["stats"]["total_refreshes"] += 1
            
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache_data, f, indent=2)
            
            token_count = len(self.cache_data['tokens'])
            print(f"🤖 TVB: 💾 Cache saved: {token_count} tokens to {self.cache_file}")
            
        except IOError as e:
            print(f"🤖 TVB: ❌ Failed to save cache: {e}")
    
    def is_fresh(self):
        """Check if cache is still within the freshness window"""
        last_updated = self.cache_data.get("last_updated")
        if not last_updated:
            return False
        
        try:
            updated_time = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
            now = datetime.utcnow().replace(tzinfo=updated_time.tzinfo)
            age = now - updated_time
            
            is_fresh = age < self.cache_duration
            if not is_fresh:
                print(f"🤖 TVB: ⏰ Cache is {age} old (max: {self.cache_duration})")
            
            return is_fresh
            
        except (ValueError, TypeError):
            return False
    
    def get_token(self, address):
        """Get cached token info by address"""
        token = self.cache_data["tokens"].get(address.lower())
        if token:
            self.cache_data["stats"]["cache_hits"] += 1
        else:
            self.cache_data["stats"]["cache_misses"] += 1
        return token
    
    def store_token(self, address, name, symbol, state=None, extra_data=None):
        """Store token information in cache"""
        token_data = {
            "address": address,
            "name": name,
            "symbol": symbol,
            "state": state,
            "cached_at": datetime.utcnow().isoformat() + "Z"
        }
        
        if extra_data:
            token_data.update(extra_data)
        
        self.cache_data["tokens"][address.lower()] = token_data
    
    def get_all_tokens(self):
        """Get all cached tokens as a list"""
        return list(self.cache_data["tokens"].values())
    
    def get_tradeable_tokens(self):
        """Get only tokens marked as tradeable (state 1 or 4)"""
        tradeable = []
        for token in self.cache_data["tokens"].values():
            state = token.get("state")
            if state in [1, 4]:  # TRADING or RESUMED
                tradeable.append(token)
        return tradeable
    
    def mark_full_refresh(self):
        """Mark that a full refresh was completed"""
        self.cache_data["stats"]["last_full_refresh"] = datetime.utcnow().isoformat() + "Z"
    
    def clear_stale_tokens(self, current_addresses):
        """Remove tokens that no longer exist in the factory"""
        current_lower = {addr.lower() for addr in current_addresses}
        cached_addresses = set(self.cache_data["tokens"].keys())
        
        stale_addresses = cached_addresses - current_lower
        for addr in stale_addresses:
            del self.cache_data["tokens"][addr]
        
        if stale_addresses:
            print(f"🤖 TVB: 🧹 Removed {len(stale_addresses)} stale tokens from cache")
    
    def force_refresh(self):
        """Force cache to be considered stale"""
        self.cache_data["last_updated"] = None
        print("🤖 TVB: 🔄 Cache marked for forced refresh")
    
    def get_stats(self):
        """Get cache performance statistics"""
        stats = self.cache_data["stats"].copy()
        stats.update({
            "cached_tokens": len(self.cache_data["tokens"]),
            "is_fresh": self.is_fresh(),
            "cache_file": self.cache_file,
            "last_updated": self.cache_data.get("last_updated", "Never"),
            "age_hours": self._get_age_hours()
        })
        return stats
    
    def _get_age_hours(self):
        """Get cache age in hours"""
        last_updated = self.cache_data.get("last_updated")
        if not last_updated:
            return float('inf')
        
        try:
            updated_time = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
            now = datetime.utcnow().replace(tzinfo=updated_time.tzinfo)
            age = now - updated_time
            return age.total_seconds() / 3600
        except:
            return float('inf')
    
    def print_stats(self):
        """Print cache statistics in a readable format"""
        stats = self.get_stats()
        print("\n🤖 TVB: 📊 Cache Statistics:")
        print(f"  📁 File: {stats['cache_file']}")
        print(f"  🗃️  Cached tokens: {stats['cached_tokens']}")
        print(f"  ⏰ Age: {stats['age_hours']:.1f} hours")
        print(f"  ✅ Fresh: {'Yes' if stats['is_fresh'] else 'No'}")
        print(f"  🎯 Cache hits: {stats['cache_hits']}")
        print(f"  ❌ Cache misses: {stats['cache_misses']}")
        
        if stats['cache_hits'] + stats['cache_misses'] > 0:
            hit_rate = stats['cache_hits'] / (stats['cache_hits'] + stats['cache_misses']) * 100
            print(f"  📈 Hit rate: {hit_rate:.1f}%")


class TokenLoader:
    """Handles token loading with cache integration"""
    
    def __init__(self, factory_contract, token_abi, w3, cache, logger=None):
        self.factory_contract = factory_contract
        self.token_abi = token_abi
        self.w3 = w3
        self.cache = cache
        self.logger = logger
    
    def load_tokens_optimized(self):
        """Load tokens with cache optimization"""
        if self.logger:
            self.logger.info("🚀 Starting optimized token loading...")
        else:
            print("🤖 TVB: 🚀 Starting optimized token loading...")
        
        start_time = time.time()
        
        try:
            # Get all token addresses from factory
            token_addresses = self.factory_contract.functions.getAllTokens().call()
            if self.logger:
                self.logger.info(f"📡 Factory returned {len(token_addresses)} token addresses")
            else:
                print(f"🤖 TVB: 📡 Factory returned {len(token_addresses)} token addresses")
            
            # Clean up stale tokens
            self.cache.clear_stale_tokens(token_addresses)
            
            tradeable_tokens = []
            
            if self.cache.is_fresh():
                # Use cache for fast loading
                tradeable_tokens = self._load_from_cache(token_addresses)
            else:
                # Do full refresh
                tradeable_tokens = self._full_refresh(token_addresses)
                self.cache.mark_full_refresh()
                self.cache.save()
            
            elapsed = time.time() - start_time
            if self.logger:
                self.logger.success(f"Loaded {len(tradeable_tokens)} tradeable tokens in {elapsed:.2f}s")
            else:
                print(f"🤖 TVB: ✅ Loaded {len(tradeable_tokens)} tradeable tokens in {elapsed:.2f}s")
            
            return tradeable_tokens
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Token loading error: {e}")
            else:
                print(f"🤖 TVB: ❌ Token loading error: {e}")
            return []
    
    def _load_from_cache(self, token_addresses):
        """Load tokens using cache with state verification"""
        print("🤖 TVB: 💨 Using fresh cache for fast loading...")
        
        tradeable_tokens = []
        
        for address in token_addresses:
            cached_token = self.cache.get_token(address)
            
            if cached_token:
                # Quick state verification
                try:
                    current_state = self.factory_contract.functions.getTokenState(address).call()
                    
                    if current_state in [1, 4]:  # TRADING or RESUMED
                        tradeable_tokens.append({
                            "address": address,
                            "name": cached_token["name"],
                            "symbol": cached_token["symbol"]
                        })
                    
                    # Update state in cache
                    self.cache.store_token(
                        address, 
                        cached_token["name"], 
                        cached_token["symbol"], 
                        current_state
                    )
                    
                except Exception as e:
                    print(f"🤖 TVB: ⚠️  State check failed for {address[:10]}...: {e}")
            else:
                # Token not in cache, need full refresh
                print(f"🤖 TVB: 🔄 Cache miss detected, switching to full refresh...")
                return self._full_refresh(token_addresses)
        
        print(f"🤖 TVB: 💾 Cache loading complete")
        return tradeable_tokens
    
    def _full_refresh(self, token_addresses):
        """Perform complete token refresh and update cache"""
        print("🤖 TVB: 🔍 Performing full token refresh...")
        
        tradeable_tokens = []
        
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
                
                # Store in cache regardless of state
                self.cache.store_token(address, name, symbol, state)
                
                # Add to tradeable list if appropriate
                if state in [1, 4]:  # TRADING or RESUMED
                    tradeable_tokens.append({
                        "address": address,
                        "name": name,
                        "symbol": symbol
                    })
                    status = "✅ Tradeable"
                else:
                    status = "⏭️  Not trading"
                
                print(f"🤖 TVB: {status}: {symbol} ({name}) [{i}/{len(token_addresses)}]")
                
            except Exception as e:
                print(f"🤖 TVB: ❌ Error processing {address[:10]}... [{i}/{len(token_addresses)}]: {e}")
        
        return tradeable_tokens


# Example usage and testing
if __name__ == "__main__":
    # Test cache functionality
    cache = TokenCache("test_bot", cache_duration_hours=1)
    
    # Store some test tokens
    cache.store_token("0x123", "Test Token", "TEST", 1)
    cache.store_token("0x456", "Another Token", "ANTH", 4)
    
    cache.save()
    cache.print_stats()
    
    print("🤖 TVB: ✅ Cache system test complete!")