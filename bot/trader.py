#!/usr/bin/env python3
"""
Enhanced Trading execution logic with Web3.py compatibility fix and comprehensive debugging
"""

import random
from web3 import Web3
from bot.token_creator import TokenCreator

class TokenTrader:
    """Handles all trading operations with Web3.py compatibility fixes"""
    
    def __init__(self, w3, account, factory_contract, config, webhook_manager=None, verbose=False, logger=None):
        self.w3 = w3
        self.account = account
        self.factory_contract = factory_contract
        self.config = config
        self.webhook = webhook_manager
        self.verbose = verbose
        self.logger = logger
        
        # Trading parameters from config
        self.buy_bias = config.get('buyBias', 0.6)
        self.risk_tolerance = config.get('riskTolerance', 0.5)
        self.min_trade_amount = config.get('minTradeAmount', 0.005)
        self.max_trade_amount = config.get('maxTradeAmount', 0.02)
        
        # Token creator
        self.token_creator = TokenCreator(
            bot_name=config.get('name', 'unknown'),
            config=config,
            logger=logger
        )
        
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
    
    def _send_raw_transaction_safe(self, signed_txn):
        """Safely send raw transaction with Web3.py version compatibility"""
        try:
            # Handle different Web3.py versions
            if hasattr(signed_txn, 'rawTransaction'):
                # Newer versions use rawTransaction
                raw_transaction = signed_txn.rawTransaction
            elif hasattr(signed_txn, 'raw_transaction'):
                # Some versions use raw_transaction
                raw_transaction = signed_txn.raw_transaction
            else:
                # Fallback - the signed transaction might be the raw data itself
                raw_transaction = signed_txn
            
            return self.w3.eth.send_raw_transaction(raw_transaction)
            
        except Exception as e:
            self._debug_log(f"❌ Raw transaction send error: {e}")
            # Try alternative method
            try:
                return self.w3.eth.send_raw_transaction(signed_txn)
            except Exception as e2:
                raise Exception(f"Failed to send transaction with both methods: {e}, {e2}")
    
    def execute_trade_decision(self, token):
        """Make and execute a trading decision for the given token"""
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
            
            self._debug_log(f"🎯 Processing trade decision for {token_symbol} ({token_address})")
            
            # Check token state FIRST
            try:
                token_state = self.factory_contract.functions.getTokenState(token_address).call()
                self._debug_log(f"📊 Token {token_symbol} state: {token_state}")
                
                if token_state not in [1, 4]:  # Not TRADING or RESUMED
                    error_msg = f"Token {token_symbol} not tradeable (state: {token_state})"
                    self._debug_log(f"⚠️ {error_msg}")
                    if self.webhook:
                        self.webhook.send_error_update(error_msg, "invalid_token_state")
                    return False
                    
            except Exception as state_error:
                error_msg = f"Failed to get token state for {token_symbol}: {state_error}"
                self._debug_log(f"❌ {error_msg}")
                if self.webhook:
                    self.webhook.send_error_update(error_msg, "state_check_failed")
                return False
            
            # Get current balances
            token_balance = self._get_token_balance(token_address)
            current_avax = self._get_avax_balance()
            min_trade = self.min_trade_amount
            
            self._debug_log(f"💰 Current balances - AVAX: {current_avax:.6f}, {token_symbol}: {token_balance/1e18:.6f}")
            
            # Check if we have enough AVAX for minimum trade
            if current_avax < min_trade:
                # Force sell if we have tokens but insufficient AVAX to buy
                if token_balance > 0:
                    self._debug_log(f"🔄 Insufficient AVAX ({current_avax:.4f}) for buying, forcing sell of {token_symbol}")
                    return self._execute_sell(token_info, token_balance, forced=True)
                else:
                    self._debug_log(f"❌ Insufficient AVAX ({current_avax:.4f}) and no {token_symbol} to sell")
                    
                    # Send webhook for insufficient funds (this won't be logged as ERROR now)
                    if self.webhook:
                        self.webhook.send_update("insufficient_funds", {
                            "message": f"Insufficient AVAX ({current_avax:.4f}) for trading",
                            "tokenAddress": token_address,
                            "tokenSymbol": token_symbol,
                            "tokenName": token_name,
                            "availableAvax": round(current_avax, 6),
                            "minimumRequired": min_trade
                        })
                    
                    return False
            
            # Make trading decision based on personality and holdings
            action = self._decide_trade_action(token_balance)
            
            self._debug_log(f"🎲 Decision for {token_symbol}: {action.upper()} (balance: {token_balance/1e18:.4f})")
            
            if action == 'buy':
                return self._execute_buy(token_info)
            elif action == 'sell':
                return self._execute_sell(token_info, token_balance)
            else:
                # Handle 'hold' decision with webhook
                self._debug_log(f"⏭️ Holding position for {token_symbol}")
                
                # Send webhook for hold decision
                if self.webhook:
                    self.webhook.send_update("hold", {
                        "message": f"Holding position in {token_symbol}",
                        "tokenAddress": token_address,
                        "tokenSymbol": token_symbol,
                        "tokenName": token_name,
                        "tokenBalance": str(token_balance),
                        "readableBalance": round(token_balance / 1e18, 6),
                        "reason": "personality_decision"
                    })
                
                return True
                
        except Exception as e:
            error_msg = f"Trade decision error for {token.get('symbol', 'Unknown')}: {e}"
            self._debug_log(f"❌ {error_msg}")
            
            # Send error webhook with personality message
            if self.webhook:
                self.webhook.send_error_update(error_msg, "trade_decision")
            
            return False
    
    def _execute_buy(self, token_info):
        """Execute a buy transaction with Web3.py compatibility fixes"""
        token_address = token_info['address']
        token_symbol = token_info['symbol']
        
        try:
            self._debug_log(f"🟢 Starting BUY execution for {token_symbol}")
            
            # Calculate buy amount based on risk tolerance
            dynamic_max = self.min_trade_amount + (
                self.max_trade_amount - self.min_trade_amount
            ) * self.risk_tolerance
            
            amount_to_buy = random.uniform(self.min_trade_amount, dynamic_max)
            
            # Safety check - don't spend all AVAX
            current_avax = self._get_avax_balance()
            if amount_to_buy > current_avax * 0.9:
                amount_to_buy = current_avax * 0.5
                self._debug_log(f"⚠️ Adjusted buy amount to preserve AVAX balance: {amount_to_buy:.6f}")
            
            if amount_to_buy < self.min_trade_amount:
                error_msg = f"Insufficient AVAX for minimum trade ({current_avax:.4f} AVAX available)"
                self._debug_log(f"❌ {error_msg}")
                if self.webhook:
                    self.webhook.send_error_update(error_msg, "insufficient_funds")
                return False
            
            self._debug_log(f"💰 Planning to buy {amount_to_buy:.6f} AVAX worth of {token_symbol}")
            
            # Get transaction parameters
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            gas_price = self.w3.eth.gas_price
            
            self._debug_log(f"📋 Transaction params - Nonce: {nonce}, Gas Price: {gas_price}")
            
            # Build transaction (includes minTokensOut parameter)
            txn = self.factory_contract.functions.buy(
                self.w3.to_checksum_address(token_address),
                0  # minTokensOut = 0 (no slippage protection)
            ).build_transaction({
                'from': self.account.address,
                'value': self.w3.to_wei(amount_to_buy, 'ether'),
                'gas': 800000,  # Increased gas limit
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': 43113  # Avalanche Fuji testnet
            })
            
            self._debug_log(f"📝 Transaction built - Gas: {txn['gas']}, Value: {amount_to_buy:.6f} AVAX")
            
            # Sign and send with compatibility fix
            self._debug_log("🔐 Signing transaction...")
            signed_txn = self.account.sign_transaction(txn)
            
            self._debug_log("📡 Sending transaction...")
            tx_hash = self._send_raw_transaction_safe(signed_txn)
            tx_hash_hex = self.w3.to_hex(tx_hash)
            
            self._debug_log(f"✅ Transaction sent! Hash: {tx_hash_hex}")
            self._debug_log("⏳ Waiting for confirmation...")
            
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            self._debug_log(f"📄 Receipt received - Status: {receipt.status}, Gas Used: {receipt.gasUsed}")
            
            if receipt.status == 1:
                post_trade_balance = self._get_avax_balance()
                
                self._debug_log(f"🎉 BUY SUCCESS! New balance: {post_trade_balance:.6f} AVAX")
                
                # Send success webhook with personality message
                if self.webhook:
                    self.webhook.send_buy_update(
                        token_info, 
                        amount_to_buy, 
                        tx_hash_hex, 
                        post_trade_balance
                    )
                
                return True
            else:
                # Enhanced error reporting for failed transactions
                error_msg = f"Buy transaction failed! TX: {tx_hash_hex}"
                
                try:
                    # Get transaction details for debugging
                    tx_details = self.w3.eth.get_transaction(tx_hash)
                    error_msg += f" | Gas: {receipt.gasUsed}/{tx_details.gas}"
                    
                    # Check for revert reason
                    if hasattr(receipt, 'logs') and len(receipt.logs) == 0:
                        error_msg += " | Transaction reverted (no logs - likely contract revert)"
                    
                except Exception as debug_error:
                    error_msg += f" | Debug error: {debug_error}"
                
                self._debug_log(f"❌ {error_msg}")
                
                if self.webhook:
                    self.webhook.send_error_update(error_msg, "transaction_failed")
                
                return False
                
        except Exception as e:
            error_msg = f"Buy execution error for {token_symbol}: {e}"
            self._debug_log(f"❌ {error_msg}")
            
            if self.webhook:
                self.webhook.send_error_update(error_msg, "buy_execution")
            
            return False
    
    def _execute_sell(self, token_info, token_balance, forced=False):
        """Execute a sell transaction with Web3.py compatibility fixes"""
        token_address = token_info['address']
        token_symbol = token_info['symbol']
        
        try:
            self._debug_log(f"🔴 Starting SELL execution for {token_symbol}")
            
            # Calculate sell percentage based on risk tolerance
            min_sell_perc = 0.1  # Always sell at least 10%
            max_sell_perc = max(min_sell_perc + 0.1, 1.0 - self.risk_tolerance)
            sell_percentage = random.uniform(min_sell_perc, max_sell_perc)
            
            if forced:
                sell_percentage = 1.0  # Sell everything if forced
                self._debug_log("🔄 Forced sell - selling 100%")
            
            amount_to_sell = int(token_balance * sell_percentage)
            
            if amount_to_sell <= 0:
                error_msg = "Calculated sell amount is zero, skipping"
                self._debug_log(f"❌ {error_msg}")
                if self.webhook:
                    self.webhook.send_error_update(error_msg, "zero_amount")
                return False
            
            readable_amount = amount_to_sell / 1e18
            
            self._debug_log(f"💰 Planning to sell {readable_amount:.6f} {token_symbol} ({sell_percentage*100:.1f}%)")
            
            # Get transaction parameters
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            gas_price = self.w3.eth.gas_price
            
            self._debug_log(f"📋 Transaction params - Nonce: {nonce}, Gas Price: {gas_price}")
            
            # Build transaction
            txn = self.factory_contract.functions.sell(
                self.w3.to_checksum_address(token_address),
                amount_to_sell
            ).build_transaction({
                'from': self.account.address,
                'gas': 800000,  # Increased gas limit
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': 43113  # Avalanche Fuji testnet
            })
            
            self._debug_log(f"📝 Transaction built - Gas: {txn['gas']}, Amount: {amount_to_sell}")
            
            # Sign and send with compatibility fix
            self._debug_log("🔐 Signing transaction...")
            signed_txn = self.account.sign_transaction(txn)
            
            self._debug_log("📡 Sending transaction...")
            tx_hash = self._send_raw_transaction_safe(signed_txn)
            tx_hash_hex = self.w3.to_hex(tx_hash)
            
            self._debug_log(f"✅ Transaction sent! Hash: {tx_hash_hex}")
            self._debug_log("⏳ Waiting for confirmation...")
            
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            self._debug_log(f"📄 Receipt received - Status: {receipt.status}, Gas Used: {receipt.gasUsed}")
            
            if receipt.status == 1:
                post_trade_balance = self._get_avax_balance()
                
                self._debug_log(f"🎉 SELL SUCCESS! New balance: {post_trade_balance:.6f} AVAX")
                
                # Send success webhook with personality message
                if self.webhook:
                    self.webhook.send_sell_update(
                        token_info, 
                        amount_to_sell, 
                        readable_amount, 
                        sell_percentage, 
                        tx_hash_hex, 
                        post_trade_balance
                    )
                
                return True
            else:
                # Enhanced error reporting for failed transactions
                error_msg = f"Sell transaction failed! TX: {tx_hash_hex}"
                
                try:
                    # Get transaction details for debugging
                    tx_details = self.w3.eth.get_transaction(tx_hash)
                    error_msg += f" | Gas: {receipt.gasUsed}/{tx_details.gas}"
                    
                    # Check for revert reason
                    if hasattr(receipt, 'logs') and len(receipt.logs) == 0:
                        error_msg += " | Transaction reverted (no logs - likely contract revert)"
                        
                except Exception as debug_error:
                    error_msg += f" | Debug error: {debug_error}"
                
                self._debug_log(f"❌ {error_msg}")
                
                if self.webhook:
                    self.webhook.send_error_update(error_msg, "transaction_failed")
                
                return False
                
        except Exception as e:
            error_msg = f"Sell execution error for {token_symbol}: {e}"
            self._debug_log(f"❌ {error_msg}")
            
            if self.webhook:
                self.webhook.send_error_update(error_msg, "sell_execution")
            
            return False
    
    def attempt_token_creation(self):
        """Attempt to create a new token with personality-driven concept"""
        try:
            if not self.token_creator.should_create_token():
                if self.verbose:
                    self._debug_log("🎲 Token creation check: Not this time")
                return False
            
            # Check if we have enough AVAX for creation
            current_avax = self._get_avax_balance()
            creation_amount = 0.01  # 0.01 AVAX for token creation
            
            if current_avax < creation_amount + 0.01:  # Keep some AVAX for gas
                self._debug_log(f"💰 Insufficient AVAX for token creation ({current_avax:.4f} < {creation_amount + 0.01:.4f})")
                return False
            
            # Generate token concept
            concept = self.token_creator.generate_token_concept()
            
            # Send creation webhook with concept
            if self.webhook:
                self.webhook.send_update("create_token", {
                    "message": f"Creating new token: {concept['name']} (${concept['symbol']}) {concept['image_emoji']}",
                    "tokenConcept": concept,
                    "plannedInvestment": creation_amount,
                    "status": "creating"
                })
            
            self._debug_log(f"🎨 Creating token: {concept['name']} (${concept['symbol']}) {concept['image_emoji']}")
            
            # Create token on-chain with compatibility fix
            success, result = self.token_creator.create_token_on_chain(
                w3=self.w3,
                factory_contract=self.factory_contract,
                account=self.account,
                concept=concept,
                eth_amount=creation_amount
            )
            
            if success:
                # Send success webhook
                if self.webhook:
                    self.webhook.send_update("create_token", {
                        "message": f"Successfully created {concept['name']}! 🎉",
                        "tokenConcept": concept,
                        "txHash": result,
                        "investmentAmount": creation_amount,
                        "status": "success"
                    })
                
                self._debug_log(f"🎉 Token creation successful! TX: {result}")
                return True
            else:
                # Send error webhook
                if self.webhook:
                    self.webhook.send_error_update(f"Token creation failed: {result}", "token_creation_failed")
                
                self._debug_log(f"❌ Token creation failed: {result}")
                return False
                
        except Exception as e:
            error_msg = f"Token creation attempt error: {e}"
            self._debug_log(f"❌ {error_msg}")
            
            if self.webhook:
                self.webhook.send_error_update(error_msg, "token_creation_error")
            
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
            balance = token_contract.functions.balanceOf(self.account.address).call()
            self._debug_log(f"🔍 Token balance for {token_address[:10]}...: {balance/1e18:.6f}")
            return balance
        except Exception as e:
            self._debug_log(f"❌ Error getting token balance for {token_address[:10]}...: {e}")
            return 0
    
    def _get_avax_balance(self):
        """Get current AVAX balance"""
        try:
            balance_wei = self.w3.eth.get_balance(self.account.address)
            balance_avax = float(self.w3.from_wei(balance_wei, 'ether'))
            return balance_avax
        except Exception as e:
            self._debug_log(f"❌ Error getting AVAX balance: {e}")
            return 0.0
    
    def _debug_log(self, message):
        """Centralized debug logging"""
        if self.verbose:
            if self.logger:
                self.logger.info(message)
            else:
                print(f"🤖 TVB: {message}")
    
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
    print("🤖 TVB: Fixed trading module with Web3.py compatibility loaded!")
    
    # Example personality test
    test_config = {
        'name': 'test_bot',
        'buyBias': 0.7,
        'riskTolerance': 0.6,
        'minTradeAmount': 0.01,
        'maxTradeAmount': 0.05,
        'createTokenChance': 0.02
    }
    
    print(f"🤖 TVB: Test config - Buy bias: {test_config['buyBias']}, Risk: {test_config['riskTolerance']}")
    print("🤖 TVB: ✅ Fixed trading module test complete!")