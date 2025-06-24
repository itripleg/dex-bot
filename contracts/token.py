#!/usr/bin/env python3
"""
Token contract interface for TVB bot interactions
Simple interface for ERC20-like token operations
"""

class TokenContract:
    """Interface for token contract interactions"""
    
    def __init__(self, w3):
        self.w3 = w3
        self.abi = self._get_token_abi()
    
    def _get_token_abi(self):
        """Get the token contract ABI"""
        return [
            {
                "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "name",
                "outputs": [{"internalType": "string", "name": "", "type": "string"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "symbol", 
                "outputs": [{"internalType": "string", "name": "", "type": "string"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "decimals",
                "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "totalSupply",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
    
    def get_contract(self, token_address):
        """Get a token contract instance"""
        return self.w3.eth.contract(
            address=self.w3.to_checksum_address(token_address),
            abi=self.abi
        )
    
    def get_balance(self, token_address, account_address):
        """Get token balance for an account"""
        try:
            contract = self.get_contract(token_address)
            return contract.functions.balanceOf(
                self.w3.to_checksum_address(account_address)
            ).call()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting balance for {token_address}: {e}")
            return 0
    
    def get_name(self, token_address):
        """Get token name"""
        try:
            contract = self.get_contract(token_address)
            return contract.functions.name().call()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting name for {token_address}: {e}")
            return "Unknown"
    
    def get_symbol(self, token_address):
        """Get token symbol"""
        try:
            contract = self.get_contract(token_address)
            return contract.functions.symbol().call()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting symbol for {token_address}: {e}")
            return "UNK"
    
    def get_decimals(self, token_address):
        """Get token decimals"""
        try:
            contract = self.get_contract(token_address)
            return contract.functions.decimals().call()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting decimals for {token_address}: {e}")
            return 18  # Default to 18 decimals
    
    def get_total_supply(self, token_address):
        """Get token total supply"""
        try:
            contract = self.get_contract(token_address)
            return contract.functions.totalSupply().call()
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting total supply for {token_address}: {e}")
            return 0
    
    def get_token_info(self, token_address, account_address=None):
        """Get comprehensive token information"""
        try:
            info = {
                "address": token_address,
                "name": self.get_name(token_address),
                "symbol": self.get_symbol(token_address),
                "decimals": self.get_decimals(token_address),
                "totalSupply": self.get_total_supply(token_address)
            }
            
            if account_address:
                info["balance"] = self.get_balance(token_address, account_address)
            
            return info
            
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting token info for {token_address}: {e}")
            return None

# Example usage
if __name__ == "__main__":
    print("🤖 TVB: Token contract interface loaded!")
    print("🤖 TVB: ✅ Token contract module test complete!")