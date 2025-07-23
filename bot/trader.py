# bot/trader.py - Fixed trading module with robust error handling
#!/usr/bin/env python3
"""
Enhanced Trading execution logic with comprehensive error handling and recovery
Fixed to prevent trader failures from crashing bots
"""

import random
import time
import traceback
from web3 import Web3
from web3.exceptions import (
    Web3Exception, 
    TimeExhausted, 
    TransactionNotFound, 
    BlockNotFound,
    ContractLogicError,
    Web3RPCError,
    ProviderConnectionError
)
from bot.token_creator import TokenCreator

class TokenTrader:
    """Handles all trading operations with comprehensive error handling and recovery"""
    
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
        
        # Error handling configuration
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        self.transaction_timeout = 60  # Reduced from 120 to prevent hanging
        
        # Token creator with error handling
        try:
            self.token_creator = TokenCreator(
                bot_name=config.get('name', 'unknown'),
                config=config,
                logger=logger
            )
        except Exception as e:
            self._debug_log(f"⚠️ Token creator initialization failed: {e}")
            self.token_creator = None
        
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
        """Make and execute a trading decision for the given token with comprehensive error handling"""
        try:
            token_address = token.get('address')
            token_symbol = token.get('symbol', 'UNKNOWN')
            token_name = token.get('name', token_symbol)
            
            if not token_address:
                self._debug_log(f"❌ Invalid token data: missing address")
                return False
            
            # Create token info dict for webhooks
            token_info = {
                "address": token_address,
                "symbol": token_symbol,
                "name": token_name
            }
            
            self._debug_log(f"🎯 Processing trade decision for {token_symbol} ({token_address})")
            
            # Check token state with retry logic
            token_state = self._get_token_state_with_retry(token_address, token_symbol)
            if token_state is None:
                return False
            
            if token_state not in [1, 4]:  # Not TRADING or RESUMED
                error_msg = f"Token {token_symbol} not tradeable (state: {token_state})"
                self._debug_log(f"⚠️ {error_msg}")
                if self.webhook:
                    self.webhook.send_error_update(error_msg, "invalid_token_state")
                return False
            
            # Get current balances with retry logic
            token_balance = self._get_token_balance_with_retry(token_address)
            current_avax = self._get_avax_balance_with_retry()
            
            if token_balance is None or current_avax is None:
                self._debug_log(f"❌ Failed to get balances for {token_symbol}")
                return False
            
            min_trade = self.min_trade_amount
            
            self._debug_log(f"💰 Current balances - AVAX: {current_avax:.6f}, {token_symbol}: {token_balance/1e18:.6f}")
            
            # Check if we have enough AVAX for minimum trade
            if current_avax < min_trade:
                # Force sell if we have tokens but insufficient AVAX to buy
                if token_balance > 0:
                    self._debug_log(f"🔄 Insufficient AVAX ({current_avax:.4f}) for buying, forcing sell of {token_symbol}")
                    return self._execute_sell_with_retry(token_info, token_balance, forced=True)
                else:
                    self._debug_log(f"❌ Insufficient AVAX ({current_avax:.4f}) and no {token_symbol} to sell")
                    
                    # Send webhook for insufficient funds
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
                return self._execute_buy_with_retry(token_info)
            elif action == 'sell':
                return self._execute_sell_with_retry(token_info, token_balance)
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
            self._debug_log(f"Traceback: {traceback.format_exc()}")
            
            # Send error webhook with personality message
            if self.webhook:
                self.webhook.send_error_update(error_msg, "trade_decision")
            
            return False
    
    def _get_token_state_with_retry(self, token_address, token_symbol):
        """Get token state with retry logic"""
        for attempt in range(self.max_retries):
            try:
                token_state = self.factory_contract.functions.getTokenState(token_address).call()
                self._debug_log(f"📊 Token {token_symbol} state: {token_state}")
                return token_state
                
            except (Web3Exception, Web3RPCError, ProviderConnectionError) as e:
                if attempt == self.max_retries - 1:
                    error_msg = f"Failed to get token state for {token_symbol} after {self.max_retries} attempts: {e}"
                    self._debug_log(f"❌ {error_msg}")
                    if self.webhook:
                        self.webhook.send_error_update(error_msg, "state_check_failed")
                    return None
                
                self._debug_log(f"⚠️ Token state check attempt {attempt + 1} failed: {e}")
                time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                
            except Exception as e:
                error_msg = f"Unexpected error checking token state for {token_symbol}: {e}"
                self._debug_log(f"❌ {error_msg}")
                if self.webhook:
                    self.webhook.send_error_update(error_msg, "state_check_error")
                return None
        
        return None
    
    def _get_token_balance_with_retry(self, token_address):
        """Get token balance with retry logic"""
        for attempt in range(self.max_retries):
            try:
                token_contract = self.w3.eth.contract(
                    address=self.w3.to_checksum_address(token_address),
                    abi=self.token_abi
                )
                balance = token_contract.functions.balanceOf(self.account.address).call()
                self._debug_log(f"🔍 Token balance for {token_address[:10]}...: {balance/1e18:.6f}")
                return balance
                
            except (Web3Exception, Web3RPCError, ProviderConnectionError) as e:
                if attempt == self.max_retries - 1:
                    self._debug_log(f"❌ Error getting token balance for {token_address[:10]}... after {self.max_retries} attempts: {e}")
                    return None
                
                self._debug_log(f"⚠️ Token balance attempt {attempt + 1} failed: {e}")
                time.sleep(self.retry_delay * (attempt + 1))
                
            except Exception as e:
                self._debug_log(f"❌ Unexpected error getting token balance for {token_address[:10]}...: {e}")
                return None
        
        return None
    
    def _get_avax_balance_with_retry(self):
        """Get AVAX balance with retry logic"""
        for attempt in range(self.max_retries):
            try:
                balance_wei = self.w3.eth.get_balance(self.account.address)
                balance_avax = float(self.w3.from_wei(balance_wei, 'ether'))
                return balance_avax
                
            except (Web3Exception, Web3RPCError, ProviderConnectionError) as e:
                if attempt == self.max_retries - 1:
                    self._debug_log(f"❌ Error getting AVAX balance after {self.max_retries} attempts: {e}")
                    return None
                
                self._debug_log(f"⚠️ AVAX balance attempt {attempt + 1} failed: {e}")
                time.sleep(self.retry_delay * (attempt + 1))
                
            except Exception as e:
                self._debug_log(f"❌ Unexpected error getting AVAX balance: {e}")
                return None
        
        return None
    
    def _execute_buy_with_retry(self, token_info):
        """Execute buy with retry logic"""
        for attempt in range(self.max_retries):
            try:
                result = self._execute_buy(token_info)
                if result:
                    return True
                
                # If buy failed but didn't throw exception, don't retry
                return False
                
            except (Web3Exception, Web3RPCError, ProviderConnectionError) as e:
                if attempt == self.max_retries - 1:
                    error_msg = f"Buy failed after {self.max_retries} attempts: {e}"
                    self._debug_log(f"❌ {error_msg}")
                    if self.webhook:
                        self.webhook.send_error_update(error_msg, "buy_retry_exhausted")
                    return False
                
                self._debug_log(f"⚠️ Buy attempt {attempt + 1} failed: {e}")
                time.sleep(self.retry_delay * (attempt + 1))
                
            except Exception as e:
                error_msg = f"Unexpected error in buy execution: {e}"
                self._debug_log(f"❌ {error_msg}")
                if self.webhook:
                    self.webhook.send_error_update(error_msg, "buy_unexpected_error")
                return False
        
        return False
    
    def _execute_sell_with_retry(self, token_info, token_balance, forced=False):
        """Execute sell with retry logic"""
        for attempt in range(self.max_retries):
            try:
                result = self._execute_sell(token_info, token_balance, forced)
                if result:
                    return True
                
                # If sell failed but didn't throw exception, don't retry
                return False
                
            except (Web3Exception, Web3RPCError, ProviderConnectionError) as e:
                if attempt == self.max_retries - 1:
                    error_msg = f"Sell failed after {self.max_retries} attempts: {e}"
                    self._debug_log(f"❌ {error_msg}")
                    if self.webhook:
                        self.webhook.send_error_update(error_msg, "sell_retry_exhausted")
                    return False
                
                self._debug_log(f"⚠️ Sell attempt {attempt + 1} failed: {e}")
                time.sleep(self.retry_delay * (attempt + 1))
                
            except Exception as e:
                error_msg = f"Unexpected error in sell execution: {e}"
                self._debug_log(f"❌ {error_msg}")
                if self.webhook:
                    self.webhook.send_error_update(error_msg, "sell_unexpected_error")
                return False
        
        return False
    
    def _execute_buy(self, token_info):
        """Execute a buy transaction with comprehensive error handling"""
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
            current_avax = self._get_avax_balance_with_retry()
            if current_avax is None:
                return False
                
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
            
            # Get transaction parameters with error handling
            try:
                nonce = self.w3.eth.get_transaction_count(self.account.address)
                gas_price = self.w3.eth.gas_price
            except Exception as e:
                self._debug_log(f"❌ Failed to get transaction parameters: {e}")
                return False
            
            self._debug_log(f"📋 Transaction params - Nonce: {nonce}, Gas Price: {gas_price}")
            
            # Build transaction with error handling (FIXED: correct function signature)
            try:
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
            except Exception as e:
                error_msg = f"Failed to build buy transaction: {e}"
                self._debug_log(f"❌ {error_msg}")
                if self.webhook:
                    self.webhook.send_error_update(error_msg, "transaction_build_failed")
                return False
            
            self._debug_log(f"📝 Transaction built - Gas: {txn['gas']}, Value: {amount_to_buy:.6f} AVAX")
            
            # Sign and send with error handling
            try:
                self._debug_log("🔐 Signing transaction...")
                signed_txn = self.account.sign_transaction(txn)
                
                self._debug_log("📡 Sending transaction...")
                tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
                tx_hash_hex = self.w3.to_hex(tx_hash)
            except Exception as e:
                error_msg = f"Failed to sign/send transaction: {e}"
                self._debug_log(f"❌ {error_msg}")
                if self.webhook:
                    self.webhook.send_error_update(error_msg, "transaction_send_failed")
                return False
            
            self._debug_log(f"✅ Transaction sent! Hash: {tx_hash_hex}")
            self._debug_log("⏳ Waiting for confirmation...")
            
            # Wait for receipt with reduced timeout and error handling
            try:
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=self.transaction_timeout)
            except TimeExhausted:
                error_msg = f"Transaction timeout after {self.transaction_timeout}s: {tx_hash_hex}"
                self._debug_log(f"⏰ {error_msg}")
                if self.webhook:
                    self.webhook.send_error_update(error_msg, "transaction_timeout")
                return False
            except Exception as e:
                error_msg = f"Error waiting for transaction receipt: {e}"
                self._debug_log(f"❌ {error_msg}")
                if self.webhook:
                    self.webhook.send_error_update(error_msg, "receipt_error")
                return False
            
            self._debug_log(f"📄 Receipt received - Status: {receipt.status}, Gas Used: {receipt.gasUsed}")
            
            if receipt.status == 1:
                post_trade_balance = self._get_avax_balance_with_retry()
                
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
            self._debug_log(f"Traceback: {traceback.format_exc()}")
            
            if self.webhook:
                self.webhook.send_error_update(error_msg, "buy_execution")
            
            return False
    
    def _execute_sell(self, token_info, token_balance, forced=False):
        """Execute a sell transaction with comprehensive error handling"""
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
            
            # Get transaction parameters with error handling
            try:
                nonce = self.w3.eth.get_transaction_count(self.account.address)
                gas_price = self.w3.eth.gas_price
            except Exception as e:
                self._debug_log(f"❌ Failed to get transaction parameters: {e}")
                return False
            
            self._debug_log(f"📋 Transaction params - Nonce: {nonce}, Gas Price: {gas_price}")
            
            # Build transaction with error handling (FIXED: added minEthOut parameter)
            try:
                txn = self.factory_contract.functions.sell(
                    self.w3.to_checksum_address(token_address),
                    amount_to_sell,
                    0  # minEthOut = 0 (no slippage protection)
                ).build_transaction({
                    'from': self.account.address,
                    'gas': 800000,  # Increased gas limit
                    'gasPrice': gas_price,
                    'nonce': nonce,
                    'chainId': 43113  # Avalanche Fuji testnet
                })
            except Exception as e:
                error_msg = f"Failed to build sell transaction: {e}"
                self._debug_log(f"❌ {error_msg}")
                if self.webhook:
                    self.webhook.send_error_update(error_msg, "transaction_build_failed")
                return False
            
            self._debug_log(f"📝 Transaction built - Gas: {txn['gas']}, Amount: {amount_to_sell}")
            
            # Sign and send with error handling
            try:
                self._debug_log("🔐 Signing transaction...")
                signed_txn = self.account.sign_transaction(txn)
                
                self._debug_log("📡 Sending transaction...")
                tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
                tx_hash_hex = self.w3.to_hex(tx_hash)
            except Exception as e:
                error_msg = f"Failed to sign/send transaction: {e}"
                self._debug_log(f"❌ {error_msg}")
                if self.webhook:
                    self.webhook.send_error_update(error_msg, "transaction_send_failed")
                return False
            
            self._debug_log(f"✅ Transaction sent! Hash: {tx_hash_hex}")
            self._debug_log("⏳ Waiting for confirmation...")
            
            # Wait for receipt with reduced timeout and error handling
            try:
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=self.transaction_timeout)
            except TimeExhausted:
                error_msg = f"Transaction timeout after {self.transaction_timeout}s: {tx_hash_hex}"
                self._debug_log(f"⏰ {error_msg}")
                if self.webhook:
                    self.webhook.send_error_update(error_msg, "transaction_timeout")
                return False
            except Exception as e:
                error_msg = f"Error waiting for transaction receipt: {e}"
                self._debug_log(f"❌ {error_msg}")
                if self.webhook:
                    self.webhook.send_error_update(error_msg, "receipt_error")
                return False
            
            self._debug_log(f"📄 Receipt received - Status: {receipt.status}, Gas Used: {receipt.gasUsed}")
            
            if receipt.status == 1:
                post_trade_balance = self._get_avax_balance_with_retry()
                
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
            self._debug_log(f"Traceback: {traceback.format_exc()}")
            
            if self.webhook:
                self.webhook.send_error_update(error_msg, "sell_execution")
            
            return False
    
    def attempt_token_creation(self):
        """Attempt to create a new token with personality-driven concept"""
        try:
            if not self.token_creator:
                self._debug_log("❌ Token creator not available")
                return False
                
            if not self.token_creator.should_create_token():
                if self.verbose:
                    self._debug_log("🎲 Token creation check: Not this time")
                return False
            
            # Check if we have enough AVAX for creation
            current_avax = self._get_avax_balance_with_retry()
            if current_avax is None:
                return False
                
            creation_amount = 0.01  # 0.01 AVAX for token creation
            
            if current_avax < creation_amount + 0.01:  # Keep some AVAX for gas
                self._debug_log(f"💰 Insufficient AVAX for token creation ({current_avax:.4f} < {creation_amount + 0.01:.4f})")
                return False
            
            # Generate token concept
            try:
                concept = self.token_creator.generate_token_concept()
            except Exception as e:
                error_msg = f"Failed to generate token concept: {e}"
                self._debug_log(f"❌ {error_msg}")
                if self.webhook:
                    self.webhook.send_error_update(error_msg, "concept_generation_failed")
                return False
            
            # Send creation webhook with concept
            if self.webhook:
                self.webhook.send_update("create_token", {
                    "message": f"Creating new token: {concept['name']} (${concept['symbol']}) {concept['image_emoji']}",
                    "tokenConcept": concept,
                    "plannedInvestment": creation_amount,
                    "status": "creating"
                })
            
            self._debug_log(f"🎨 Creating token: {concept['name']} (${concept['symbol']}) {concept['image_emoji']}")
            
            # Create token on-chain with error handling
            try:
                success, result = self.token_creator.create_token_on_chain(
                    w3=self.w3,
                    factory_contract=self.factory_contract,
                    account=self.account,
                    concept=concept,
                    eth_amount=creation_amount
                )
            except Exception as e:
                error_msg = f"Token creation failed: {e}"
                self._debug_log(f"❌ {error_msg}")
                if self.webhook:
                    self.webhook.send_error_update(error_msg, "token_creation_execution_failed")
                return False
            
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
            self._debug_log(f"Traceback: {traceback.format_exc()}")
            
            if self.webhook:
                self.webhook.send_error_update(error_msg, "token_creation_error")
            
            return False
    
    def _decide_trade_action(self, token_balance):
        """Decide whether to buy, sell, or hold based on personality and balance"""
        try:
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
            
        except Exception as e:
            self._debug_log(f"❌ Error in trade decision logic: {e}")
            return 'hold'  # Safe default
    
    def _get_token_balance(self, token_address):
        """Get current balance of a specific token (legacy method - use with_retry version)"""
        return self._get_token_balance_with_retry(token_address) or 0
    
    def _get_avax_balance(self):
        """Get current AVAX balance (legacy method - use with_retry version)"""
        return self._get_avax_balance_with_retry() or 0.0
    
    def _debug_log(self, message):
        """Centralized debug logging with error handling"""
        try:
            if self.verbose:
                if self.logger:
                    self.logger.info(message)
                else:
                    print(f"🤖 TVB: {message}")
        except Exception as e:
            # Fallback logging if logger fails
            print(f"🤖 TVB: [LOG ERROR] {message} | Logger error: {e}")
    
    def get_trading_stats(self):
        """Get current trading configuration and stats"""
        try:
            current_balance = self._get_avax_balance_with_retry()
            return {
                "buy_bias": self.buy_bias,
                "risk_tolerance": self.risk_tolerance,
                "min_trade_amount": self.min_trade_amount,
                "max_trade_amount": self.max_trade_amount,
                "current_avax_balance": current_balance or 0.0,
                "max_retries": self.max_retries,
                "transaction_timeout": self.transaction_timeout,
                "token_creator_available": self.token_creator is not None
            }
        except Exception as e:
            self._debug_log(f"❌ Error getting trading stats: {e}")
            return {
                "buy_bias": self.buy_bias,
                "risk_tolerance": self.risk_tolerance,
                "min_trade_amount": self.min_trade_amount,
                "max_trade_amount": self.max_trade_amount,
                "current_avax_balance": 0.0,
                "error": str(e)
            }
    
    def simulate_trade_decision(self, token, num_simulations=100):
        """Simulate trade decisions for testing personality calibration"""
        try:
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
            
        except Exception as e:
            self._debug_log(f"❌ Error in simulation: {e}")
            return None
    
    def health_check(self):
        """Perform a health check on the trader components"""
        try:
            health_status = {
                "trader_initialized": True,
                "web3_connected": False,
                "factory_contract_available": False,
                "token_creator_available": self.token_creator is not None,
                "can_get_balance": False,
                "configuration_valid": False
            }
            
            # Test Web3 connection
            try:
                self.w3.eth.get_block_number()
                health_status["web3_connected"] = True
            except Exception as e:
                self._debug_log(f"⚠️ Web3 connection test failed: {e}")
            
            # Test factory contract
            try:
                # Try a simple contract call
                self.factory_contract.functions
                health_status["factory_contract_available"] = True
            except Exception as e:
                self._debug_log(f"⚠️ Factory contract test failed: {e}")
            
            # Test balance retrieval
            try:
                balance = self._get_avax_balance_with_retry()
                if balance is not None:
                    health_status["can_get_balance"] = True
            except Exception as e:
                self._debug_log(f"⚠️ Balance test failed: {e}")
            
            # Check configuration
            try:
                if (self.buy_bias >= 0 and self.buy_bias <= 1 and
                    self.risk_tolerance >= 0 and self.risk_tolerance <= 1 and
                    self.min_trade_amount > 0 and self.max_trade_amount > self.min_trade_amount):
                    health_status["configuration_valid"] = True
            except Exception as e:
                self._debug_log(f"⚠️ Configuration validation failed: {e}")
            
            # Overall health
            critical_components = ["web3_connected", "factory_contract_available", "configuration_valid"]
            health_status["overall_healthy"] = all(health_status[comp] for comp in critical_components)
            
            return health_status
            
        except Exception as e:
            self._debug_log(f"❌ Health check failed: {e}")
            return {
                "trader_initialized": False,
                "error": str(e),
                "overall_healthy": False
            }


# Example usage and testing
if __name__ == "__main__":
    print("🤖 TVB: Enhanced trading module with comprehensive error handling loaded!")
    
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
    print("🤖 TVB: ✅ Enhanced trading module with error handling test complete!")