# keygen.py
#!/usr/bin/env python3
"""
TVB Key Generation Utility
Simple script to generate new Ethereum key pairs for TVB bots
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

from eth_account import Account
from bot.config import create_example_env_file

def generate_keypair(save_to_env=False, show_qr=False):
    """Generate a new Ethereum key pair"""
    print("🔑 TVB Key Generator")
    print("=" * 50)
    
    # Generate new account
    account = Account.create()
    
    print(f"✨ New key pair generated!")
    print(f"📍 Address: {account.address}")
    print(f"🔐 Private Key: {account.key.hex()}")
    print("=" * 50)
    
    # Security warnings
    print("⚠️  SECURITY WARNINGS:")
    print("• Keep your private key secret and secure!")
    print("• Never share it with anyone!")
    print("• Back it up in a safe location!")
    print("• Consider using hardware wallets for large amounts!")
    print("=" * 50)
    
    # Funding instructions
    print("💰 FUNDING INSTRUCTIONS:")
    print(f"• Send AVAX to: {account.address}")
    print("• Recommended minimum: 0.1 AVAX for testing")
    print("• Avalanche Fuji Testnet Faucet:")
    print("  https://faucet.avax.network/")
    print("=" * 50)
    
    # Save to .env.local if requested
    if save_to_env:
        try:
            create_example_env_file(account.key.hex())
            print("✅ Private key saved to .env.local file!")
        except Exception as e:
            print(f"❌ Error saving to .env.local: {e}")
    
    # Show QR code if requested and qrcode is available
    if show_qr:
        try:
            import qrcode
            
            print("\n📱 QR Code for Address:")
            qr = qrcode.QRCode(version=1, box_size=1, border=1)
            qr.add_data(account.address)
            qr.make(fit=True)
            qr.print_ascii(invert=True)
            
        except ImportError:
            print("⚠️  QR code generation requires: pip install qrcode[pil]")
    
    return account.address, account.key.hex()

def main():
    """Main CLI interface"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Generate new Ethereum key pairs for TVB bots',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python keygen.py                          # Generate and display key pair
  python keygen.py --save                   # Generate and save to .env.local
  python keygen.py --save --qr              # Generate, save, and show QR code
  python keygen.py --multiple 5             # Generate 5 key pairs
        """
    )
    
    parser.add_argument(
        '--save', '-s',
        action='store_true',
        help='Save the generated private key to .env.local file'
    )
    
    parser.add_argument(
        '--qr', '-q',
        action='store_true',
        help='Display QR code for the address (requires qrcode package)'
    )
    
    parser.add_argument(
        '--multiple', '-m',
        type=int,
        default=1,
        help='Generate multiple key pairs (default: 1)'
    )
    
    parser.add_argument(
        '--format',
        choices=['table', 'json', 'csv'],
        default='table',
        help='Output format for multiple keys (default: table)'
    )
    
    args = parser.parse_args()
    
    if args.multiple == 1:
        # Single key generation
        generate_keypair(save_to_env=args.save, show_qr=args.qr)
    else:
        # Multiple key generation
        print(f"🔑 Generating {args.multiple} key pairs...")
        print("=" * 70)
        
        keypairs = []
        for i in range(args.multiple):
            account = Account.create()
            keypairs.append((account.address, account.key.hex()))
        
        # Output in requested format
        if args.format == 'table':
            print(f"{'#':<3} {'Address':<42} {'Private Key'}")
            print("-" * 70)
            for i, (addr, key) in enumerate(keypairs, 1):
                print(f"{i:<3} {addr:<42} {key}")
                
        elif args.format == 'json':
            import json
            output = [{"address": addr, "privateKey": key} for addr, key in keypairs]
            print(json.dumps(output, indent=2))
            
        elif args.format == 'csv':
            print("address,privateKey")
            for addr, key in keypairs:
                print(f"{addr},{key}")
        
        print("=" * 70)
        print("⚠️  Remember to keep these private keys secure!")

if __name__ == "__main__":
    main()