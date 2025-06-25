#!/usr/bin/env python3
"""
Enhanced Webhook Manager for TVB bot communication
Now includes real-time AVAX balance and token ticker information
"""

import json
import random
import requests
from datetime import datetime

class WebhookManager:
    """Manages webhook communications with personality-driven messaging and balance tracking"""
    
    def __init__(self, bot_name, display_name, avatar_url, webhook_url, bot_secret, phrases, bio=None, get_balance_callback=None):
        self.bot_name = bot_name
        self.display_name = display_name
        self.avatar_url = avatar_url
        self.webhook_url = webhook_url
        self.bot_secret = bot_secret
        self.phrases = phrases
        self.bio = bio
        self.get_balance_callback = get_balance_callback  # Callback to get current AVAX balance
        
        # Track webhook statistics
        self.webhook_stats = {
            "total_sent": 0,
            "successful": 0,
            "failed": 0,
            "last_sent": None,
            "last_error": None
        }
        
        self.enabled = bool(webhook_url and bot_secret)
        
        if self.enabled:
            print(f"🤖 TVB: 📡 Webhook manager initialized for {display_name}")
            print(f"🤖 TVB: 🎯 Target: {webhook_url}")
            if bio:
                print(f"🤖 TVB: 📝 Bio: {bio[:50]}..." if len(bio) > 50 else f"🤖 TVB: 📝 Bio: {bio}")
        else:
            print(f"🤖 TVB: ⚠️ Webhook disabled - missing URL or secret")
    
    def _get_current_balance(self):
        """Get current AVAX balance via callback"""
        if self.get_balance_callback:
            try:
                return self.get_balance_callback()
            except Exception as e:
                print(f"🤖 TVB: ⚠️ Error getting balance: {e}")
                return None
        return None
    
    def send_update(self, action_type, details):
        """Send webhook update with personality-appropriate messaging and current balance"""
        if not self.enabled:
            return False
        
        try:
            # Add personality message if not already provided
            if 'message' not in details and action_type in self.phrases:
                phrase_list = self.phrases[action_type]
                if phrase_list:
                    details['message'] = random.choice(phrase_list)
            
            # Add current balance to all updates
            current_balance = self._get_current_balance()
            if current_balance is not None:
                details['currentBalance'] = round(current_balance, 6)
            
            # Build payload with bio and balance included
            payload = {
                "botName": self.bot_name,
                "displayName": self.display_name,
                "avatarUrl": self.avatar_url,
                "bio": self.bio,
                "action": action_type,
                "details": details,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "botSecret": self.bot_secret
            }
            
            # Also add bio to details for startup specifically
            if action_type == 'startup' and self.bio:
                payload["details"]["bio"] = self.bio
            
            # Send webhook
            success = self._send_webhook(payload)
            
            # Update statistics
            self._update_stats(success, action_type)
            
            return success
            
        except Exception as e:
            print(f"🤖 TVB: ❌ Webhook error: {e}")
            self._update_stats(False, action_type, str(e))
            return False
    
    def send_trade_update(self, action, token_info, trade_details, post_trade_balance=None):
        """Send specialized trading update with rich details including balance"""
        details = {
            "tokenAddress": token_info["address"],
            "tokenSymbol": token_info["symbol"],
            "tokenName": token_info["name"]
        }
        details.update(trade_details)
        
        # Add post-trade balance if provided
        if post_trade_balance is not None:
            details['postTradeBalance'] = round(post_trade_balance, 6)
        
        return self.send_update(action, details)
    
    def send_buy_update(self, token_info, amount_avax, tx_hash, post_trade_balance=None):
        """Send buy transaction update with balance"""
        return self.send_trade_update("buy", token_info, {
            "amountAvax": round(amount_avax, 6),
            "txHash": tx_hash,
            "tradeType": "BUY"
        }, post_trade_balance)
    
    def send_sell_update(self, token_info, token_amount, readable_amount, sell_percentage, tx_hash, post_trade_balance=None):
        """Send sell transaction update with balance"""
        return self.send_trade_update("sell", token_info, {
            "tokenAmount": str(token_amount),
            "readableAmount": round(readable_amount, 6),
            "sellPercentage": round(sell_percentage * 100, 1),
            "txHash": tx_hash,
            "tradeType": "SELL"
        }, post_trade_balance)
    
    def send_trade_attempt(self, action, token_info, planned_amount=None):
        """Send notification when trade is being attempted (before execution)"""
        details = {
            "tokenAddress": token_info["address"],
            "tokenSymbol": token_info["symbol"],
            "tokenName": token_info["name"],
            "status": "attempting"
        }
        
        if planned_amount:
            if action == "buy":
                details["plannedAmountAvax"] = round(planned_amount, 6)
            else:
                details["plannedTokenAmount"] = round(planned_amount, 6)
        
        return self.send_update(f"{action}_attempt", details)
    
    def send_trade_success(self, action, token_info, actual_amounts, tx_hash):
        """Send notification when trade succeeds"""
        details = {
            "tokenAddress": token_info["address"],
            "tokenSymbol": token_info["symbol"],
            "tokenName": token_info["name"],
            "status": "success",
            "txHash": tx_hash
        }
        details.update(actual_amounts)
        
        return self.send_update(f"{action}_success", details)
    
    def send_trade_failure(self, action, token_info, error_reason):
        """Send notification when trade fails"""
        details = {
            "tokenAddress": token_info["address"],
            "tokenSymbol": token_info["symbol"],
            "tokenName": token_info["name"],
            "status": "failed",
            "error": str(error_reason)
        }
        
        return self.send_update(f"{action}_failed", details)
    
    def send_error_update(self, error_message, context=None, token_info=None):
        """Send error notification with context and optional token info"""
        details = {"message": error_message}
        if context:
            details["context"] = context
        if token_info:
            details.update({
                "tokenAddress": token_info.get("address"),
                "tokenSymbol": token_info.get("symbol"),
                "tokenName": token_info.get("name")
            })
        
        return self.send_update("error", details)
    
    def send_heartbeat(self, balance_info, token_count, extra_data=None):
        """Send heartbeat update with current status"""
        details = {
            "message": f"{self.display_name} is active and trading",
            "currentBalance": round(balance_info["current"], 6),
            "balanceChange": round(balance_info["change"], 6),
            "tokensTracked": token_count,
            "status": "active"
        }
        
        if extra_data:
            details.update(extra_data)
        
        return self.send_update("heartbeat", details)
    
    def send_startup_notification(self, startup_info):
        """Send startup notification with bio and initial balance"""
        # Ensure bio is included in startup info
        if self.bio and 'bio' not in startup_info:
            startup_info['bio'] = self.bio
        
        # Add initial balance
        current_balance = self._get_current_balance()
        if current_balance is not None:
            startup_info['initialBalance'] = round(current_balance, 6)
        
        return self.send_update("startup", startup_info)
    
    def send_shutdown_notification(self, shutdown_info):
        """Send shutdown notification with final balance"""
        current_balance = self._get_current_balance()
        if current_balance is not None:
            shutdown_info['finalBalance'] = round(current_balance, 6)
        
        return self.send_update("shutdown", shutdown_info)
    
    def send_balance_alert(self, balance, threshold, alert_type="low"):
        """Send balance alert when AVAX gets low or high"""
        details = {
            "message": f"Balance alert: {balance:.6f} AVAX",
            "currentBalance": round(balance, 6),
            "threshold": round(threshold, 6),
            "alertType": alert_type
        }
        
        return self.send_update("balance_alert", details)
    
    def _send_webhook(self, payload):
        """Send the actual HTTP request"""
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                action = payload['action']
                balance = payload['details'].get('currentBalance', 'unknown')
                token = payload['details'].get('tokenSymbol', '')
                
                if token:
                    print(f"🤖 TVB: ✅ Webhook sent: {action} {token} (Balance: {balance} AVAX)")
                else:
                    print(f"🤖 TVB: ✅ Webhook sent: {action} (Balance: {balance} AVAX)")
                return True
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                print(f"🤖 TVB: ❌ Webhook failed: {error_msg}")
                return False
                
        except requests.exceptions.Timeout:
            print(f"🤖 TVB: ⏰ Webhook timeout")
            return False
        except requests.exceptions.ConnectionError:
            print(f"🤖 TVB: 🔌 Webhook connection error")
            return False
        except requests.exceptions.RequestException as e:
            print(f"🤖 TVB: 🌐 Webhook request error: {e}")
            return False
    
    def _update_stats(self, success, action_type, error_msg=None):
        """Update webhook statistics"""
        self.webhook_stats["total_sent"] += 1
        self.webhook_stats["last_sent"] = datetime.utcnow().isoformat() + "Z"
        
        if success:
            self.webhook_stats["successful"] += 1
        else:
            self.webhook_stats["failed"] += 1
            if error_msg:
                self.webhook_stats["last_error"] = {
                    "action": action_type,
                    "error": error_msg,
                    "timestamp": self.webhook_stats["last_sent"]
                }
    
    # ... rest of the methods remain the same ...