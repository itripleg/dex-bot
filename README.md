# Transparent Volume Bot (TVB)

A personality-driven trading bot ecosystem designed specifically for the **Motherhaven TokenFactory** on Avalanche. TVB creates engaging volume and activity during the platform's development phase through multiple bot personalities, each with unique trading behaviors, risk tolerances, and communication styles.

## 🎯 Purpose & Philosophy

These bots are **light-hearted development companions** designed to:
- **Generate authentic trading volume** during Motherhaven's development phase
- **Test platform functionality** through realistic trading patterns  
- **Create engaging market activity** with personality-driven interactions
- **Provide entertainment** through character-based trading behaviors

**Important:** These bots are **not designed to generate significant profits** for anyone. They're funded with real AVAX (currently on testnet) but focus on platform testing and community engagement rather than profit maximization. Future updates may include gaming characteristics and enhanced interactions.

## 🤖 Meet the Bots

### Bullish Billy
*The eternal optimist of the trading floor*
- **Buy Bias**: 80% (loves to buy dips)
- **Risk Tolerance**: 65% (moderate risk)
- **Personality**: Always seeing green candles, never met a dip he wouldn't buy
- **Trade Range**: 0.005 - 0.02 AVAX

### Jackpot Jax
*The Grandmaster at Arms of the order book*
- **Buy Bias**: 85% (aggressive buyer)
- **Risk Tolerance**: 90% (high risk)
- **Personality**: Every trade is a duel, never backs down from a fight
- **Trade Range**: 0.01 - 0.05 AVAX

### Melancholy Mort
*The market prophet of doom*
- **Buy Bias**: 15% (primarily sells)
- **Risk Tolerance**: 30% (conservative)
- **Personality**: Sees every peak as a cliff, secures positions before crashes
- **Trade Range**: 0.008 - 0.03 AVAX

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pip package manager
- Avalanche Fuji testnet wallet with AVAX

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd transparent-volume-bot
```

2. **Install dependencies**
```bash
pip install web3 requests python-dotenv eth-account
```

3. **Environment Setup**
Create a `.env.local` file (automatically gitignored):
```bash
# Required - Your private key
BOT_PRIVATE_KEY=0x1234567890abcdef...

# Required - Avalanche Fuji RPC URL
RPC_URL=https://avax-fuji.g.alchemy.com/v2/your-api-key

# Required - Motherhaven TokenFactory contract address
FACTORY_ADDRESS=0xc117C6c34CB75213f73d538Af643DA0fAb30B9bc

# Required for webhook functionality - bot authentication
BOT_SECRET=your-webhook-secret-key

# Required if using webhooks - endpoint URL
WEBHOOK_URL=https://your-api-endpoint.com/api/tvb/webhook

# Optional - Cache settings
DEFAULT_CACHE_DURATION_HOURS=6
LOG_LEVEL=INFO
```

**Important:** The `BOT_SECRET` is required for webhook authentication. Without it, the webhook endpoint will reject bot updates. For local development, you can use `--local` flag to automatically set webhook URL to `http://localhost:3000/api/tvb/webhook`.

### Running a Single Bot

```bash
# Start Bullish Billy
python main.py --config configs/bullish_billy.json --auto

# Dry run (test configuration)
python main.py --config configs/bullish_billy.json --dry-run

# Verbose logging
python main.py --config configs/bullish_billy.json --auto --verbose

# Local development mode
python main.py --config configs/bullish_billy.json --auto --local
```

### Running Multiple Bots

```bash
# Start all bots automatically
python launch_all.py --auto

# Test all configurations
python launch_all.py --dry-run

# Start specific bots
python launch_all.py --configs bullish_billy.json jackpot_jax.json --auto

# Local development mode
python launch_all.py --auto --local
```

## 📁 Project Structure

```
transparent-volume-bot/
├── bot/                    # Core bot modules
│   ├── cache.py           # Token caching system
│   ├── config.py          # Configuration management
│   ├── core.py            # Main bot orchestration
│   ├── logger.py          # Bot-specific logging
│   ├── trader.py          # Trading logic
│   └── webhook.py         # Webhook notifications
├── contracts/             # Smart contract interfaces
│   ├── factory.py         # TokenFactory contract
│   └── token.py           # ERC20 token interface
├── configs/               # Bot configuration files
│   ├── bullish_billy.json
│   ├── jackpot_jax.json
│   └── melancholy_mort.json
├── main.py               # Single bot launcher
├── launch_all.py         # Multi-bot launcher
└── .env.local           # Environment variables (you create this)
```

## ⚙️ Configuration

Each bot has a JSON configuration file with these key settings:

```json
{
  "name": "bullish_billy",
  "displayName": "Bullish Billy",
  "bio": "The eternal optimist...",
  "privateKey": "SET_IN_ENV_LOCAL",        // Must be replaced via environment
  "factoryAddress": "SET_IN_ENV_LOCAL",    // Must be replaced via environment  
  "rpcUrl": "SET_IN_ENV_LOCAL",            // Must be replaced via environment
  "webhookUrl": "SET_IN_ENV_LOCAL",        // Must be replaced via environment
  "botSecret": "SET_IN_ENV_LOCAL",         // Must be replaced via environment
  "buyBias": 0.8,                          // 0.0-1.0, higher = more buying
  "riskTolerance": 0.65,                   // 0.0-1.0, higher = larger trades
  "minInterval": 15,                       // Minimum seconds between trades
  "maxInterval": 70,                       // Maximum seconds between trades
  "minTradeAmount": 0.005,                 // Minimum AVAX per trade
  "maxTradeAmount": 0.02,                  // Maximum AVAX per trade
  "createTokenChance": 0.02,               // Probability of creating new tokens
  "buyPhrases": ["..."],                   // Personality messages for buys
  "sellPhrases": ["..."],                  // Personality messages for sells
  "createPhrases": ["..."],                // Personality messages for creates
  "errorPhrases": ["..."]                  // Personality messages for errors
}
```

**Security Note:** All sensitive values (privateKey, rpcUrl, etc.) are set to `"SET_IN_ENV_LOCAL"` placeholders in the config files and **must** be provided via environment variables in your `.env.local` file.

## 🔧 Features

### Intelligent Caching
- **Local JSON cache** for fast startup (avoids slow blockchain queries)
- **Configurable cache duration** (default: 6 hours)
- **Automatic stale token cleanup**
- **Cache performance statistics**

### Bot Personalities
- **Unique trading behaviors** based on buyBias and riskTolerance
- **Custom messaging** with personality-specific phrases
- **Different risk profiles** and trade sizes
- **Individualized avatars** and branding

### Multi-Bot Management
- **Threaded execution** - run multiple bots simultaneously
- **Centralized logging** with bot identification
- **Graceful shutdown** handling
- **Dry-run testing** for all configurations

### Webhook Integration
- **Real-time notifications** for all trading activities
- **Rich trade details** including transaction hashes
- **Heartbeat monitoring** with balance tracking
- **Error reporting** and bot status updates

### Smart Contract Integration
- **Motherhaven TokenFactory interface** for token discovery and trading
- **Bonding curve mechanics** - buy/sell through linear pricing algorithm
- **Token state verification** (trading/halted/goal_reached/resumed)
- **Virtual supply tracking** for accurate pricing calculations
- **Gas estimation** for transactions
- **Automatic retry logic** for failed transactions

## 🔐 Security Features

- **Environment variable management** - sensitive data never in code
- **Gitignore protection** - `.env.local` automatically ignored
- **Public config sanitization** - safe templates for sharing
- **Bot-specific private keys** - separate wallets per bot

## 📊 Monitoring

### Cache Statistics
```bash
# View cache performance
python -c "from bot.cache import TokenCache; c=TokenCache('test'); c.print_stats()"
```

### Webhook Health
- Success/failure rates
- Response time tracking
- Error logging with context
- Automatic retry mechanisms

### Trading Metrics
- Balance changes over time
- Trade success rates
- Token discovery statistics
- Gas usage optimization

## 🛠️ Development

### Adding New Bots

1. **Create configuration file** in `configs/` directory
2. **Define personality traits** (buyBias, riskTolerance, phrases)
3. **Set trading parameters** (intervals, amounts)
4. **Add environment variables** if needed (BOT_NEWBOT_PRIVATE_KEY)

### Testing

```bash
# Test specific bot configuration
python main.py --config configs/your_bot.json --dry-run

# Test all bots
python launch_all.py --dry-run

# Validate configuration only
python -m bot.config --validate configs/your_bot.json
```

### Local Development

```bash
# Use local webhook endpoint
python main.py --config configs/bullish_billy.json --local --auto
```

## 🌐 Network Configuration

Currently configured for **Avalanche Fuji Testnet** with the **Motherhaven TokenFactory**:
- Chain ID: 43113
- Gas Price: Auto-detected  
- RPC URL: Set in environment variables
- Factory Contract: Specifically designed for Motherhaven's bonding curve tokens
- Trading Mechanism: Linear bonding curve with dual supply system

## 📝 Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `BOT_PRIVATE_KEY` | Default private key for all bots | Yes |
| `BOT_{BOTNAME}_PRIVATE_KEY` | Bot-specific private key | Optional |
| `RPC_URL` | Avalanche RPC endpoint | Yes |
| `FACTORY_ADDRESS` | Motherhaven TokenFactory contract address | Yes |
| `BOT_SECRET` | Webhook authentication secret | Required for webhooks |
| `WEBHOOK_URL` | Notification endpoint | Optional |
| `DEFAULT_CACHE_DURATION_HOURS` | Cache freshness (default: 6) | Optional |

## 🚨 Troubleshooting

### Common Issues

**"Private key not found"**
- Create `.env.local` file with `BOT_PRIVATE_KEY=0x...`
- Ensure private key starts with `0x`

**"Failed to connect to RPC"**
- Check `RPC_URL` in `.env.local`
- Verify your Alchemy/Infura API key

**"No tradeable tokens found"**
- Check `FACTORY_ADDRESS` is correct for Motherhaven TokenFactory
- Verify factory contract has deployed tokens in tradeable state
- Use `--refresh-cache` to force token reload

**Webhook errors**
- Verify `WEBHOOK_URL` is accessible
- **Critical:** Ensure `BOT_SECRET` matches your API endpoint authentication
- Check that config files have placeholder values "SET_IN_ENV_LOCAL" replaced
- Use `--local` for local development (sets webhook to localhost:3000)

### Debug Mode

```bash
# Enable verbose logging
python main.py --config configs/bullish_billy.json --auto --verbose

# Force cache refresh
python main.py --config configs/bullish_billy.json --auto --refresh-cache
```

## 📜 License

This project is provided as-is for educational and development purposes.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

---

**⚠️ Disclaimer**: These bots are development tools for the Motherhaven platform, designed for testing and entertainment rather than profit generation. They trade with real cryptocurrency on testnet and will eventually operate on mainnet. Always test thoroughly and understand that the bots prioritize platform development and community engagement over financial returns. The developers are not responsible for any trading losses.

**🎮 Future Gaming Features**: Planned updates may include RPG-style characteristics, bot battles, achievement systems, and enhanced personality interactions as the Motherhaven ecosystem evolves.