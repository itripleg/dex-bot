#!/usr/bin/env python3
"""
FIXED Factory contract interface with correct ABI from the actual contract
Addresses transaction revert issues by using the exact function signatures
"""

from web3 import Web3

class FactoryContract:
    """FIXED Interface for the TokenFactory smart contract with correct ABI"""
    
    def __init__(self, w3, address):
        self.w3 = w3
        self.address = w3.to_checksum_address(address)
        self.abi = self._get_correct_factory_abi()
        self.contract = w3.eth.contract(address=self.address, abi=self.abi)
        
        print(f"🤖 TVB: 📜 FIXED Factory contract initialized at {address}")
    
    def _get_correct_factory_abi(self):
        """Get the CORRECTED factory contract ABI based on the actual Solidity contract"""
        return [
            # CREATE TOKEN FUNCTION - matches createToken in GrandFactory.sol
            {
                "inputs": [
                    {"internalType": "string", "name": "name", "type": "string"},
                    {"internalType": "string", "name": "symbol", "type": "string"}, 
                    {"internalType": "string", "name": "imageUrl", "type": "string"},
                    {"internalType": "address", "name": "burnManager", "type": "address"},
                    {"internalType": "uint256", "name": "minTokensOut", "type": "uint256"}
                ],
                "name": "createToken",
                "outputs": [{"internalType": "address", "name": "", "type": "address"}],
                "stateMutability": "payable",
                "type": "function"
            },
            
            # BUY FUNCTION - matches buy function in GrandFactory.sol
            {
                "inputs": [
                    {"internalType": "address", "name": "tokenAddress", "type": "address"},
                    {"internalType": "uint256", "name": "minTokensOut", "type": "uint256"}
                ],
                "name": "buy",
                "outputs": [],
                "stateMutability": "payable", 
                "type": "function"
            },
            
            # SELL FUNCTION - matches sell function in GrandFactory.sol
            {
                "inputs": [
                    {"internalType": "address", "name": "tokenAddress", "type": "address"},
                    {"internalType": "uint256", "name": "tokenAmount", "type": "uint256"},
                    {"internalType": "uint256", "name": "minEthOut", "type": "uint256"}
                ],
                "name": "sell",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            
            # VIEW FUNCTIONS
            {
                "inputs": [],
                "name": "getAllTokens", 
                "outputs": [{"internalType": "address[]", "name": "", "type": "address[]"}],
                "stateMutability": "view",
                "type": "function"
            },
            
            {
                "inputs": [{"internalType": "address", "name": "tokenAddress", "type": "address"}],
                "name": "getTokenState",
                "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
                "stateMutability": "view", 
                "type": "function"
            },
            
            {
                "inputs": [{"internalType": "address", "name": "", "type": "address"}],
                "name": "lastPrice",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            
            {
                "inputs": [
                    {"internalType": "address", "name": "tokenAddress", "type": "address"},
                    {"internalType": "uint256", "name": "tokenAmount", "type": "uint256"}
                ],
                "name": "calculateBuyPrice", 
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            
            {
                "inputs": [
                    {"internalType": "address", "name": "tokenAddress", "type": "address"},
                    {"internalType": "uint256", "name": "tokenAmount", "type": "uint256"}
                ],
                "name": "calculateSellPrice",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], 
                "stateMutability": "view",
                "type": "function"
            },
            
            {
                "inputs": [
                    {"internalType": "address", "name": "tokenAddress", "type": "address"},
                    {"internalType": "uint256", "name": "ethAmount", "type": "uint256"}
                ],
                "name": "calculateTokenAmount",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            
            {
                "inputs": [{"internalType": "uint256", "name": "amount", "type": "uint256"}],
                "name": "calculateFee",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "pure",
                "type": "function"
            },
            
            {
                "inputs": [{"internalType": "address", "name": "token", "type": "address"}],
                "name": "getFundingGoal",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            
            {
                "inputs": [{"internalType": "address", "name": "", "type": "address"}],
                "name": "collateral",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            
            {
                "inputs": [{"internalType": "address", "name": "", "type": "address"}],
                "name": "virtualSupply",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            
            # CONSTANTS
            {
                "inputs": [],
                "name": "INITIAL_PRICE",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            
            {
                "inputs": [],
                "name": "MIN_PURCHASE", 
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            
            {
                "inputs": [],
                "name": "MAX_PURCHASE",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
    
    def get_all_tokens(self):
        """Get all token addresses from the factory"""
        try:
            return self.contract.functions.getAllTokens().call()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting all tokens: {e}")
            return []
    
    def get_token_state(self, token_address):
        """Get the current state of a token"""
        try:
            return self.contract.functions.getTokenState(
                self.w3.to_checksum_address(token_address)
            ).call()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting token state for {token_address}: {e}")
            return 0
    
    def get_last_price(self, token_address):
        """Get the last recorded price of a token"""
        try:
            return self.contract.functions.lastPrice(
                self.w3.to_checksum_address(token_address)
            ).call()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting last price for {token_address}: {e}")
            return 0
    
    def calculate_token_amount(self, token_address, eth_amount):
        """Calculate how many tokens can be bought with given ETH amount"""
        try:
            eth_amount_wei = self.w3.to_wei(eth_amount, 'ether')
            return self.contract.functions.calculateTokenAmount(
                self.w3.to_checksum_address(token_address),
                eth_amount_wei
            ).call()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error calculating token amount: {e}")
            return 0
    
    def calculate_buy_price(self, token_address, token_amount):
        """Calculate price for buying specific token amount"""
        try:
            return self.contract.functions.calculateBuyPrice(
                self.w3.to_checksum_address(token_address),
                token_amount
            ).call()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error calculating buy price: {e}")
            return 0
    
    def calculate_sell_price(self, token_address, token_amount):
        """Calculate price for selling specific token amount"""
        try:
            return self.contract.functions.calculateSellPrice(
                self.w3.to_checksum_address(token_address),
                token_amount
            ).call()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error calculating sell price: {e}")
            return 0
    
    def calculate_fee(self, amount):
        """Calculate trading fee for given amount"""
        try:
            amount_wei = self.w3.to_wei(amount, 'ether')
            return self.contract.functions.calculateFee(amount_wei).call()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error calculating fee: {e}")
            return 0
    
    def get_funding_goal(self, token_address):
        """Get the funding goal for a token"""
        try:
            return self.contract.functions.getFundingGoal(
                self.w3.to_checksum_address(token_address)
            ).call()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting funding goal for {token_address}: {e}")
            return 0
    
    def get_collateral(self, token_address):
        """Get the current collateral amount for a token"""
        try:
            return self.contract.functions.collateral(
                self.w3.to_checksum_address(token_address)
            ).call()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting collateral for {token_address}: {e}")
            return 0
    
    def get_virtual_supply(self, token_address):
        """Get virtual supply for a token"""
        try:
            return self.contract.functions.virtualSupply(
                self.w3.to_checksum_address(token_address)
            ).call()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting virtual supply for {token_address}: {e}")
            return 0
    
    def get_constants(self):
        """Get contract constants for validation"""
        try:
            return {
                "INITIAL_PRICE": self.contract.functions.INITIAL_PRICE().call(),
                "MIN_PURCHASE": self.contract.functions.MIN_PURCHASE().call(), 
                "MAX_PURCHASE": self.contract.functions.MAX_PURCHASE().call()
            }
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting constants: {e}")
            return {}
    
    def is_token_tradeable(self, token_address):
        """Check if a token is in a tradeable state"""
        state = self.get_token_state(token_address)
        return state in [1, 4]  # TRADING or RESUMED states
    
    def get_tradeable_tokens(self):
        """Get all tokens that are currently tradeable"""
        all_tokens = self.get_all_tokens()
        tradeable = []
        
        for token_address in all_tokens:
            if self.is_token_tradeable(token_address):
                tradeable.append(token_address)
        
        return tradeable
    
    def validate_trade_parameters(self, token_address, action, amount=None):
        """Validate parameters before making a trade"""
        try:
            # Check token state
            state = self.get_token_state(token_address)
            if state not in [1, 4]:  # TRADING or RESUMED
                return False, f"Token not tradeable (state: {state})"
            
            # Get contract constants for validation
            constants = self.get_constants()
            
            if action == "buy" and amount:
                amount_wei = self.w3.to_wei(amount, 'ether')
                min_purchase = constants.get('MIN_PURCHASE', 0)
                max_purchase = constants.get('MAX_PURCHASE', 0)
                
                if amount_wei < min_purchase:
                    return False, f"Amount below minimum ({self.w3.from_wei(min_purchase, 'ether')} AVAX)"
                
                if amount_wei > max_purchase:
                    return False, f"Amount above maximum ({self.w3.from_wei(max_purchase, 'ether')} AVAX)"
            
            return True, "Valid"
            
        except Exception as e:
            return False, f"Validation error: {e}"


# Token state constants
class TokenState:
    NOT_CREATED = 0
    TRADING = 1
    GOAL_REACHED = 2
    HALTED = 3
    RESUMED = 4
    
    @classmethod
    def get_name(cls, state):
        """Get human-readable name for token state"""
        names = {
            0: "Not Created",
            1: "Trading", 
            2: "Goal Reached",
            3: "Halted",
            4: "Resumed"
        }
        return names.get(state, f"Unknown ({state})")
    
    @classmethod
    def is_tradeable(cls, state):
        """Check if a state allows trading"""
        return state in [cls.TRADING, cls.RESUMED]


# Example usage and testing
if __name__ == "__main__":
    print("🤖 TVB: FIXED Factory contract interface loaded!")
    print("🤖 TVB: Key fixes:")
    print("  ✅ Correct sell function signature (3 parameters)")
    print("  ✅ Added minEthOut parameter to sell calls")
    print("  ✅ Added validation functions")
    print("  ✅ Updated ABI to match actual contract")
    
    print("\n🤖 TVB: Token states:")
    for i in range(5):
        print(f"  {i}: {TokenState.get_name(i)} (Tradeable: {TokenState.is_tradeable(i)})")
    
    print("\n🤖 TVB: ✅ FIXED Factory contract module ready!")