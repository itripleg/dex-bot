#!/usr/bin/env python3
"""
Enhanced Webhook Manager with session balance tracking and P&L calculations
"""

import json
import random
import requests
from datetime import datetime

class WebhookManager:
    """Manages webhook communications with session balance tracking and P&L calculations"""
    
    def __init__(self, bot_name, display_name, avatar_url, webhook_url, bot_secret, phrases, bio=None, get_balance_callback=None):
        self.bot_name = bot_name
        self.display_name = display_name
        self.avatar_url = avatar_url
        self.webhook_url = webhook_url
        self.bot_secret = bot_secret
        self.phrases = phrases
        self.bio = bio
        self.get_balance_callback = get_balance_callback  # Callback to get current AVAX balance
        
        # Session balance tracking
        self.starting_balance = None
        self.session_start_time = None
        
        # Define which actions should get personality phrases vs system messages
        self.personality_actions = {'buy', 'sell', 'create_token', 'error'}
        self.system_actions = {
            'cycle_start', 'cycle_complete', 'token_refresh', 'heartbeat', 'startup', 
            'shutdown', 'buy_attempt', 'sell_attempt', 'trade_failure', 'insufficient_funds',
            'forced_sell', 'hold', 'balance_alert', 'token_refresh_start', 'token_refresh_complete',
            'creation_cancelled', 'no_tokens', 'buy_success', 'sell_success', 'buy_failed', 'sell_failed'
        }
        
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
    
    def _calculate_session_metrics(self):
        """Calculate session financial metrics"""
        current_balance = self._get_current_balance()
        
        if current_balance is None or self.starting_balance is None:
            return {
                "currentBalance": current_balance,
                "startingBalance": self.starting_balance,
                "pnlAmount": 0,
                "pnlPercentage": 0
            }
        
        pnl_amount = current_balance - self.starting_balance
        pnl_percentage = (pnl_amount / self.starting_balance * 100) if self.starting_balance > 0 else 0
        
        return {
            "currentBalance": round(current_balance, 6),
            "startingBalance": round(self.starting_balance, 6),
            "pnlAmount": round(pnl_amount, 6),
            "pnlPercentage": round(pnl_percentage, 2)
        }
    
    def set_session_start(self, starting_balance, start_time=None):
        """Set the session starting balance and time"""
        self.starting_balance = starting_balance
        self.session_start_time = start_time or datetime.utcnow().isoformat() + "Z"
        print(f"🤖 TVB: 💰 Session started with {starting_balance:.6f} AVAX")
    
    def send_update(self, action_type, details):
        """Send webhook update with session financial metrics"""
        if not self.enabled:
            return False
        
        try:
            # Only add personality phrases for actual trading actions, not system messages
            if action_type in self.personality_actions and 'message' not in details:
                phrase_list = self.phrases.get(action_type, [])
                if phrase_list:
                    details['message'] = random.choice(phrase_list)
            
            # For system actions, keep the provided message or use a default
            elif action_type in self.system_actions and 'message' not in details:
                details['message'] = f"System: {action_type.replace('_', ' ').title()}"
            
            # Add session financial metrics to all updates
            session_metrics = self._calculate_session_metrics()
            details.update(session_metrics)
            
            # Add session timing
            if self.session_start_time:
                details['sessionStartTime'] = self.session_start_time
                details['sessionDurationMinutes'] = self._get_session_duration_minutes()
            
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
    
    def _get_session_duration_minutes(self):
        """Get session duration in minutes"""
        if not self.session_start_time:
            return 0
        
        try:
            start_time = datetime.fromisoformat(self.session_start_time.replace('Z', ''))
            duration = datetime.utcnow() - start_time
            return int(duration.total_seconds() / 60)
        except:
            return 0
    
    def send_trade_update(self, action, token_info, trade_details, post_trade_balance=None):
        """Send specialized trading update with financial impact"""
        details = {
            "tokenAddress": token_info["address"],
            "tokenSymbol": token_info["symbol"],
            "tokenName": token_info["name"]
        }
        details.update(trade_details)
        
        # Add pre/post trade balance comparison if provided
        if post_trade_balance is not None:
            pre_trade_balance = self._get_current_balance()
            if pre_trade_balance is not None:
                balance_change = post_trade_balance - pre_trade_balance
                details.update({
                    'preTradeBalance': round(pre_trade_balance, 6),
                    'postTradeBalance': round(post_trade_balance, 6),
                    'balanceChange': round(balance_change, 6)
                })
        
        return self.send_update(action, details)
    
    def send_buy_update(self, token_info, amount_avax, tx_hash, post_trade_balance=None):
        """Send buy transaction update with financial metrics"""
        return self.send_trade_update("buy", token_info, {
            "amountAvax": round(amount_avax, 6),
            "txHash": tx_hash,
            "tradeType": "BUY"
        }, post_trade_balance)
    
    def send_sell_update(self, token_info, token_amount, readable_amount, sell_percentage, tx_hash, post_trade_balance=None):
        """Send sell transaction update with financial metrics"""
        return self.send_trade_update("sell", token_info, {
            "tokenAmount": str(token_amount),
            "readableAmount": round(readable_amount, 6),
            "sellPercentage": round(sell_percentage * 100, 1),
            "txHash": tx_hash,
            "tradeType": "SELL"
        }, post_trade_balance)
    
    def send_trade_attempt(self, action, token_info, planned_amount=None):
        """Send notification when trade is being attempted (before execution) - SYSTEM MESSAGE"""
        details = {
            "message": f"Attempting to {action} {token_info['symbol']}",
            "tokenAddress": token_info["address"],
            "tokenSymbol": token_info["symbol"],
            "tokenName": token_info["name"],
            "status": "attempting"
        }
        
        if planned_amount:
            if action == "buy":
                details["plannedAmountAvax"] = round(planned_amount, 6)
                details["message"] = f"Attempting to buy {planned_amount:.4f} AVAX worth of {token_info['symbol']}"
            else:
                details["plannedTokenAmount"] = round(planned_amount, 6)
                details["message"] = f"Attempting to sell {planned_amount:.4f} {token_info['symbol']}"
        
        return self.send_update(f"{action}_attempt", details)
    
    def send_error_update(self, error_message, context=None, token_info=None):
        """Send error notification with context and optional token info - PERSONALITY MESSAGE"""
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
        """Send heartbeat update with comprehensive session metrics"""
        details = {
            "message": f"{self.display_name} is active and trading",
            "tokensTracked": token_count,
            "status": "active"
        }
        
        if extra_data:
            details.update(extra_data)
        
        # Financial metrics are automatically added by send_update()
        return self.send_update("heartbeat", details)
    
    def send_startup_notification(self, startup_info):
        """Send startup notification and set session metrics"""
        # Set session start metrics
        current_balance = self._get_current_balance()
        if current_balance is not None:
            self.set_session_start(current_balance)
            startup_info['initialBalance'] = round(current_balance, 6)
        
        # Ensure bio is included in startup info
        if self.bio and 'bio' not in startup_info:
            startup_info['bio'] = self.bio
        
        return self.send_update("startup", startup_info)
    
    def send_shutdown_notification(self, shutdown_info):
        """Send shutdown notification with final session metrics"""
        # Final metrics are automatically added by send_update()
        return self.send_update("shutdown", shutdown_info)
    
    def send_balance_alert(self, balance, threshold, alert_type="low"):
        """Send balance alert when AVAX gets low or high - SYSTEM MESSAGE"""
        details = {
            "message": f"Balance alert: {balance:.6f} AVAX ({alert_type} threshold)",
            "threshold": round(threshold, 6),
            "alertType": alert_type
        }
        
        return self.send_update("balance_alert", details)
    
    def _send_webhook(self, payload):
        """Send the actual HTTP request with enhanced logging"""
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
                pnl = payload['details'].get('pnlAmount', 0)
                token = payload['details'].get('tokenSymbol', '')
                
                # Enhanced logging with P&L
                pnl_str = f"P&L: {pnl:+.6f}" if isinstance(pnl, (int, float)) else ""
                
                if action in self.personality_actions:
                    if token:
                        print(f"🤖 TVB: ✅ Personality webhook: {action} {token} | Balance: {balance} AVAX | {pnl_str}")
                    else:
                        print(f"🤖 TVB: ✅ Personality webhook: {action} | Balance: {balance} AVAX | {pnl_str}")
                else:
                    if token:
                        print(f"🤖 TVB: ✅ System webhook: {action} {token} | Balance: {balance} AVAX | {pnl_str}")
                    else:
                        print(f"🤖 TVB: ✅ System webhook: {action} | Balance: {balance} AVAX | {pnl_str}")
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
    
    def get_session_summary(self):
        """Get comprehensive session summary"""
        metrics = self._calculate_session_metrics()
        
        return {
            "sessionStartTime": self.session_start_time,
            "sessionDurationMinutes": self._get_session_duration_minutes(),
            "startingBalance": metrics["startingBalance"],
            "currentBalance": metrics["currentBalance"],
            "pnlAmount": metrics["pnlAmount"],
            "pnlPercentage": metrics["pnlPercentage"],
            "webhookStats": self.get_stats()
        }
    
    def print_session_summary(self):
        """Print session financial summary"""
        summary = self.get_session_summary()
        
        print(f"\n🤖 TVB: 📊 Session Financial Summary:")
        print(f"  💰 Starting Balance: {summary['startingBalance']:.6f} AVAX")
        print(f"  💰 Current Balance: {summary['currentBalance']:.6f} AVAX")
        print(f"  📈 P&L Amount: {summary['pnlAmount']:+.6f} AVAX")
        print(f"  📈 P&L Percentage: {summary['pnlPercentage']:+.2f}%")
        print(f"  ⏰ Session Duration: {summary['sessionDurationMinutes']} minutes")
    
    # ... rest of the methods remain the same (test_webhook, get_stats, print_stats, etc.)
    
    def test_webhook(self):
        """Test webhook connectivity"""
        if not self.enabled:
            print("🤖 TVB: ❌ Webhook not configured - cannot test")
            return False
        
        print("🤖 TVB: 🧪 Testing webhook connectivity...")
        
        test_payload = {
            "botName": self.bot_name,
            "displayName": self.display_name,
            "avatarUrl": self.avatar_url,
            "action": "test",
            "details": {
                "message": "Webhook connectivity test",
                "test": True
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "botSecret": self.bot_secret
        }
        
        success = self._send_webhook(test_payload)
        
        if success:
            print("🤖 TVB: ✅ Webhook test successful!")
        else:
            print("🤖 TVB: ❌ Webhook test failed!")
        
        return success
    
    def get_stats(self):
        """Get webhook performance statistics"""
        stats = self.webhook_stats.copy()
        
        if stats["total_sent"] > 0:
            stats["success_rate"] = (stats["successful"] / stats["total_sent"]) * 100
        else:
            stats["success_rate"] = 0
        
        stats["enabled"] = self.enabled
        stats["webhook_url"] = self.webhook_url if self.enabled else None
        
        return stats
    
    def print_stats(self):
        """Print webhook statistics in a readable format"""
        stats = self.get_stats()
        
        print("\n🤖 TVB: 📊 Webhook Statistics:")
        print(f"  📡 Enabled: {'Yes' if stats['enabled'] else 'No'}")
        
        if stats["enabled"]:
            print(f"  🎯 Target: {stats['webhook_url']}")
            print(f"  📤 Total sent: {stats['total_sent']}")
            print(f"  ✅ Successful: {stats['successful']}")
            print(f"  ❌ Failed: {stats['failed']}")
            print(f"  📈 Success rate: {stats['success_rate']:.1f}%")
            
            if stats.get("last_sent"):
                print(f"  ⏰ Last sent: {stats['last_sent']}")
            
            if stats.get("last_error"):
                error = stats["last_error"]
                print(f"  🚨 Last error: {error['error']} (Action: {error['action']})")
    
    def update_phrases(self, new_phrases):
        """Update personality phrases dynamically"""
        self.phrases.update(new_phrases)
        print(f"🤖 TVB: 💬 Updated personality phrases")
    
    def add_phrase(self, action_type, phrase):
        """Add a new phrase to a specific action type"""
        if action_type not in self.phrases:
            self.phrases[action_type] = []
        
        self.phrases[action_type].append(phrase)
        print(f"🤖 TVB: ➕ Added phrase to {action_type}: '{phrase}'")
    
    def get_random_phrase(self, action_type):
        """Get a random phrase for an action type"""
        phrases = self.phrases.get(action_type, [])
        if phrases:
            return random.choice(phrases)
        return None
    
    def is_healthy(self):
        """Check if webhook system is healthy"""
        if not self.enabled:
            return False
        
        stats = self.get_stats()
        
        # Consider healthy if:
        # - No sends yet (fresh start)
        # - Or success rate is above 80%
        if stats["total_sent"] == 0:
            return True
        
        return stats["success_rate"] >= 80.0
    
    def reset_stats(self):
        """Reset webhook statistics"""
        self.webhook_stats = {
            "total_sent": 0,
            "successful": 0,
            "failed": 0,
            "last_sent": None,
            "last_error": None
        }
        print("🤖 TVB: 🔄 Webhook statistics reset")