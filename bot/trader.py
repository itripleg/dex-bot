# Add this import at the top of bot/trader.py:
from bot.token_creator import TokenCreator

# Then add this method to the TokenTrader class:

def __init__(self, w3, account, factory_contract, config, webhook_manager=None, verbose=False, logger=None):
    # ... existing init code ...
    
    # Add token creator
    self.token_creator = TokenCreator(
        bot_name=config.get('name', 'unknown'),
        config=config,
        logger=logger
    )

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
        
        # Create token on-chain
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