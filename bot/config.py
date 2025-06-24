#!/usr/bin/env python3
"""
Enhanced configuration loading with environment security for public repositories
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv

class EnvironmentManager:
    """Secure environment variable management"""
    
    def __init__(self, project_root=None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.loaded_files = []
        self._load_environment_files()
    
    def _load_environment_files(self):
        """Load environment files in priority order"""
        env_files = ['.env', '.env.local', '.env.production']
        
        for env_file in env_files:
            env_path = self.project_root / env_file
            if env_path.exists():
                load_dotenv(env_path, override=True)
                self.loaded_files.append(str(env_path))
                print(f"🤖 TVB: 📄 Loaded environment from {env_file}")
    
    def get_private_key(self, config, override_key=None, bot_name=None):
        """Get private key with multiple fallback sources"""
        # Ensure bot_name is valid for environment variable construction
        if bot_name:
            bot_name = str(bot_name).upper()
        
        sources = [
            ("CLI override", override_key),
            (f"BOT_{bot_name}_PRIVATE_KEY", os.getenv(f"BOT_{bot_name}_PRIVATE_KEY") if bot_name else None),
            ("BOT_PRIVATE_KEY", os.getenv('BOT_PRIVATE_KEY')),
            ("PRIVATE_KEY", os.getenv('PRIVATE_KEY')),
            ("Config file", config.get('privateKey')),
        ]
        
        for source_name, key in sources:
            if key and key != "SET_IN_ENV_LOCAL":  # Skip placeholder values
                if not key.startswith('0x'):
                    key = f"0x{key}"
                print(f"🤖 TVB: 🔑 Private key loaded from: {source_name}")
                return key
        
        raise ValueError(self._get_private_key_error_message(bot_name))
    
    def _get_private_key_error_message(self, bot_name):
        """Generate helpful error message for missing private key"""
        bot_specific = f"BOT_{bot_name.upper()}_PRIVATE_KEY" if bot_name else None
        
        message = [
            "🔑 Private key not found! Please provide via one of these methods:",
            "",
            "1. Command line:",
            "   python main.py --private-key 0x123...",
            "",
            "2. Environment variables (.env.local):"
        ]
        
        if bot_specific:
            message.extend([
                f"   {bot_specific}=0x123...",
                "   BOT_PRIVATE_KEY=0x123...",
            ])
        else:
            message.append("   BOT_PRIVATE_KEY=0x123...")
        
        message.extend([
            "",
            "💡 Recommended: Create .env.local with your secrets",
            "   (automatically gitignored for security)"
        ])
        
        return "\n".join(message)
    
    def get_secure_value(self, config, config_key, env_keys, description="value", bot_name=None):
        """Get a secure value from environment or config with bot-specific support"""
        # Add bot-specific environment key if bot_name provided
        if bot_name:
            bot_name = str(bot_name).upper()
            # Create bot-specific key from the first generic key
            if env_keys:
                base_key = env_keys[0].replace('BOT_', '').replace(f'{bot_name}_', '')
                bot_specific_key = f"BOT_{bot_name}_{base_key}"
                env_keys = [bot_specific_key] + env_keys
        
        # Try environment variables first
        for env_key in env_keys:
            value = os.getenv(env_key)
            if value and value != f"SET_IN_ENV_LOCAL":
                print(f"🤖 TVB: 🔐 {description} loaded from: {env_key}")
                return value
        
        # Fall back to config
        config_value = config.get(config_key)
        if config_value and config_value != "SET_IN_ENV_LOCAL":
            print(f"🤖 TVB: ⚠️  {description} loaded from config file (consider moving to .env.local)")
            return config_value
        
        return None

# Initialize global environment manager
_env_manager = EnvironmentManager()

def load_bot_config(config_path):
    """Load and parse bot configuration from JSON file"""
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        print(f"🤖 TVB: ✅ Loaded config from {config_path}")
        return config
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file {config_path}: {e}")

def validate_config(config):
    """Validate required configuration fields"""
    required_fields = ['name', 'displayName', 'factoryAddress']
    
    missing_fields = []
    for field in required_fields:
        if not config.get(field):
            missing_fields.append(field)
    
    if missing_fields:
        raise ValueError(f"Missing required config fields: {missing_fields}")
    
    # Validate personality parameters
    personality_fields = {
        'buyBias': (0.0, 1.0),
        'riskTolerance': (0.0, 1.0),
        'createTokenChance': (0.0, 1.0),
        'minInterval': (1, 3600),
        'maxInterval': (1, 3600),
        'minTradeAmount': (0.0001, 1000),
        'maxTradeAmount': (0.0001, 1000)
    }
    
    for field, (min_val, max_val) in personality_fields.items():
        value = config.get(field)
        if value is not None and not (min_val <= value <= max_val):
            raise ValueError(f"Config field '{field}' must be between {min_val} and {max_val}")
    
    # Validate intervals
    min_interval = config.get('minInterval', 10)
    max_interval = config.get('maxInterval', 60)
    if max_interval < min_interval:
        raise ValueError("maxInterval must be >= minInterval")
    
    # Validate trade amounts
    min_trade = config.get('minTradeAmount', 0.001)
    max_trade = config.get('maxTradeAmount', 0.01)
    if max_trade < min_trade:
        raise ValueError("maxTradeAmount must be >= minTradeAmount")
    
    print("🤖 TVB: ✅ Configuration validation passed")

def get_private_key(config, override_key=None, bot_name=None):
    """Get private key with security and multiple sources"""
    return _env_manager.get_private_key(config, override_key, bot_name)

def merge_config_with_environment(config, use_local=False):
    """Merge config with environment variables for sensitive data"""
    enhanced_config = config.copy()
    bot_name = config.get('name', '')
    
    # Override webhook URL for local development
    if use_local:
        enhanced_config['webhookUrl'] = 'http://localhost:3000/api/tvb/webhook'
        print(f"🤖 TVB: 🏠 Using local development webhook: http://localhost:3000/api/tvb/webhook")
    
    # Get RPC URL from environment or config
    rpc_url = _env_manager.get_secure_value(
        config, 
        'rpcUrl',
        ['RPC_URL', 'AVALANCHE_RPC_URL'],
        'RPC URL',
        bot_name
    )
    if rpc_url:
        enhanced_config['rpcUrl'] = rpc_url
    elif not config.get('rpcUrl'):
        raise ValueError("RPC URL not found in environment or config")
    
    # Get webhook URL from environment (unless overridden by --local)
    if not use_local:
        webhook_url = _env_manager.get_secure_value(
            config,
            'webhookUrl', 
            ['WEBHOOK_URL'],
            'Webhook URL',
            bot_name
        )
        if webhook_url:
            enhanced_config['webhookUrl'] = webhook_url
    
    # Get webhook secret from environment (bot-specific first)
    webhook_secret = _env_manager.get_secure_value(
        config,
        'botSecret',
        ['WEBHOOK_SECRET', 'BOT_SECRET'],
        'Webhook secret',
        bot_name
    )
    if webhook_secret:
        enhanced_config['botSecret'] = webhook_secret
    
    # Get factory address from environment
    factory_address = _env_manager.get_secure_value(
        config,
        'factoryAddress',
        ['FACTORY_ADDRESS', 'TOKEN_FACTORY_ADDRESS'],
        'Factory address',
        bot_name
    )
    if factory_address:
        enhanced_config['factoryAddress'] = factory_address
    elif not config.get('factoryAddress'):
        raise ValueError("Factory address not found in environment or config")
    
    return enhanced_config

def get_default_phrases():
    """Get default personality phrases if not specified in config"""
    return {
        "buy": [
            "Going long! 📈",
            "Buying the dip! 💎", 
            "This looks bullish! 🚀",
            "Adding to my position! 💰",
            "Can't resist this price! 🤑"
        ],
        "sell": [
            "Taking profits! 💰",
            "Time to secure gains! ✅",
            "Partial exit here! 📉", 
            "Booking some wins! 🎯",
            "Smart exit strategy! 🧠"
        ],
        "create": [
            "Launching something new! 🚀",
            "Fresh opportunity incoming! ✨",
            "Creating the next gem! 💎",
            "Innovation time! 🔥",
            "New token, new possibilities! 🌟"
        ],
        "error": [
            "Minor technical hiccup! 🔧",
            "Temporary setback! ⏰",
            "Quick system adjustment! ⚙️", 
            "Brief interruption! 🛠️",
            "Back online soon! 🔄"
        ]
    }

def merge_config_with_defaults(config):
    """Merge user config with sensible defaults"""
    defaults = {
        "buyBias": 0.6,
        "riskTolerance": 0.5,
        "minInterval": 15,
        "maxInterval": 60,
        "minTradeAmount": 0.005,
        "maxTradeAmount": 0.02,
        "createTokenChance": 0.02,
        "avatarUrl": "/default-avatar.png",
        "cacheDurationHours": 6
    }
    
    # Merge defaults
    for key, default_value in defaults.items():
        if key not in config:
            config[key] = default_value
    
    # Merge default phrases
    default_phrases = get_default_phrases()
    for phrase_type, phrases in default_phrases.items():
        config_key = f"{phrase_type}Phrases"
        if config_key not in config or not config[config_key]:
            config[config_key] = phrases
    
    return config

def print_config_summary(config):
    """Print a summary of the loaded configuration"""
    print(f"🤖 TVB: Bot: {config['displayName']} ({config['name']})")
    
    # Mask sensitive RPC URL
    rpc_url = config.get('rpcUrl', 'Not configured')
    if 'alchemy.com' in rpc_url or 'infura.io' in rpc_url:
        # Mask API keys in URLs
        import re
        rpc_url = re.sub(r'/v2/[a-zA-Z0-9_-]+', '/v2/***API_KEY***', rpc_url)
    
    print(f"🤖 TVB: Network: {rpc_url}")
    print(f"🤖 TVB: Personality: Buy Bias={config['buyBias']:.2f}, Risk={config['riskTolerance']:.2f}")
    print(f"🤖 TVB: Intervals: {config['minInterval']}-{config['maxInterval']}s")
    print(f"🤖 TVB: Trade Size: {config['minTradeAmount']:.4f}-{config['maxTradeAmount']:.4f} AVAX")
    
    webhook_status = "✅ Enabled" if config.get('webhookUrl') else "❌ Disabled"
    print(f"🤖 TVB: Webhooks: {webhook_status}")

def sanitize_config_for_public(config):
    """Remove sensitive data from config for public sharing"""
    sanitized = config.copy()
    
    # Remove or replace sensitive fields
    sensitive_fields = {
        'privateKey': "SET_IN_ENV_LOCAL",
        'botSecret': "SET_IN_ENV_LOCAL", 
        'webhookUrl': "SET_IN_ENV_LOCAL",
        'rpcUrl': "SET_IN_ENV_LOCAL"  # Often contains API keys
    }
    
    for field, replacement in sensitive_fields.items():
        if field in sanitized:
            sanitized[field] = replacement
    
    return sanitized

def create_public_config_template(config, output_path=None):
    """Create a public-safe version of the config"""
    sanitized = sanitize_config_for_public(config)
    
    if output_path:
        output_file = Path(output_path)
        with open(output_file, 'w') as f:
            json.dump(sanitized, f, indent=2)
        print(f"🤖 TVB: 💾 Public config template saved to {output_path}")
    
    return sanitized

# CLI helper for config management
def main():
    """CLI tool for config management"""
    import argparse
    
    parser = argparse.ArgumentParser(description='TVB Config Management Tool')
    parser.add_argument('--sanitize', type=str, help='Sanitize config file for public sharing')
    parser.add_argument('--validate', type=str, help='Validate config file')
    parser.add_argument('--create-env', action='store_true', help='Create example environment files')
    
    args = parser.parse_args()
    
    if args.create_env:
        from .security import create_example_env_files
        create_example_env_files()
    
    if args.sanitize:
        config = load_bot_config(args.sanitize)
        sanitized = sanitize_config_for_public(config)
        
        output_path = Path(args.sanitize).stem + '_public.json'
        create_public_config_template(config, output_path)
        
        print("🤖 TVB: ✅ Config sanitized for public sharing!")
    
    if args.validate:
        try:
            config = load_bot_config(args.validate)
            config = merge_config_with_environment(config)
            validate_config(config)
            print_config_summary(config)
            print("🤖 TVB: ✅ Config validation passed!")
        except Exception as e:
            print(f"🤖 TVB: ❌ Config validation failed: {e}")

if __name__ == "__main__":
    main()