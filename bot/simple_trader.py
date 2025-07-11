#!/usr/bin/env python3
"""
bot/simple_trader.py - Real trader implementation
Save this as bot/simple_trader.py
"""

import random
from web3 import Web3

class SimpleTrader:
    """Simplified trader with clean, consistent logic"""
    
    def __init__(self, w3, account, factory_contract, config, webhook_manager=None, bot_logger=None):
        self.w3 = w3
        self.account = account
        self.factory_contract = factory_contract
        self.config = config
        self.webhook = webhook_manager
        self.bot_logger = bot_logger
        
        # Trading parameters
        self.buy_bias = config.get('buyBias', 0.6)
        self.risk_tolerance = config.get('riskTolerance', 0.5)
        self.min_trade_amount = config.get('minTradeAmount', 0.005)
        self.max_trade_amount = config.get('maxTradeAmount', 0.02)
        
        # Token ABI for balance checks
        self.token_abi = [
            {
                "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
        
        self.log(f"🤖 Trader initialized: Buy Bias={self.buy_bias:.2f}, Risk={self.risk_tolerance:.2f}")
    
    def log(self, message: str):
        """Log with bot-specific colors if available"""
        if self.bot_logger:
            self.bot_logger.log(message)
        else:
            print(message)
    
    def get_avax_balance(self) -> float:
        """Get current AVAX balance"""
        try:
            balance_wei = self.w3.eth.get_balance(self.account.address)
            return float(self.w3.from_wei(balance_wei, 'ether'))
        except Exception as e:
            self.log(f"❌ Error getting AVAX balance: {e}")
            return 0.0
    
    def get_token_balance(self, token_address: str) -> int:
        """Get token balance in wei"""
        try:
            token_contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(token_address),
                abi=self.token_abi
            )
            return token_contract.functions.balanceOf(self.account.address).call()
        except Exception as e:
            self.log(f"❌ Error getting token balance: {e}")
            return 0
    
    def check_token_state(self, token_address: str) -> bool:
        """Check if token is tradeable"""
        try:
            state = self.factory_contract.functions.getTokenState(token_address).call()
            return state in [1, 4]  # TRADING or RESUMED
        except Exception as e:
            self.log(f"❌ Error checking token state: {e}")
            return False
    
    def decide_action(self, token_balance: int) -> str:
        """Decide whether to buy, sell, or hold based on personality"""
        has_tokens = token_balance > 0
        
        if has_tokens:
            # If we have tokens, decide whether to sell based on buy_bias
            # Lower buy_bias = more likely to sell
            sell_probability = 1.0 - self.buy_bias
            if random.random() < sell_probability:
                return 'sell'
        
        # Decide whether to buy based on buy_bias and risk tolerance
        buy_probability = self.buy_bias * self.risk_tolerance
        if random.random() < buy_probability:
            return 'buy'
        
        return 'hold'
    
    def execute_buy(self, token_address: str, token_symbol: str, token_name: str) -> bool:
        """Execute a buy transaction"""
        try:
            self.log(f"🟢 Executing BUY for {token_symbol}")
            
            # Calculate amount to buy
            current_avax = self.get_avax_balance()
            dynamic_max = self.min_trade_amount + (self.max_trade_amount - self.min_trade_amount) * self.risk_tolerance
            amount_to_buy = random.uniform(self.min_trade_amount, min(dynamic_max, current_avax * 0.8))
            
            if amount_to_buy < self.min_trade_amount:
                error_msg = f"Insufficient AVAX for trade ({current_avax:.4f} available)"
                self.log(f"❌ {error_msg}")
                if self.webhook:
                    self.webhook.send_error(error_msg, "insufficient_funds", current_avax)
                return False
            
            self.log(f"💰 Buying {amount_to_buy:.6f} AVAX worth of {token_symbol}")
            
            # Build transaction
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            txn = self.factory_contract.functions.buy(
                self.w3.to_checksum_address(token_address),
                0  # minTokensOut
            ).build_transaction({
                'from': self.account.address,
                'value': self.w3.to_wei(amount_to_buy, 'ether'),
                'gas': 1200000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
                'chainId': 43113
            })
            
            # Sign and send
            signed_txn = self.account.sign_transaction(txn)
            
            # Handle different Web3.py versions
            if hasattr(signed_txn, 'rawTransaction'):
                raw_transaction = signed_txn.rawTransaction
            elif hasattr(signed_txn, 'raw_transaction'):
                raw_transaction = signed_txn.raw_transaction
            else:
                raw_transaction = signed_txn
            
            tx_hash = self.w3.eth.send_raw_transaction(raw_transaction)
            tx_hash_hex = self.w3.to_hex(tx_hash)
            
            print(f"📡 Transaction sent: {tx_hash_hex}")
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt.status == 1:
                post_balance = self.get_avax_balance()
                print(f"✅ BUY SUCCESS! New balance: {post_balance:.6f} AVAX")
                
                if self.webhook:
                    self.webhook.send_buy(
                        token_address, token_symbol, token_name,
                        amount_to_buy, tx_hash_hex, post_balance
                    )
                return True
            else:
                error_msg = f"Buy transaction failed: {tx_hash_hex}"
                print(f"❌ {error_msg}")
                if self.webhook:
                    self.webhook.send_error(error_msg, "transaction_failed")
                return False
                
        except Exception as e:
            error_msg = f"Buy execution error: {e}"
            print(f"❌ {error_msg}")
            if self.webhook:
                self.webhook.send_error(error_msg, "buy_execution")
            return False
    
    def execute_sell(self, token_address: str, token_symbol: str, token_name: str, token_balance: int) -> bool:
        """Execute a sell transaction"""
        try:
            print(f"🔴 Executing SELL for {token_symbol}")
            
            # Calculate amount to sell (percentage based on risk tolerance)
            min_sell_perc = 0.1
            max_sell_perc = max(0.2, 1.0 - self.risk_tolerance)
            sell_percentage = random.uniform(min_sell_perc, max_sell_perc)
            amount_to_sell = int(token_balance * sell_percentage)
            readable_amount = amount_to_sell / 1e18
            
            if amount_to_sell <= 0:
                print("❌ Calculated sell amount is zero")
                return False
            
            print(f"💰 Selling {readable_amount:.6f} {token_symbol} ({sell_percentage*100:.1f}%)")
            
            # Build transaction
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            txn = self.factory_contract.functions.sell(
                self.w3.to_checksum_address(token_address),
                amount_to_sell,
                0  # minEthOut
            ).build_transaction({
                'from': self.account.address,
                'gas': 1200000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
                'chainId': 43113
            })
            
            # Sign and send
            signed_txn = self.account.sign_transaction(txn)
            
            # Handle different Web3.py versions
            if hasattr(signed_txn, 'rawTransaction'):
                raw_transaction = signed_txn.rawTransaction
            elif hasattr(signed_txn, 'raw_transaction'):
                raw_transaction = signed_txn.raw_transaction
            else:
                raw_transaction = signed_txn
            
            tx_hash = self.w3.eth.send_raw_transaction(raw_transaction)
            tx_hash_hex = self.w3.to_hex(tx_hash)
            
            print(f"📡 Transaction sent: {tx_hash_hex}")
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt.status == 1:
                post_balance = self.get_avax_balance()
                print(f"✅ SELL SUCCESS! New balance: {post_balance:.6f} AVAX")
                
                if self.webhook:
                    self.webhook.send_sell(
                        token_address, token_symbol, token_name,
                        amount_to_sell, readable_amount, sell_percentage * 100,
                        tx_hash_hex, post_balance
                    )
                return True
            else:
                error_msg = f"Sell transaction failed: {tx_hash_hex}"
                print(f"❌ {error_msg}")
                if self.webhook:
                    self.webhook.send_error(error_msg, "transaction_failed")
                return False
                
        except Exception as e:
            error_msg = f"Sell execution error: {e}"
            print(f"❌ {error_msg}")
            if self.webhook:
                self.webhook.send_error(error_msg, "sell_execution")
            return False
    
    def execute_trade_decision(self, token: dict) -> bool:
        """Main trading logic - simplified and consistent"""
        try:
            token_address = token['address']
            token_symbol = token['symbol']
            token_name = token.get('name', token_symbol)
            
            print(f"🎯 Processing {token_symbol}")
            
            # Check if token is tradeable
            if not self.check_token_state(token_address):
                print(f"⚠️ {token_symbol} not tradeable")
                return False
            
            # Get current balances
            token_balance = self.get_token_balance(token_address)
            current_avax = self.get_avax_balance()
            
            print(f"💰 Balances - AVAX: {current_avax:.6f}, {token_symbol}: {token_balance/1e18:.6f}")
            
            # Check minimum AVAX for trading
            if current_avax < self.min_trade_amount:
                if token_balance > 0:
                    # Force sell if we have tokens but no AVAX
                    print(f"🔄 Insufficient AVAX, forcing sell of {token_symbol}")
                    return self.execute_sell(token_address, token_symbol, token_name, token_balance)
                else:
                    error_msg = f"Insufficient AVAX for trading ({current_avax:.4f})"
                    print(f"❌ {error_msg}")
                    if self.webhook:
                        self.webhook.send_error(error_msg, "insufficient_funds", current_avax)
                    return False
            
            # Make trading decision
            action = self.decide_action(token_balance)
            print(f"🎲 Decision: {action.upper()}")
            
            if action == 'buy':
                return self.execute_buy(token_address, token_symbol, token_name)
            elif action == 'sell' and token_balance > 0:
                return self.execute_sell(token_address, token_symbol, token_name, token_balance)
            else:  # hold
                print(f"⏸️ Holding {token_symbol}")
                if self.webhook:
                    self.webhook.send_hold(
                        token_address, token_symbol, token_name,
                        token_balance, current_avax
                    )
                return True
                
        except Exception as e:
            error_msg = f"Trade decision error: {e}"
            print(f"❌ {error_msg}")
            if self.webhook:
                self.webhook.send_error(error_msg, "trade_decision")
            return False
    
    def attempt_token_creation(self) -> bool:
        """Attempt to create a new token"""
        try:
            # Simple creation chance check
            create_chance = self.config.get('createTokenChance', 0.02)
            if random.random() > create_chance:
                return False
            
            current_avax = self.get_avax_balance()
            creation_amount = 0.01
            
            if current_avax < creation_amount + 0.01:
                print(f"💰 Insufficient AVAX for token creation ({current_avax:.4f})")
                return False
            
            # Generate simple token concept
            token_name = f"Test Token {random.randint(100, 999)}"
            token_symbol = f"TEST{random.randint(10, 99)}"
            
            print(f"🎨 Creating token: {token_name} (${token_symbol})")
            
            if self.webhook:
                self.webhook.send_create_token(
                    token_name, token_symbol, creation_amount,
                    None, current_avax
                )
            
            # For now, just return True - actual creation would happen here
            return True
            
        except Exception as e:
            error_msg = f"Token creation error: {e}"
            print(f"❌ {error_msg}")
            if self.webhook:
                self.webhook.send_error(error_msg, "token_creation")
            return False