#!/usr/bin/env python3
"""
Simplified Main Entry Point for TVB Bot
Clean, straightforward bot launcher with minimal complexity
"""

import argparse
import sys
import json
import os
from pathlib import Path
from eth_account import Account

def load_config(config_path: str) -> dict:
    """Load bot configuration from JSON file"""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        print(f"✅ Loaded config from {config_path}")
        return config
    except FileNotFoundError:
        print(f"❌ Config file not found: {config_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in config file: {e}")
        sys.exit(1)

def merge_environment_variables(config: dict) -> dict:
    """Merge environment variables into config"""
    # Environment variable mappings
    env_mappings = {
        'RPC_URL': 'rpcUrl',
        'FACTORY_ADDRESS': 'factoryAddress', 
        'WEBHOOK_URL': 'webhookUrl',
        'BOT_SECRET': 'botSecret',
        'PRIVATE_KEY': 'privateKey'
    }
    
    for env_var, config_key in env_mappings.items():
        env_value = os.getenv(env_var)
        if env_value:
            config[config_key] = env_value
            print(f"🔧 Using {env_var} from environment")
    
    # Check for .env.local file
    env_local_path = Path('.env.local')
    if env_local_path.exists():
        print(f"📄 Found .env.local file")
        try:
            from dotenv import load_dotenv
            load_dotenv(env_local_path)
            
            # Re-check environment variables after loading .env.local
            for env_var, config_key in env_mappings.items():
                env_value = os.getenv(env_var)
                if env_value and (config_key not in config or config.get(config_key) == "SET_IN_ENV_LOCAL"):
                    config[config_key] = env_value
                    print(f"🔧 Using {env_var} from .env.local")
                    
        except ImportError:
            print("⚠️  python-dotenv not installed, skipping .env.local")
    
    return config

def validate_config(config: dict, private_key_override: str = None, network_override: str = None) -> dict:
    """Validate and apply overrides to config"""
    # Apply CLI overrides
    if network_override:
        config['rpcUrl'] = network_override
        print(f"🌐 Using CLI network override")
    
    if private_key_override:
        config['privateKey'] = private_key_override
        print(f"🔑 Using CLI private key override")
    
    # Check required fields
    required_fields = ['name', 'displayName']
    for field in required_fields:
        if not config.get(field):
            print(f"❌ Missing required field: {field}")
            sys.exit(1)
    
    # Check RPC URL
    if not config.get('rpcUrl') or config.get('rpcUrl') == "SET_IN_ENV_LOCAL":
        print("❌ RPC URL not configured")
        print("💡 Set RPC_URL environment variable or use --network flag")
        print("💡 Example: --network https://avax-fuji.g.alchemy.com/v2/YOUR_API_KEY")
        sys.exit(1)
    
    # Check factory address
    if not config.get('factoryAddress') or config.get('factoryAddress') == "SET_IN_ENV_LOCAL":
        print("❌ Factory address not configured")
        print("💡 Set FACTORY_ADDRESS environment variable")
        sys.exit(1)
    
    # Set defaults for optional fields
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
        'avatarUrl': '/default.png',
        'bio': f"An AI trading bot named {config.get('displayName', 'Unknown')}"
    }
    
    for key, default_value in defaults.items():
        if key not in config or config[key] == "SET_IN_ENV_LOCAL":
            config[key] = default_value
    
    return config

def generate_new_keypair():
    """Generate a new Ethereum keypair"""
    print("🔑 Generating new Ethereum keypair...")
    
    account = Account.create()
    
    print("✨ New keypair generated!")
    print("=" * 60)
    print(f"📍 Address: {account.address}")
    print(f"🔐 Private Key: {account.key.hex()}")
    print("=" * 60)
    print("⚠️  IMPORTANT:")
    print("• Save this private key in a secure location")
    print("• Add it to your .env.local file as PRIVATE_KEY=...")
    print("• Fund the address with AVAX before trading")
    print("• Avalanche Fuji Testnet Faucet: https://faucet.avax.network/")
    print("=" * 60)
    
    # Offer to create .env.local
    try:
        create_env = input("Create .env.local file with this key? (y/N): ").strip().lower()
        if create_env in ['y', 'yes']:
            create_env_local_file(account.key.hex())
    except KeyboardInterrupt:
        print("\n👋 Keypair generation cancelled")

def create_env_local_file(private_key: str = None):
    """Create a .env.local file template"""
    env_content = """# TVB Bot Environment Variables
# Copy these values and update with your actual configuration

# Network Configuration
RPC_URL=https://avax-fuji.g.alchemy.com/v2/YOUR_API_KEY_HERE
FACTORY_ADDRESS=0x20BC84B00406cd0cc6B467569553E5f46A990f3C

# Webhook Configuration (optional)
WEBHOOK_URL=http://localhost:3000/api/tvb/webhook
BOT_SECRET=dev

# Bot Configuration
"""
    
    if private_key:
        env_content += f"\n# Generated Private Key\nPRIVATE_KEY={private_key}\n"
    else:
        env_content += "\n# Private Key (add your own)\n# PRIVATE_KEY=0x123...\n"
    
    env_path = Path('.env.local')
    
    if env_path.exists():
        print("⚠️  .env.local already exists, not overwriting")
        return
    
    try:
        with open(env_path, 'w') as f:
            f.write(env_content)
        print(f"✅ Created .env.local file")
        if private_key:
            print("🔐 Your private key has been saved to .env.local")
    except Exception as e:
        print(f"❌ Failed to create .env.local: {e}")

def print_config_summary(config: dict):
    """Print a summary of the bot configuration"""
    print("\n🤖 Bot Configuration Summary:")
    print(f"  👤 Name: {config['displayName']} ({config['name']})")
    print(f"  🎯 Personality: Buy Bias={config['buyBias']:.2f}, Risk={config['riskTolerance']:.2f}")
    print(f"  ⏱️  Intervals: {config['minInterval']}-{config['maxInterval']}s")
    print(f"  💰 Trade Size: {config['minTradeAmount']:.4f}-{config['maxTradeAmount']:.4f} AVAX")
    print(f"  🎨 Create Chance: {config['createTokenChance']*100:.1f}%")
    
    # Mask sensitive RPC URL
    rpc_url = config['rpcUrl']
    if 'alchemy.com' in rpc_url or 'infura.io' in rpc_url:
        import re
        rpc_url = re.sub(r'/v2/[a-zA-Z0-9_-]+', '/v2/***API_KEY***', rpc_url)
    print(f"  🌐 Network: {rpc_url}")
    
    webhook_status = "✅ Enabled" if config.get('webhookUrl') else "❌ Disabled"
    print(f"  📡 Webhooks: {webhook_status}")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Simplified TVB Bot - Personality-driven trading bot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate new wallet
  python main.py --generate-key
  
  # Run bot with config file
  python main.py --config configs/bullish_billy.json --auto
  
  # Override network and key
  python main.py --config configs/bullish_billy.json --network https://avax-fuji.g.alchemy.com/v2/KEY --private-key 0x123... --auto
  
  # Test configuration
  python main.py --config configs/bullish_billy.json --dry-run
  
  # Use local development mode
  python main.py --config configs/bullish_billy.json --local --auto
        """
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to bot configuration JSON file'
    )
    
    parser.add_argument(
        '--generate-key',
        action='store_true',
        help='Generate a new Ethereum keypair and exit'
    )
    
    parser.add_argument(
        '--auto',
        action='store_true',
        help='Start bot automatically without confirmation'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Test configuration without starting bot'
    )
    
    parser.add_argument(
        '--private-key',
        type=str,
        help='Private key override (0x...)'
    )
    
    parser.add_argument(
        '--network',
        type=str,
        help='Network RPC URL override'
    )
    
    parser.add_argument(
        '--local',
        action='store_true',
        help='Use local development mode (localhost webhook)'
    )
    
    parser.add_argument(
        '--create-env',
        action='store_true',
        help='Create .env.local template file'
    )
    
    args = parser.parse_args()
    
    # Handle special commands
    if args.generate_key:
        generate_new_keypair()
        return
    
    if args.create_env:
        create_env_local_file()
        return
    
    # Require config for bot operations
    if not args.config:
        print("❌ --config is required")
        print("💡 Example: python main.py --config configs/bullish_billy.json --auto")
        parser.print_help()
        sys.exit(1)
    
    try:
        # Load and validate configuration
        print("🔧 Loading configuration...")
        config = load_config(args.config)
        
        print("🔧 Merging environment variables...")
        config = merge_environment_variables(config)
        
        # Apply local development mode
        if args.local:
            config['webhookUrl'] = 'http://localhost:3000/api/tvb/webhook'
            config['botSecret'] = 'dev'
            print("🏠 Local development mode enabled")
        
        print("🔧 Validating configuration...")
        config = validate_config(config, args.private_key, args.network)
        
        # Print config summary
        print_config_summary(config)
        
        # Initialize bot
        print("\n🤖 Initializing bot...")
        
        # Import the simplified bot core
        try:
            from bot.simple_core import SimpleTVBBot
        except ImportError:
            print("❌ SimpleTVBBot not found")
            print("💡 Make sure bot/simple_core.py exists")
            sys.exit(1)
        
        bot = SimpleTVBBot(config, args.private_key)
        
        if args.dry_run:
            print("\n✅ Dry run completed successfully!")
            print(f"🤖 Bot '{bot.display_name}' is ready to trade")
            print(f"💼 Wallet: {bot.account.address}")
            print(f"💰 Balance: {bot.get_avax_balance():.6f} AVAX")
            print(f"🎯 Tradeable tokens: {len(bot.tokens)}")
            
            # Show funding instructions if balance is 0
            if bot.get_avax_balance() == 0:
                print("\n💡 To start trading, fund your wallet:")
                print(f"📍 Send AVAX to: {bot.account.address}")
                print("🌐 Avalanche Fuji Testnet Faucet: https://faucet.avax.network/")
            
            return
        
        if args.auto:
            print("\n🚀 Starting automated trading...")
            bot.run()
        else:
            print(f"\n✅ Bot '{bot.display_name}' initialized successfully!")
            print(f"💼 Wallet: {bot.account.address}")
            print(f"💰 Balance: {bot.get_avax_balance():.6f} AVAX")
            print(f"🎯 Tradeable tokens: {len(bot.tokens)}")
            
            # Show funding instructions if balance is 0
            if bot.get_avax_balance() == 0:
                print("\n⚠️  Your wallet has no AVAX! Fund it first:")
                print(f"📍 Send AVAX to: {bot.account.address}")
                print("🌐 Avalanche Fuji Testnet Faucet: https://faucet.avax.network/")
            
            print(f"\n💡 Add --auto to start trading automatically")
            print(f"Example: python main.py --config {args.config} --auto")
    
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()