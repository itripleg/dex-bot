#!/usr/bin/env python3
"""
Bot-specific logging system for clear multi-bot identification
"""

import threading
from datetime import datetime

class BotLogger:
    """Logger that prefixes all messages with bot identification"""
    
    def __init__(self, bot_name, display_name=None, color_code=None):
        self.bot_name = bot_name
        self.display_name = display_name or bot_name
        self.color_code = color_code
        self.thread_id = threading.get_ident()
        
        # Assign colors based on bot name hash for consistency
        self.colors = {
            'red': '\033[91m',
            'green': '\033[92m', 
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'purple': '\033[95m',
            'cyan': '\033[96m',
            'white': '\033[97m',
            'reset': '\033[0m'
        }
        
        if not color_code:
            # Auto-assign color based on bot name
            color_names = ['green', 'blue', 'purple', 'cyan', 'yellow']
            color_index = hash(bot_name) % len(color_names)
            self.color_code = color_names[color_index]
    
    def _get_prefix(self):
        """Get the bot prefix for log messages"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = self.colors.get(self.color_code, '')
        reset = self.colors['reset']
        
        if color:
            return f"{color}[{timestamp}] {self.display_name}{reset}"
        else:
            return f"[{timestamp}] {self.display_name}"
    
    def info(self, message):
        """Log info message with bot prefix"""
        print(f"{self._get_prefix()}: {message}")
    
    def success(self, message):
        """Log success message"""
        print(f"{self._get_prefix()}: ✅ {message}")
    
    def warning(self, message):
        """Log warning message"""
        print(f"{self._get_prefix()}: ⚠️  {message}")
    
    def error(self, message):
        """Log error message"""
        print(f"{self._get_prefix()}: ❌ {message}")
    
    def trade(self, action, details):
        """Log trading action with emphasis"""
        action_emoji = {
            'buy': '🟢',
            'sell': '🔴', 
            'create': '🎨',
            'heartbeat': '💓'
        }
        emoji = action_emoji.get(action.lower(), '🔄')
        print(f"{self._get_prefix()}: {emoji} {action.upper()}: {details}")
    
    def cycle(self, cycle_num, action=None):
        """Log cycle information"""
        if action:
            print(f"{self._get_prefix()}: 🔄 Cycle #{cycle_num} - {action}")
        else:
            print(f"{self._get_prefix()}: 🔄 Starting Cycle #{cycle_num}")


def get_bot_logger(bot_name, display_name=None):
    """Factory function to create bot loggers"""
    return BotLogger(bot_name, display_name)


# Monkey patch print function for a specific bot context
class BotLoggerContext:
    """Context manager to temporarily redirect print statements"""
    
    def __init__(self, logger):
        self.logger = logger
        self.original_print = print
        
    def __enter__(self):
        # Replace print with logger in this context
        import builtins
        builtins.print = self._bot_print
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original print
        import builtins
        builtins.print = self.original_print
    
    def _bot_print(self, *args, **kwargs):
        """Custom print that adds bot prefix"""
        # Convert all args to strings and join
        message = ' '.join(str(arg) for arg in args)
        
        # Only prefix if it looks like a TVB message
        if "🤖 TVB:" in message:
            # Remove the original prefix and use bot prefix
            clean_message = message.replace("🤖 TVB:", "").strip()
            self.logger.info(clean_message)
        else:
            # Pass through non-TVB messages as-is
            self.original_print(*args, **kwargs)


# Simple replacement functions for the main bot files
def replace_tvb_logs(original_message, logger):
    """Replace TVB log format with bot-specific format"""
    if "🤖 TVB:" not in original_message:
        return original_message
    
    # Extract the actual message
    clean_message = original_message.replace("🤖 TVB:", "").strip()
    
    # Determine log level from content
    if "❌" in clean_message or "Error" in clean_message or "Failed" in clean_message:
        logger.error(clean_message.replace("❌", "").strip())
    elif "⚠️" in clean_message or "Warning" in clean_message:
        logger.warning(clean_message.replace("⚠️", "").strip())
    elif "✅" in clean_message or "Success" in clean_message:
        logger.success(clean_message.replace("✅", "").strip())
    elif "🟢" in clean_message and ("BUY" in clean_message or "Buy" in clean_message):
        logger.trade("buy", clean_message)
    elif "🔴" in clean_message and ("SELL" in clean_message or "Sell" in clean_message):
        logger.trade("sell", clean_message)
    else:
        logger.info(clean_message)


# Example usage
if __name__ == "__main__":
    # Test the logger
    billy_logger = BotLogger("bullish_billy", "Bullish Billy", "green")
    jax_logger = BotLogger("jackpot_jax", "Jackpot Jax", "blue")
    
    billy_logger.info("Bot initialized successfully")
    billy_logger.trade("buy", "0.005 AVAX for COOL tokens")
    billy_logger.success("Trade completed!")
    
    jax_logger.info("Bot initialized successfully") 
    jax_logger.trade("sell", "1000 tokens for 0.03 AVAX")
    jax_logger.warning("Low AVAX balance detected")
    
    print("🤖 TVB: ✅ Logger system test complete!")