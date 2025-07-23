#!/usr/bin/env python3
"""
Fixed Factory contract interface for TVB bot interactions
Corrected ABI to match the actual GrandFactory.sol contract
"""

from web3 import Web3

class FactoryContract:
    """Interface for the TokenFactory smart contract with correct ABI"""
    
    def __init__(self, w3, address):
        self.w3 = w3
        self.address = w3.to_checksum_address(address)
        self.abi = self._get_factory_abi()
        self.contract = w3.eth.contract(address=self.address, abi=self.abi)
        
        print(f"🤖 TVB: 📜 Factory contract initialized at {address}")
    
    def _get_factory_abi(self):
        """Get the CORRECTED factory contract ABI matching GrandFactory.sol"""
        return [
            # CORRECTED: createToken with all required parameters
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
            # CORRECTED: buy with minTokensOut parameter
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
            # CORRECTED: sell with minEthOut parameter (this was the big one!)
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
            # View functions (these were mostly correct)
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
                "inputs": [
                    {"internalType": "address", "name": "tokenAddress", "type": "address"},
                    {"internalType": "uint256", "name": "ethAmount", "type": "uint256"}
                ],
                "name": "calculateTokenAmount",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            # NEW: Functions that were missing from original ABI
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
            },
            {
                "inputs": [{"internalType": "address", "name": "tokenAddress", "type": "address"}],
                "name": "resumeTrading",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [{"internalType": "address", "name": "tokenAddress", "type": "address"}],
                "name": "getGoalReachedTimestamp",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [{"internalType": "address", "name": "tokenAddress", "type": "address"}],
                "name": "getTimeUntilAutoResume",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            # Contract constants and state variables
            {
                "inputs": [],
                "name": "DECIMALS",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "MAX_SUPPLY",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
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
            },
            {
                "inputs": [],
                "name": "TRADING_FEE",
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
            {
                "inputs": [{"internalType": "address", "name": "", "type": "address"}],
                "name": "tokenCreators",
                "outputs": [{"internalType": "address", "name": "", "type": "address"}],
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
    
    def get_current_price(self, token_address):
        """Get the current price of a token using lastPrice (deprecated method name)"""
        return self.get_last_price(token_address)
    
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
        """Calculate the price to buy a specific amount of tokens"""
        try:
            return self.contract.functions.calculateBuyPrice(
                self.w3.to_checksum_address(token_address),
                token_amount
            ).call()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error calculating buy price: {e}")
            return 0
    
    def calculate_sell_price(self, token_address, token_amount):
        """Calculate the price received for selling a specific amount of tokens"""
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
        """Get the virtual supply of a token"""
        try:
            return self.contract.functions.virtualSupply(
                self.w3.to_checksum_address(token_address)
            ).call()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting virtual supply for {token_address}: {e}")
            return 0
    
    def get_token_creator(self, token_address):
        """Get the creator address of a token"""
        try:
            return self.contract.functions.tokenCreators(
                self.w3.to_checksum_address(token_address)
            ).call()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting token creator for {token_address}: {e}")
            return "0x0000000000000000000000000000000000000000"
    
    def get_goal_reached_timestamp(self, token_address):
        """Get the timestamp when token reached its funding goal"""
        try:
            return self.contract.functions.getGoalReachedTimestamp(
                self.w3.to_checksum_address(token_address)
            ).call()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting goal timestamp for {token_address}: {e}")
            return 0
    
    def get_time_until_auto_resume(self, token_address):
        """Get time remaining until automatic trading resumption"""
        try:
            return self.contract.functions.getTimeUntilAutoResume(
                self.w3.to_checksum_address(token_address)
            ).call()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting auto resume time for {token_address}: {e}")
            return 0
    
    def get_contract_constants(self):
        """Get important contract constants"""
        try:
            return {
                "DECIMALS": self.contract.functions.DECIMALS().call(),
                "MAX_SUPPLY": self.contract.functions.MAX_SUPPLY().call(),
                "INITIAL_PRICE": self.contract.functions.INITIAL_PRICE().call(),
                "MIN_PURCHASE": self.contract.functions.MIN_PURCHASE().call(),
                "MAX_PURCHASE": self.contract.functions.MAX_PURCHASE().call(),
                "TRADING_FEE": self.contract.functions.TRADING_FEE().call(),
            }
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting contract constants: {e}")
            return {}
    
    def get_token_info(self, token_address):
        """Get comprehensive information about a token"""
        try:
            address = self.w3.to_checksum_address(token_address)
            
            info = {
                "address": address,
                "state": self.get_token_state(address),
                "lastPrice": self.get_last_price(address),
                "fundingGoal": self.get_funding_goal(address),
                "collateral": self.get_collateral(address),
                "virtualSupply": self.get_virtual_supply(address),
                "creator": self.get_token_creator(address),
                "goalReachedTimestamp": self.get_goal_reached_timestamp(address),
                "timeUntilAutoResume": self.get_time_until_auto_resume(address)
            }
            
            # Add calculated fields
            if info["fundingGoal"] > 0:
                info["fundingProgress"] = (info["collateral"] / info["fundingGoal"]) * 100
            else:
                info["fundingProgress"] = 0
            
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
    
    def estimate_gas_for_buy(self, token_address, eth_amount, min_tokens_out=0):
        """Estimate gas needed for a buy transaction"""
        try:
            return self.contract.functions.buy(
                self.w3.to_checksum_address(token_address),
                min_tokens_out
            ).estimate_gas({
                'value': self.w3.to_wei(eth_amount, 'ether')
            })
        except Exception as e:
            print(f"🤖 TVB: ❌ Error estimating buy gas: {e}")
            return 800000  # Increased default fallback
    
    def estimate_gas_for_sell(self, token_address, token_amount, min_eth_out=0):
        """Estimate gas needed for a sell transaction"""
        try:
            return self.contract.functions.sell(
                self.w3.to_checksum_address(token_address),
                token_amount,
                min_eth_out
            ).estimate_gas()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error estimating sell gas: {e}")
            return 800000  # Increased default fallback


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
    print("🤖 TVB: CORRECTED Factory contract interface loaded!")
    
    # Example of how to use the interface
    print("🤖 TVB: Token states:")
    for i in range(5):
        print(f"  {i}: {TokenState.get_name(i)} (Tradeable: {TokenState.is_tradeable(i)})")
    
    print("🤖 TVB: ✅ CORRECTED Factory contract module test complete!")
    print("🤖 TVB: 🔧 Key fixes:")
    print("  - Added minEthOut parameter to sell() function")
    print("  - Corrected all function signatures to match contract")
    print("  - Added missing view functions")
    print("  - Increased gas estimates for more complex contract")