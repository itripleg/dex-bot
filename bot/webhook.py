# bot/webhook.py - Fixed webhook manager with proper error handling and wallet address
#!/usr/bin/env python3
"""
Enhanced Webhook Manager with session balance tracking, P&L calculations, and wallet address
Fixed to prevent webhook failures from crashing bots
"""

import json
import random
import requests
from datetime import datetime
from requests.exceptions import RequestException, Timeout, ConnectionError

class WebhookManager:
    """Manages webhook communications with session balance tracking, P&L calculations, and wallet address"""
    
    def __init__(self, bot_name, display_name, avatar_url, webhook_url, bot_secret, phrases, bio=None, get_balance_callback=None, wallet_address=None):
        self.bot_name = bot_name
        self.display_name = display_name
        self.avatar_url = avatar_url
        self.webhook_url = webhook_url
        self.bot_secret = bot_secret or "dev"  # Fallback to "dev" if None
        self.phrases = phrases
        self.bio = bio
        self.get_balance_callback = get_balance_callback  # Callback to get current AVAX balance
        self.wallet_address = wallet_address  # Store the bot's wallet address
        
        # Session balance tracking
        self.starting_balance = None
        self.session_start_time = None
        
        # Define which actions should get personality phrases vs system messages
        self.personality_actions = {'buy', 'sell', 'create_token', 'error', 'hold'}
        self.system_actions = {
            'cycle_start', 'cycle_complete', 'token_refresh', 'heartbeat', 'startup', 
            'shutdown', 'buy_attempt', 'sell_attempt', 'trade_failure', 'insufficient_funds',
            'forced_sell', 'balance_alert', 'token_refresh_start', 'token_refresh_complete',
            'creation_cancelled', 'no_tokens', 'buy_success', 'sell_success', 'buy_failed', 'sell_failed'
        }
        
        # Track webhook statistics
        self.webhook_stats = {
            "total_sent": 0,
            "successful": 0,
            "failed": 0,
            "last_sent": None,
            "last_error": None,
            "consecutive_failures": 0
        }
        
        # Webhook failure handling
        self.max_consecutive_failures = 5
        self.failure_backoff_time = 60  # seconds
        self.last_failure_time = 0
        
        self.enabled = bool(webhook_url and self.bot_secret)
        
        if self.enabled:
            print(f"🤖 TVB: 📡 Webhook manager initialized for {display_name}")
            print(f"🤖 TVB: 🎯 Target: {webhook_url}")
            print(f"🤖 TVB: 💼 Wallet: {wallet_address or 'Not provided'}")
            if self.bot_secret == "dev":
                print("🤖 TVB: 🔐 Using default webhook secret: 'dev' (development mode)")
            else:
                print("🤖 TVB: 🔐 Using configured webhook secret")
            if bio:
                print(f"🤖 TVB: 📝 Bio: {bio[:50]}..." if len(bio) > 50 else f"🤖 TVB: 📝 Bio: {bio}")
        else:
            print(f"🤖 TVB: ⚠️ Webhook disabled - missing URL or secret")
    
    def set_wallet_address(self, wallet_address):
        """Set or update the bot's wallet address"""
        self.wallet_address = wallet_address
        print(f"🤖 TVB: 💼 Wallet address set: {wallet_address}")
    
    def _get_current_balance(self):
        """Get current AVAX balance via callback with error handling"""
        if self.get_balance_callback:
            try:
                return self.get_balance_callback()
            except Exception as e:
                print(f"🤖 TVB: ⚠️ Error getting balance: {e}")
                return None
        return None
    
    def _calculate_session_metrics(self):
        """Calculate session financial metrics with error handling"""
        try:
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
        except Exception as e:
            print(f"🤖 TVB: ⚠️ Error calculating session metrics: {e}")
            return {
                "currentBalance": 0,
                "startingBalance": 0,
                "pnlAmount": 0,
                "pnlPercentage": 0
            }
    
    def set_session_start(self, starting_balance, start_time=None):
        """Set the session starting balance and time"""
        self.starting_balance = starting_balance
        self.session_start_time = start_time or datetime.utcnow().isoformat() + "Z"
        print(f"🤖 TVB: 💰 Session started with {starting_balance:.6f} AVAX")
    
    def _should_skip_webhook(self):
        """Check if we should skip webhook due to consecutive failures"""
        if self.webhook_stats["consecutive_failures"] >= self.max_consecutive_failures:
            time_since_failure = datetime.utcnow().timestamp() - self.last_failure_time
            if time_since_failure < self.failure_backoff_time:
                return True
            else:
                # Reset after backoff period
                self.webhook_stats["consecutive_failures"] = 0
        return False
    
    def send_update(self, action_type, details):
        """Send webhook update with session financial metrics and wallet address"""
        if not self.enabled:
            return False
        
        # Skip if we're in failure backoff
        if self._should_skip_webhook():
            return False
        
        try:
            # Ensure details is a dictionary
            if details is None:
                details = {}
            elif not isinstance(details, dict):
                details = {"message": str(details)}
            
            # Only add personality phrases for actual trading actions, not system messages
            if action_type in self.personality_actions and 'message' not in details:
                phrase_list = self.phrases.get(action_type, [])
                if phrase_list:
                    details['message'] = random.choice(phrase_list)
                else:
                    # Fallback messages for actions without configured phrases
                    fallback_messages = {
                        'hold': f"Staying put with this position for now.",
                        'buy': "Making a purchase!",
                        'sell': "Time to take some profits!",
                        'create_token': "Creating something new!",
                        'error': "Encountered a minor hiccup."
                    }
                    details['message'] = fallback_messages.get(action_type, f"Personality action: {action_type}")
            
            # For system actions, keep the provided message or use a default
            elif action_type in self.system_actions and 'message' not in details:
                system_messages = {
                    'insufficient_funds': "Insufficient AVAX for trading operations",
                    'forced_sell': "Forced to sell due to low AVAX balance",
                    'balance_alert': "Balance threshold reached",
                    'heartbeat': f"{self.display_name} is active and monitoring markets",
                    'startup': f"{self.display_name} is initializing trading systems",
                    'shutdown': f"{self.display_name} is going offline"
                }
                details['message'] = system_messages.get(action_type, f"System: {action_type.replace('_', ' ').title()}")
            
            # Add session financial metrics to all updates
            session_metrics = self._calculate_session_metrics()
            details.update(session_metrics)
            
            # Add session timing
            if self.session_start_time:
                details['sessionStartTime'] = self.session_start_time
                details['sessionDurationMinutes'] = self._get_session_duration_minutes()
            
            # ALWAYS INCLUDE WALLET ADDRESS IN DETAILS
            if self.wallet_address:
                details['walletAddress'] = self.wallet_address
                details['address'] = self.wallet_address  # Alternative field name for compatibility
            
            # Build payload with bio, balance, and wallet address included
            payload = {
                "botName": self.bot_name,
                "displayName": self.display_name,
                "avatarUrl": self.avatar_url,
                "bio": self.bio,
                "walletAddress": self.wallet_address,  # Include at top level too
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
    
    def send_startup_notification(self, startup_info):
        """Send startup notification and set session metrics with wallet address"""
        try:
            # Set session start metrics
            current_balance = self._get_current_balance()
            if current_balance is not None:
                self.set_session_start(current_balance)
                startup_info['initialBalance'] = round(current_balance, 6)
            
            # Ensure bio is included in startup info
            if self.bio and 'bio' not in startup_info:
                startup_info['bio'] = self.bio
            
            # Log wallet address at startup
            if self.wallet_address:
                print(f"🤖 TVB: 💼 {self.display_name} Wallet: {self.wallet_address}")
                startup_info['walletAddress'] = self.wallet_address
            else:
                print(f"🤖 TVB: ⚠️ {self.display_name} has no wallet address configured!")
            
            return self.send_update("startup", startup_info)
        except Exception as e:
            print(f"🤖 TVB: ❌ Error sending startup notification: {e}")
            return False
    
    def send_trade_update(self, action, token_info, trade_details, post_trade_balance=None):
        """Send specialized trading update with financial impact and wallet address"""
        try:
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
        except Exception as e:
            print(f"🤖 TVB: ❌ Error sending trade update: {e}")
            return False
    
    def send_buy_update(self, token_info, amount_avax, tx_hash, post_trade_balance=None):
        """Send buy transaction update with financial metrics and wallet address"""
        return self.send_trade_update("buy", token_info, {
            "amountAvax": round(amount_avax, 6),
            "txHash": tx_hash,
            "tradeType": "BUY"
        }, post_trade_balance)
    
    def send_sell_update(self, token_info, token_amount, readable_amount, sell_percentage, tx_hash, post_trade_balance=None):
        """Send sell transaction update with financial metrics and wallet address"""
        return self.send_trade_update("sell", token_info, {
            "tokenAmount": str(token_amount),
            "readableAmount": round(readable_amount, 6),
            "sellPercentage": round(sell_percentage * 100, 1),
            "txHash": tx_hash,
            "tradeType": "SELL"
        }, post_trade_balance)
    
    def send_heartbeat(self, balance_info, token_count, extra_data=None):
        """Send heartbeat update with comprehensive session metrics and wallet address"""
        try:
            details = {
                "message": f"{self.display_name} is active and trading",
                "tokensTracked": token_count,
                "status": "active"
            }
            
            if extra_data:
                details.update(extra_data)
            
            # Financial metrics are automatically added by send_update()
            return self.send_update("heartbeat", details)
        except Exception as e:
            print(f"🤖 TVB: ❌ Error sending heartbeat: {e}")
            return False
    
    def send_error_update(self, error_message, error_type="general_error"):
        """Send error notification with personality phrase"""
        try:
            return self.send_update("error", {
                "message": f"Encountered an issue: {error_message}",
                "errorType": error_type,
                "errorDetails": error_message
            })
        except Exception as e:
            print(f"🤖 TVB: ❌ Error sending error update: {e}")
            return False

    def send_balance_alert(self, balance, threshold, alert_type="low"):
        """Send balance alert notification"""
        try:
            return self.send_update("balance_alert", {
                "message": f"Balance alert: {balance:.6f} AVAX (threshold: {threshold:.6f})",
                "currentBalance": balance,
                "threshold": threshold,
                "alertType": alert_type
            })
        except Exception as e:
            print(f"🤖 TVB: ❌ Error sending balance alert: {e}")
            return False

    def send_shutdown_notification(self, shutdown_info):
        """Send shutdown notification with session summary"""
        try:
            return self.send_update("shutdown", shutdown_info)
        except Exception as e:
            print(f"🤖 TVB: ❌ Error sending shutdown notification: {e}")
            return False
    
    def _send_webhook(self, payload):
        """Send the actual HTTP request with enhanced logging and error handling"""
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
                wallet = payload.get('walletAddress', 'No wallet')
                
                # Enhanced logging with P&L and wallet
                pnl_str = f"P&L: {pnl:+.6f}" if isinstance(pnl, (int, float)) else ""
                wallet_str = f"Wallet: {wallet[:10]}..." if wallet and wallet != 'No wallet' else "No wallet"
                
                if action in self.personality_actions:
                    if token:
                        print(f"🤖 TVB: ✅ Personality webhook: {action} {token} | Balance: {balance} AVAX | {pnl_str} | {wallet_str}")
                    else:
                        print(f"🤖 TVB: ✅ Personality webhook: {action} | Balance: {balance} AVAX | {pnl_str} | {wallet_str}")
                else:
                    if token:
                        print(f"🤖 TVB: ✅ System webhook: {action} {token} | Balance: {balance} AVAX | {pnl_str} | {wallet_str}")
                    else:
                        print(f"🤖 TVB: ✅ System webhook: {action} | Balance: {balance} AVAX | {pnl_str} | {wallet_str}")
                return True
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                print(f"🤖 TVB: ❌ Webhook failed: {error_msg}")
                return False
                
        except Timeout:
            print(f"🤖 TVB: ⏰ Webhook timeout")
            return False
        except ConnectionError:
            print(f"🤖 TVB: 🔌 Webhook connection error")
            return False
        except RequestException as e:
            print(f"🤖 TVB: 🌐 Webhook request error: {e}")
            return False
        except Exception as e:
            print(f"🤖 TVB: ❌ Unexpected webhook error: {e}")
            return False
    
    def _update_stats(self, success, action_type, error_msg=None):
        """Update webhook statistics"""
        self.webhook_stats["total_sent"] += 1
        self.webhook_stats["last_sent"] = datetime.utcnow().isoformat() + "Z"
        
        if success:
            self.webhook_stats["successful"] += 1
            self.webhook_stats["consecutive_failures"] = 0  # Reset on success
        else:
            self.webhook_stats["failed"] += 1
            self.webhook_stats["consecutive_failures"] += 1
            self.last_failure_time = datetime.utcnow().timestamp()
            
            if error_msg:
                self.webhook_stats["last_error"] = {
                    "action": action_type,
                    "error": error_msg,
                    "timestamp": self.webhook_stats["last_sent"]
                }
    
    def get_session_summary(self):
        """Get comprehensive session summary"""
        try:
            metrics = self._calculate_session_metrics()
            
            return {
                "sessionStartTime": self.session_start_time,
                "sessionDurationMinutes": self._get_session_duration_minutes(),
                "startingBalance": metrics["startingBalance"],
                "currentBalance": metrics["currentBalance"],
                "pnlAmount": metrics["pnlAmount"],
                "pnlPercentage": metrics["pnlPercentage"],
                "walletAddress": self.wallet_address,
                "webhookStats": self.get_stats()
            }
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting session summary: {e}")
            return {
                "sessionStartTime": self.session_start_time,
                "sessionDurationMinutes": 0,
                "startingBalance": 0,
                "currentBalance": 0,
                "pnlAmount": 0,
                "pnlPercentage": 0,
                "walletAddress": self.wallet_address,
                "webhookStats": self.get_stats()
            }
    
    def print_session_summary(self):
        """Print session financial summary with wallet address"""
        try:
            summary = self.get_session_summary()
            
            print(f"\n🤖 TVB: 📊 Session Financial Summary:")
            print(f"  💼 Wallet: {summary['walletAddress'] or 'Not configured'}")
            print(f"  💰 Starting Balance: {summary['startingBalance']:.6f} AVAX")
            print(f"  💰 Current Balance: {summary['currentBalance']:.6f} AVAX")
            print(f"  📈 P&L Amount: {summary['pnlAmount']:+.6f} AVAX")
            print(f"  📈 P&L Percentage: {summary['pnlPercentage']:+.2f}%")
            print(f"  ⏰ Session Duration: {summary['sessionDurationMinutes']} minutes")
            
            # Show webhook health
            stats = summary['webhookStats']
            if stats['total_sent'] > 0:
                print(f"  📡 Webhook Success Rate: {stats['success_rate']:.1f}% ({stats['successful']}/{stats['total_sent']})")
                if stats['consecutive_failures'] > 0:
                    print(f"  ⚠️ Consecutive Webhook Failures: {stats['consecutive_failures']}")
        except Exception as e:
            print(f"🤖 TVB: ❌ Error printing session summary: {e}")
    
    def get_stats(self):
        """Get webhook performance statistics"""
        try:
            stats = self.webhook_stats.copy()
            
            if stats["total_sent"] > 0:
                stats["success_rate"] = (stats["successful"] / stats["total_sent"]) * 100
            else:
                stats["success_rate"] = 0
            
            stats["enabled"] = self.enabled
            stats["webhook_url"] = self.webhook_url if self.enabled else None
            stats["wallet_address"] = self.wallet_address
            
            return stats
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting webhook stats: {e}")
            return {
                "total_sent": 0,
                "successful": 0,
                "failed": 0,
                "success_rate": 0,
                "consecutive_failures": 0,
                "enabled": self.enabled,
                "webhook_url": self.webhook_url if self.enabled else None,
                "wallet_address": self.wallet_address
            }