#!/usr/bin/env python3
"""
Transparent Volume Bot (TVB) - Main Entry Point
Fixed imports for direct execution with working --private-key and --network flags
"""

import argparse
import sys
import os
from pathlib import Path

# Add the project root to Python path for absolute imports
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

# Now use absolute imports
from bot.core import TransparentVolumeBot
from bot.config import load_bot_config, validate_config, merge_config_with_environment

def main():
    """Main entry point with clean argument parsing"""
    parser = argparse.ArgumentParser(
        description='Transparent Volume Bot (TVB) - A personality-driven trading bot.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --config configs/bullish_billy.json --private-key 0x123... --network https://avax-fuji.g.alchemy.com/v2/YOUR_API_KEY --auto
  python main.py --config configs/bullish_billy.json --auto
  python main.py --config configs/bullish_billy.json --dry-run
        """
    )
    
    parser.add_argument(
        '--config', 
        type=str, 
        required=True, 
        help='Path to the JSON configuration file for the bot.'
    )
    
    parser.add_argument(
        '--auto', 
        action='store_true', 
        help='Start bot automatically without confirmation.'
    )
    
    parser.add_argument(
        '--private-key', 
        type=str, 
        help='Private key for signing transactions (overrides config/env).'
    )
    
    parser.add_argument(
        '--network',
        type=str,
        help='Network RPC URL (overrides config/env). Example: https://avax-fuji.g.alchemy.com/v2/YOUR_API_KEY'
    )
    
    parser.add_argument(
        '--dry-run', 
        action='store_true', 
        help='Test configuration without starting trading.'
    )
    
    parser.add_argument(
        '--refresh-cache', 
        action='store_true', 
        help='Force refresh token cache on startup.'
    )
    
    parser.add_argument(
        '--verbose', '-v', 
        action='store_true', 
        help='Enable verbose logging.'
    )
    
    parser.add_argument(
        '--local', 
        action='store_true', 
        help='Use local development mode (webhook: http://localhost:3000/api/tvb/webhook)'
    )
    
    args = parser.parse_args()
    
    try:
        print("🤖 TVB: Loading configuration...")
        config = load_bot_config(args.config)
        
        print("🤖 TVB: Merging with environment variables...")
        config = merge_config_with_environment(config, use_local=args.local)
        
        # Apply CLI overrides AFTER environment merge
        if args.network:
            config['rpcUrl'] = args.network
            print(f"🤖 TVB: 🌐 Using CLI network override: {args.network}")
        
        # Store CLI private key override for later use
        private_key_override = args.private_key
        if private_key_override:
            print("🤖 TVB: 🔑 Using CLI private key override")
        
        print("🤖 TVB: Validating configuration...")
        validate_config(config)
        
        print("🤖 TVB: Initializing bot...")
        bot = TransparentVolumeBot(
            config=config,
            private_key_override=private_key_override,
            force_cache_refresh=args.refresh_cache,
            verbose=args.verbose
        )
        
        if args.dry_run:
            print("🤖 TVB: ✅ Dry run completed successfully!")
            print(f"🤖 TVB: Bot '{bot.display_name}' is ready to trade.")
            print(f"🤖 TVB: Wallet: {bot.account.address}")
            print(f"🤖 TVB: Balance: {bot.get_avax_balance():.6f} AVAX")
            print(f"🤖 TVB: Network: {config.get('rpcUrl', 'Unknown')}")
            print(f"🤖 TVB: Tradeable tokens: {len(bot.tokens)}")
            return
        
        if args.auto:
            print("🤖 TVB: 🚀 Starting automated trading...")
            bot.run()
        else:
            print("🤖 TVB: ✅ Bot initialized successfully!")
            print("🤖 TVB: Add --auto flag to start trading automatically.")
            print(f"🤖 TVB: Example: python main.py --config {args.config} --auto")
            
    except KeyboardInterrupt:
        print("\n🤖 TVB: 👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"🤖 TVB: 💥 Critical Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()