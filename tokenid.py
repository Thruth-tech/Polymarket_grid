import requests
import json

# Change the Token_ID here !!!!!!!!!!!!!
token_id = "28916754509502738859848655207562363081546707598755894013716813694042149519904"

print("="*70)
print("CHECKING POLYMARKET TOKEN BY TOKEN_ID")
print("="*70)
print(f"\nToken ID: {token_id}\n")

try:
    # Query Gamma API for this specific token
    url = "https://gamma-api.polymarket.com/markets"
    params = {"clob_token_ids": token_id, "limit": 1}
    response = requests.get(url, params=params, timeout=10)

    if response.status_code == 200:
        data = response.json()
        if data and len(data) > 0:
            market = data[0]

            # Extract market information
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

            # Find which outcome this token represents
            token_index = -1
            for idx, tid in enumerate(tokens):
                if str(tid) == str(token_id):
                    token_index = idx
                    break

            print("TOKEN FOUND!")
            print("="*70)
            print(f"\nMarket Question: {question}")
            print(f"Market ID: {condition_id}")

            if token_index != -1:
                outcome_name = "YES" if token_index == 0 else "NO"
                price = prices[token_index] if token_index < len(prices) else 'N/A'

                print(f"\n[Your Token - {outcome_name} Outcome]")
                print(f"  Token ID: {token_id}")
                print(f"  Current Price: ${price}")
                print(f"  Implied Probability: {float(price)*100:.1f}%" if price != 'N/A' else "")

                # Show the opposite side for reference
                other_index = 1 - token_index
                other_outcome = "NO" if token_index == 0 else "YES"
                other_price = prices[other_index] if other_index < len(prices) else 'N/A'

                print(f"\n[Opposite Side - {other_outcome} Outcome]")
                print(f"  Token ID: {tokens[other_index] if other_index < len(tokens) else 'N/A'}")
                print(f"  Current Price: ${other_price}")

            else:
                print(f"\n⚠ Token ID not found in market tokens")
                print(f"Available tokens: {tokens}")

        else:
            print("[ERROR] No market found with that Token ID")
    else:
        print(f"[ERROR] API returned status {response.status_code}")

except Exception as e:
    print(f"[ERROR] {e}")
