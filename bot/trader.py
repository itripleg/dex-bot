#!/usr/bin/env python3
"""
Trading execution logic for the Transparent Volume Bot
Handles buy/sell decisions and transaction execution with bot-specific logging
"""

import random
from web3 import Web3

class TokenTrader:
    """Handles all trading operations and decision logic"""
    
    def __init__(self, w3, account, factory_contract, config, verbose=False, logger=None):
        self.w3 = w3
        self.account = account
        self.factory_contract = factory_contract
        self.config = config
        self.verbose = verbose
        self.logger = logger  # Bot-specific logger
        
        # Trading parameters from config
        self.buy_bias = config.get('buyBias', 0.6)
        self.risk_tolerance = config.get('riskTolerance', 0.5)
        self.min_trade_amount = config.get('minTradeAmount', 0.005)
        self.max_trade_amount = config.get('maxTradeAmount', 0.02)
        
        # Contract ABI for token interactions
        self.token_abi = [
            {
                "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
        
        if self.verbose and self.logger:
            self.logger.info(f"💹 Trader initialized with buy bias: {self.buy_bias:.2f}, risk: {self.risk_tolerance:.2f}")
    
    def execute_trade_decision(self, token):
        """Make and execute a trading decision for the given token"""
        try:
            token_address = token['address']
            token_symbol = token['symbol']
            
            # Get current token balance
            token_balance = self._get_token_balance(token_address)
            
            # Check if we have enough AVAX for minimum trade
            current_avax = self._get_avax_balance()
            min_trade = self.min_trade_amount
            
            if current_avax < min_trade:
                # Force sell if we have tokens but insufficient AVAX to buy
                if token_balance > 0:
                    if self.logger:
                        self.logger.warning(f"Insufficient AVAX ({current_avax:.4f}) for buying, forcing sell of {token_symbol}")
                    else:
                        print(f"🤖 TVB: ⚠️ Insufficient AVAX ({current_avax:.4f}) for buying, forcing sell of {token_symbol}")
                    
                    return self._execute_sell(token, token_balance)
                else:
                    if self.logger:
                        self.logger.warning(f"Insufficient AVAX ({current_avax:.4f}) and no {token_symbol} to sell")
                    else:
                        print(f"🤖 TVB: ⚠️ Insufficient AVAX ({current_avax:.4f}) and no {token_symbol} to sell")
                    return False
            
            # Make trading decision based on personality and holdings
            action = self._decide_trade_action(token_balance)
            
            if self.verbose and self.logger:
                balance_display = token_balance / 1e18
                self.logger.info(f"🎲 Decision for {token_symbol}: {action.upper()} (balance: {balance_display:.4f})")
            
            if action == 'buy':
                return self._execute_buy(token)
            elif action == 'sell':
                return self._execute_sell(token, token_balance)
            else:
                if self.verbose and self.logger:
                    self.logger.info(f"⏭️ No action taken for {token_symbol}")
                return True
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Trade decision error for {token.get('symbol', 'Unknown')}: {e}")
            else:
                print(f"🤖 TVB: ❌ Trade decision error for {token.get('symbol', 'Unknown')}: {e}")
            return False
    
    def _decide_trade_action(self, token_balance):
        """Decide whether to buy, sell, or hold based on personality and balance"""
        has_tokens = token_balance > 0
        
        if has_tokens:
            # If we have tokens, personality determines if we sell
            # Higher buy_bias = less likely to sell
            sell_probability = 1.0 - self.buy_bias
            
            # Add some randomness based on risk tolerance
            sell_probability += (random.random() - 0.5) * (1.0 - self.risk_tolerance)
            sell_probability = max(0.0, min(1.0, sell_probability))  # Clamp to [0,1]
            
            if random.random() < sell_probability:
                return 'sell'
        
        # Default to buy (influenced by buy_bias)
        # Higher buy_bias = more likely to buy
        buy_probability = self.buy_bias
        
        # Add risk tolerance influence
        buy_probability += (random.random() - 0.5) * self.risk_tolerance
        buy_probability = max(0.0, min(1.0, buy_probability))  # Clamp to [0,1]
        
        if random.random() < buy_probability:
            return 'buy'
        
        return 'hold'
    
    def _execute_buy(self, token):
        """Execute a buy transaction"""
        token_address = token['address']
        token_symbol = token['symbol']
        
        try:
            # Calculate buy amount based on risk tolerance
            dynamic_max = self.min_trade_amount + (
                self.max_trade_amount - self.min_trade_amount
            ) * self.risk_tolerance
            
            amount_to_buy = random.uniform(self.min_trade_amount, dynamic_max)
            
            # Safety check - don't spend all AVAX
            current_avax = self._get_avax_balance()
            if amount_to_buy > current_avax * 0.9:
                amount_to_buy = current_avax * 0.5
                if self.logger:
                    self.logger.warning("Adjusted buy amount to preserve AVAX balance")
                else:
                    print(f"🤖 TVB: ⚠️  Adjusted buy amount to preserve AVAX balance")
            
            if amount_to_buy < self.min_trade_amount:
                if self.logger:
                    self.logger.warning(f"Insufficient AVAX for minimum trade ({current_avax:.4f} AVAX available)")
                else:
                    print(f"🤖 TVB: ⏭️ Insufficient AVAX for minimum trade size ({current_avax:.4f} AVAX available)")
                return False
                
            if self.logger:
                self.logger.trade("buy", f"{amount_to_buy:.4f} AVAX for {token_symbol}")
            else:
                print(f"🤖 TVB: 🟢 Executing BUY: {amount_to_buy:.4f} AVAX for {token_symbol}")
            
            # Build and send transaction
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            
            txn = self.factory_contract.functions.buy(
                self.w3.to_checksum_address(token_address)
            ).build_transaction({
                'from': self.account.address,
                'value': self.w3.to_wei(amount_to_buy, 'ether'),
                'gas': 500000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
                'chainId': 43113  # Avalanche Fuji testnet
            })
            
            # Sign and send
            signed_txn = self.account.sign_transaction(txn)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            if self.logger:
                self.logger.info("🟢 BUY transaction sent, waiting for confirmation...")
            else:
                print(f"🤖 TVB: 🟢 BUY transaction sent, waiting for confirmation...")
            
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt.status == 1:
                tx_hash_hex = self.w3.to_hex(tx_hash)
                if self.logger:
                    self.logger.success(f"Buy successful! TX: {tx_hash_hex}")
                else:
                    print(f"🤖 TVB: ✅ Buy successful! TX: {tx_hash_hex}")
                return True
            else:
                if self.logger:
                    self.logger.error("Buy transaction failed in receipt")
                else:
                    print(f"🤖 TVB: ❌ Buy transaction failed in receipt")
                return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Buy execution error for {token_symbol}: {e}")
            else:
                print(f"🤖 TVB: ❌ Buy execution error for {token_symbol}: {e}")
            return False
    
    def _execute_sell(self, token, token_balance):
        """Execute a sell transaction"""
        token_address = token['address']
        token_symbol = token['symbol']
        
        try:
            # Calculate sell percentage based on risk tolerance
            # Lower risk tolerance = sell smaller amounts
            min_sell_perc = 0.1  # Always sell at least 10%
            max_sell_perc = max(min_sell_perc + 0.1, 1.0 - self.risk_tolerance)
            sell_percentage = random.uniform(min_sell_perc, max_sell_perc)
            
            amount_to_sell = int(token_balance * sell_percentage)
            
            if amount_to_sell <= 0:
                if self.logger:
                    self.logger.warning("Calculated sell amount is zero, skipping")
                else:
                    print(f"🤖 TVB: ⏭️ Calculated sell amount is zero, skipping")
                return False
            
            readable_amount = amount_to_sell / 1e18
            if self.logger:
                self.logger.trade("sell", f"{readable_amount:.4f} {token_symbol} ({sell_percentage*100:.1f}%)")
            else:
                print(f"🤖 TVB: 🔴 Executing SELL: {readable_amount:.4f} {token_symbol} ({sell_percentage*100:.1f}%)")
            
            # Build and send transaction
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            
            txn = self.factory_contract.functions.sell(
                self.w3.to_checksum_address(token_address),
                amount_to_sell
            ).build_transaction({
                'from': self.account.address,
                'gas': 500000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
                'chainId': 43113  # Avalanche Fuji testnet
            })
            
            # Sign and send
            signed_txn = self.account.sign_transaction(txn)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            if self.logger:
                self.logger.info("🔴 SELL transaction sent, waiting for confirmation...")
            else:
                print(f"🤖 TVB: 🔴 SELL transaction sent, waiting for confirmation...")
            
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt.status == 1:
                tx_hash_hex = self.w3.to_hex(tx_hash)
                if self.logger:
                    self.logger.success(f"Sell successful! TX: {tx_hash_hex}")
                else:
                    print(f"🤖 TVB: ✅ Sell successful! TX: {tx_hash_hex}")
                return True
            else:
                if self.logger:
                    self.logger.error("Sell transaction failed in receipt")
                else:
                    print(f"🤖 TVB: ❌ Sell transaction failed in receipt")
                return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Sell execution error for {token_symbol}: {e}")
            else:
                print(f"🤖 TVB: ❌ Sell execution error for {token_symbol}: {e}")
            return False
    
    def _get_token_balance(self, token_address):
        """Get current balance of a specific token"""
        try:
            token_contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(token_address),
                abi=self.token_abi
            )
            return token_contract.functions.balanceOf(self.account.address).call()
        except Exception as e:
            if self.verbose and self.logger:
                self.logger.error(f"Error getting token balance for {token_address[:10]}...: {e}")
            return 0
    
    def _get_avax_balance(self):
        """Get current AVAX balance"""
        balance_wei = self.w3.eth.get_balance(self.account.address)
        return float(self.w3.from_wei(balance_wei, 'ether'))
    
    def get_trading_stats(self):
        """Get current trading configuration and stats"""
        return {
            "buy_bias": self.buy_bias,
            "risk_tolerance": self.risk_tolerance,
            "min_trade_amount": self.min_trade_amount,
            "max_trade_amount": self.max_trade_amount,
            "current_avax_balance": self._get_avax_balance()
        }
    
    def simulate_trade_decision(self, token, num_simulations=100):
        """Simulate trade decisions for testing personality calibration"""
        if not self.verbose or not self.logger:
            return None
            
        self.logger.info(f"🧪 Simulating {num_simulations} decisions for {token.get('symbol', 'Unknown')}:")
        
        # Test with no tokens
        actions_no_tokens = []
        for _ in range(num_simulations):
            action = self._decide_trade_action(0)
            actions_no_tokens.append(action)
        
        # Test with tokens
        fake_balance = 1000 * 1e18  # 1000 tokens
        actions_with_tokens = []
        for _ in range(num_simulations):
            action = self._decide_trade_action(fake_balance)
            actions_with_tokens.append(action)
        
        # Print statistics
        buy_rate_no_tokens = actions_no_tokens.count('buy') / num_simulations * 100
        sell_rate_with_tokens = actions_with_tokens.count('sell') / num_simulations * 100
        
        self.logger.info(f"📊 No tokens → Buy rate: {buy_rate_no_tokens:.1f}%")
        self.logger.info(f"📊 With tokens → Sell rate: {sell_rate_with_tokens:.1f}%")
        self.logger.info(f"🎯 Expected buy bias: {self.buy_bias * 100:.1f}%")
        
        return {
            "buy_rate_no_tokens": buy_rate_no_tokens,
            "sell_rate_with_tokens": sell_rate_with_tokens,
            "expected_buy_bias": self.buy_bias * 100
        }


# Example usage and testing
if __name__ == "__main__":
    print("🤖 TVB: Trading module loaded!")
    
    # Example personality test
    test_config = {
        'buyBias': 0.7,
        'riskTolerance': 0.6,
        'minTradeAmount': 0.01,
        'maxTradeAmount': 0.05
    }
    
    # Note: Would need actual Web3 instance to fully test
    print(f"🤖 TVB: Test config - Buy bias: {test_config['buyBias']}, Risk: {test_config['riskTolerance']}")
    print("🤖 TVB: ✅ Trading module test complete!")