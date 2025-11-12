# Polymarket Range Grid Trading Bot

Automated grid bot for Polymarket prediction markets. Places orders at fixed intervals to capture price volatility.

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get Your Credentials

**Wallet:**

- Private key from Polygon wallet
- USDC.e (bridged USDC) on Polygon network
- MATIC for gas fees

**Find Token ID:**

- Go to market: https://polymarket.com/event/xxxxx
- Press F12 → Network tab
- Search "positions?user=" in requests
- Find `market=0x...` in headers (this is your token ID)

### 3. Configure `.env`

```env
# Wallet
POLYMARKET_PRIVATE_KEY=0xYourPrivateKeyHere

# Token to trade
TOKEN_ID=YourTokenIdHere

# Price Range
RANGE_MIN=0.60          # Bottom of trading range
RANGE_MAX=0.80          # Top of trading range

# Grid Settings
GRID_LEVELS=5           # Number of orders per side (5 BUY + 5 SELL)
GRID_SPACING=0.02       # Distance between orders (2¢)
PRICE_PRECISION=2       # Decimal places (2 for $0.01, 3 for $0.001)
ORDER_SIZE_USD=10       # USD per order
MAX_POSITION_USD=100    # Maximum position size

# Timing
CYCLE_INTERVAL=60       # Seconds between cycles
```

### 4. Run Bot

```bash
python poly.py
```

Stop with `Ctrl+C` (automatically cancels all orders).

---

## 📊 How It Works

### Grid Placement

Orders are placed at **fixed intervals** starting from current price:

```
Current price: $0.705
GRID_SPACING: $0.02
GRID_LEVELS: 5

BUY orders (below current price):
$0.69, $0.67, $0.65, $0.63, $0.61

SELL orders (above current price):
$0.73, $0.75, $0.77, $0.79
```

Orders outside `RANGE_MIN` to `RANGE_MAX` are skipped.

### Profit-Taking Strategy

When orders fill, bot places **opposite side** to capture profit:

1. **BUY fills @ $0.67** → Place SELL @ $0.69 (+$0.02 profit)
2. **SELL fills @ $0.75** → Place BUY @ $0.73 (-$0.02 profit)

This creates buy-sell cycles to profit from volatility.

---

## ⚙️ Configuration Guide

### Normal Markets ($0.50 - $0.80)

```env
GRID_SPACING=0.02       # 2¢ between orders
PRICE_PRECISION=2       # Display as $0.67, $0.69
```

### Low-Price Markets ($0.02 - $0.10)

```env
GRID_SPACING=0.002      # 0.2¢ between orders
PRICE_PRECISION=3       # Display as $0.021, $0.023
```

### Risk Examples

**Conservative (Low Risk):**

```env
RANGE_MIN=0.55
RANGE_MAX=0.85          # Wide range
GRID_LEVELS=3           # Fewer orders
GRID_SPACING=0.03       # Wide spacing
ORDER_SIZE_USD=5        # Small orders
```

**Balanced (Medium Risk):**

```env
RANGE_MIN=0.60
RANGE_MAX=0.80          # Moderate range
GRID_LEVELS=5           # 5 BUY + 5 SELL
GRID_SPACING=0.02       # 2¢ spacing
ORDER_SIZE_USD=10       # Standard orders
```

**Aggressive (High Risk):**

```env
RANGE_MIN=0.60
RANGE_MAX=0.75          # Tight range
GRID_LEVELS=7           # More orders
GRID_SPACING=0.01       # Tight spacing
ORDER_SIZE_USD=20       # Larger orders
```

---

## 💡 Trading Tips

**Best for:**

- ✅ Volatile markets (price oscillates in range)
- ✅ Ranging markets (sideways movement)
- ✅ Markets you expect to mean-revert

**Not good for:**

- ❌ Strong trends (price exits range)
- ❌ Low liquidity markets
- ❌ Markets near resolution (0% or 100%)

**Token Types:**

- Each market has YES and NO tokens
- YES price + NO price = $1.00
- Choose token based on your range strategy

---

## 📚 Resources

**Polymarket:**

- Docs: https://docs.polymarket.com/
- API: https://docs.polymarket.com/developers
- Markets: https://docs.polymarket.com/developers/gamma-markets-api/get-markets

**Python Client:**

- GitHub: https://github.com/Polymarket/py-clob-client
- Examples: https://github.com/Polymarket/py-clob-client/tree/main/examples

**Polygon:**

- Explorer: https://polygonscan.com/
- RPC: https://polygon-rpc.com

---

## 🔒 Security

- ⚠️ Never share your private key
- ⚠️ Never commit `.env` to version control
- ⚠️ Start with small amounts to test
- ⚠️ Monitor your positions regularly

---
