#!/usr/bin/env python3
"""
Factory contract interface for TVB bot interactions
Handles all factory contract calls and ABI management
"""

from web3 import Web3

class FactoryContract:
    """Interface for the TokenFactory smart contract"""
    
    def __init__(self, w3, address):
        self.w3 = w3
        self.address = w3.to_checksum_address(address)
        self.abi = self._get_factory_abi()
        self.contract = w3.eth.contract(address=self.address, abi=self.abi)
        
        print(f"🤖 TVB: 📜 Factory contract initialized at {address}")
    
    def _get_factory_abi(self):
        """Get the complete factory contract ABI"""
        return [
            {
                "inputs": [
                    {"internalType": "string", "name": "name", "type": "string"},
                    {"internalType": "string", "name": "symbol", "type": "string"},
                    {"internalType": "string", "name": "imageUrl", "type": "string"},
                    {"internalType": "address", "name": "burnManager", "type": "address"}
                ],
                "name": "createToken",
                "outputs": [{"internalType": "address", "name": "", "type": "address"}],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [{"internalType": "address", "name": "token", "type": "address"}],
                "name": "buy",
                "outputs": [],
                "stateMutability": "payable",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "address", "name": "token", "type": "address"},
                    {"internalType": "uint256", "name": "amount", "type": "uint256"}
                ],
                "name": "sell",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "getAllTokens",
                "outputs": [{"internalType": "address[]", "name": "", "type": "address[]"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [{"internalType": "address", "name": "tokenAddress", "type": "address"}],
                "name": "lastPrice",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
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
                "inputs": [{"internalType": "address", "name": "tokenAddress", "type": "address"}],
                "name": "getCurrentPrice",
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
                "inputs": [{"internalType": "uint256", "name": "amount", "type": "uint256"}],
                "name": "calculateFee",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "pure",
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
    
    def get_current_price(self, token_address):
        """Get the current price of a token"""
        try:
            return self.contract.functions.getCurrentPrice(
                self.w3.to_checksum_address(token_address)
            ).call()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting current price for {token_address}: {e}")
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
    
    def get_token_info(self, token_address):
        """Get comprehensive information about a token"""
        try:
            address = self.w3.to_checksum_address(token_address)
            
            info = {
                "address": address,
                "state": self.get_token_state(address),
                "current_price": self.get_current_price(address),
                "last_price": self.get_last_price(address),
                "funding_goal": self.get_funding_goal(address),
                "collateral": self.get_collateral(address)
            }
            
            # Add calculated fields
            if info["funding_goal"] > 0:
                info["funding_progress"] = (info["collateral"] / info["funding_goal"]) * 100
            else:
                info["funding_progress"] = 0
            
            return info
            
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting token info for {token_address}: {e}")
            return None
    
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
    
    def get_token_states_batch(self, token_addresses):
        """Get states for multiple tokens efficiently"""
        states = {}
        
        for address in token_addresses:
            try:
                state = self.get_token_state(address)
                states[address] = state
            except Exception as e:
                print(f"🤖 TVB: ⚠️ Error getting state for {address}: {e}")
                states[address] = 0  # Default to NOT_CREATED
        
        return states
    
    def estimate_gas_for_buy(self, token_address, eth_amount):
        """Estimate gas needed for a buy transaction"""
        try:
            return self.contract.functions.buy(
                self.w3.to_checksum_address(token_address)
            ).estimate_gas({
                'value': self.w3.to_wei(eth_amount, 'ether')
            })
        except Exception as e:
            print(f"🤖 TVB: ❌ Error estimating buy gas: {e}")
            return 500000  # Default fallback
    
    def estimate_gas_for_sell(self, token_address, token_amount):
        """Estimate gas needed for a sell transaction"""
        try:
            return self.contract.functions.sell(
                self.w3.to_checksum_address(token_address),
                token_amount
            ).estimate_gas()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error estimating sell gas: {e}")
            return 500000  # Default fallback


# Token state constants for easy reference
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
    print("🤖 TVB: Factory contract interface loaded!")
    
    # Example of how to use the interface
    print("🤖 TVB: Token states:")
    for i in range(5):
        print(f"  {i}: {TokenState.get_name(i)} (Tradeable: {TokenState.is_tradeable(i)})")
    
    print("🤖 TVB: ✅ Factory contract module test complete!")