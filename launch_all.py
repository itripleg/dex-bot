#!/usr/bin/env python3
"""
Multi-Bot Launcher for TVB
Simple threaded launcher to run multiple bots simultaneously
"""

import threading
import time
import sys
import argparse
from pathlib import Path
import glob

# Add project root to path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

from bot.core import TransparentVolumeBot
from bot.config import load_bot_config, validate_config, merge_config_with_environment

class BotManager:
    """Manages multiple bot instances"""
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.bots = {}
        self.threads = {}
        self.running = False
        
    def discover_bot_configs(self, config_dir="configs"):
        """Auto-discover bot configuration files"""
        config_path = Path(config_dir)
        
        if not config_path.exists():
            print(f"🤖 TVB: ❌ Config directory not found: {config_dir}")
            return []
        
        # Find all .json files in configs directory
        config_files = list(config_path.glob("*.json"))
        
        print(f"🤖 TVB: 📁 Found {len(config_files)} config files in {config_dir}/")
        
        valid_configs = []
        for config_file in config_files:
            try:
                # Test load the config to make sure it's valid
                config = load_bot_config(config_file)
                if config.get('name') and config.get('displayName'):
                    valid_configs.append(str(config_file))
                    print(f"🤖 TVB: ✅ {config_file.name} - {config.get('displayName')}")
                else:
                    print(f"🤖 TVB: ⚠️  {config_file.name} - Missing name/displayName, skipping")
            except Exception as e:
                print(f"🤖 TVB: ❌ {config_file.name} - Invalid config: {e}")
        
        return valid_configs
    
    def create_bot(self, config_path, force_cache_refresh=False, use_local=False, network_override=None, private_key_override=None):
        """Create a bot instance from config"""
        try:
            print(f"\n🤖 TVB: 🔧 Initializing bot from {config_path}...")
            
            config = load_bot_config(config_path)
            config = merge_config_with_environment(config, use_local=use_local)

            # Apply global CLI overrides
            if network_override:
                print(f"🤖 TVB: 🌐 Applying global network override: {network_override}")
                config['rpcUrl'] = network_override
            if private_key_override:
                print("🤖 TVB: 🔑 Applying global private key override")

            validate_config(config)
            
            bot = TransparentVolumeBot(
                config=config,
                private_key_override=private_key_override,
                force_cache_refresh=force_cache_refresh,
                verbose=self.verbose
            )
            
            bot_name = bot.bot_name
            self.bots[bot_name] = bot
            
            print(f"🤖 TVB: ✅ {bot.display_name} initialized successfully")
            return bot_name, bot
            
        except Exception as e:
            print(f"🤖 TVB: ❌ Failed to initialize bot from {config_path}: {e}")
            return None, None
    
    def run_bot(self, bot_name):
        """Run a single bot (called in thread)"""
        try:
            bot = self.bots[bot_name]
            print(f"🤖 TVB: 🚀 Starting {bot.display_name} in thread...")
            bot.run()
        except KeyboardInterrupt:
            print(f"🤖 TVB: ⏹️  {bot_name} stopped by user")
        except Exception as e:
            print(f"🤖 TVB: 💥 {bot_name} crashed: {e}")
        finally:
            print(f"🤖 TVB: 👋 {bot_name} thread ended")
    
    def start_all_bots(self, config_files, force_cache_refresh=False, use_local=False, network_override=None, private_key_override=None):
        """Start all bots in separate threads"""
        print(f"\n🤖 TVB: 🚀 Starting multi-bot launcher...")
        
        if use_local:
            print("🤖 TVB: 🏠 Local development mode enabled - using localhost:3000 webhook")
        
        # Initialize all bots first
        successful_bots = []
        for config_path in config_files:
            bot_name, bot = self.create_bot(config_path, force_cache_refresh, use_local, network_override, private_key_override)
            if bot:
                successful_bots.append(bot_name)
        
        if not successful_bots:
            print("🤖 TVB: ❌ No bots were successfully initialized!")
            return
        
        print(f"\n🤖 TVB: 🎯 Starting {len(successful_bots)} bots:")
        for bot_name in successful_bots:
            bot = self.bots[bot_name]
            print(f"  - {bot.display_name} ({bot_name})")
        
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
            time.sleep(1)  # Stagger starts slightly
        
        print(f"\n🤖 TVB: ✅ All {len(successful_bots)} bots are now running!")
        print("🤖 TVB: Press Ctrl+C to stop all bots")
        
        # Wait for threads or user interrupt
        try:
            self.monitor_bots()
        except KeyboardInterrupt:
            print(f"\n🤖 TVB: 🛑 Shutdown signal received...")
            self.stop_all_bots()
    
    def monitor_bots(self):
        """Monitor running bots and keep main thread alive"""
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
            
            if dead_bots and self.verbose:
                for bot_name in dead_bots:
                    print(f"🤖 TVB: ⚰️  {bot_name} thread has stopped")
            
            # If all bots are dead, exit
            if not active_bots:
                print("🤖 TVB: ⚰️  All bots have stopped")
                break
    
    def stop_all_bots(self):
        """Stop all running bots"""
        self.running = False
        
        print("🤖 TVB: 🛑 Stopping all bots...")
        
        # Give threads a moment to shut down gracefully
        for bot_name, thread in self.threads.items():
            if thread.is_alive():
                print(f"🤖 TVB: ⏳ Waiting for {bot_name} to stop...")
                thread.join(timeout=5)
                
                if thread.is_alive():
                    print(f"🤖 TVB: ⚠️  {bot_name} did not stop gracefully")
        
        print("🤖 TVB: 👋 All bots stopped")
    
    def dry_run_all(self, config_files, force_cache_refresh=False, use_local=False, network_override=None, private_key_override=None):
        """Test all bot configurations without starting them"""
        print(f"\n🤖 TVB: 🧪 Dry run for all bot configurations...")
        
        if use_local:
            print("🤖 TVB: 🏠 Local development mode enabled for dry run")
        
        successful = 0
        failed = 0
        
        for config_path in config_files:
            try:
                print(f"\n🤖 TVB: 🧪 Testing {config_path}...")
                
                config = load_bot_config(config_path)
                config = merge_config_with_environment(config, use_local=use_local)

                # Apply global CLI overrides
                if network_override:
                    print(f"🤖 TVB: 🌐 Applying global network override: {network_override}")
                    config['rpcUrl'] = network_override
                if private_key_override:
                    print("🤖 TVB: 🔑 Applying global private key override")

                validate_config(config)
                
                bot = TransparentVolumeBot(
                    config=config,
                    private_key_override=private_key_override,
                    force_cache_refresh=force_cache_refresh,
                    verbose=self.verbose
                )
                
                print(f"🤖 TVB: ✅ {bot.display_name}")
                print(f"  Wallet: {bot.account.address}")
                print(f"  Balance: {bot.get_avax_balance():.6f} AVAX")
                print(f"  Tokens: {len(bot.tokens)}")
                
                successful += 1
                
            except Exception as e:
                print(f"🤖 TVB: ❌ {config_path} failed: {e}")
                failed += 1
        
        print(f"\n🤖 TVB: 📊 Dry run complete:")
        print(f"  ✅ Successful: {successful}")
        print(f"  ❌ Failed: {failed}")
        
        return successful > 0


def main():
    """Main entry point for multi-bot launcher"""
    parser = argparse.ArgumentParser(
        description='TVB Multi-Bot Launcher - Run multiple trading bots simultaneously',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python launch_all.py --auto                    # Start all bots in configs/
  python launch_all.py --dry-run --network <RPC_URL> # Test all configs on a specific network
  python launch_all.py --auto --private-key <KEY>    # Run all bots with the same wallet
  python launch_all.py --configs bullish_billy.json jackpot_jax.json --auto
  python launch_all.py --config-dir my_bots/ --auto
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
        help='Specific config files to run (default: auto-discover all)'
    )
    
    parser.add_argument(
        '--config-dir',
        default='configs',
        help='Directory to search for config files (default: configs/)'
    )

    parser.add_argument(
        '--private-key',
        type=str,
        help='Global private key to use for ALL bots (overrides config/env).'
    )
    
    parser.add_argument(
        '--network',
        type=str,
        help='Global network RPC URL to use for ALL bots (overrides config/env).'
    )
    
    parser.add_argument(
        '--refresh-cache',
        action='store_true',
        help='Force refresh token cache for all bots'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--local',
        action='store_true',
        help='Use local development mode (webhook: http://localhost:3000/api/tvb/webhook)'
    )

    args = parser.parse_args()
    
    # Initialize bot manager
    manager = BotManager(verbose=args.verbose)
    
    # Determine which configs to use
    if args.configs:
        # Use specific configs
        config_files = []
        for config in args.configs:
            config_path = Path(args.config_dir) / config
            if config_path.exists():
                config_files.append(str(config_path))
            else:
                print(f"🤖 TVB: ❌ Config file not found: {config_path}")
    else:
        # Auto-discover configs
        config_files = manager.discover_bot_configs(args.config_dir)
    
    if not config_files:
        print("🤖 TVB: ❌ No valid config files found!")
        sys.exit(1)
    
    # Run dry run or start bots
    if args.dry_run:
        success = manager.dry_run_all(config_files, args.refresh_cache, args.local, args.network, args.private_key)
        sys.exit(0 if success else 1)
    elif args.auto:
        manager.start_all_bots(config_files, args.refresh_cache, args.local, args.network, args.private_key)
    else:
        print("🤖 TVB: ✅ Multi-bot launcher ready!")
        print(f"🤖 TVB: Found {len(config_files)} bot configurations")
        if args.local:
            print("🤖 TVB: 🏠 Add --auto to start all bots in local development mode")
        else:
            print("🤖 TVB: Add --auto to start all bots, or --dry-run to test")


if __name__ == "__main__":
    main()