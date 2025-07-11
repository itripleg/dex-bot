#!/usr/bin/env python3
"""
Simplified Multi-Bot Launcher for TVB
Clean, straightforward launcher without complex optimization
"""

import threading
import time
import sys
import argparse
import json
import os
from pathlib import Path
from typing import List, Dict

def load_config(config_path: str) -> dict:
    """Load bot configuration from JSON file"""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"❌ Failed to load {config_path}: {e}")
        return None

def merge_environment_variables(config: dict) -> dict:
    """Merge environment variables into config"""
    # Standard environment mappings
    env_mappings = {
        'RPC_URL': 'rpcUrl',
        'FACTORY_ADDRESS': 'factoryAddress',
        'WEBHOOK_URL': 'webhookUrl',
        'BOT_SECRET': 'botSecret',
        'PRIVATE_KEY': 'privateKey'
    }
    
    # Load .env.local if it exists
    env_local_path = Path('.env.local')
    if env_local_path.exists():
        print(f"📄 Loading environment from .env.local")
        try:
            from dotenv import load_dotenv
            load_dotenv(env_local_path)
            print(f"✅ Loaded .env.local successfully")
        except ImportError:
            print("⚠️  python-dotenv not installed, install with: pip install python-dotenv")
    else:
        print(f"⚠️  .env.local not found at {env_local_path.absolute()}")
    
    # Also try regular .env file
    env_path = Path('.env')
    if env_path.exists():
        print(f"📄 Loading environment from .env")
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
            print(f"✅ Loaded .env successfully")
        except ImportError:
            print("⚠️  python-dotenv not installed for .env file")
    
    # Apply environment variables with debugging
    print(f"🔍 Checking environment variables:")
    for env_var, config_key in env_mappings.items():
        env_value = os.getenv(env_var)
        if env_value:
            if config_key not in config or config.get(config_key) == "SET_IN_ENV_LOCAL":
                config[config_key] = env_value
                print(f"  ✅ {env_var} -> {config_key}")
            else:
                print(f"  ⏭️  {env_var} skipped (already set in config)")
        else:
            print(f"  ❌ {env_var} not found in environment")
    
    # Check for bot-specific private key if no global one found
    if not config.get('privateKey') or config.get('privateKey') == "SET_IN_ENV_LOCAL":
        bot_name = config.get('name', '').upper()
        if bot_name:
            # Try bot-specific private key patterns
            bot_key_patterns = [
                f"{bot_name}_PRIVATE_KEY",
                f"BOT_{bot_name}_PRIVATE_KEY", 
                f"BULLISH_BILLY_PRIVATE_KEY" if bot_name == "BULLISH_BILLY" else None,
                f"JACKPOT_JAX_PRIVATE_KEY" if bot_name == "JACKPOT_JAX" else None,
                f"COMPANION_CUBE_PRIVATE_KEY" if bot_name == "COMPANION_CUBE" else None
            ]
            
            for pattern in bot_key_patterns:
                if pattern:
                    bot_key = os.getenv(pattern)
                    if bot_key:
                        config['privateKey'] = bot_key
                        print(f"  ✅ Found bot-specific key: {pattern}")
                        break
            
            if not config.get('privateKey') or config.get('privateKey') == "SET_IN_ENV_LOCAL":
                print(f"  ❌ No private key found for bot: {bot_name}")
    
    return config

def validate_and_prepare_config(config: dict, global_overrides: dict) -> dict:
    """Validate and apply global overrides to config"""
    if not config:
        return None
    
    # Apply global overrides
    if global_overrides.get('network'):
        config['rpcUrl'] = global_overrides['network']
    
    if global_overrides.get('private_key'):
        config['privateKey'] = global_overrides['private_key']
    
    if global_overrides.get('local_mode'):
        config['webhookUrl'] = 'http://localhost:3000/api/tvb/webhook'
        config['botSecret'] = 'dev'
    
    # Check required fields
    if not config.get('name') or not config.get('displayName'):
        print(f"❌ Config missing name/displayName")
        return None
    
    if not config.get('rpcUrl') or config.get('rpcUrl') == "SET_IN_ENV_LOCAL":
        print(f"❌ {config.get('displayName', 'Bot')} missing RPC URL")
        return None
    
    if not config.get('factoryAddress') or config.get('factoryAddress') == "SET_IN_ENV_LOCAL":
        print(f"❌ {config.get('displayName', 'Bot')} missing factory address")
        return None
    
    # Set defaults
    defaults = {
        'webhookUrl': None,
        'botSecret': 'dev',
        'buyBias': 0.6,
        'riskTolerance': 0.5,
        'minInterval': 15,
        'maxInterval': 60,
        'minTradeAmount': 0.005,
        'maxTradeAmount': 0.02,
        'createTokenChance': 0.02,
        'avatarUrl': '/default.png'
    }
    
    for key, default_value in defaults.items():
        if key not in config or config[key] == "SET_IN_ENV_LOCAL":
            config[key] = default_value
    
    return config

def discover_bot_configs(config_dir: str = "configs") -> List[str]:
    """Auto-discover bot configuration files"""
    config_path = Path(config_dir)
    
    if not config_path.exists():
        print(f"❌ Config directory not found: {config_dir}")
        return []
    
    # Find all .json files
    config_files = list(config_path.glob("*.json"))
    
    valid_configs = []
    for config_file in config_files:
        config = load_config(config_file)
        if config and config.get('name') and config.get('displayName'):
            valid_configs.append(str(config_file))
            print(f"✅ Found: {config.get('displayName')} ({config_file.name})")
        else:
            print(f"⚠️  Skipped: {config_file.name} (invalid config)")
    
    return valid_configs

class SimpleBotManager:
    """Simple multi-bot manager without complex optimization"""
    
    def __init__(self):
        self.bots = {}
        self.threads = {}
        self.running = False
        self.successful_inits = 0
        self.failed_inits = 0
    
    def create_bot(self, config_path: str, global_overrides: dict) -> tuple:
        """Create a bot instance from config"""
        try:
            print(f"\n🔧 Initializing bot from {Path(config_path).name}...")
            
            # Load and prepare config
            config = load_config(config_path)
            if not config:
                return None, None
            
            config = merge_environment_variables(config)
            config = validate_and_prepare_config(config, global_overrides)
            
            if not config:
                return None, None
            
            # Import and create bot
            try:
                from bot.simple_core import SimpleTVBBot
            except ImportError:
                print("❌ SimpleTVBBot not found - make sure bot/simple_core.py exists")
                return None, None
            
            bot = SimpleTVBBot(config, global_overrides.get('private_key'))
            
            bot_name = bot.bot_name
            self.bots[bot_name] = bot
            self.successful_inits += 1
            
            print(f"✅ {bot.display_name} initialized successfully")
            return bot_name, bot
            
        except Exception as e:
            print(f"❌ Failed to initialize bot from {Path(config_path).name}: {e}")
            self.failed_inits += 1
            return None, None
    
    def run_bot(self, bot_name: str):
        """Run a single bot (called in thread)"""
        try:
            bot = self.bots[bot_name]
            print(f"🚀 Starting {bot.display_name} in thread...")
            bot.run()
        except KeyboardInterrupt:
            print(f"⏹️  {bot_name} stopped by user")
        except Exception as e:
            print(f"💥 {bot_name} crashed: {e}")
        finally:
            print(f"👋 {bot_name} thread ended")
    
    def start_all_bots(self, config_files: List[str], global_overrides: dict):
        """Start all bots in separate threads"""
        print(f"\n🚀 Starting multi-bot launcher...")
        print(f"📁 Found {len(config_files)} config files")
        
        if global_overrides.get('local_mode'):
            print("🏠 Local development mode enabled")
        
        # Initialize all bots
        successful_bots = []
        start_time = time.time()
        
        for config_path in config_files:
            bot_name, bot = self.create_bot(config_path, global_overrides)
            if bot:
                successful_bots.append(bot_name)
        
        init_time = time.time() - start_time
        
        if not successful_bots:
            print("❌ No bots were successfully initialized!")
            return
        
        print(f"\n📊 Initialization Summary:")
        print(f"  ✅ Successful: {self.successful_inits}")
        print(f"  ❌ Failed: {self.failed_inits}")
        print(f"  ⏱️  Time: {init_time:.2f}s")
        
        # Show shared loader stats if available
        try:
            from shared.simple_token_loader import print_shared_loader_stats
            print_shared_loader_stats()
        except ImportError:
            print("  ℹ️  Shared token loader not available")
        
        print(f"\n🎯 Starting {len(successful_bots)} bots:")
        for bot_name in successful_bots:
            bot = self.bots[bot_name]
            balance = bot.get_avax_balance()
            status = "💰 Funded" if balance > 0 else "💸 Unfunded"
            print(f"  🤖 {bot.display_name} - {status} ({balance:.6f} AVAX)")
        
        # Start all bots in threads
        self.running = True
        for bot_name in successful_bots:
            thread = threading.Thread(
                target=self.run_bot,
                args=(bot_name,),
                name=f"Bot-{bot_name}",
                daemon=True
            )
            self.threads[bot_name] = thread
            thread.start()
            time.sleep(0.5)  # Stagger starts
        
        print(f"\n✅ All {len(successful_bots)} bots are now running!")
        print("🛑 Press Ctrl+C to stop all bots")
        
        # Monitor bots
        try:
            self.monitor_bots()
        except KeyboardInterrupt:
            print(f"\n🛑 Shutdown signal received...")
            self.stop_all_bots()
    
    def monitor_bots(self):
        """Monitor running bots"""
        while self.running:
            time.sleep(5)
            
            # Check if any threads have died
            active_bots = []
            dead_bots = []
            
            for bot_name, thread in self.threads.items():
                if thread.is_alive():
                    active_bots.append(bot_name)
                else:
                    dead_bots.append(bot_name)
            
            if dead_bots:
                for bot_name in dead_bots:
                    print(f"⚰️  {bot_name} thread has stopped")
            
            # If all bots are dead, exit
            if not active_bots:
                print("⚰️  All bots have stopped")
                break
    
    def stop_all_bots(self):
        """Stop all running bots"""
        self.running = False
        
        # Print a nice goodbye message
        print("\n" + "="*60)
        print("🛑 TVB MULTI-BOT SHUTDOWN INITIATED")
        print("="*60)
        print("🤖 Stopping all trading bots...")
        
        # Give threads time to shut down gracefully
        for bot_name, thread in self.threads.items():
            if thread.is_alive():
                print(f"⏳ Waiting for {bot_name} to stop...")
                thread.join(timeout=5)
                
                if thread.is_alive():
                    print(f"⚠️  {bot_name} did not stop gracefully")
                else:
                    print(f"✅ {bot_name} stopped cleanly")
        
        print("\n🏁 ALL BOTS OFFLINE")
        print("="*60)
        print("📊 Session Summary:")
        print(f"  🤖 Bots managed: {len(self.threads)}")
        print(f"  ✅ Successful inits: {self.successful_inits}")
        print(f"  ❌ Failed inits: {self.failed_inits}")
        
        # Show final shared loader stats
        try:
            from shared.simple_token_loader import print_shared_loader_stats
            print_shared_loader_stats()
        except ImportError:
            pass
        
        print("="*60)
        print("👋 Thank you for using TVB Multi-Bot Launcher!")
        print("💎 May your trades be profitable and your wallets full!")
        print("="*60 + "\n")
    
    def dry_run_all(self, config_files: List[str], global_overrides: dict):
        """Test all bot configurations without starting them"""
        print(f"\n🧪 Dry run for {len(config_files)} bot configurations...")
        
        if global_overrides.get('local_mode'):
            print("🏠 Local development mode enabled for dry run")
        
        successful = 0
        failed = 0
        start_time = time.time()
        
        for config_path in config_files:
            config_name = Path(config_path).name
            
            try:
                print(f"\n🧪 Testing {config_name}...")
                
                # Load and prepare config
                config = load_config(config_path)
                if not config:
                    failed += 1
                    continue
                
                config = merge_environment_variables(config)
                config = validate_and_prepare_config(config, global_overrides)
                
                if not config:
                    failed += 1
                    continue
                
                # Create bot instance
                try:
                    from bot.simple_core import SimpleTVBBot
                except ImportError:
                    print("❌ SimpleTVBBot not found")
                    failed += 1
                    continue
                
                bot = SimpleTVBBot(config, global_overrides.get('private_key'))
                
                print(f"✅ {bot.display_name}")
                print(f"   💼 Wallet: {bot.account.address}")
                print(f"   💰 Balance: {bot.get_avax_balance():.6f} AVAX")
                print(f"   🎯 Tokens: {len(bot.tokens)}")
                
                successful += 1
                
            except Exception as e:
                print(f"❌ {config_name} failed: {e}")
                failed += 1
        
        total_time = time.time() - start_time
        
        print(f"\n📊 Dry run complete:")
        print(f"  ✅ Successful: {successful}")
        print(f"  ❌ Failed: {failed}")
        print(f"  ⏱️  Total time: {total_time:.2f}s")
        
        return successful > 0

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Simplified TVB Multi-Bot Launcher',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start all bots automatically
  python launch_all.py --auto
  
  # Test all configurations
  python launch_all.py --dry-run
  
  # Start specific bots
  python launch_all.py --configs bullish_billy.json jackpot_jax.json --auto
  
  # Use same wallet for all bots
  python launch_all.py --auto --private-key 0x123...
  
  # Local development mode
  python launch_all.py --auto --local
        """
    )
    
    parser.add_argument(
        '--auto',
        action='store_true',
        help='Start all bots automatically'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Test all configurations without starting bots'
    )
    
    parser.add_argument(
        '--configs',
        nargs='*',
        help='Specific config files to use (default: auto-discover all)'
    )
    
    parser.add_argument(
        '--config-dir',
        default='configs',
        help='Directory to search for config files (default: configs/)'
    )
    
    parser.add_argument(
        '--private-key',
        type=str,
        help='Global private key for all bots (overrides individual configs)'
    )
    
    parser.add_argument(
        '--network',
        type=str,
        help='Global network RPC URL for all bots'
    )
    
    parser.add_argument(
        '--local',
        action='store_true',
        help='Use local development mode (localhost webhook)'
    )
    
    args = parser.parse_args()
    
    # Build global overrides
    global_overrides = {
        'private_key': args.private_key,
        'network': args.network,
        'local_mode': args.local
    }
    
    # Determine which configs to use
    if args.configs:
        # Use specific configs
        config_files = []
        for config in args.configs:
            config_path = Path(args.config_dir) / config
            if config_path.exists():
                config_files.append(str(config_path))
            else:
                print(f"❌ Config file not found: {config_path}")
    else:
        # Auto-discover configs
        print(f"🔍 Auto-discovering configs in {args.config_dir}/")
        config_files = discover_bot_configs(args.config_dir)
    
    if not config_files:
        print("❌ No valid config files found!")
        sys.exit(1)
    
    # Initialize manager
    manager = SimpleBotManager()
    
    # Run operation
    if args.dry_run:
        success = manager.dry_run_all(config_files, global_overrides)
        sys.exit(0 if success else 1)
    elif args.auto:
        manager.start_all_bots(config_files, global_overrides)
    else:
        print("✅ Multi-bot launcher ready!")
        print(f"📁 Found {len(config_files)} config files")
        print("💡 Add --auto to start all bots, or --dry-run to test")
        if args.local:
            print("🏠 Local development mode configured")

if __name__ == "__main__":
    main()