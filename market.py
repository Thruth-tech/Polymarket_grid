import requests
import json

# Change the Market_ID here !!!!!!!!!!!!!
market_id = "0xfc6260666d020a912a87d9000eff5116d2adfb8c30aba543427a4c1f1411f1a0"

print("="*70)
print("CHECKING MARKET ID FROM YOUR URL")
print("="*70)
print(f"\nMarket ID: {market_id}\n")

try:
    url = "https://gamma-api.polymarket.com/markets"
    params = {"condition_ids": market_id, "limit": 1}
    response = requests.get(url, params=params, timeout=10)

    if response.status_code == 200:
        data = response.json()
        if data and len(data) > 0:
            market = data[0]

            question = market.get('question', 'N/A')
            condition_id = market.get('conditionId', 'N/A')

            # Parse token IDs
            tokens_raw = market.get('clobTokenIds', [])
            if isinstance(tokens_raw, str):
                tokens = json.loads(tokens_raw)
            else:
                tokens = tokens_raw

            # Parse prices
            prices_raw = market.get('outcomePrices', [])
            if isinstance(prices_raw, str):
                prices = json.loads(prices_raw)
            else:
                prices = prices_raw

            print("MARKET FOUND!")
            print("="*70)
            print(f"\nQuestion: {question}")
            print(f"Market ID: {condition_id}")
            print(f"\n[YES Outcome]")
            print(f"  Token ID: {tokens[0] if tokens else 'N/A'}")
            print(f"  Price: ${prices[0] if prices else 'N/A'}")
            print(f"\n[NO Outcome]")
            print(f"  Token ID: {tokens[1] if len(tokens) > 1 else 'N/A'}")
            print(f"  Price: ${prices[1] if len(prices) > 1 else 'N/A'}")
        else:
            print("[ERROR] No market found with that ID")
    else:
        print(f"[ERROR] API returned status {response.status_code}")

except Exception as e:
    print(f"[ERROR] {e}")
