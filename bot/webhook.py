# bot/webhook.py - OPTIMIZED webhook manager with smart heartbeat and reduced requests
#!/usr/bin/env python3
"""
OPTIMIZED Webhook Manager with intelligent heartbeat scheduling and request reduction
Dramatically reduces API calls while maintaining reliable connection status
"""

import json
import random
import requests
import time
import threading
from datetime import datetime, timedelta
from requests.exceptions import RequestException, Timeout, ConnectionError

class OptimizedWebhookManager:
    """OPTIMIZED webhook manager with smart heartbeat scheduling and request batching"""
    
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
        
        # Session balance tracking
        self.starting_balance = None
        self.session_start_time = None
        
        # OPTIMIZATION: Smart heartbeat scheduling
        self.last_heartbeat_sent = 0
        self.heartbeat_interval = 120  # 2 minutes base interval
        self.adaptive_heartbeat_interval = 120  # Starts at 2 minutes, can adapt
        self.max_heartbeat_interval = 300  # Maximum 5 minutes
        self.min_heartbeat_interval = 60   # Minimum 1 minute
        self.consecutive_heartbeat_failures = 0
        self.last_significant_activity = time.time()
        
        # OPTIMIZATION: Request batching and queuing
        self.pending_updates = []
        self.batch_timer = None
        self.batch_timeout = 5  # Send batch after 5 seconds of inactivity
        self.max_batch_size = 5  # Or when 5 updates accumulate
        self.batch_lock = threading.Lock()
        
        # OPTIMIZATION: Webhook failure handling
        self.webhook_stats = {
            "total_sent": 0,
            "successful": 0,
            "failed": 0,
            "last_sent": None,
            "last_error": None,
            "consecutive_failures": 0,
            "heartbeats_sent": 0,
            "heartbeats_successful": 0,
            "requests_saved": 0,  # Track how many requests we've saved through optimization
        }
        
        self.max_consecutive_failures = 3  # Reduced from 5
        self.failure_backoff_time = 30  # Reduced from 60
        self.last_failure_time = 0
        
        # OPTIMIZATION: Activity classification
        self.priority_actions = {'buy', 'sell', 'create_token', 'error', 'startup', 'shutdown', 'insufficient_funds'}
        self.system_actions = {'heartbeat', 'hold', 'balance_alert', 'token_refresh', 'cycle_complete'}
        self.personality_actions = {'buy', 'sell', 'create_token', 'hold', 'error'}
        
        self.enabled = bool(webhook_url and self.bot_secret)
        
        # Start heartbeat scheduler
        self._start_heartbeat_scheduler()
        
        if self.enabled:
            print(f"🤖 TVB: 📡 OPTIMIZED Webhook manager initialized for {display_name}")
            print(f"🤖 TVB: 🎯 Target: {webhook_url}")
            print(f"🤖 TVB: 💓 Smart heartbeat: {self.heartbeat_interval}s (adaptive)")
            print(f"🤖 TVB: 📦 Request batching enabled (max {self.max_batch_size} items, {self.batch_timeout}s timeout)")
            print(f"🤖 TVB: 💼 Wallet: {wallet_address or 'Not provided'}")
        else:
            print(f"🤖 TVB: ⚠️ Webhook disabled - missing URL or secret")
    
    def _start_heartbeat_scheduler(self):
        """Start the background heartbeat scheduler thread"""
        if not self.enabled:
            return
            
        def heartbeat_worker():
            while True:
                try:
                    time.sleep(10)  # Check every 10 seconds
                    
                    current_time = time.time()
                    time_since_last_heartbeat = current_time - self.last_heartbeat_sent
                    
                    # OPTIMIZATION: Adaptive heartbeat interval based on activity
                    time_since_activity = current_time - self.last_significant_activity
                    
                    if time_since_activity < 300:  # Active in last 5 minutes
                        self.adaptive_heartbeat_interval = self.min_heartbeat_interval
                    elif time_since_activity < 900:  # Active in last 15 minutes
                        self.adaptive_heartbeat_interval = self.heartbeat_interval
                    else:  # Inactive for a while
                        self.adaptive_heartbeat_interval = self.max_heartbeat_interval
                    
                    # Send heartbeat if interval has passed
                    if time_since_last_heartbeat >= self.adaptive_heartbeat_interval:
                        self._send_scheduled_heartbeat()
                        
                except Exception as e:
                    print(f"🤖 TVB: ❌ Heartbeat scheduler error: {e}")
                    time.sleep(30)  # Wait before retrying
        
        heartbeat_thread = threading.Thread(target=heartbeat_worker, daemon=True)
        heartbeat_thread.start()
        print(f"🤖 TVB: 💓 Heartbeat scheduler started for {self.display_name}")
    
    def _send_scheduled_heartbeat(self):
        """Send an automatic heartbeat"""
        try:
            # Don't send heartbeat if we have recent failures
            if self._should_skip_webhook():
                self.webhook_stats["requests_saved"] += 1
                return
            
            current_balance = self._get_current_balance()
            session_metrics = self._calculate_session_metrics()
            
            details = {
                "message": f"{self.display_name} heartbeat",
                "status": "active",
                "automaticHeartbeat": True,
                "intervalUsed": self.adaptive_heartbeat_interval,
                "timeSinceActivity": time.time() - self.last_significant_activity,
            }
            
            # Add session metrics
            details.update(session_metrics)
            
            # Add wallet address
            if self.wallet_address:
                details["walletAddress"] = self.wallet_address
            
            success = self._send_webhook_direct("heartbeat", details)
            
            if success:
                self.last_heartbeat_sent = time.time()
                self.consecutive_heartbeat_failures = 0
                self.webhook_stats["heartbeats_successful"] += 1
                
                # OPTIMIZATION: Extend heartbeat interval on success if no recent activity
                if time.time() - self.last_significant_activity > 600:  # 10 minutes
                    self.adaptive_heartbeat_interval = min(
                        self.adaptive_heartbeat_interval * 1.2,
                        self.max_heartbeat_interval
                    )
            else:
                self.consecutive_heartbeat_failures += 1
                # OPTIMIZATION: Reduce heartbeat interval on failure to try to reconnect
                self.adaptive_heartbeat_interval = max(
                    self.adaptive_heartbeat_interval * 0.8,
                    self.min_heartbeat_interval
                )
            
            self.webhook_stats["heartbeats_sent"] += 1
            
        except Exception as e:
            print(f"🤖 TVB: ❌ Scheduled heartbeat error: {e}")
    
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
            
            # Add session timing
            session_duration_minutes = 0
            if self.session_start_time:
                try:
                    start_time = datetime.fromisoformat(self.session_start_time.replace('Z', ''))
                    duration = datetime.utcnow() - start_time
                    session_duration_minutes = int(duration.total_seconds() / 60)
                except:
                    pass
            
            return {
                "currentBalance": round(current_balance, 6),
                "startingBalance": round(self.starting_balance, 6),
                "pnlAmount": round(pnl_amount, 6),
                "pnlPercentage": round(pnl_percentage, 2),
                "sessionDurationMinutes": session_duration_minutes,
            }
        except Exception as e:
            print(f"🤖 TVB: ⚠️ Error calculating session metrics: {e}")
            return {
                "currentBalance": 0,
                "startingBalance": 0,
                "pnlAmount": 0,
                "pnlPercentage": 0,
                "sessionDurationMinutes": 0,
            }
    
    def set_session_start(self, starting_balance, start_time=None):
        """Set the session starting balance and time"""
        self.starting_balance = starting_balance
        self.session_start_time = start_time or datetime.utcnow().isoformat() + "Z"
        print(f"🤖 TVB: 💰 Session started with {starting_balance:.6f} AVAX")
    
    def set_wallet_address(self, wallet_address):
        """Set or update the bot's wallet address"""
        self.wallet_address = wallet_address
        print(f"🤖 TVB: 💼 Wallet address set: {wallet_address}")
    
    def _should_skip_webhook(self):
        """Check if we should skip webhook due to consecutive failures"""
        if self.webhook_stats["consecutive_failures"] >= self.max_consecutive_failures:
            time_since_failure = time.time() - self.last_failure_time
            if time_since_failure < self.failure_backoff_time:
                return True
            else:
                # Reset after backoff period
                self.webhook_stats["consecutive_failures"] = 0
        return False
    
    def _queue_update(self, action_type, details):
        """OPTIMIZATION: Queue update for batch processing"""
        with self.batch_lock:
            update = {
                "action": action_type,
                "details": details,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "priority": self._get_action_priority(action_type)
            }
            
            self.pending_updates.append(update)
            
            # Mark significant activity for heartbeat scheduling
            if action_type in self.priority_actions:
                self.last_significant_activity = time.time()
            
            # OPTIMIZATION: Send immediately for high priority actions
            if action_type in {'startup', 'shutdown', 'error', 'insufficient_funds'}:
                self._flush_batch()
            # OPTIMIZATION: Send batch when it reaches max size
            elif len(self.pending_updates) >= self.max_batch_size:
                self._flush_batch()
            # OPTIMIZATION: Set timer for batch timeout
            elif self.batch_timer is None:
                self._set_batch_timer()
    
    def _get_action_priority(self, action_type):
        """Get priority score for action (higher = more important)"""
        priority_map = {
            'error': 10,
            'insufficient_funds': 10,
            'startup': 9,
            'shutdown': 9,
            'buy': 8,
            'sell': 8,
            'create_token': 7,
            'hold': 5,
            'balance_alert': 4,
            'heartbeat': 2,
        }
        return priority_map.get(action_type, 3)
    
    def _set_batch_timer(self):
        """Set timer to flush batch after timeout"""
        def flush_timer():
            time.sleep(self.batch_timeout)
            with self.batch_lock:
                if self.batch_timer is not None:
                    self.batch_timer = None
                    self._flush_batch()
        
        self.batch_timer = threading.Thread(target=flush_timer, daemon=True)
        self.batch_timer.start()
    
    def _flush_batch(self):
        """Flush all pending updates"""
        if not self.pending_updates:
            return
        
        # Sort by priority (highest first)
        self.pending_updates.sort(key=lambda x: x["priority"], reverse=True)
        
        # OPTIMIZATION: For multiple updates, send most important one
        # and summarize the rest in details
        primary_update = self.pending_updates[0]
        other_updates = self.pending_updates[1:]
        
        # Add summary of other updates
        if other_updates:
            primary_update["details"]["batchedUpdates"] = len(other_updates)
            primary_update["details"]["otherActions"] = [u["action"] for u in other_updates[:3]]
            if len(other_updates) > 3:
                primary_update["details"]["additionalActions"] = len(other_updates) - 3
            
            # Save requests by batching
            self.webhook_stats["requests_saved"] += len(other_updates)
        
        # Send the primary update
        self._send_webhook_direct(primary_update["action"], primary_update["details"])
        
        # Clear pending updates
        self.pending_updates.clear()
        
        # Clear batch timer
        if self.batch_timer is not None:
            self.batch_timer = None
    
    def send_update(self, action_type, details):
        """OPTIMIZED send update with intelligent batching"""
        if not self.enabled:
            return False
        
        # Skip if we're in failure backoff (except for critical actions)
        if self._should_skip_webhook() and action_type not in {'startup', 'shutdown', 'error'}:
            self.webhook_stats["requests_saved"] += 1
            return False
        
        try:
            # Ensure details is a dictionary
            if details is None:
                details = {}
            elif not isinstance(details, dict):
                details = {"message": str(details)}
            
            # Add personality phrases for personality actions
            if action_type in self.personality_actions and 'message' not in details:
                phrase_list = self.phrases.get(action_type, [])
                if phrase_list:
                    details['message'] = random.choice(phrase_list)
                else:
                    fallback_messages = {
                        'hold': f"Staying put with this position for now.",
                        'buy': "Making a purchase!",
                        'sell': "Time to take some profits!",
                        'create_token': "Creating something new!",
                        'error': "Encountered a minor hiccup."
                    }
                    details['message'] = fallback_messages.get(action_type, f"Performed {action_type}")
            
            # Add session financial metrics to all updates
            session_metrics = self._calculate_session_metrics()
            details.update(session_metrics)
            
            # Add session timing
            if self.session_start_time:
                details['sessionStartTime'] = self.session_start_time
            
            # Always include wallet address
            if self.wallet_address:
                details['walletAddress'] = self.wallet_address
                details['address'] = self.wallet_address
            
            # OPTIMIZATION: Queue for batch processing (except critical actions)
            if action_type in {'startup', 'shutdown', 'error', 'insufficient_funds'}:
                return self._send_webhook_direct(action_type, details)
            else:
                self._queue_update(action_type, details)
                return True
                
        except Exception as e:
            print(f"🤖 TVB: ❌ Webhook error: {e}")
            self._update_stats(False, action_type, str(e))
            return False
    
    def _send_webhook_direct(self, action_type, details):
        """Send webhook directly without batching"""
        try:
            # Build payload
            payload = {
                "botName": self.bot_name,
                "displayName": self.display_name,
                "avatarUrl": self.avatar_url,
                "bio": self.bio,
                "walletAddress": self.wallet_address,
                "action": action_type,
                "details": details,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "botSecret": self.bot_secret
            }
            
            # Include bio in startup
            if action_type == 'startup' and self.bio:
                payload["details"]["bio"] = self.bio
            
            # Send webhook
            success = self._send_webhook_request(payload)
            
            # Update statistics
            self._update_stats(success, action_type)
            
            return success
            
        except Exception as e:
            print(f"🤖 TVB: ❌ Direct webhook error: {e}")
            self._update_stats(False, action_type, str(e))
            return False
    
    def _send_webhook_request(self, payload):
        """Send the actual HTTP request with enhanced logging and error handling"""
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=15,  # Increased timeout for batch requests
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                action = payload['action']
                balance = payload['details'].get('currentBalance', 'unknown')
                pnl = payload['details'].get('pnlAmount', 0)
                token = payload['details'].get('tokenSymbol', '')
                wallet = payload.get('walletAddress', 'No wallet')
                batched = payload['details'].get('batchedUpdates', 0)
                
                # OPTIMIZED: Less verbose logging for heartbeats
                if action == 'heartbeat':
                    if payload['details'].get('automaticHeartbeat'):
                        # Only log automatic heartbeats occasionally
                        if self.webhook_stats["heartbeats_sent"] % 10 == 0:
                            print(f"🤖 TVB: 💓 {self.display_name} heartbeat #{self.webhook_stats['heartbeats_sent']} | Balance: {balance}")
                    else:
                        print(f"🤖 TVB: 💓 {self.display_name} manual heartbeat | Balance: {balance}")
                else:
                    # Enhanced logging with batch info
                    pnl_str = f"P&L: {pnl:+.6f}" if isinstance(pnl, (int, float)) else ""
                    wallet_str = f"Wallet: {wallet[:10]}..." if wallet and wallet != 'No wallet' else ""
                    batch_str = f" [+{batched} batched]" if batched > 0 else ""
                    
                    if token:
                        print(f"🤖 TVB: ✅ {action} {token}{batch_str} | Balance: {balance} | {pnl_str} | {wallet_str}")
                    else:
                        print(f"🤖 TVB: ✅ {action}{batch_str} | Balance: {balance} | {pnl_str} | {wallet_str}")
                
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
            self.webhook_stats["consecutive_failures"] = 0
        else:
            self.webhook_stats["failed"] += 1
            self.webhook_stats["consecutive_failures"] += 1
            self.last_failure_time = time.time()
            
            if error_msg:
                self.webhook_stats["last_error"] = {
                    "action": action_type,
                    "error": error_msg,
                    "timestamp": self.webhook_stats["last_sent"]
                }
    
    # Convenience methods with optimized implementations
    def send_startup_notification(self, startup_info):
        """Send startup notification with session metrics"""
        try:
            current_balance = self._get_current_balance()
            if current_balance is not None:
                self.set_session_start(current_balance)
                startup_info['initialBalance'] = round(current_balance, 6)
            
            if self.bio and 'bio' not in startup_info:
                startup_info['bio'] = self.bio
            
            if self.wallet_address:
                startup_info['walletAddress'] = self.wallet_address
            
            return self.send_update("startup", startup_info)
        except Exception as e:
            print(f"🤖 TVB: ❌ Error sending startup notification: {e}")
            return False
    
    def send_buy_update(self, token_info, amount_avax, tx_hash, post_trade_balance=None):
        """Send buy transaction update"""
        return self.send_update("buy", {
            "tokenAddress": token_info["address"],
            "tokenSymbol": token_info["symbol"],
            "tokenName": token_info["name"],
            "amountAvax": round(amount_avax, 6),
            "txHash": tx_hash,
            "tradeType": "BUY"
        })
    
    def send_sell_update(self, token_info, token_amount, readable_amount, sell_percentage, tx_hash, post_trade_balance=None):
        """Send sell transaction update"""
        return self.send_update("sell", {
            "tokenAddress": token_info["address"],
            "tokenSymbol": token_info["symbol"],
            "tokenName": token_info["name"],
            "tokenAmount": str(token_amount),
            "readableAmount": round(readable_amount, 6),
            "sellPercentage": round(sell_percentage * 100, 1),
            "txHash": tx_hash,
            "tradeType": "SELL"
        })
    
    def send_heartbeat(self, balance_info=None, token_count=0, extra_data=None):
        """Send manual heartbeat (automatic heartbeats are handled by scheduler)"""
        try:
            details = {
                "message": f"{self.display_name} manual heartbeat",
                "tokensTracked": token_count,
                "status": "active",
                "automaticHeartbeat": False,
            }
            
            if extra_data:
                details.update(extra_data)
            
            return self.send_update("heartbeat", details)
        except Exception as e:
            print(f"🤖 TVB: ❌ Error sending heartbeat: {e}")
            return False
    
    def send_error_update(self, error_message, error_type="general_error"):
        """Send error notification"""
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
        """Send shutdown notification"""
        try:
            # Flush any pending updates before shutdown
            with self.batch_lock:
                self._flush_batch()
            
            return self.send_update("shutdown", shutdown_info)
        except Exception as e:
            print(f"🤖 TVB: ❌ Error sending shutdown notification: {e}")
            return False
    
    def get_session_summary(self):
        """Get comprehensive session summary with optimization stats"""
        try:
            metrics = self._calculate_session_metrics()
            stats = self.get_stats()
            
            return {
                "sessionStartTime": self.session_start_time,
                "sessionDurationMinutes": metrics.get("sessionDurationMinutes", 0),
                "startingBalance": metrics["startingBalance"],
                "currentBalance": metrics["currentBalance"],
                "pnlAmount": metrics["pnlAmount"],
                "pnlPercentage": metrics["pnlPercentage"],
                "walletAddress": self.wallet_address,
                "webhookStats": stats,
                "optimizationStats": {
                    "requestsSaved": stats["requests_saved"],
                    "heartbeatSuccessRate": (stats["heartbeats_successful"] / max(stats["heartbeats_sent"], 1)) * 100,
                    "adaptiveHeartbeatInterval": self.adaptive_heartbeat_interval,
                    "batchingEnabled": True,
                }
            }
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting session summary: {e}")
            return {}
    
    def print_session_summary(self):
        """Print session summary with optimization stats"""
        try:
            summary = self.get_session_summary()
            optimization = summary.get("optimizationStats", {})
            
            print(f"\n🤖 TVB: 📊 OPTIMIZED Session Summary:")
            print(f"  💼 Wallet: {summary.get('walletAddress', 'Not configured')}")
            print(f"  💰 Starting: {summary.get('startingBalance', 0):.6f} AVAX")
            print(f"  💰 Current: {summary.get('currentBalance', 0):.6f} AVAX")
            print(f"  📈 P&L: {summary.get('pnlAmount', 0):+.6f} AVAX ({summary.get('pnlPercentage', 0):+.2f}%)")
            print(f"  ⏰ Duration: {summary.get('sessionDurationMinutes', 0)} minutes")
            
            # Optimization stats
            print(f"\n🤖 TVB: 🚀 Optimization Performance:")
            print(f"  💾 Requests saved: {optimization.get('requestsSaved', 0)}")
            print(f"  💓 Heartbeat success: {optimization.get('heartbeatSuccessRate', 0):.1f}%")
            print(f"  ⚡ Current heartbeat interval: {optimization.get('adaptiveHeartbeatInterval', 0):.0f}s")
            print(f"  📦 Request batching: {'Enabled' if optimization.get('batchingEnabled') else 'Disabled'}")
            
        except Exception as e:
            print(f"🤖 TVB: ❌ Error printing session summary: {e}")
    
    def get_stats(self):
        """Get webhook performance statistics with optimization metrics"""
        try:
            stats = self.webhook_stats.copy()
            
            if stats["total_sent"] > 0:
                stats["success_rate"] = (stats["successful"] / stats["total_sent"]) * 100
            else:
                stats["success_rate"] = 0
            
            stats["enabled"] = self.enabled
            stats["webhook_url"] = self.webhook_url if self.enabled else None
            stats["wallet_address"] = self.wallet_address
            stats["adaptive_heartbeat_interval"] = self.adaptive_heartbeat_interval
            stats["pending_batch_size"] = len(self.pending_updates)
            
            return stats
        except Exception as e:
            print(f"🤖 TVB: ❌ Error getting webhook stats: {e}")
            return {}


# Backward compatibility alias
WebhookManager = OptimizedWebhookManager