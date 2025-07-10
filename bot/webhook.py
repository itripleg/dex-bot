# bot/webhook.py - Fixed webhook manager with clean logging integration
#!/usr/bin/env python3
"""
Enhanced Webhook Manager with session balance tracking, P&L calculations, wallet address,
and CLEAN LOGGING INTEGRATION to eliminate spam
"""

import json
import random
import requests
import time
from datetime import datetime
from typing import Optional, Dict, Any

class WebhookManager:
    """Manages webhook communications with enhanced reliability and CLEAN LOGGING"""
    
    def __init__(self, bot_name, display_name, avatar_url, webhook_url, bot_secret, phrases, bio=None, get_balance_callback=None, wallet_address=None):
        self.bot_name = bot_name
        self.display_name = display_name
        self.avatar_url = avatar_url
        self.webhook_url = webhook_url
        self.bot_secret = bot_secret or "dev"
        self.phrases = phrases
        self.bio = bio
        self.get_balance_callback = get_balance_callback
        self.wallet_address = wallet_address
        
        # Import logger for clean output
        try:
            from bot.logger import BotLogger
            self.clean_logger = BotLogger
        except ImportError:
            self.clean_logger = None
        
        # Session balance tracking
        self.starting_balance = None
        self.session_start_time = None
        
        # Connection reliability settings
        self.max_retries = 3
        self.base_timeout = 10
        self.retry_delays = [1, 2, 5]
        self.connection_failures = 0
        self.max_consecutive_failures = 5
        
        # Last successful communication tracking
        self.last_successful_webhook = None
        self.consecutive_failures = 0
        
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
            "retries_used": 0,
            "last_sent": None,
            "last_successful": None,
            "last_error": None,
            "consecutive_failures": 0,
            "connection_recovered": 0
        }
        
        self.enabled = bool(webhook_url and self.bot_secret)
        
        if self.enabled:
            # Use clean system logging instead of print statements
            if self.clean_logger:
                self.clean_logger.system(f"📡 Webhook manager initialized for {display_name}")
                self.clean_logger.system(f"🎯 Target: {webhook_url}")
                self.clean_logger.system(f"💼 Wallet: {wallet_address or 'Not provided'}")
                self.clean_logger.system(f"🔄 Max retries: {self.max_retries}, Timeouts: {self.base_timeout}s")
                if self.bot_secret == "dev":
                    self.clean_logger.system("🔐 Using dev mode webhook secret")
                if bio:
                    bio_preview = bio[:50] + "..." if len(bio) > 50 else bio
                    self.clean_logger.system(f"📝 Bio: {bio_preview}")
            else:
                # Fallback to old logging
                print(f"🤖 TVB: 📡 Enhanced webhook manager initialized for {display_name}")
        else:
            if self.clean_logger:
                self.clean_logger.system(f"⚠️ Webhook disabled for {display_name} - missing URL or secret", "warning")
    
    def set_wallet_address(self, wallet_address):
        """Set or update the bot's wallet address"""
        self.wallet_address = wallet_address
        if self.clean_logger:
            self.clean_logger.system(f"💼 {self.display_name} wallet address set: {wallet_address}")
    
    def _get_current_balance(self):
        """Get current AVAX balance via callback"""
        if self.get_balance_callback:
            try:
                return self.get_balance_callback()
            except Exception as e:
                if self.clean_logger:
                    self.clean_logger.system(f"⚠️ Error getting balance for {self.display_name}: {e}", "warning")
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
        if self.clean_logger:
            self.clean_logger.system(f"💰 {self.display_name} session started with {starting_balance:.6f} AVAX")
    
    def send_update(self, action_type, details):
        """Send webhook update with CLEAN LOGGING and proper error categorization"""
        if not self.enabled:
            return False
        
        try:
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
            
            # Send webhook with retry logic
            success = self._send_webhook_with_retries(payload)
            
            # Use CLEAN LOGGING with proper error details
            if self.clean_logger:
                self.clean_logger.clean_webhook_log(self.bot_name, action_type, success, details)
            
            # Update statistics
            self._update_stats(success, action_type)
            
            return success
            
        except Exception as e:
            if self.clean_logger:
                self.clean_logger.system(f"❌ {self.display_name} webhook error: {e}", "error")
            self._update_stats(False, action_type, str(e))
            return False
    
    def _send_webhook_with_retries(self, payload) -> bool:
        """Send webhook with retry logic and progressive delays"""
        for attempt in range(self.max_retries + 1):
            try:
                # Calculate timeout (increase with attempts)
                timeout = self.base_timeout + (attempt * 2)
                
                if attempt > 0:
                    delay = self.retry_delays[min(attempt - 1, len(self.retry_delays) - 1)]
                    if self.clean_logger:
                        self.clean_logger.system(f"🔄 {self.display_name} webhook retry {attempt}/{self.max_retries} in {delay}s...")
                    time.sleep(delay)
                    self.webhook_stats["retries_used"] += 1
                
                response = requests.post(
                    self.webhook_url,
                    json=payload,
                    timeout=timeout,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    # Success - reset failure counters
                    if self.consecutive_failures > 0:
                        if self.clean_logger:
                            self.clean_logger.system(f"✅ {self.display_name} connection recovered after {self.consecutive_failures} failures!")
                        self.webhook_stats["connection_recovered"] += 1
                    
                    self.consecutive_failures = 0
                    self.last_successful_webhook = datetime.utcnow()
                    self.webhook_stats["last_successful"] = self.last_successful_webhook.isoformat() + "Z"
                    
                    return True
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text[:100]}"
                    if self.clean_logger and attempt == 0:  # Only log on first attempt to avoid spam
                        self.clean_logger.system(f"❌ {self.display_name} webhook HTTP error: {error_msg}", "error")
                    
                    # Don't retry on client errors (4xx)
                    if 400 <= response.status_code < 500:
                        break
                        
            except requests.exceptions.Timeout:
                if self.clean_logger and attempt == 0:
                    self.clean_logger.system(f"⏰ {self.display_name} webhook timeout ({timeout}s)", "warning")
            except requests.exceptions.ConnectionError:
                if self.clean_logger and attempt == 0:
                    self.clean_logger.system(f"🔌 {self.display_name} webhook connection error", "warning")
            except requests.exceptions.RequestException as e:
                if self.clean_logger and attempt == 0:
                    self.clean_logger.system(f"🌐 {self.display_name} webhook request error: {e}", "error")
            except Exception as e:
                if self.clean_logger and attempt == 0:
                    self.clean_logger.system(f"💥 {self.display_name} unexpected webhook error: {e}", "error")
        
        # All retries failed
        self.consecutive_failures += 1
        self.webhook_stats["consecutive_failures"] = self.consecutive_failures
        
        if self.consecutive_failures >= self.max_consecutive_failures:
            if self.clean_logger:
                self.clean_logger.system(f"🚨 {self.display_name} CRITICAL: {self.consecutive_failures} consecutive webhook failures!", "error")
        
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
            if self.clean_logger:
                self.clean_logger.system(f"💼 {self.display_name} Wallet: {self.wallet_address}")
            startup_info['walletAddress'] = self.wallet_address
        else:
            if self.clean_logger:
                self.clean_logger.system(f"⚠️ {self.display_name} has no wallet address configured!", "warning")
        
        return self.send_update("startup", startup_info)
    
    def send_heartbeat(self, balance_info=None, token_count=0, extra_data=None):
        """Send enhanced heartbeat with connection status info - SILENT unless there are issues"""
        details = {
            "message": f"{self.display_name} is active and monitoring markets",
            "tokensTracked": token_count,
            "status": "active",
            "connectionHealth": {
                "consecutiveFailures": self.consecutive_failures,
                "lastSuccessfulWebhook": self.webhook_stats.get("last_successful"),
                "totalRetries": self.webhook_stats.get("retries_used", 0),
                "connectionRecoveries": self.webhook_stats.get("connection_recovered", 0)
            }
        }
        
        if extra_data:
            details.update(extra_data)
        
        # Send heartbeat but don't spam logs (clean_webhook_log will filter this out)
        success = self.send_update("heartbeat", details)
        
        if not success and self.clean_logger:
            # Only log heartbeat failures
            self.clean_logger.system(f"⚠️ {self.display_name} heartbeat failed - bot may appear offline", "warning")
        
        return success
    
    def send_trade_update(self, action, token_info, trade_details, post_trade_balance=None):
        """Send specialized trading update with financial impact and wallet address"""
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
    
    def send_error_update(self, error_message, error_type="general_error"):
        """Send error notification with personality phrase"""
        return self.send_update("error", {
            "message": f"Encountered an issue: {error_message}",
            "errorType": error_type,
            "errorDetails": error_message
        })
    
    def send_balance_alert(self, balance, threshold, alert_type="low"):
        """Send balance alert notification - SILENT (filtered by clean logging)"""
        return self.send_update("balance_alert", {
            "message": f"Balance alert: {balance:.6f} AVAX (threshold: {threshold:.6f})",
            "currentBalance": balance,
            "threshold": threshold,
            "alertType": alert_type
        })
    
    def send_shutdown_notification(self, shutdown_info):
        """Send shutdown notification with session summary"""
        return self.send_update("shutdown", shutdown_info)
    
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
    
    def get_connection_health(self) -> Dict[str, Any]:
        """Get connection health information"""
        last_success = self.last_successful_webhook
        time_since_success = None
        
        if last_success:
            time_since_success = (datetime.utcnow() - last_success).total_seconds()
        
        return {
            "is_healthy": self.consecutive_failures < 3,
            "consecutive_failures": self.consecutive_failures,
            "time_since_last_success_seconds": time_since_success,
            "total_connection_recoveries": self.webhook_stats.get("connection_recovered", 0),
            "total_retries_used": self.webhook_stats.get("retries_used", 0)
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
            "walletAddress": self.wallet_address,
            "webhookStats": self.get_stats(),
            "connectionHealth": self.get_connection_health()
        }
    
    def print_session_summary(self):
        """Print session financial summary with wallet address and connection health"""
        summary = self.get_session_summary()
        
        if self.clean_logger:
            self.clean_logger.section(f"{self.display_name} Session Summary")
            self.clean_logger.system(f"💼 Wallet: {summary['walletAddress'] or 'Not configured'}")
            self.clean_logger.system(f"💰 Starting: {summary['startingBalance']:.6f} AVAX, Current: {summary['currentBalance']:.6f} AVAX")
            self.clean_logger.system(f"📈 P&L: {summary['pnlAmount']:+.6f} AVAX ({summary['pnlPercentage']:+.2f}%)")
            self.clean_logger.system(f"⏰ Session: {summary['sessionDurationMinutes']} minutes")
            
            # Connection health
            health = summary['connectionHealth']
            health_icon = "✅" if health['is_healthy'] else "❌"
            self.clean_logger.system(f"{health_icon} Connection: {health['consecutive_failures']} failures, {health['total_connection_recoveries']} recoveries")
    
    def get_stats(self):
        """Get webhook performance statistics"""
        stats = self.webhook_stats.copy()
        
        if stats["total_sent"] > 0:
            stats["success_rate"] = (stats["successful"] / stats["total_sent"]) * 100
        else:
            stats["success_rate"] = 0
        
        stats["enabled"] = self.enabled
        stats["webhook_url"] = self.webhook_url if self.enabled else None
        stats["wallet_address"] = self.wallet_address
        stats["connection_health"] = self.get_connection_health()
        
        return stats
    
    def force_heartbeat(self):
        """Force an immediate heartbeat (for error recovery)"""
        if self.clean_logger:
            self.clean_logger.system(f"💓 {self.display_name} forcing heartbeat for connection recovery...")
        return self.send_heartbeat(extra_data={"forced": True, "reason": "connection_recovery"})
    
    def send_keepalive(self):
        """Send a lightweight keepalive message"""
        if not self.enabled:
            return False
            
        # Simple keepalive without full session metrics calculation
        minimal_payload = {
            "botName": self.bot_name,
            "displayName": self.display_name,
            "action": "keepalive",
            "details": {
                "message": f"{self.display_name} keepalive",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "walletAddress": self.wallet_address
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "botSecret": self.bot_secret
        }
        
        # Use single retry for keepalive
        try:
            response = requests.post(
                self.webhook_url,
                json=minimal_payload,
                timeout=5,  # Shorter timeout for keepalive
                headers={"Content-Type": "application/json"}
            )
            return response.status_code == 200
        except:
            return False