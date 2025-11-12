# Polymarket Grid Trading Bot

Automated grid trading bot for Polymarket prediction markets with multi-token support and profit-taking strategy.

## Features

- 🎯 Range grid trading with fixed price intervals
- 💰 Automatic profit-taking on fills
- 🔄 Multi-token support (up to 10 markets)
- 📊 Smart price detection (Gamma API + order book)
- 🛡️ Position limits and risk management

---

## Quick Start

### 1. Install

```bash
pip install -r requirements.txt
```

### 2. Setup Wallet

- Private key from Polygon wallet
- USDC.e on Polygon network
- MATIC for gas fees

### 3. Find Token ID

**Use helper scripts:**

```bash
# Option A: Check token info
python tokenid.py  # Edit token_id in file first

# Option B: Find tokens by market
python market.py   # Edit market_id in file first
```

**Or manually:**

- Go to Polymarket market → F12 → Network tab → Search "markets" → Find `clobTokenIds`

### 4. Configure `.env`

**Single Token:**

```env
POLYMARKET_PRIVATE_KEY=0xYourKeyHere

TOKEN_ID_1=YourTokenIdHere
TOKEN_NAME_1=Market Name

GRID_LEVELS_1=5
GRID_SPACING_1=0.02
ORDER_SIZE_USD_1=10
MAX_POSITION_USD_1=100
RANGE_MIN_1=0.40
RANGE_MAX_1=0.60
PRICE_PRECISION_1=2

CYCLE_INTERVAL=60
```

**Multi-Token:**
See `.env.multi-token-example` for trading multiple markets with different settings.

### 5. Run

```bash
python poly.py
```

Stop with `Ctrl+C` (auto-cancels all orders).

---

## How It Works

### Initial Grid

Places orders at fixed intervals from current price:

```
Price: $0.50, Spacing: $0.02, Levels: 5

BUY:  $0.48, $0.46, $0.44, $0.42, $0.40
SELL: $0.52, $0.54, $0.56, $0.58, $0.60
```

### Profit-Taking

After fills, places opposite orders:

- **BUY fills @ $0.46** → SELL @ $0.48 (+$0.02 profit)
- **SELL fills @ $0.54** → BUY @ $0.52 (-$0.02 rebuy)

---

## Configuration Examples

### Normal Market ($0.40-$0.60)

```env
GRID_SPACING=0.02
PRICE_PRECISION=2
```

### Low Price Market ($0.05-$0.20)

```env
GRID_SPACING=0.005
PRICE_PRECISION=3
```

### Conservative

```env
GRID_LEVELS=3
GRID_SPACING=0.03
ORDER_SIZE_USD=5
RANGE_MIN=0.35
RANGE_MAX=0.65
```

### Aggressive

```env
GRID_LEVELS=10
GRID_SPACING=0.01
ORDER_SIZE_USD=20
RANGE_MIN=0.45
RANGE_MAX=0.55
```

---

## VPS Deployment

### Push to GitHub

```bash
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/USERNAME/REPO.git
git branch -M main
git push -u origin main
```

### Setup on VPS

```bash
# Clone
git clone https://github.com/USERNAME/REPO.git
cd REPO

# Install
pip install -r requirements.txt

# Create .env with your settings
nano .env

# Test
python poly.py

# Run in background (choose one):

# Option 1: nohup
nohup python poly.py > bot.log 2>&1 &
tail -f bot.log

# Option 2: screen (recommended)
screen -S polybot
python poly.py
# Detach: Ctrl+A then D
# Reattach: screen -r polybot

# Option 3: systemd (auto-restart)
# Create /etc/systemd/system/polybot.service
sudo systemctl enable polybot
sudo systemctl start polybot
sudo journalctl -u polybot -f
```

**Stop bot:**

```bash
pkill -f poly.py                    # nohup
screen -X -S polybot quit           # screen
sudo systemctl stop polybot         # systemd
```

---

## Trading Tips

**Best for:**

- Volatile/ranging markets
- Good liquidity markets
- Mean-reverting price action

**Avoid:**

- Strong trends (exits range)
- Low liquidity (wide spreads)
- Near resolution (0% or 100%)

**YES vs NO Token:**

- YES + NO price = $1.00
- Choose based on your target range
- Use NO token for inverted pricing

---

## Troubleshooting

| Issue                              | Solution                                      |
| ---------------------------------- | --------------------------------------------- |
| `POLYMARKET_PRIVATE_KEY not found` | Create `.env` file                            |
| `Max position reached`             | Reduce `MAX_POSITION_USD` or wait for sells   |
| `SELL @ $0.65 exceeds range`       | Increase `RANGE_MAX` or reduce `GRID_SPACING` |
| Wide spread warning                | Low liquidity - try different market          |
| Price precision issues             | Increase `PRICE_PRECISION` to 3 or 4          |

---

## Security

**Critical:**

- ⚠️ Never share private key
- ⚠️ Never commit `.env` (already in `.gitignore`)
- ⚠️ Start with small amounts ($5-10)

**VPS Security:**

- Use SSH keys (not passwords)
- Enable firewall: `sudo ufw enable`
- Keep updated: `sudo apt update && sudo apt upgrade`
- Use non-root user

---

## Resources

- [Polymarket Docs](https://docs.polymarket.com/)
- [py-clob-client](https://github.com/Polymarket/py-clob-client)
- [Gamma API](https://docs.polymarket.com/developers/gamma-markets-api)
- [Bridge USDC](https://wallet.polygon.technology/polygon/bridge)
- [PolygonScan](https://polygonscan.com/)

---

## Example Output

```
🤖 POLYMARKET RANGE GRID BOT (PROFIT-TAKING)
======================================================================
Token ID: 10939397796843...
Range: $0.400 - $0.600 | Profit: $0.02/cycle
Grid Levels: 5 BUY + 5 SELL
======================================================================

⏰ Time: 2025-01-12 15:30:45
📊 Current Price: $0.505
💼 Position: 45.23 YES shares | Value: $22.84
💰 Realized PnL: +$3.45 | Volume: $234.50
📋 Active Orders: 8

🟢 BUY  @ $0.48 | Size: 83.33 shares ($40.00)
🟢 BUY  @ $0.46 | Size: 86.96 shares ($40.00)
🔴 SELL @ $0.52 | Size: 76.92 shares ($40.00)
🔴 SELL @ $0.54 | Size: 74.07 shares ($40.00)

✓ Cycle complete: 8/8 orders placed
💤 Sleeping for 60 seconds...
```

---

**Disclaimer:** Trading involves risk. Only trade with funds you can afford to lose. This is educational software - use at your own risk.
