#!/usr/bin/env python3
"""
bot/simple_webhook.py - Real webhook manager implementation
Save this as bot/simple_webhook.py
"""

import json
import requests
import time
from datetime import datetime
from typing import Optional, Dict, Any

class SimpleWebhookManager:
    """Simplified webhook manager that exactly matches API expectations"""
    
    def __init__(self, bot_name: str, display_name: str, avatar_url: str, 
                 webhook_url: str, bot_secret: str, bio: str = None, wallet_address: str = None):
        self.bot_name = bot_name
        self.display_name = display_name
        self.avatar_url = avatar_url
        self.webhook_url = webhook_url
        self.bot_secret = bot_secret
        self.bio = bio
        self.wallet_address = wallet_address
        
        # Session tracking
        self.session_start_time = None
        self.starting_balance = None
        
        # Simple stats
        self.total_webhooks_sent = 0
        self.successful_webhooks = 0
        
        self.enabled = bool(webhook_url and bot_secret)
        
        print(f"🤖 {display_name}: Webhook {'enabled' if self.enabled else 'disabled'}")
    
    def set_session_start(self, starting_balance: float, start_time: str = None):
        """Set session start metrics"""
        self.starting_balance = starting_balance
        self.session_start_time = start_time or datetime.utcnow().isoformat() + "Z"
    
    def _build_base_payload(self, action: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """Build the base payload that matches API expectations exactly"""
        return {
            "botName": self.bot_name,
            "displayName": self.display_name,
            "avatarUrl": self.avatar_url,
            "action": action,
            "details": details,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "botSecret": self.bot_secret
        }
    
    def _send_webhook(self, payload: Dict[str, Any]) -> bool:
        """Send webhook with basic retry logic"""
        if not self.enabled:
            return False
        
        self.total_webhooks_sent += 1
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                self.successful_webhooks += 1
                return True
            else:
                print(f"🤖 {self.display_name}: Webhook failed - HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"🤖 {self.display_name}: Webhook error - {e}")
            return False
    
    # CORE TRADING ACTIONS - These are the main ones the API expects
    
    def send_startup(self, starting_balance: float, tokens_found: int, config: Dict = None) -> bool:
        """Send startup notification"""
        details = {
            "message": f"{self.display_name} is now online and ready to trade!",
            "startingBalance": starting_balance,
            "tokensFound": tokens_found,
            "walletAddress": self.wallet_address
        }
        
        if self.bio:
            details["bio"] = self.bio
        
        if config:
            details["config"] = config
        
        payload = self._build_base_payload("startup", details)
        return self._send_webhook(payload)
    
    def send_buy(self, token_address: str, token_symbol: str, token_name: str, 
                 amount_avax: float, tx_hash: str, current_balance: float) -> bool:
        """Send buy action"""
        details = {
            "message": f"Bought {token_symbol} with {amount_avax:.4f} AVAX",
            "tokenAddress": token_address,
            "tokenSymbol": token_symbol, 
            "tokenName": token_name,
            "amountAvax": amount_avax,
            "txHash": tx_hash,
            "currentBalance": current_balance,
            "walletAddress": self.wallet_address
        }
        
        payload = self._build_base_payload("buy", details)
        return self._send_webhook(payload)
    
    def send_sell(self, token_address: str, token_symbol: str, token_name: str,
                  token_amount: int, readable_amount: float, sell_percentage: float,
                  tx_hash: str, current_balance: float) -> bool:
        """Send sell action"""
        details = {
            "message": f"Sold {readable_amount:.4f} {token_symbol} ({sell_percentage:.1f}%)",
            "tokenAddress": token_address,
            "tokenSymbol": token_symbol,
            "tokenName": token_name,
            "tokenAmount": str(token_amount),
            "readableAmount": readable_amount,
            "sellPercentage": sell_percentage,
            "txHash": tx_hash,
            "currentBalance": current_balance,
            "walletAddress": self.wallet_address
        }
        
        payload = self._build_base_payload("sell", details)
        return self._send_webhook(payload)
    
    def send_hold(self, token_address: str, token_symbol: str, token_name: str,
                  token_balance: int, current_balance: float) -> bool:
        """Send hold action"""
        readable_balance = token_balance / 1e18
        details = {
            "message": f"Holding {readable_balance:.4f} {token_symbol}",
            "tokenAddress": token_address,
            "tokenSymbol": token_symbol,
            "tokenName": token_name,
            "tokenBalance": str(token_balance),
            "readableBalance": readable_balance,
            "currentBalance": current_balance,
            "walletAddress": self.wallet_address
        }
        
        payload = self._build_base_payload("hold", details)
        return self._send_webhook(payload)
    
    def send_create_token(self, token_name: str, token_symbol: str, 
                         investment_amount: float, tx_hash: str = None, 
                         current_balance: float = None) -> bool:
        """Send token creation action"""
        details = {
            "message": f"Created new token: {token_name} (${token_symbol})",
            "tokenName": token_name,
            "tokenSymbol": token_symbol,
            "investmentAmount": investment_amount,
            "currentBalance": current_balance,
            "walletAddress": self.wallet_address
        }
        
        if tx_hash:
            details["txHash"] = tx_hash
        
        payload = self._build_base_payload("create_token", details)
        return self._send_webhook(payload)
    
    def send_error(self, error_message: str, error_type: str = "general_error", 
                   current_balance: float = None) -> bool:
        """Send error notification"""
        details = {
            "message": f"Error: {error_message}",
            "errorType": error_type,
            "errorDetails": error_message,
            "walletAddress": self.wallet_address
        }
        
        if current_balance is not None:
            details["currentBalance"] = current_balance
        
        payload = self._build_base_payload("error", details)
        return self._send_webhook(payload)
    
    def send_heartbeat(self, current_balance: float, tokens_tracked: int) -> bool:
        """Send simple heartbeat"""
        details = {
            "message": f"{self.display_name} is active",
            "currentBalance": current_balance,
            "tokensTracked": tokens_tracked,
            "walletAddress": self.wallet_address,
            "status": "active"
        }
        
        payload = self._build_base_payload("heartbeat", details)
        return self._send_webhook(payload)
    
    def send_shutdown(self, total_cycles: int, current_balance: float, reason: str = "user") -> bool:
        """Send shutdown notification"""
        details = {
            "message": f"{self.display_name} is going offline",
            "totalCycles": total_cycles,
            "currentBalance": current_balance,
            "reason": reason,
            "walletAddress": self.wallet_address
        }
        
        # Calculate P&L if we have starting balance
        if self.starting_balance is not None:
            pnl_amount = current_balance - self.starting_balance
            pnl_percentage = (pnl_amount / self.starting_balance * 100) if self.starting_balance > 0 else 0
            details.update({
                "startingBalance": self.starting_balance,
                "pnlAmount": pnl_amount,
                "pnlPercentage": pnl_percentage
            })
        
        payload = self._build_base_payload("shutdown", details)
        return self._send_webhook(payload)
    
    # UTILITY METHODS
    
    def get_success_rate(self) -> float:
        """Get webhook success rate"""
        if self.total_webhooks_sent == 0:
            return 1.0
        return self.successful_webhooks / self.total_webhooks_sent
    
    def print_stats(self):
        """Print simple stats"""
        success_rate = self.get_success_rate() * 100
        print(f"🤖 {self.display_name}: Webhook Stats:")
        print(f"   📡 Sent: {self.total_webhooks_sent}")
        print(f"   ✅ Success: {self.successful_webhooks}")
        print(f"   📊 Rate: {success_rate:.1f}%")