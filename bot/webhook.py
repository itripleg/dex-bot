#!/usr/bin/env python3
"""
Webhook management for TVB bot communication
Handles all API communication and personality-driven messaging
"""

import json
import random
import requests
from datetime import datetime

class WebhookManager:
    """Manages webhook communications with personality-driven messaging"""
    
    def __init__(self, bot_name, display_name, avatar_url, webhook_url, bot_secret, phrases):
        self.bot_name = bot_name
        self.display_name = display_name
        self.avatar_url = avatar_url
        self.webhook_url = webhook_url
        self.bot_secret = bot_secret
        self.phrases = phrases
        
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
        else:
            print(f"🤖 TVB: ⚠️ Webhook disabled - missing URL or secret")
    
    def send_update(self, action_type, details):
        """Send webhook update with personality-appropriate messaging"""
        if not self.enabled:
            return False
        
        try:
            # Add personality message if not already provided
            if 'message' not in details and action_type in self.phrases:
                phrase_list = self.phrases[action_type]
                if phrase_list:
                    details['message'] = random.choice(phrase_list)
            
            # Build payload
            payload = {
                "botName": self.bot_name,
                "displayName": self.display_name,
                "avatarUrl": self.avatar_url,
                "action": action_type,
                "details": details,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "botSecret": self.bot_secret
            }
            
            # Send webhook
            success = self._send_webhook(payload)
            
            # Update statistics
            self._update_stats(success, action_type)
            
            return success
            
        except Exception as e:
            print(f"🤖 TVB: ❌ Webhook error: {e}")
            self._update_stats(False, action_type, str(e))
            return False
    
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
                print(f"🤖 TVB: ✅ Webhook sent: {payload['action']}")
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
    
    def send_trade_update(self, action, token_info, trade_details):
        """Send specialized trading update with rich details"""
        details = {
            "tokenAddress": token_info["address"],
            "tokenSymbol": token_info["symbol"],
            "tokenName": token_info["name"]
        }
        details.update(trade_details)
        
        return self.send_update(action, details)
    
    def send_buy_update(self, token_info, amount_avax, tx_hash):
        """Send buy transaction update"""
        return self.send_trade_update("buy", token_info, {
            "amountAvax": amount_avax,
            "txHash": tx_hash
        })
    
    def send_sell_update(self, token_info, token_amount, readable_amount, sell_percentage, tx_hash):
        """Send sell transaction update"""
        return self.send_trade_update("sell", token_info, {
            "tokenAmount": token_amount,
            "readableAmount": readable_amount,
            "sellPercentage": sell_percentage,
            "txHash": tx_hash
        })
    
    def send_error_update(self, error_message, context=None):
        """Send error notification with context"""
        details = {"message": error_message}
        if context:
            details["context"] = context
        
        return self.send_update("error", details)
    
    def send_heartbeat(self, balance_info, token_count, extra_data=None):
        """Send heartbeat update with current status"""
        details = {
            "message": f"{self.display_name} is active and trading",
            "currentBalance": balance_info["current"],
            "balanceChange": balance_info["change"],
            "tokensTracked": token_count
        }
        
        if extra_data:
            details.update(extra_data)
        
        return self.send_update("heartbeat", details)
    
    def send_startup_notification(self, startup_info):
        """Send startup notification with initial status"""
        return self.send_update("startup", startup_info)
    
    def send_shutdown_notification(self, shutdown_info):
        """Send shutdown notification"""
        return self.send_update("shutdown", shutdown_info)
    
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


class MockWebhookManager(WebhookManager):
    """Mock webhook manager for testing without actual HTTP calls"""
    
    def __init__(self, bot_name, display_name, avatar_url="", phrases=None):
        # Initialize with mock values
        super().__init__(
            bot_name=bot_name,
            display_name=display_name,
            avatar_url=avatar_url,
            webhook_url="http://mock.webhook.test",
            bot_secret="mock_secret",
            phrases=phrases or {}
        )
        self.sent_webhooks = []
        print(f"🤖 TVB: 🧪 Mock webhook manager initialized for testing")
    
    def _send_webhook(self, payload):
        """Mock webhook sending - just store the payload"""
        self.sent_webhooks.append(payload)
        print(f"🤖 TVB: 🧪 Mock webhook sent: {payload['action']}")
        return True
    
    def get_sent_webhooks(self):
        """Get all webhooks that were 'sent' during testing"""
        return self.sent_webhooks
    
    def clear_sent_webhooks(self):
        """Clear the list of sent webhooks"""
        self.sent_webhooks = []
        print("🤖 TVB: 🧪 Mock webhook history cleared")


# Example usage and testing
if __name__ == "__main__":
    # Test webhook manager functionality
    test_phrases = {
        "buy": ["Test buy phrase!", "Mock purchase!"],
        "sell": ["Test sell phrase!", "Mock sale!"],
        "error": ["Test error!", "Mock problem!"]
    }
    
    # Test mock webhook manager
    mock_webhook = MockWebhookManager(
        bot_name="test_bot",
        display_name="Test Bot",
        phrases=test_phrases
    )
    
    # Send test updates
    mock_webhook.send_update("buy", {"amount": 0.01})
    mock_webhook.send_update("sell", {"amount": 500})
    mock_webhook.send_error_update("Test error message")
    
    # Check results
    sent = mock_webhook.get_sent_webhooks()
    print(f"\n🤖 TVB: 📊 Sent {len(sent)} mock webhooks:")
    for webhook in sent:
        print(f"  - {webhook['action']}: {webhook['details'].get('message', 'No message')}")
    
    mock_webhook.print_stats()
    print("🤖 TVB: ✅ Webhook module test complete!")