#!/usr/bin/env python3
"""
Enhanced Trading execution logic with balance and token reporting
"""

import random
from web3 import Web3

class TokenTrader:
    """Handles all trading operations with enhanced webhook reporting"""
    
    def __init__(self, w3, account, factory_contract, config, webhook_manager=None, verbose=False, logger=None):
        self.w3 = w3
        self.account = account
        self.factory_contract = factory_contract
        self.config = config
        self.webhook = webhook_manager  # Add webhook manager
        self.verbose = verbose
        self.logger = logger
        
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
        """Make and execute a trading decision for the given token with webhook updates"""
        try:
            token_address = token['address']
            token_symbol = token['symbol']
            token_name = token.get('name', token_symbol)
            
            # Create token info dict for webhooks
            token_info = {
                "address": token_address,
                "symbol": token_symbol,
                "name": token_name
            }
            
            # Get current balances
            token_balance = self._get_token_balance(token_address)
            current_avax = self._get_avax_balance()
            min_trade = self.min_trade_amount
            
            # Check if we have enough AVAX for minimum trade
            if current_avax < min_trade:
                # Force sell if we have tokens but insufficient AVAX to buy
                if token_balance > 0:
                    if self.webhook:
                        self.webhook.send_update("forced_sell", {
                            "message": f"Insufficient AVAX ({current_avax:.4f}), forced to sell {token_symbol}",
                            "tokenSymbol": token_symbol,
                            "tokenAddress": token_address,
                            "reason": "insufficient_avax",
                            "currentBalance": current_avax
                        })
                    
                    if self.logger:
                        self.logger.warning(f"Insufficient AVAX ({current_avax:.4f}) for buying, forcing sell of {token_symbol}")
                    
                    return self._execute_sell(token_info, token_balance, forced=True)
                else:
                    if self.webhook:
                        self.webhook.send_update("insufficient_funds", {
                            "message": f"Insufficient AVAX ({current_avax:.4f}) and no {token_symbol} to sell",
                            "tokenSymbol": token_symbol,
                            "tokenAddress": token_address,
                            "currentBalance": current_avax
                        })
                    
                    if self.logger:
                        self.logger.warning(f"Insufficient AVAX ({current_avax:.4f}) and no {token_symbol} to sell")
                    return False
            
            # Make trading decision based on personality and holdings
            action = self._decide_trade_action(token_balance)
            
            if self.verbose and self.logger:
                balance_display = token_balance / 1e18
                self.logger.info(f"🎲 Decision for {token_symbol}: {action.upper()} (balance: {balance_display:.4f})")
            
            if action == 'buy':
                return self._execute_buy(token_info)
            elif action == 'sell':
                return self._execute_sell(token_info, token_balance)
            else:
                if self.verbose and self.logger:
                    self.logger.info(f"⏭️ No action taken for {token_symbol}")
                
                # Send "hold" webhook
                if self.webhook:
                    self.webhook.send_update("hold", {
                        "message": f"Holding position on {token_symbol}",
                        "tokenSymbol": token_symbol,
                        "tokenAddress": token_address,
                        "decision": "hold"
                    })
                
                return True
                
        except Exception as e:
            error_msg = f"Trade decision error for {token.get('symbol', 'Unknown')}: {e}"
            
            if self.logger:
                self.logger.error(error_msg)
            else:
                print(f"🤖 TVB: ❌ {error_msg}")
            
            # Send error webhook
            if self.webhook:
                self.webhook.send_error_update(error_msg, "trade_decision", token)
            
            return False
    
    def _execute_buy(self, token_info):
        """Execute a buy transaction with webhook updates"""
        token_address = token_info['address']
        token_symbol = token_info['symbol']
        
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
            
            if amount_to_buy < self.min_trade_amount:
                error_msg = f"Insufficient AVAX for minimum trade ({current_avax:.4f} AVAX available)"
                if self.webhook:
                    self.webhook.send_error_update(error_msg, "insufficient_funds", token_info)
                return False
            
            # Send buy attempt webhook
            if self.webhook:
                self.webhook.send_trade_attempt("buy", token_info, amount_to_buy)
            
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
                post_trade_balance = self._get_avax_balance()
                
                # Send success webhook with post-trade balance
                if self.webhook:
                    self.webhook.send_buy_update(
                        token_info, 
                        amount_to_buy, 
                        tx_hash_hex, 
                        post_trade_balance
                    )
                
                if self.logger:
                    self.logger.success(f"Buy successful! TX: {tx_hash_hex} | New balance: {post_trade_balance:.6f} AVAX")
                else:
                    print(f"🤖 TVB: ✅ Buy successful! TX: {tx_hash_hex} | New balance: {post_trade_balance:.6f} AVAX")
                
                return True
            else:
                error_msg = "Buy transaction failed in receipt"
                if self.webhook:
                    self.webhook.send_trade_failure("buy", token_info, error_msg)
                
                if self.logger:
                    self.logger.error(error_msg)
                else:
                    print(f"🤖 TVB: ❌ {error_msg}")
                return False
                
        except Exception as e:
            error_msg = f"Buy execution error for {token_symbol}: {e}"
            
            if self.webhook:
                self.webhook.send_trade_failure("buy", token_info, str(e))
            
            if self.logger:
                self.logger.error(error_msg)
            else:
                print(f"🤖 TVB: ❌ {error_msg}")
            return False
    
    def _execute_sell(self, token_info, token_balance, forced=False):
        """Execute a sell transaction with webhook updates"""
        token_address = token_info['address']
        token_symbol = token_info['symbol']
        
        try:
            # Calculate sell percentage based on risk tolerance
            min_sell_perc = 0.1  # Always sell at least 10%
            max_sell_perc = max(min_sell_perc + 0.1, 1.0 - self.risk_tolerance)
            sell_percentage = random.uniform(min_sell_perc, max_sell_perc)
            
            if forced:
                sell_percentage = 1.0  # Sell everything if forced
            
            amount_to_sell = int(token_balance * sell_percentage)
            
            if amount_to_sell <= 0:
                error_msg = "Calculated sell amount is zero, skipping"
                if self.webhook:
                    self.webhook.send_error_update(error_msg, "zero_amount", token_info)
                return False
            
            readable_amount = amount_to_sell / 1e18
            
            # Send sell attempt webhook
            if self.webhook:
                self.webhook.send_trade_attempt("sell", token_info, readable_amount)
            
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
                post_trade_balance = self._get_avax_balance()
                
                # Send success webhook with post-trade balance
                if self.webhook:
                    self.webhook.send_sell_update(
                        token_info, 
                        amount_to_sell, 
                        readable_amount, 
                        sell_percentage, 
                        tx_hash_hex, 
                        post_trade_balance
                    )
                
                if self.logger:
                    self.logger.success(f"Sell successful! TX: {tx_hash_hex} | New balance: {post_trade_balance:.6f} AVAX")
                else:
                    print(f"🤖 TVB: ✅ Sell successful! TX: {tx_hash_hex} | New balance: {post_trade_balance:.6f} AVAX")
                
                return True
            else:
                error_msg = "Sell transaction failed in receipt"
                if self.webhook:
                    self.webhook.send_trade_failure("sell", token_info, error_msg)
                
                if self.logger:
                    self.logger.error(error_msg)
                else:
                    print(f"🤖 TVB: ❌ {error_msg}")
                return False
                
        except Exception as e:
            error_msg = f"Sell execution error for {token_symbol}: {e}"
            
            if self.webhook:
                self.webhook.send_trade_failure("sell", token_info, str(e))
            
            if self.logger:
                self.logger.error(error_msg)
            else:
                print(f"🤖 TVB: ❌ {error_msg}")
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