#!/usr/bin/env python3
"""
Improved logging system for clear multi-bot identification with clean, organized output
"""

import threading
import sys
from datetime import datetime
from typing import Optional, Dict

class BotLogger:
    """Logger that provides clean, organized output for multi-bot environments"""
    
    # Class-level settings for consistent formatting
    _log_lock = threading.Lock()
    _system_prefix = "🌐 TVB"
    _initialized_bots = []  # Changed to list to track order
    _quiet_mode = False
    
    # Colors as class attribute (not method)
    colors = {
        'red': '\033[91m',
        'green': '\033[92m', 
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'purple': '\033[95m',
        'cyan': '\033[96m',
        'white': '\033[97m',
        'reset': '\033[0m',
        'bold': '\033[1m',
        'dim': '\033[2m'
    }
    
    def __init__(self, bot_name: str, display_name: Optional[str] = None, color_code: Optional[str] = None):
        self.bot_name = bot_name
        self.display_name = display_name or bot_name
        self.thread_id = threading.get_ident()
        
        # Bot-specific emoji mapping
        self.bot_emojis = {
            'bullish_billy': '📈',
            'companion_cube': '🟧',
            'jackpot_jax': '🎯',
            'melancholy_mort': '📉',
            'default': '🤖'
        }
        
        # Color definitions (use class attribute)
        # (removed duplicate - using class-level colors attribute above)
        
        # Auto-assign color based on registration order (fixed index)
        with self._log_lock:
            if bot_name not in self._initialized_bots:
                self._initialized_bots.append(bot_name)
            
            bot_index = self._initialized_bots.index(bot_name)
            color_sequence = ['blue', 'purple', 'cyan', 'yellow', 'green']
            self.color_code = color_sequence[bot_index % len(color_sequence)]
    
    def _get_bot_prefix(self) -> str:
        """Get the bot prefix for log messages"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        emoji = self.bot_emojis.get(self.bot_name, self.bot_emojis['default'])
        color = self.colors.get(self.color_code, '')
        reset = self.colors['reset']
        bold = self.colors['bold']
        
        if color:
            return f"{color}{bold}[{timestamp}] {emoji} {self.display_name}{reset}"
        else:
            return f"[{timestamp}] {emoji} {self.display_name}"
    
    def _log_with_lock(self, message: str, level: str = "info"):
        """Thread-safe logging with proper formatting"""
        if self._quiet_mode and level in ["debug", "verbose"]:
            return
            
        with self._log_lock:
            print(f"{self._get_bot_prefix()}: {message}", flush=True)
    
    def info(self, message: str):
        """Log info message with bot prefix"""
        self._log_with_lock(message, "info")
    
    def success(self, message: str):
        """Log success message"""
        self._log_with_lock(f"✅ {message}", "success")
    
    def warning(self, message: str):
        """Log warning message"""
        self._log_with_lock(f"⚠️  {message}", "warning")
    
    def error(self, message: str):
        """Log error message"""
        self._log_with_lock(f"❌ {message}", "error")
    
    def trade(self, action: str, details: str, token: Optional[str] = None):
        """Log trading action with emphasis and cleaner format"""
        action_emojis = {
            'buy': '🟢 BUY',
            'sell': '🔴 SELL', 
            'create': '🎨 CREATE',
            'hold': '⏸️  HOLD',
            'heartbeat': '💓 HEARTBEAT',
            'error': '⚠️  ERROR'
        }
        
        action_display = action_emojis.get(action.lower(), f"🔄 {action.upper()}")
        
        if token:
            message = f"{action_display} {token}: {details}"
        else:
            message = f"{action_display}: {details}"
            
        self._log_with_lock(message, "trade")
    
    def cycle(self, cycle_num: int, action: Optional[str] = None):
        """Log cycle information (only in verbose mode)"""
        if action:
            self._log_with_lock(f"🔄 Cycle #{cycle_num} - {action}", "debug")
        else:
            self._log_with_lock(f"🔄 Starting Cycle #{cycle_num}", "debug")
    
    def webhook(self, action: str, status: str, details: Optional[str] = None):
        """Log webhook activity in a clean format"""
        status_emojis = {
            'success': '✅',
            'failed': '❌',
            'retry': '🔄',
            'timeout': '⏰'
        }
        
        emoji = status_emojis.get(status, '📡')
        message = f"{emoji} Webhook {action}"
        
        if details:
            message += f" - {details}"
            
        self._log_with_lock(message, "webhook")
    
    def connection(self, status: str, details: Optional[str] = None):
        """Log connection status"""
        status_emojis = {
            'connected': '🔗',
            'disconnected': '🔌',
            'recovering': '🔄',
            'failed': '❌'
        }
        
        emoji = status_emojis.get(status, '📡')
        message = f"{emoji} Connection {status}"
        
        if details:
            message += f": {details}"
            
        self._log_with_lock(message, "connection")
    
    @classmethod
    def system(cls, message: str, level: str = "info"):
        """Log system-level messages (not bot-specific)"""
        if cls._quiet_mode and level in ["debug", "verbose"]:
            return
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        level_emojis = {
            'info': 'ℹ️ ',
            'success': '✅ ',
            'warning': '⚠️  ',
            'error': '❌ ',
            'debug': '🔧 ',
            'startup': '🚀 ',
            'shutdown': '🛑 '
        }
        
        emoji = level_emojis.get(level, '')
        
        with cls._log_lock:
            print(f"{cls._system_prefix}: {emoji}{message}", flush=True)
    
    @classmethod
    def separator(cls, title: Optional[str] = None, char: str = "=", width: int = 60):
        """Print a visual separator"""
        if title:
            title_str = f" {title} "
            padding = (width - len(title_str)) // 2
            separator = char * padding + title_str + char * padding
            if len(separator) < width:
                separator += char
        else:
            separator = char * width
            
        with cls._log_lock:
            print(f"{cls._system_prefix}: {separator}", flush=True)
    
    @classmethod
    def header(cls, title: str):
        """Print a prominent header"""
        cls.separator()
        cls.system(f"🎯 {title}", "startup")
        cls.separator()
    
    @classmethod
    def section(cls, title: str):
        """Print a section header"""
        cls.separator(title, "-", 50)
    
    @classmethod
    def set_quiet_mode(cls, quiet: bool):
        """Enable/disable quiet mode (reduces verbose output)"""
        cls._quiet_mode = quiet
        if quiet:
            cls.system("Quiet mode enabled - reduced output", "debug")
        else:
            cls.system("Verbose mode enabled - full output", "debug")
    
    @classmethod
    def startup_summary(cls, bots: list, stats: dict):
        """Print a clean startup summary"""
        cls.header("Bot Fleet Initialization Complete")
        
        cls.system(f"✅ Initialized {len(bots)} bots in {stats.get('init_time', 0):.1f}s")
        
        if bots:
            cls.system("📋 Active Bots:")
            for bot in bots:
                emoji = cls._get_bot_emoji(bot.get('name', ''))
                status = "🟢 Online" if bot.get('funded', False) else "🟡 Unfunded"
                balance = bot.get('balance', 0)
                cls.system(f"  {emoji} {bot.get('display_name', 'Unknown')} - {status} ({balance:.6f} AVAX)")
        
        if stats.get('optimization_saved', 0) > 0:
            cls.system(f"🚀 Optimization: Saved {stats['optimization_saved']} factory queries ({stats.get('efficiency_gain', 0):.1f}% efficiency gain)")
        
        cls.separator()
    
    @classmethod
    def _get_bot_emoji(cls, bot_name: str) -> str:
        """Get emoji for bot name"""
        emoji_map = {
            'bullish_billy': '📈',
            'companion_cube': '🟧',
            'jackpot_jax': '🎯',
            'melancholy_mort': '📉'
        }
        return emoji_map.get(bot_name, '🤖')
    
    @classmethod
    def optimization_stats(cls, stats: dict):
        """Print optimization statistics in a clean format"""
        cls.section("Shared Token Manager Stats")
        
        cls.system(f"🤖 Registered bots: {stats.get('registered_bots', 0)}")
        cls.system(f"🎯 Total tokens: {stats.get('total_tokens', 0)} ({stats.get('tradeable_tokens', 0)} tradeable)")
        cls.system(f"🚀 Factory queries saved: {stats.get('factory_queries_saved', 0)}")
        cls.system(f"⏰ Next refresh: {stats.get('next_refresh_in_minutes', 0):.1f} minutes")
    
    @classmethod
    def clean_webhook_log(cls, bot_name: str, action: str, success: bool, details: Optional[Dict] = None):
        """Log webhook activity with CLEAR bot identity and proper error categorization"""
        # Skip noisy system webhooks - only log important personality actions and actual errors
        # important_actions = {'buy', 'sell', 'create_token', 'startup', 'shutdown', 'error'}
        
        # if action not in important_actions:
        #     return  # Skip heartbeats, balance_alerts, insufficient_funds, etc.
        
        # Get bot info
        bot_display_name = cls._get_bot_display_name(bot_name)
        bot_color = cls._get_bot_color(bot_name)
        wallet_short = cls._get_wallet_short(details)
        
        # Format action nicely with proper error handling
        if action == 'error':
            # For errors, show the actual error details
            error_type = details.get('errorType', 'unknown') if details else 'unknown'
            error_details = details.get('errorDetails', 'No details') if details else 'No details'
            
            # Categorize errors properly
            if 'insufficient' in error_details.lower() or 'balance' in error_details.lower():
                # These are expected - don't log as errors
                return  # Skip insufficient balance "errors"
            elif 'timeout' in error_details.lower() or 'connection' in error_details.lower():
                action_display = '🔌 CONNECTION ERROR'
                level = "warning"
            elif 'transaction' in error_details.lower() or 'gas' in error_details.lower():
                action_display = '⛽ TRANSACTION ERROR'
                level = "error"
            elif 'trade' in error_details.lower() or 'execution' in error_details.lower():
                action_display = '💹 TRADE ERROR'
                level = "error"
            else:
                action_display = '⚠️  ERROR'
                level = "error"
            
            # Show the actual error in the message
            if details:
                balance = details.get('currentBalance', 0)
                message = f"{bot_color}{bot_display_name}{cls.colors['reset']} {action_display}: {error_details} | Balance: {balance:.4f} AVAX | Wallet: {wallet_short}"
            else:
                message = f"{bot_color}{bot_display_name}{cls.colors['reset']} {action_display}: {error_details} | Wallet: {wallet_short}"
        else:
            # Regular actions
            action_map = {
                'buy': '🟢 BUY',
                'sell': '🔴 SELL',
                'create_token': '🎨 CREATE',
                'startup': '🚀 STARTUP',
                'shutdown': '🛑 SHUTDOWN'
            }
            
            action_display = action_map.get(action, action.upper())
            level = "info"
            
            # Get additional info
            if details:
                token = details.get('tokenSymbol', '')
                balance = details.get('currentBalance', 0)
                
                # Build comprehensive message with bot identity
                if token and action in ['buy', 'sell']:
                    message = f"{bot_color}{bot_display_name}{cls.colors['reset']} {action_display} {token} | Balance: {balance:.4f} AVAX | Wallet: {wallet_short}"
                else:
                    message = f"{bot_color}{bot_display_name}{cls.colors['reset']} {action_display} | Balance: {balance:.4f} AVAX | Wallet: {wallet_short}"
            else:
                message = f"{bot_color}{bot_display_name}{cls.colors['reset']} {action_display} | Wallet: {wallet_short}"
        
        # Log with appropriate level
        if not success:
            level = "error"
        
        cls.system(message, level)
    
    @classmethod
    def _get_bot_display_name(cls, bot_name: str) -> str:
        """Get display name for bot"""
        name_map = {
            'bullish_billy': '👤 Bullish Billy',
            'companion_cube': '👤 Companion Cube',
            'jackpot_jax': '👤 Jackpot Jax',
            'melancholy_mort': '👤 Melancholy Mort'
        }
        return name_map.get(bot_name, f'👤 {bot_name.replace("_", " ").title()}')
    
    @classmethod
    def _get_bot_color(cls, bot_name: str) -> str:
        """Get color code for bot based on registration order"""
        # Get color based on fixed sequence
        bot_list = ['bullish_billy', 'companion_cube', 'jackpot_jax', 'melancholy_mort']
        
        try:
            bot_index = bot_list.index(bot_name)
        except ValueError:
            # For unknown bots, use hash
            bot_index = hash(bot_name) % len(bot_list)
        
        color_sequence = [cls.colors['blue'], cls.colors['purple'], cls.colors['cyan'], cls.colors['yellow']]
        return cls.colors['bold'] + color_sequence[bot_index % len(color_sequence)]
    
    @classmethod
    def _get_wallet_short(cls, details: Optional[Dict]) -> str:
        """Get shortened wallet address from details"""
        if not details:
            return "No wallet"
        
        wallet = details.get('walletAddress') or details.get('address', 'No wallet')
        
        if wallet and wallet != 'No wallet' and len(wallet) > 10:
            return f"{wallet[:6]}...{wallet[-4:]}"
        
        return wallet or "No wallet"
    
        # Remove the colors method since it's now a class attribute


def get_bot_logger(bot_name: str, display_name: Optional[str] = None) -> BotLogger:
    """Factory function to create bot loggers"""
    return BotLogger(bot_name, display_name)


def setup_clean_logging(quiet_mode: bool = False):
    """Setup clean logging system"""
    BotLogger.set_quiet_mode(quiet_mode)
    BotLogger.system("Clean logging system initialized", "startup")


# Context manager for clean sections
class LogSection:
    """Context manager for clean log sections"""
    
    def __init__(self, title: str, system_logger=None):
        self.title = title
        self.logger = system_logger or BotLogger
    
    def __enter__(self):
        self.logger.section(self.title)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.logger.system(f"Section '{self.title}' completed with error: {exc_val}", "error")
        else:
            self.logger.system(f"Section '{self.title}' completed", "success")


# Replacement functions for existing TVB log statements
def replace_tvb_print(message: str, bot_logger: Optional[BotLogger] = None):
    """Replace existing 'print("🤖 TVB: ...")' statements with clean logging"""
    # Remove the TVB prefix if present
    clean_message = message.replace("🤖 TVB:", "").strip()
    
    # Determine log level from content
    if any(indicator in clean_message for indicator in ["❌", "Error", "Failed", "error", "failed"]):
        level = "error"
    elif any(indicator in clean_message for indicator in ["⚠️", "Warning", "warning"]):
        level = "warning"
    elif any(indicator in clean_message for indicator in ["✅", "Success", "success", "✓"]):
        level = "success"
    elif any(indicator in clean_message for indicator in ["🚀", "Starting", "Initializing"]):
        level = "startup"
    elif any(indicator in clean_message for indicator in ["🔧", "Debug", "debug"]):
        level = "debug"
    else:
        level = "info"
    
    if bot_logger:
        bot_logger._log_with_lock(clean_message, level)
    else:
        BotLogger.system(clean_message, level)


# Example usage
if __name__ == "__main__":
    # Test the improved logger
    setup_clean_logging(quiet_mode=False)
    
    BotLogger.header("Testing Clean Logging System")
    
    # Test bot loggers
    billy_logger = BotLogger("bullish_billy", "Bullish Billy", "green")
    cube_logger = BotLogger("companion_cube", "Companion Cube", "blue")
    
    with LogSection("Bot Activity Test"):
        billy_logger.trade("buy", "0.005 AVAX for COOL tokens", "COOL")
        cube_logger.trade("sell", "1000 tokens for 0.03 AVAX", "TEST")
        billy_logger.success("Trade completed successfully!")
        cube_logger.warning("Low AVAX balance detected")
    
    # Test system messages
    BotLogger.system("All bots initialized successfully", "success")
    BotLogger.system("Starting trading operations", "startup")
    
    # Test optimization stats
    test_stats = {
        'registered_bots': 4,
        'total_tokens': 15,
        'tradeable_tokens': 12,
        'factory_queries_saved': 3,
        'next_refresh_in_minutes': 25.5
    }
    BotLogger.optimization_stats(test_stats)
    
    # Test startup summary
    test_bots = [
        {'name': 'bullish_billy', 'display_name': 'Bullish Billy', 'funded': True, 'balance': 0.05},
        {'name': 'companion_cube', 'display_name': 'Companion Cube', 'funded': False, 'balance': 0.0}
    ]
    test_summary_stats = {
        'init_time': 15.5,
        'optimization_saved': 3,
        'efficiency_gain': 75.0
    }
    BotLogger.startup_summary(test_bots, test_summary_stats)
    
    print("\n🌐 TVB: ✅ Clean logging system test complete!")