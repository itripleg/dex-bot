# main.py
#!/usr/bin/env python3
"""
Transparent Volume Bot (TVB) - Main Entry Point
Enhanced with automatic key pair generation when no private key is provided
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
from bot.config import load_bot_config, validate_config, merge_config_with_environment, create_example_env_file
from eth_account import Account

def generate_key_if_needed():
    """Helper function to generate key pair when explicitly requested"""
    print("🤖 TVB: 🔑 Generating new random key pair...")
    
    account = Account.create()
    
    print("🤖 TVB: ✨ New key pair generated!")
    print("🤖 TVB: " + "="*60)
    print(f"🤖 TVB: 📍 PUBLIC ADDRESS: {account.address}")
    print(f"🤖 TVB: 🔐 PRIVATE KEY: {account.key.hex()}")
    print("🤖 TVB: " + "="*60)
    print("🤖 TVB: ⚠️  IMPORTANT SECURITY NOTES:")
    print("🤖 TVB: • Save this private key immediately!")
    print("🤖 TVB: • Add it to your .env.local file as PRIVATE_KEY=...")
    print("🤖 TVB: • Never share your private key with anyone!")
    print("🤖 TVB: • Fund this address with AVAX before trading!")
    print("🤖 TVB: " + "="*60)
    
    # Offer to create .env.local file
    try:
        user_input = input("🤖 TVB: Create .env.local file with this key? (y/N): ").strip().lower()
        if user_input in ['y', 'yes']:
            create_example_env_file(account.key.hex())
            print("🤖 TVB: ✅ .env.local file created with your private key!")
        else:
            print("🤖 TVB: ⚠️  Remember to save your private key!")
    except KeyboardInterrupt:
        print("\n🤖 TVB: ⚠️  Remember to save your private key!")
    
    return account.key.hex()

def main():
    """Main entry point with enhanced argument parsing and auto key generation"""
    parser = argparse.ArgumentParser(
        description='Transparent Volume Bot (TVB) - A personality-driven trading bot with auto key generation.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate a new wallet and run bot (auto-generates keys if none provided)
  python main.py --config configs/bullish_billy.json --network https://avax-fuji.g.alchemy.com/v2/YOUR_API_KEY --auto
  
  # Use existing private key
  python main.py --config configs/bullish_billy.json --private-key 0x123... --auto
  
  # Generate a new key pair and save to .env.local
  python main.py --generate-key
  
  # Test configuration without trading
  python main.py --config configs/bullish_billy.json --dry-run
        """
    )
    
    parser.add_argument(
        '--config', 
        type=str, 
        help='Path to the JSON configuration file for the bot.'
    )
    
    parser.add_argument(
        '--generate-key',
        action='store_true',
        help='Generate a new private key and exit (option to save to .env.local)'
    )
    
    parser.add_argument(
        '--auto', 
        action='store_true', 
        help='Start bot automatically without confirmation.'
    )
    
    parser.add_argument(
        '--private-key', 
        type=str, 
        help='Private key for signing transactions (overrides config/env). If not provided, a new one will be generated.'
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
    
    # Handle key generation mode
    if args.generate_key:
        generate_key_if_needed()
        return
    
    # Require config for all other operations
    if not args.config:
        print("🤖 TVB: ❌ --config is required (unless using --generate-key)")
        print("🤖 TVB: Example: python main.py --config configs/bullish_billy.json --auto")
        parser.print_help()
        sys.exit(1)
    
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
        else:
            print("🤖 TVB: 🔑 No private key provided - will auto-generate if needed")
        
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
            
            # Show funding instructions if balance is 0
            if bot.get_avax_balance() == 0:
                print("\n🤖 TVB: ⚠️  To start trading, fund your wallet:")
                print(f"🤖 TVB: Send AVAX to: {bot.account.address}")
                print("🤖 TVB: Recommended minimum: 0.1 AVAX for testing")
                print("🤖 TVB: Avalanche Fuji Testnet Faucet: https://faucet.avax.network/")
            
            return
        
        if args.auto:
            print("🤖 TVB: 🚀 Starting automated trading...")
            bot.run()
        else:
            print("🤖 TVB: ✅ Bot initialized successfully!")
            print(f"🤖 TVB: Wallet: {bot.account.address}")
            print(f"🤖 TVB: Balance: {bot.get_avax_balance():.6f} AVAX")
            
            # Show funding instructions if balance is 0
            if bot.get_avax_balance() == 0:
                print("\n🤖 TVB: ⚠️  Your wallet has no AVAX! Fund it first:")
                print(f"🤖 TVB: Send AVAX to: {bot.account.address}")
                print("🤖 TVB: Recommended minimum: 0.1 AVAX for testing")
                print("🤖 TVB: Avalanche Fuji Testnet Faucet: https://faucet.avax.network/")
            
            print("\n🤖 TVB: Add --auto flag to start trading automatically.")
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