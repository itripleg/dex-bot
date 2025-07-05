#!/usr/bin/env python3
"""
Token Creation System for TVB Bots
Generates clever names, tickers, and images based on bot personality
"""

import random
import json
from typing import Dict, List, Tuple

class TokenCreator:
    """Handles creative token generation with personality-driven names and themes"""
    
    def __init__(self, bot_name: str, config: dict, logger=None):
        self.bot_name = bot_name
        self.config = config
        self.logger = logger
        
        # Bot personality traits
        self.buy_bias = config.get('buyBias', 0.6)
        self.risk_tolerance = config.get('riskTolerance', 0.5)
        
        # Initialize theme datasets based on bot personality
        self._init_personality_themes()
    
    def _init_personality_themes(self):
        """Initialize token themes based on bot personality"""
        
        # Bullish themes (high buy bias)
        self.bullish_themes = {
            "names": [
                "Moon Shot", "Rocket Fuel", "Diamond Hands", "Bull Power", "To The Stars",
                "Green Candles", "Profit Express", "Golden Bull", "Sky Rocket", "Victory Token",
                "Champion Coin", "Success Stone", "Winner Token", "Growth Gold", "Rise Coin"
            ],
            "symbols": ["MOON", "REKT", "BULL", "PUMP", "GOLD", "WIN", "UP", "RISE", "GAIN", "BOOM"],
            "images": [
                "🚀", "🌙", "💎", "🐂", "⭐", "📈", "💰", "🏆", "✨", "🔥",
                "🎯", "💪", "🌟", "⚡", "🎉"
            ]
        }
        
        # Bearish themes (low buy bias)
        self.bearish_themes = {
            "names": [
                "Market Crash", "Bear Cave", "Red Alert", "Down Turn", "Sell Signal",
                "Market Fear", "Crash Warning", "Bear Trap", "Drop Zone", "Decline Token",
                "Short Squeeze", "Market Doom", "Red Candle", "Fall Token", "Bear Market"
            ],
            "symbols": ["BEAR", "DUMP", "DOWN", "SELL", "RED", "FALL", "DROP", "FEAR", "CASH", "EXIT"],
            "images": [
                "🐻", "📉", "🔴", "⬇️", "💔", "😱", "🚨", "⚠️", "💸", "🔻",
                "❌", "💀", "🌧️", "⚡", "🖤"
            ]
        }
        
        # Neutral/Balanced themes
        self.neutral_themes = {
            "names": [
                "Stable Coin", "Balance Token", "Steady Growth", "Market Neutral", "Calm Waters",
                "Even Steven", "Middle Ground", "Balanced View", "Steady State", "Equal Weight",
                "Fair Value", "Moderate Move", "Center Point", "Level Playing", "Balanced Force"
            ],
            "symbols": ["BAL", "EVEN", "FAIR", "MID", "CALM", "ZERO", "NEUT", "CENT", "PARITY", "STILL"],
            "images": [
                "⚖️", "🎯", "🔄", "🟨", "🔸", "⭕", "🔆", "🔳", "⚪", "🔘",
                "🎪", "🎭", "🎨", "🎲", "🎮"
            ]
        }
        
        # High-risk themes (high risk tolerance)
        self.risky_themes = {
            "names": [
                "Wild Card", "Risk Taker", "High Stakes", "Danger Zone", "All In",
                "Maximum Risk", "Bold Move", "Extreme Play", "Risky Business", "High Roller",
                "Gamble Gold", "Lucky Strike", "Fortune Favors", "High Voltage", "Adrenaline"
            ],
            "symbols": ["RISK", "WILD", "YOLO", "LUCK", "DICE", "ODDS", "VOLT", "RUSH", "EDGE", "PEAK"],
            "images": [
                "🎰", "🎲", "⚡", "🔥", "💥", "🌪️", "🎯", "🎪", "🎢", "⚔️",
                "🏁", "🎭", "🌋", "💎", "🚀"
            ]
        }
        
        # Conservative themes (low risk tolerance)
        self.conservative_themes = {
            "names": [
                "Safe Haven", "Steady Eddie", "Conservative Choice", "Stable Foundation", "Secure Vault",
                "Prudent Pick", "Careful Capital", "Safety First", "Stable Ground", "Secure Base",
                "Cautious Coin", "Protected Asset", "Stable Value", "Security Token", "Safe Bet"
            ],
            "symbols": ["SAFE", "VAULT", "GUARD", "SHIELD", "SECURE", "STABLE", "SOLID", "TRUST", "SAVE", "KEEP"],
            "images": [
                "🛡️", "🏰", "🔒", "🏦", "⚓", "🛶", "🏠", "🎯", "📊", "💼",
                "🔐", "🎪", "🌳", "🗻", "⛰️"
            ]
        }
        
        # Bot-specific personality themes
        self.bot_specific_themes = {
            "bullish_billy": {
                "names": ["Billy's Best", "Optimistic Option", "Billy Bull Run", "Positive Profit", "Happy Holdings"],
                "symbols": ["BILLY", "OPT", "HAPPY", "SMILE", "BULL"],
                "images": ["😊", "👍", "🎉", "🌟", "💚"]
            },
            "companion_cube": {
                "names": ["Test Subject", "Portal Protocol", "Aperture Asset", "Science Coin", "Lab Token"],
                "symbols": ["TEST", "PORTAL", "LAB", "CUBE", "SCI"],
                "images": ["🧪", "🔬", "⚗️", "🔳", "🎯"]
            },
            "jackpot_jax": {
                "names": ["Sniper Shot", "Precision Play", "Tactical Token", "Sharp Shooter", "Exact Entry"],
                "symbols": ["SNIPE", "SHARP", "AIM", "HIT", "EXACT"],
                "images": ["🎯", "🔫", "🏹", "⚡", "🎪"]
            },
            "melancholy_mort": {
                "names": ["Doom Token", "Pessimist Coin", "Gloom Gold", "Sad Coin", "Despair Dollar"],
                "symbols": ["DOOM", "GLOOM", "SAD", "MORT", "DARK"],
                "images": ["😔", "🌧️", "⚫", "💀", "⚰️"]
            }
        }
    
    def generate_token_concept(self) -> Dict[str, str]:
        """Generate a complete token concept with name, symbol, and image"""
        
        # Choose theme based on personality
        chosen_theme = self._select_theme()
        
        # Generate components
        name = self._generate_name(chosen_theme)
        symbol = self._generate_symbol(chosen_theme, name)
        image_emoji = self._generate_image(chosen_theme)
        
        # Create concept
        concept = {
            "name": name,
            "symbol": symbol,
            "image_emoji": image_emoji,
            "theme": chosen_theme["type"],
            "personality_match": self._calculate_personality_match(chosen_theme)
        }
        
        if self.logger:
            self.logger.info(f"🎨 Generated token concept: {concept['name']} (${concept['symbol']}) {concept['image_emoji']}")
        
        return concept
    
    def _select_theme(self) -> Dict:
        """Select appropriate theme based on bot personality"""
        themes = []
        
        # Add bot-specific themes (higher weight)
        if self.bot_name in self.bot_specific_themes:
            for _ in range(3):  # 3x weight
                themes.append({
                    "type": "bot_specific",
                    "data": self.bot_specific_themes[self.bot_name]
                })
        
        # Add personality-based themes
        if self.buy_bias > 0.7:
            for _ in range(2):  # 2x weight for strong bias
                themes.append({"type": "bullish", "data": self.bullish_themes})
        elif self.buy_bias < 0.3:
            for _ in range(2):
                themes.append({"type": "bearish", "data": self.bearish_themes})
        else:
            themes.append({"type": "neutral", "data": self.neutral_themes})
        
        # Add risk-based themes
        if self.risk_tolerance > 0.7:
            themes.append({"type": "risky", "data": self.risky_themes})
        elif self.risk_tolerance < 0.3:
            themes.append({"type": "conservative", "data": self.conservative_themes})
        
        # Fallback to neutral if no themes
        if not themes:
            themes.append({"type": "neutral", "data": self.neutral_themes})
        
        return random.choice(themes)
    
    def _generate_name(self, theme: Dict) -> str:
        """Generate a creative token name"""
        base_names = theme["data"]["names"]
        
        # 80% chance use base name, 20% chance modify it
        if random.random() < 0.8:
            return random.choice(base_names)
        else:
            # Create variations
            base = random.choice(base_names)
            modifiers = ["Pro", "Max", "Plus", "Ultra", "Super", "Mega", "Prime", "Elite", "Advanced"]
            
            if random.random() < 0.5:
                return f"{base} {random.choice(modifiers)}"
            else:
                return f"{random.choice(modifiers)} {base}"
    
    def _generate_symbol(self, theme: Dict, name: str) -> str:
        """Generate a ticker symbol"""
        base_symbols = theme["data"]["symbols"]
        
        # 70% chance use theme symbol, 30% chance derive from name
        if random.random() < 0.7:
            symbol = random.choice(base_symbols)
        else:
            # Derive from name
            words = name.upper().split()
            if len(words) >= 2:
                symbol = words[0][:2] + words[1][:2]  # First 2 chars of each word
            else:
                symbol = words[0][:4]  # First 4 chars
        
        # Ensure 3-5 characters
        if len(symbol) < 3:
            symbol += "X" * (3 - len(symbol))
        elif len(symbol) > 5:
            symbol = symbol[:5]
        
        return symbol.upper()
    
    def _generate_image(self, theme: Dict) -> str:
        """Generate an image emoji"""
        return random.choice(theme["data"]["images"])
    
    def _calculate_personality_match(self, theme: Dict) -> float:
        """Calculate how well the theme matches bot personality (0-1)"""
        theme_type = theme["type"]
        
        if theme_type == "bot_specific":
            return 1.0
        elif theme_type == "bullish" and self.buy_bias > 0.6:
            return 0.9
        elif theme_type == "bearish" and self.buy_bias < 0.4:
            return 0.9
        elif theme_type == "risky" and self.risk_tolerance > 0.6:
            return 0.8
        elif theme_type == "conservative" and self.risk_tolerance < 0.4:
            return 0.8
        elif theme_type == "neutral":
            return 0.6
        else:
            return 0.3
    
    def should_create_token(self) -> bool:
        """Determine if bot should create a token based on personality and randomness"""
        base_chance = self.config.get('createTokenChance', 0.02)
        
        # Modify based on personality
        if self.buy_bias > 0.7:  # Very bullish bots create more
            base_chance *= 1.5
        elif self.buy_bias < 0.3:  # Bearish bots create less
            base_chance *= 0.5
        
        if self.risk_tolerance > 0.7:  # Risky bots create more
            base_chance *= 1.3
        elif self.risk_tolerance < 0.3:  # Conservative bots create less
            base_chance *= 0.7
        
        return random.random() < base_chance
    
    def create_token_on_chain(self, w3, factory_contract, account, concept: Dict, eth_amount: float = 0.01) -> Tuple[bool, str]:
        """Actually create the token on-chain"""
        try:
            if self.logger:
                self.logger.info(f"🎨 Creating token on-chain: {concept['name']} (${concept['symbol']})")
            
            # Convert emoji to IPFS-compatible image URL (simplified)
            # In a real implementation, you'd upload the image to IPFS
            image_url = f"data:text/plain;charset=utf-8,{concept['image_emoji']}"
            
            # Build transaction
            nonce = w3.eth.get_transaction_count(account.address)
            
            txn = factory_contract.functions.createToken(
                concept['name'],
                concept['symbol'],
                image_url,
                account.address,  # burnManager = creator
                0  # minTokensOut = 0 (no slippage protection)
            ).build_transaction({
                'from': account.address,
                'value': w3.to_wei(eth_amount, 'ether'),
                'gas': 1000000,  # Higher gas for token creation
                'gasPrice': w3.eth.gas_price,
                'nonce': nonce,
                'chainId': 43113  # Avalanche Fuji testnet
            })
            
            # Sign and send
            signed_txn = account.sign_transaction(txn)
            tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
            tx_hash_hex = w3.to_hex(tx_hash)
            
            if self.logger:
                self.logger.info(f"🎨 Token creation transaction sent: {tx_hash_hex}")
            
            # Wait for confirmation
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt.status == 1:
                if self.logger:
                    self.logger.success(f"🎉 Token created successfully! TX: {tx_hash_hex}")
                return True, tx_hash_hex
            else:
                error_msg = f"Token creation failed! TX: {tx_hash_hex}"
                if self.logger:
                    self.logger.error(error_msg)
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Token creation error: {e}"
            if self.logger:
                self.logger.error(error_msg)
            return False, error_msg
    
    def get_creation_phrases(self) -> List[str]:
        """Get personality-appropriate creation phrases"""
        base_phrases = self.config.get('createPhrases', [
            "Launching something new!",
            "Fresh opportunity incoming!",
            "Creating the next gem!",
            "Innovation time!",
            "New token, new possibilities!"
        ])
        
        return base_phrases


# Example usage and testing
if __name__ == "__main__":
    # Test with different bot personalities
    test_configs = {
        "bullish_billy": {"buyBias": 0.8, "riskTolerance": 0.65, "createTokenChance": 0.03},
        "companion_cube": {"buyBias": 0.5, "riskTolerance": 0.5, "createTokenChance": 0.001},
        "melancholy_mort": {"buyBias": 0.15, "riskTolerance": 0.3, "createTokenChance": 0.005}
    }
    
    print("🎨 Testing Token Creator System:")
    print("=" * 50)
    
    for bot_name, config in test_configs.items():
        print(f"\n🤖 {bot_name.replace('_', ' ').title()}:")
        creator = TokenCreator(bot_name, config)
        
        # Generate 3 concepts for each bot
        for i in range(3):
            concept = creator.generate_token_concept()
            print(f"  {i+1}. {concept['name']} (${concept['symbol']}) {concept['image_emoji']} - Theme: {concept['theme']}")
    
    print("\n🎨 ✅ Token Creator system test complete!")