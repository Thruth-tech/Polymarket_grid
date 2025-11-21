# VPS Setup Guide for Polymarket Grid Bot

## Quick Setup (All-in-One)

```bash
# 1. Update system and install dependencies
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv git screen -y

# 2. Clone repository
cd ~
git clone https://github.com/Thruth-tech/Polymarket_grid.git
cd Polymarket_grid

# 3. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 4. Install Python packages
pip install --upgrade pip
pip install -r requirements.txt

# 5. Apply HMAC fix (if needed)
python3 fix_hmac.py

# 6. Configure environment
cp .env.example .env
nano .env
# Add your credentials and save (Ctrl+X, Y, Enter)

# 7. Test the bot
python3 poly.py

# 8. Run in background with screen
screen -S polymarket
python3 poly.py
# Press Ctrl+A then D to detach
```

## Troubleshooting

### "Unauthorized/Invalid api key" Error

If you get this error, run the HMAC fix script:

```bash
python3 fix_hmac.py
```

This patches a bug in py-clob-client's HMAC signature generation.

### Update Bot

To pull latest updates:

```bash
cd ~/Polymarket_grid
git pull
source venv/bin/activate
pip install --upgrade -r requirements.txt
python3 fix_hmac.py  # Re-apply fix after updates
```

### Screen Commands

```bash
# List all screen sessions
screen -ls

# Reattach to bot
screen -r polymarket

# Detach from screen (while inside)
# Press: Ctrl+A then D

# Kill a screen session
screen -X -S polymarket quit
```

## Important Notes

1. **API Credentials**: You MUST uncomment and fill in your API credentials in `.env`:
   ```
   POLYMARKET_API_KEY=your_key_here
   POLYMARKET_API_SECRET=your_secret_here
   POLYMARKET_API_PASSPHRASE=your_passphrase_here
   ```

2. **Generate API Key**: Create API key from the same wallet address as your `POLYMARKET_PROXY_WALLET`

3. **Security**: Never commit `.env` file to GitHub
