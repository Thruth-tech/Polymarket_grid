import asyncio
import os
import sys
from typing import Optional, Dict, List, Tuple
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType, OpenOrderParams, ApiCreds
from py_clob_client.order_builder.constants import BUY, SELL
import time
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import requests
import json

# Fix Windows console encoding to support Unicode characters
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

load_dotenv()

def round_price(price: float, precision: int, grid_spacing: float) -> float:
    """
    Round price to grid spacing increments
    Examples with 0.01 spacing: $0.455 → $0.46, $0.445 → $0.45
    Examples with 0.02 spacing: $0.455 → $0.46, $0.435 → $0.44
    Uses ROUND_HALF_UP for consistent rounding behavior
    """
    # Round to grid_spacing increments
    rounded = round(price / grid_spacing) * grid_spacing

    # Apply precision formatting
    decimal_price = Decimal(str(rounded))
    quantize_format = Decimal(10) ** -precision
    return float(decimal_price.quantize(quantize_format, rounding=ROUND_HALF_UP))

class PolymarketGridBot:
    """
    Range Grid Bot for Polymarket with Profit-Taking Strategy

    Strategy:
    - Places BUY and SELL orders across a price range
    - When BUY fills → places SELL above it to take profit
    - When SELL fills → places BUY below it to rebuy
    - Creates buy-sell profit cycles from volatility
    """
    
    def __init__(
        self,
        private_key: str,
        token_id: str,  # Token ID to trade
        grid_levels: int = 5,  # Number of BUY and SELL orders
        grid_spacing: float = 0.02,  # Profit distance (2 cents per cycle)
        order_size_usd: float = 10.0,  # USD per order
        max_position_usd: float = 100.0,  # Max position size in USD
        min_spread: float = 0.01,  # Minimum spread to capture
        fee_rate_bps: int = 0,  # Fee rate in basis points
        min_order_size: float = 0.1,  # Minimum order size in shares
        max_order_size: float = 10000.0,  # Maximum order size in shares
        range_min: float = 0.30,  # Minimum price for range grid
        range_max: float = 0.70,  # Maximum price for range grid
        price_precision: int = 3,  # Decimal places for price rounding (3 for 1¢, 4 for 0.1¢)
    ):
        # Validate inputs
        if grid_spacing <= 0 or grid_spacing >= 1:
            raise ValueError(f"GRID_SPACING must be between 0 and 1, got {grid_spacing}")
        if order_size_usd <= 0:
            raise ValueError(f"ORDER_SIZE_USD must be positive, got {order_size_usd}")
        if grid_levels <= 0:
            raise ValueError(f"GRID_LEVELS must be positive, got {grid_levels}")
        if max_position_usd <= 0:
            raise ValueError(f"MAX_POSITION_USD must be positive, got {max_position_usd}")
        if not 0 < range_min < 1:
            raise ValueError(f"RANGE_MIN must be between 0 and 1, got {range_min}")
        if not 0 < range_max < 1:
            raise ValueError(f"RANGE_MAX must be between 0 and 1, got {range_max}")
        if range_min >= range_max:
            raise ValueError(f"RANGE_MIN must be less than RANGE_MAX, got {range_min} >= {range_max}")

        # Validate price precision matches grid spacing
        min_precision_needed = len(str(grid_spacing).split('.')[-1])
        if price_precision < min_precision_needed:
            raise ValueError(
                f"PRICE_PRECISION={price_precision} too low for GRID_SPACING={grid_spacing}. "
                f"Need at least {min_precision_needed} decimals. "
                f"Example: GRID_SPACING=0.01 needs PRICE_PRECISION=2, "
                f"GRID_SPACING=0.001 needs PRICE_PRECISION=3"
            )
        # Initialize Polymarket CLOB client
        # Get proxy wallet address from environment or use None for direct wallet trading
        proxy_wallet = os.getenv("POLYMARKET_PROXY_WALLET", None)

        # Determine if using proxy wallet
        # signature_type=2 for SAFE wallets (Polymarket proxy wallets)
        # signature_type=1 for Magic/email wallets
        # signature_type=0 or None for direct EOA (Externally Owned Account)
        if proxy_wallet:
            print(f"[OK] Using proxy wallet (SAFE): {proxy_wallet}")
            self.client = ClobClient(
                host="https://clob.polymarket.com",
                key=private_key,
                chain_id=137,  # Polygon mainnet
                signature_type=2,  # Required for SAFE wallets (Polymarket proxy)
                funder=proxy_wallet,  # The address holding your funds
            )
        else:
            print(f"[OK] Using direct EOA wallet")
            self.client = ClobClient(
                host="https://clob.polymarket.com",
                key=private_key,
                chain_id=137,  # Polygon mainnet
            )

        # Set up API credentials for authenticated requests
        # Option 1: Use API credentials from environment (RECOMMENDED for proxy wallet trading)
        api_key = os.getenv("POLYMARKET_API_KEY")
        api_secret = os.getenv("POLYMARKET_API_SECRET")
        api_passphrase = os.getenv("POLYMARKET_API_PASSPHRASE")

        try:
            if api_key and api_secret and api_passphrase:
                # Use provided API credentials (proxy wallet)
                print("[OK] Using API credentials from environment")
                api_creds = ApiCreds(
                    api_key=api_key,
                    api_secret=api_secret,
                    api_passphrase=api_passphrase,
                )
                self.client.set_api_creds(api_creds)
                print("[OK] API credentials configured successfully")
            else:
                # Option 2: Try to derive from private key (may not work for all wallets)
                print("[WARNING] No API credentials in .env, attempting to derive from private key...")
                self.client.set_api_creds(self.client.create_or_derive_api_creds())
                print("[OK] API credentials derived from private key")
        except Exception as e:
            print(f"[ERROR] Could not set API credentials: {e}")
            print("  Please add your Polymarket API credentials to .env:")
            print("  POLYMARKET_API_KEY=your_api_key")
            print("  POLYMARKET_API_SECRET=your_api_secret")
            print("  POLYMARKET_API_PASSPHRASE=your_api_passphrase")
            raise

        self.token_id = token_id
        self.grid_levels = grid_levels
        self.grid_spacing = grid_spacing
        self.order_size_usd = order_size_usd
        self.max_position_usd = max_position_usd
        self.min_spread = min_spread
        self.fee_rate_bps = fee_rate_bps
        self.min_order_size = min_order_size
        self.max_order_size = max_order_size
        self.range_min = range_min
        self.range_max = range_max
        self.price_precision = price_precision

        # Track state
        self.active_orders: Dict[str, dict] = {}
        self.position_yes = 0.0  # YES shares held
        self.position_no = 0.0   # NO shares held
        self.avg_buy_price = 0.0
        self.realized_pnl = 0.0
        self.total_volume = 0.0
        self.range_grid_levels: List[Dict] = []  # Track fixed price levels for range grid
        
        # Market info
        self.market_info = None
        self._load_market_info()
        
        print(f"✓ Bot initialized for token: {self.token_id}")
        print(f"✓ Range: ${self.range_min:.3f} - ${self.range_max:.3f}")
        print(f"✓ Profit spacing: ${self.grid_spacing:.{self.price_precision}f} per cycle")
        print(f"✓ Price precision: {self.price_precision} decimals")
    
    def _load_market_info(self):
        """Load market information"""
        try:
            # Get market info using the simplified markets endpoint
            # The token_id is used to identify the specific outcome
            markets = self.client.get_simplified_markets()

            # Find market containing our token
            for market in markets:
                if 'tokens' in market:
                    for token in market['tokens']:
                        if token['token_id'] == self.token_id:
                            self.market_info = market
                            print(f"✓ Market found: {market.get('question', 'Unknown')}")
                            return

            print(f"⚠ Market info not found for token {self.token_id}")
            print(f"  This won't prevent trading, but market info won't be displayed")

        except Exception as e:
            print(f"✗ Error loading market info: {e}")
            print(f"  Continuing without market info...")
    
    def get_order_book(self) -> Optional[Dict]:
        """Get current order book for the token with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                book = self.client.get_order_book(self.token_id)
                return book
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    print(f"⚠ Error getting order book (attempt {attempt + 1}/{max_retries}): {e}")
                    print(f"  Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"✗ Failed to get order book after {max_retries} attempts: {e}")
                    return None
    
    def get_mid_price(self) -> Optional[float]:
        """Calculate mid price from order book"""
        book = self.get_order_book()
        if not book:
            return None

        # Handle both dict and object responses
        if hasattr(book, 'bids'):
            bids = book.bids
            asks = book.asks
        else:
            bids = book.get('bids', [])
            asks = book.get('asks', [])

        # Handle both dict and object for individual orders
        if bids and hasattr(bids[0], 'price'):
            best_bid = float(bids[0].price) if bids else None
            best_ask = float(asks[0].price) if asks else None
        else:
            best_bid = float(bids[0]['price']) if bids else None
            best_ask = float(asks[0]['price']) if asks else None
        
        if best_bid and best_ask:
            spread = best_ask - best_bid
            mid = (best_bid + best_ask) / 2

            # Warn if spread is unreasonably wide
            if spread > 0.50:  # Spread > 50 cents = likely bad data
                print(f"⚠️  WARNING: Very wide spread detected!")
                print(f"   BID: ${best_bid:.3f} | ASK: ${best_ask:.3f} | Spread: ${spread:.3f}")
                print(f"   Mid price ${mid:.3f} may be inaccurate")
                print(f"   Consider using a more liquid market or check order book manually")

            return mid
        elif best_bid:
            return best_bid + 0.005
        elif best_ask:
            return best_ask - 0.005
        else:
            return 0.5  # Default

    def get_token_price_from_gamma(self) -> Optional[float]:
        """Get current token price from Gamma Markets API (more reliable than order book)"""
        try:
            url = "https://gamma-api.polymarket.com/markets"
            params = {"clob_token_ids": self.token_id, "limit": 1}

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    market = data[0]

                    # Parse token IDs and prices
                    clob_token_ids_raw = market.get('clobTokenIds', '')
                    if isinstance(clob_token_ids_raw, list):
                        clob_token_ids = clob_token_ids_raw
                    elif isinstance(clob_token_ids_raw, str):
                        try:
                            clob_token_ids = json.loads(clob_token_ids_raw)
                        except:
                            clob_token_ids = [t.strip() for t in clob_token_ids_raw.split(',')]
                    else:
                        clob_token_ids = []

                    outcome_prices_raw = market.get('outcomePrices', [])
                    if isinstance(outcome_prices_raw, str):
                        try:
                            outcome_prices = json.loads(outcome_prices_raw)
                        except:
                            outcome_prices = []
                    else:
                        outcome_prices = outcome_prices_raw

                    # Find our token and return its price
                    for idx, token_id in enumerate(clob_token_ids):
                        if str(token_id) == str(self.token_id):
                            if idx < len(outcome_prices):
                                price = float(outcome_prices[idx])
                                return price

            return None

        except Exception as e:
            print(f"⚠️  Could not fetch price from Gamma API: {e}")
            return None

    def get_current_price(self) -> Optional[float]:
        """Get current market price - tries Gamma API first, falls back to order book"""
        # Try Gamma API first (most reliable)
        gamma_price = self.get_token_price_from_gamma()
        if gamma_price:
            return gamma_price

        # Fall back to order book mid price
        print("⚠️  Gamma API unavailable, using order book mid price")
        return self.get_mid_price()

    def get_current_positions(self) -> Tuple[float, float]:
        """
        Get current YES and NO positions

        Note: Position tracking is done internally by monitoring order fills.
        This method returns the internally tracked position.
        The API doesn't reliably provide position data for individual tokens.
        """
        # Position tracking is handled by update_active_orders()
        # which monitors filled orders and updates self.position_yes

        # We rely on internal tracking rather than API queries
        # because the trades API may return other users' trades or incomplete data

        return self.position_yes, self.position_no
    
    def calculate_position_value(self, mid_price: float) -> float:
        """Calculate current position value in USD"""
        return self.position_yes * mid_price
    
    def can_place_order(self, side: str, mid_price: float) -> bool:
        """Check if we can place more orders based on position limits"""
        position_value = self.calculate_position_value(mid_price)

        if side == BUY:
            # Buying YES increases our long position
            if position_value >= self.max_position_usd:
                return False
        elif side == SELL:
            # Cannot sell if we don't have any tokens
            if self.position_yes <= 0:
                return False
            # Selling YES increases our short position (or reduces long)
            if position_value <= -self.max_position_usd:
                return False

        return True
    
    def calculate_order_size(self, mid_price: float) -> float:
        """Calculate order size - fixed amount per order"""
        position_value = abs(self.calculate_position_value(mid_price))

        if position_value >= self.max_position_usd:
            return 0.0

        # Fixed order size - no scaling based on position
        return self.order_size_usd
    
    def generate_range_grid_orders(self, mid_price: float) -> List[Dict]:
        """
        Generate static range grid orders with fixed spacing

        Strategy:
        - BUY orders: Start below current price, go DOWN by GRID_SPACING
        - SELL orders: Start above current price, go UP by GRID_SPACING
        - Orders use fixed spacing (e.g., $0.02 apart)
        - Skip any orders outside RANGE_MIN to RANGE_MAX
        """
        orders = []
        placed_prices = set()  # Track prices to prevent duplicates

        # Calculate order size
        size_usd = self.calculate_order_size(mid_price)
        if size_usd == 0:
            print("⚠ Max position reached, no new orders")
            return orders

        # Generate BUY orders - start at rounded current price, go DOWN
        # Calculate the grid line at or just below current price
        base_price = round_price(mid_price, self.price_precision, self.grid_spacing)

        # Ensure we're below the mid_price for BUY orders
        if base_price >= mid_price:
            base_price -= self.grid_spacing

        for i in range(self.grid_levels):
            # Calculate each price from base_price to avoid cumulative rounding errors
            raw_price = base_price - (i * self.grid_spacing)
            price = round_price(raw_price, self.price_precision, self.grid_spacing)

            # Skip if outside range
            if price < self.range_min or price >= mid_price:
                continue

            # Price validation
            if price < 0.01:
                continue

            # Skip duplicate prices
            if price in placed_prices:
                print(f"  [FILTERED] ${price:.{self.price_precision}f} duplicate price, skipping")
                continue
            placed_prices.add(price)

            # Check if we can place this order
            if not self.can_place_order(BUY, mid_price):
                print(f"⚠ Skipping BUY orders - position limit")
                break

            # Size in outcome tokens
            size = size_usd / price

            # Validate order size
            if size < self.min_order_size:
                continue
            if size > self.max_order_size:
                size = self.max_order_size

            orders.append({
                'side': BUY,
                'price': price,
                'size': round(size, 2),
                'level': -i
            })

        # Generate SELL orders - start at rounded current price + 1 spacing, go UP
        # Calculate the grid line at or just above current price
        base_price = round_price(mid_price, self.price_precision, self.grid_spacing)

        # Ensure we're above the mid_price for SELL orders
        if base_price <= mid_price:
            base_price += self.grid_spacing

        for i in range(self.grid_levels):
            # Calculate each price from base_price to avoid cumulative rounding errors
            raw_price = base_price + (i * self.grid_spacing)
            price = round_price(raw_price, self.price_precision, self.grid_spacing)

            # Skip if outside range
            if price > self.range_max or price <= mid_price:
                continue

            # Price validation
            if price > 0.99:
                continue

            # Skip duplicate prices
            if price in placed_prices:
                print(f"  [FILTERED] ${price:.{self.price_precision}f} duplicate price, skipping")
                continue
            placed_prices.add(price)

            # Check if we can place this order
            if not self.can_place_order(SELL, mid_price):
                if self.position_yes <= 0:
                    print(f"⚠ Skipping SELL orders - no YES tokens to sell (position: {self.position_yes:.2f})")
                else:
                    print(f"⚠ Skipping SELL orders - position limit")
                break

            # Size in outcome tokens
            size = size_usd / price

            # Validate order size
            if size < self.min_order_size:
                continue
            if size > self.max_order_size:
                size = self.max_order_size

            orders.append({
                'side': SELL,
                'price': price,
                'size': round(size, 2),
                'level': i
            })

        return orders

    async def place_order(self, side: str, price: float, size: float) -> Optional[str]:
        """Place a limit order on Polymarket with enhanced error handling"""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # Validate order parameters
                if price <= 0 or price >= 1:
                    print(f"✗ Invalid price: ${price:.{self.price_precision}f} (must be between 0.01 and 0.99)")
                    return None

                if size <= 0:
                    print(f"✗ Invalid size: {size:.2f} (must be positive)")
                    return None

                # Create order arguments
                order_args = OrderArgs(
                    token_id=self.token_id,
                    price=price,
                    size=size,
                    side=side,
                    fee_rate_bps=self.fee_rate_bps,
                )

                # Sign the order
                signed_order = self.client.create_order(order_args)

                # Post the order
                response = self.client.post_order(signed_order, OrderType.GTC)

                if response and 'orderID' in response:
                    order_id = response['orderID']

                    # Track the order
                    self.active_orders[order_id] = {
                        'side': side,
                        'price': price,
                        'size': size,
                        'timestamp': time.time(),
                    }

                    direction = "🟢 BUY " if side == BUY else "🔴 SELL"
                    print(f"{direction} @ ${price:.{self.price_precision}f} | Size: {size:.2f} shares (${size*price:.2f}) | ID: {order_id[:8]}")

                    return order_id
                else:
                    error_msg = response.get('error', response) if isinstance(response, dict) else response
                    print(f"✗ Failed to place order: {error_msg}")

                    if attempt < max_retries - 1:
                        print(f"  Retrying... (attempt {attempt + 2}/{max_retries})")
                        await asyncio.sleep(1)
                        continue

            except Exception as e:
                error_type = type(e).__name__
                print(f"✗ Error placing {side} order @ ${price:.{self.price_precision}f}: [{error_type}] {e}")

                if attempt < max_retries - 1:
                    print(f"  Retrying... (attempt {attempt + 2}/{max_retries})")
                    await asyncio.sleep(1)
                    continue

        return None
    
    async def cancel_order(self, order_id: str):
        """Cancel a specific order with error handling"""
        try:
            response = self.client.cancel(order_id)

            if order_id in self.active_orders:
                del self.active_orders[order_id]

            # print(f"✓ Cancelled order: {order_id[:8]}")

        except Exception as e:
            # Some errors are expected (order already filled/cancelled)
            error_str = str(e).lower()
            if 'not found' in error_str or 'already' in error_str:
                # Order was already filled or cancelled, just remove from tracking
                if order_id in self.active_orders:
                    del self.active_orders[order_id]
            else:
                print(f"✗ Error cancelling order {order_id[:8]}: {e}")
    
    async def cancel_all_orders(self):
        """Cancel all active orders - fetches from exchange to ensure all are cancelled"""
        try:
            print("Fetching open orders from exchange...")

            # Get all open orders from exchange (not just tracked ones)
            open_orders = self.get_open_orders()

            print(f"Found {len(open_orders)} open orders")

            if not open_orders:
                print("No open orders to cancel")
                return

            print(f"Cancelling {len(open_orders)} orders...")

            # Cancel each order
            cancelled_count = 0
            failed_count = 0
            for order in open_orders:
                try:
                    # Handle both dict and object
                    order_id = order.id if hasattr(order, 'id') else order.get('id')
                    if order_id:
                        print(f"  Cancelling order {order_id[:10]}...")
                        result = self.client.cancel(order_id)
                        cancelled_count += 1
                        await asyncio.sleep(0.2)  # Rate limiting
                except Exception as e:
                    failed_count += 1
                    print(f"  Failed to cancel order: {e}")

            print(f"✓ Cancelled {cancelled_count}/{len(open_orders)} orders")
            if failed_count > 0:
                print(f"⚠ {failed_count} orders failed to cancel (might be already filled)")
            self.active_orders.clear()  # Clear tracking

        except Exception as e:
            print(f"✗ Error in cancel_all_orders: {e}")
            import traceback
            traceback.print_exc()
    
    def get_open_orders(self) -> List[Dict]:
        """Get currently open orders from the exchange"""
        try:
            # Try to get orders for this specific token
            # OpenOrderParams may accept different parameters depending on API version
            # Try multiple approaches

            # Approach 1: Try with asset_id
            try:
                params = OpenOrderParams(asset_id=self.token_id)
                orders = self.client.get_orders(params)
                if orders:
                    return orders
            except:
                pass

            # Approach 2: Try with market
            try:
                params = OpenOrderParams(market=self.token_id)
                orders = self.client.get_orders(params)
                if orders:
                    return orders
            except:
                pass

            # Approach 3: Get all orders and filter
            try:
                orders = self.client.get_orders()
                # Filter to only this token - handle both dict and object
                filtered = []
                for o in orders:
                    asset_id = o.asset_id if hasattr(o, 'asset_id') else o.get('asset_id')
                    market = o.market if hasattr(o, 'market') else o.get('market')
                    if asset_id == self.token_id or market == self.token_id:
                        filtered.append(o)
                return filtered
            except:
                pass

            return []

        except Exception as e:
            print(f"✗ Error getting open orders: {e}")
            return []
    
    def update_active_orders(self):
        """Sync active orders with exchange state and track filled orders"""
        open_orders = self.get_open_orders()
        # Handle both dict and object for orders
        open_order_ids = set()
        for order in open_orders:
            order_id = order.id if hasattr(order, 'id') else order['id']
            open_order_ids.add(order_id)

        # Track filled orders for profit-taking logic
        filled_orders = []

        # Remove filled/cancelled orders from tracking
        tracked_ids = list(self.active_orders.keys())
        for order_id in tracked_ids:
            if order_id not in open_order_ids:
                # Order was filled or cancelled
                order = self.active_orders[order_id]
                order_value = order['size'] * order['price']

                # Store filled order info for profit-taking
                filled_orders.append({
                    'side': order['side'],
                    'price': order['price'],
                    'size': order['size'],
                    'value': order_value
                })

                # Update position tracking
                if order['side'] == BUY:
                    self.position_yes += order['size']
                    print(f"✓ BUY order filled @ ${order['price']:.{self.price_precision}f} | {order['size']:.2f} shares | ${order_value:.2f}")
                elif order['side'] == SELL:
                    self.position_yes -= order['size']
                    print(f"✓ SELL order filled @ ${order['price']:.{self.price_precision}f} | {order['size']:.2f} shares | ${order_value:.2f}")

                # Update total volume
                self.total_volume += order_value

                del self.active_orders[order_id]

        return filled_orders
    
    def print_status(self, mid_price: float, grid_center: float):
        """Print current bot status"""
        position_value = self.calculate_position_value(mid_price)

        print("\n" + "="*70)
        print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📊 Current Price: ${mid_price:.3f}")
        print(f"🎯 Range: ${self.range_min:.3f} - ${self.range_max:.3f} | Profit: ${self.grid_spacing:.{self.price_precision}f}/cycle")
        print(f"💼 Position: {self.position_yes:.2f} YES shares | Value: ${position_value:+.2f}")
        print(f"💰 Realized PnL: ${self.realized_pnl:+.2f} | Volume: ${self.total_volume:.2f}")
        print(f"📋 Active Orders: {len(self.active_orders)}")
        print("="*70)
    
    async def run_cycle(self):
        """Execute one trading cycle with comprehensive error handling"""
        print(f"\n🔄 Starting new cycle...")

        try:
            # Get current market state (from Gamma API or order book)
            mid_price = self.get_current_price()
            if mid_price is None:
                print("✗ Could not get current price, skipping cycle")
                return

            # Validate price is reasonable
            if mid_price <= 0 or mid_price >= 1:
                print(f"⚠ Warning: Price ${mid_price:.4f} seems unreasonable, skipping cycle")
                return

            # Update order status (check for fills)
            filled_orders = []
            try:
                filled_orders = self.update_active_orders()
            except Exception as e:
                print(f"⚠ Error updating active orders: {e}")
                # Continue anyway, this is not critical

            # Update positions from API (best effort)
            try:
                api_position, _ = self.get_current_positions()
                # Only update if API returns reasonable value
                if api_position is not None:
                    self.position_yes = api_position
            except Exception as e:
                print(f"⚠ Could not update position from API: {e}")
                # Use tracked position instead

            # === RANGE GRID (CONTINUOUS MAINTENANCE) ===
            # Maintains full grid at all times by replacing any missing orders

            # Print status
            self.print_status(mid_price, (self.range_min + self.range_max) / 2)

            # Report any filled orders
            if filled_orders:
                print(f"\n💰 {len(filled_orders)} order(s) filled this cycle:")
                for filled in filled_orders:
                    direction = "BUY" if filled['side'] == BUY else "SELL"
                    print(f"   ✓ {direction} @ ${filled['price']:.{self.price_precision}f} | {filled['size']:.2f} shares")

            # Get currently active order prices to avoid duplicates
            print("\n🔄 Checking grid status...")
            active_buy_prices = set()
            active_sell_prices = set()
            for order_id, order in self.active_orders.items():
                if order['side'] == BUY:
                    active_buy_prices.add(order['price'])
                else:
                    active_sell_prices.add(order['price'])

            # Generate what the full grid SHOULD look like
            target_grid = self.generate_range_grid_orders(mid_price)

            # Find missing orders (orders that should exist but don't)
            orders = []
            for target_order in target_grid:
                target_price = target_order['price']

                if target_order['side'] == BUY:
                    if target_price not in active_buy_prices:
                        orders.append(target_order)
                        print(f"  🟢 Missing BUY @ ${target_price:.{self.price_precision}f} - will place")
                else:  # SELL
                    if target_price not in active_sell_prices:
                        orders.append(target_order)
                        print(f"  🔴 Missing SELL @ ${target_price:.{self.price_precision}f} - will place")

            if not orders:
                print("✓ Grid is complete - all orders active")
                return

            print(f"\n📝 Placing {len(orders)} new orders...")

            # Place orders with rate limiting
            placed_count = 0
            for order in orders:
                result = await self.place_order(
                    side=order['side'],
                    price=order['price'],
                    size=order['size']
                )
                if result:
                    placed_count += 1
                await asyncio.sleep(0.3)  # Rate limiting between orders

            print(f"✓ Cycle complete: {placed_count}/{len(orders)} orders placed")

        except KeyboardInterrupt:
            # Propagate without error message
            raise
        except Exception as e:
            print(f"✗ Error in run_cycle: {type(e).__name__}: {e}")
            print("  Will retry in next cycle...")
    
    async def run(self, cycle_interval: int = 60):
        """Main bot loop"""
        print("\n" + "="*70)
        print("🤖 POLYMARKET RANGE GRID BOT (PROFIT-TAKING)")
        print("="*70)
        print(f"Token ID: {self.token_id}")
        print(f"Range: ${self.range_min:.3f} - ${self.range_max:.3f}")
        print(f"Grid Levels: {self.grid_levels} BUY + {self.grid_levels} SELL")
        print(f"Profit Spacing: ${self.grid_spacing:.{self.price_precision}f} ({self.grid_spacing*100:.1f}¢)")
        print(f"Price Precision: {self.price_precision} decimals")
        print(f"Order Size: ${self.order_size_usd:.2f}")
        print(f"Max Position: ${self.max_position_usd:.2f}")
        print(f"Cycle Interval: {cycle_interval}s")
        print("="*70 + "\n")
        
        try:
            while True:
                cycle_start = time.time()
                await self.run_cycle()

                # Calculate sleep time to maintain consistent interval
                cycle_duration = time.time() - cycle_start
                sleep_time = max(0, cycle_interval - cycle_duration)

                if cycle_duration > cycle_interval:
                    print(f"⚠ Cycle took {cycle_duration:.1f}s (longer than {cycle_interval}s interval)")
                    print(f"💤 Starting next cycle immediately...")
                else:
                    print(f"💤 Cycle took {cycle_duration:.1f}s, sleeping for {sleep_time:.1f}s...")
                    await asyncio.sleep(sleep_time)
                
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n\n🛑 Shutting down bot...")
            await self.cancel_all_orders()
            print("✓ Shutdown complete")
        except Exception as e:
            print(f"\n✗ Fatal error: {e}")
            await self.cancel_all_orders()
            raise


class MultiTokenGridBot:
    """
    Manages multiple range grid bots trading different tokens simultaneously
    """

    def __init__(self, private_key: str, bot_configs: List[Dict]):
        """
        Initialize multi-token grid bot

        Args:
            private_key: Wallet private key
            bot_configs: List of config dicts, each containing:
                - token_id: Token ID to trade
                - grid_levels: Grid levels (optional, uses default)
                - grid_spacing: Profit spacing (optional, uses default)
                - order_size_usd: Order size (optional, uses default)
                - range_min: Minimum price (optional, uses default)
                - range_max: Maximum price (optional, uses default)
                - ... other bot parameters
        """
        self.private_key = private_key
        self.bots = []

        print("\n" + "="*70)
        print("🤖 MULTI-TOKEN POLYMARKET GRID BOT")
        print("="*70)
        print(f"Initializing {len(bot_configs)} trading bots...\n")

        # Create a bot instance for each token
        for i, config in enumerate(bot_configs, 1):
            print(f"[Bot {i}/{len(bot_configs)}] Token: {config['token_id'][:16]}...")

            bot = PolymarketGridBot(
                private_key=private_key,
                token_id=config['token_id'],
                grid_levels=config.get('grid_levels', 5),
                grid_spacing=config.get('grid_spacing', 0.02),
                order_size_usd=config.get('order_size_usd', 10.0),
                max_position_usd=config.get('max_position_usd', 100.0),
                min_spread=config.get('min_spread', 0.01),
                fee_rate_bps=config.get('fee_rate_bps', 0),
                min_order_size=config.get('min_order_size', 0.1),
                max_order_size=config.get('max_order_size', 10000.0),
                range_min=config.get('range_min', 0.30),
                range_max=config.get('range_max', 0.70),
                price_precision=config.get('price_precision', 3),
            )

            self.bots.append({
                'bot': bot,
                'token_id': config['token_id'],
                'name': config.get('name', f"Token {i}")
            })

        print(f"\n✓ All {len(self.bots)} bots initialized successfully")
        print("="*70 + "\n")

    async def run_all_cycles(self):
        """Run one cycle for all bots"""
        for i, bot_info in enumerate(self.bots, 1):
            bot = bot_info['bot']
            name = bot_info['name']

            print(f"\n{'='*70}")
            print(f"🔄 [{i}/{len(self.bots)}] Running cycle for: {name}")
            print(f"{'='*70}")

            try:
                await bot.run_cycle()
            except Exception as e:
                print(f"✗ Error in {name}: {e}")
                print("  Continuing with other bots...")

    async def cancel_all_bots_orders(self):
        """Cancel all orders for all bots"""
        print("\n🛑 Cancelling orders for all bots...")
        for bot_info in self.bots:
            bot = bot_info['bot']
            name = bot_info['name']
            try:
                await bot.cancel_all_orders()
                print(f"✓ {name}: Orders cancelled")
            except Exception as e:
                print(f"✗ {name}: Error cancelling orders: {e}")

    def print_summary(self):
        """Print summary of all bot positions"""
        print("\n" + "="*70)
        print("📊 PORTFOLIO SUMMARY")
        print("="*70)

        total_position_value = 0.0
        total_pnl = 0.0
        total_volume = 0.0
        total_active_orders = 0

        for i, bot_info in enumerate(self.bots, 1):
            bot = bot_info['bot']
            name = bot_info['name']

            # Use get_current_price() instead of get_mid_price() for more reliable data
            # (uses Gamma API first, falls back to order book)
            mid_price = bot.get_current_price()
            if mid_price:
                position_value = bot.calculate_position_value(mid_price)
                total_position_value += position_value
            else:
                position_value = 0.0

            total_pnl += bot.realized_pnl
            total_volume += bot.total_volume
            total_active_orders += len(bot.active_orders)

            print(f"\n[{i}] {name}")
            print(f"    Position: {bot.position_yes:.2f} shares | Value: ${position_value:+.2f}")
            print(f"    PnL: ${bot.realized_pnl:+.2f} | Volume: ${bot.total_volume:.2f}")
            print(f"    Active Orders: {len(bot.active_orders)}")

        print(f"\n{'='*70}")
        print(f"💼 Total Position Value: ${total_position_value:+.2f}")
        print(f"💰 Total Realized PnL: ${total_pnl:+.2f}")
        print(f"📈 Total Volume: ${total_volume:.2f}")
        print(f"📋 Total Active Orders: {total_active_orders}")
        print("="*70 + "\n")

    async def run(self, cycle_interval: int = 60):
        """Main loop for multi-token bot"""
        print("\n🚀 Starting multi-token grid bot...\n")

        try:
            while True:
                await self.run_all_cycles()
                self.print_summary()

                print(f"💤 Sleeping for {cycle_interval} seconds...\n")
                await asyncio.sleep(cycle_interval)

        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n🛑 Shutting down multi-token bot...")
            await self.cancel_all_bots_orders()
            self.print_summary()
            print("✓ All bots stopped safely")
        except Exception as e:
            print(f"\n✗ Fatal error: {e}")
            await self.cancel_all_bots_orders()
            raise


async def main():
    """
    Main entry point - supports both single and multi-token trading
    """

    # Load configuration from environment
    PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY")

    # Validate private key
    if not PRIVATE_KEY:
        raise ValueError("POLYMARKET_PRIVATE_KEY not found in environment")

    # Check if running in multi-token mode
    # Multi-token mode: TOKEN_ID_1, TOKEN_ID_2, etc.
    # Single-token mode: TOKEN_ID
    token_ids = []
    names = []

    # Default/shared bot configuration (applies to all tokens unless overridden)
    DEFAULT_GRID_LEVELS = int(os.getenv("GRID_LEVELS", "5"))
    DEFAULT_GRID_SPACING = float(os.getenv("GRID_SPACING", "0.02"))
    DEFAULT_ORDER_SIZE_USD = float(os.getenv("ORDER_SIZE_USD", "10"))
    DEFAULT_MAX_POSITION_USD = float(os.getenv("MAX_POSITION_USD", "100"))
    DEFAULT_RANGE_MIN = float(os.getenv("RANGE_MIN", "0.30"))
    DEFAULT_RANGE_MAX = float(os.getenv("RANGE_MAX", "0.70"))
    DEFAULT_PRICE_PRECISION = int(os.getenv("PRICE_PRECISION", "3"))
    CYCLE_INTERVAL = int(os.getenv("CYCLE_INTERVAL", "60"))

    # Try to load multiple tokens (TOKEN_ID_1, TOKEN_ID_2, ...)
    bot_configs = []
    for i in range(1, 11):  # Support up to 10 tokens
        token_id = os.getenv(f"TOKEN_ID_{i}")
        if token_id:
            # Get token-specific settings, fall back to defaults
            name = os.getenv(f"TOKEN_NAME_{i}", f"Market {i}")
            grid_levels = int(os.getenv(f"GRID_LEVELS_{i}", DEFAULT_GRID_LEVELS))
            grid_spacing = float(os.getenv(f"GRID_SPACING_{i}", DEFAULT_GRID_SPACING))
            order_size_usd = float(os.getenv(f"ORDER_SIZE_USD_{i}", DEFAULT_ORDER_SIZE_USD))
            max_position_usd = float(os.getenv(f"MAX_POSITION_USD_{i}", DEFAULT_MAX_POSITION_USD))
            range_min = float(os.getenv(f"RANGE_MIN_{i}", DEFAULT_RANGE_MIN))
            range_max = float(os.getenv(f"RANGE_MAX_{i}", DEFAULT_RANGE_MAX))
            price_precision = int(os.getenv(f"PRICE_PRECISION_{i}", DEFAULT_PRICE_PRECISION))

            bot_configs.append({
                'token_id': token_id,
                'name': name,
                'grid_levels': grid_levels,
                'grid_spacing': grid_spacing,
                'order_size_usd': order_size_usd,
                'max_position_usd': max_position_usd,
                'range_min': range_min,
                'range_max': range_max,
                'price_precision': price_precision,
            })

    # If no multi-token config, fall back to single token
    if not bot_configs:
        TOKEN_ID = os.getenv("TOKEN_ID")
        if not TOKEN_ID:
            raise ValueError("No TOKEN_ID or TOKEN_ID_1 found in environment")

        # Single token mode
        bot_configs.append({
            'token_id': TOKEN_ID,
            'name': "Single Market",
            'grid_levels': DEFAULT_GRID_LEVELS,
            'grid_spacing': DEFAULT_GRID_SPACING,
            'order_size_usd': DEFAULT_ORDER_SIZE_USD,
            'max_position_usd': DEFAULT_MAX_POSITION_USD,
            'range_min': DEFAULT_RANGE_MIN,
            'range_max': DEFAULT_RANGE_MAX,
            'price_precision': DEFAULT_PRICE_PRECISION,
        })

    # Check if single or multi-token mode
    if len(bot_configs) == 1:
        # Single token mode - use original bot
        print("Running in SINGLE-TOKEN mode\n")
        config = bot_configs[0]
        bot = PolymarketGridBot(
            private_key=PRIVATE_KEY,
            token_id=config['token_id'],
            grid_levels=config['grid_levels'],
            grid_spacing=config['grid_spacing'],
            order_size_usd=config['order_size_usd'],
            max_position_usd=config['max_position_usd'],
            min_spread=0.01,
            fee_rate_bps=0,
            min_order_size=0.1,
            max_order_size=10000.0,
            range_min=config['range_min'],
            range_max=config['range_max'],
            price_precision=config['price_precision'],
        )
        await bot.run(cycle_interval=CYCLE_INTERVAL)
    else:
        # Multi-token mode
        print(f"Running in MULTI-TOKEN mode ({len(bot_configs)} tokens)\n")
        multi_bot = MultiTokenGridBot(
            private_key=PRIVATE_KEY,
            bot_configs=bot_configs
        )
        await multi_bot.run(cycle_interval=CYCLE_INTERVAL)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        raise