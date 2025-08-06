# Hyperliquid API Client Documentation

This document describes the updated `HyperliquidClient` class that properly implements the official Hyperliquid API according to their latest documentation.

## 🚦 Rate Limiting Implementation

The client includes a sophisticated rate limiting system to respect Hyperliquid's API limits:

### **IP-Based Rate Limits**

- **Weight Limit**: 1200 per minute per IP address
- **Request Weights**:
  - Most `info` requests: **20 weight**
  - High-frequency requests (`l2Book`, `allMids`, `clearinghouseState`, `orderStatus`, `spotClearinghouseState`, `exchangeStatus`): **2 weight**
  - Special requests (`userRole`): **60 weight**
  - Exchange actions: **1 weight** + floor(batch_length / 40)

### **Rate Limiter Features**

```python
class RateLimiter:
    def __init__(self):
        self.max_weight_per_minute = 1200  # Per IP limit

    async def wait_if_needed(self, weight: int = 20):
        # Automatically waits if approaching limits
        # Resets counters every minute
        # Logs when rate limiting occurs
```

## 📊 API Methods Overview

### **Perpetuals API**

| Method                                      | Endpoint Type         | Weight | Description                        |
| ------------------------------------------- | --------------------- | ------ | ---------------------------------- |
| `get_perp_meta()`                           | `meta`                | 20     | Universe and margin tables         |
| `get_perp_asset_contexts()`                 | `metaAndAssetCtxs`    | 20     | Mark price, funding, open interest |
| `get_user_state(address)`                   | `clearinghouseState`  | 2      | User positions and balances        |
| `get_user_fills(address)`                   | `userFills`           | 20     | Recent trades/fills                |
| `get_user_funding_history(address)`         | `userFunding`         | 20     | Funding payments history           |
| `get_funding_history(coin)`                 | `fundingHistory`      | 20     | Historical funding rates           |
| `get_predicted_funding()`                   | `predictedFundings`   | 20     | Cross-venue funding predictions    |
| `get_open_interest_caps()`                  | `openInterestCaps`    | 20     | Coins at OI caps                   |
| `get_user_active_asset_data(address, coin)` | `userActiveAssetData` | 20     | User's tradeable sizes             |

### **Spot API**

| Method                                  | Endpoint Type            | Weight | Description           |
| --------------------------------------- | ------------------------ | ------ | --------------------- |
| `get_spot_meta()`                       | `spotMeta`               | 20     | Spot tokens and pairs |
| `get_spot_asset_contexts()`             | `spotMetaAndAssetCtxs`   | 20     | Spot market data      |
| `get_spot_clearinghouse_state(address)` | `spotClearinghouseState` | 2      | Token balances        |
| `get_token_details(token_id)`           | `tokenDetails`           | 20     | Token information     |

### **Trading Data**

| Method                    | Endpoint Type  | Weight | Description          |
| ------------------------- | -------------- | ------ | -------------------- |
| `get_recent_trades(coin)` | `recentTrades` | 20     | Recent trade history |
| `get_l2_book(coin)`       | `l2Book`       | 2      | Order book data      |
| `get_all_mids()`          | `allMids`      | 2      | All mid prices       |

## 🔄 Usage Examples

### **Basic Usage**

```python
from app.services.hyperliquid_client import hyperliquid_client

# Get all perpetuals market data
perp_data = await hyperliquid_client.get_perp_asset_contexts()
if perp_data and len(perp_data) >= 2:
    universe = perp_data[0]["universe"]  # Available coins
    contexts = perp_data[1]              # Market data

# Get user's positions
user_state = await hyperliquid_client.get_user_state("0x1234...")
if user_state:
    positions = user_state.get("assetPositions", [])
    margin_summary = user_state.get("marginSummary", {})

# Get recent trades for BTC
btc_trades = await hyperliquid_client.get_recent_trades("BTC")
```

### **Rate Limiting in Action**

```python
# The client automatically handles rate limiting
for coin in ["BTC", "ETH", "SOL"]:  # Each request has weight 20
    trades = await hyperliquid_client.get_recent_trades(coin)
    # Client will automatically wait if approaching 1200 weight/minute limit
```

### **Spot Trading Data**

```python
# Get spot market metadata
spot_meta = await hyperliquid_client.get_spot_meta()
tokens = spot_meta["tokens"]  # Available tokens
pairs = spot_meta["universe"]  # Available trading pairs

# Get user's token balances
balances = await hyperliquid_client.get_spot_clearinghouse_state("0x1234...")
```

## 📋 Response Formats

### **Perpetuals Asset Context Response**

```json
[
  {
    "universe": [
      {
        "name": "BTC",
        "szDecimals": 5,
        "maxLeverage": 50
      }
    ]
  },
  [
    {
      "dayNtlVlm": "1169046.29406",
      "funding": "0.0000125",
      "markPx": "45000.0",
      "midPx": "44999.5",
      "openInterest": "688.11",
      "oraclePx": "45001.0",
      "premium": "0.00031774",
      "prevDayPx": "44500.0"
    }
  ]
]
```

### **User State Response**

```json
{
  "assetPositions": [
    {
      "position": {
        "coin": "BTC",
        "cumFunding": {
          "allTime": "514.085417",
          "sinceChange": "0.0",
          "sinceOpen": "0.0"
        },
        "entryPx": "44000.0",
        "leverage": {
          "rawUsd": "-95.059824",
          "type": "isolated",
          "value": 20
        },
        "liquidationPx": "42000.0",
        "marginUsed": "4.967826",
        "maxLeverage": 50,
        "positionValue": "100.02765",
        "returnOnEquity": "-0.0026789",
        "szi": "0.0335",
        "unrealizedPnl": "-0.0134"
      },
      "type": "oneWay"
    }
  ],
  "marginSummary": {
    "accountValue": "13109.482328",
    "totalMarginUsed": "4.967826",
    "totalNtlPos": "100.02765",
    "totalRawUsd": "13009.454678"
  }
}
```

### **Recent Trades Response**

```json
[
  {
    "coin": "BTC",
    "side": "B", // B = Buy, A = Sell
    "sz": "0.1",
    "px": "45000.0",
    "time": 1708622398623,
    "user": "0x1234567890abcdef...",
    "hash": "0xabcdef..."
  }
]
```

## 🔧 Integration with Copy Trading System

### **Trader Discovery (Service 1)**

```python
async def discover_traders():
    for coin in settings.POPULAR_COINS:
        # Weight: 20 per coin
        trades = await hyperliquid_client.get_recent_trades(coin)

        for trade in trades:
            trader_address = trade.get("user")
            # Store new traders in database
```

### **Position Tracking (Service 2)**

```python
async def track_trader_positions(trader_address: str):
    # Weight: 2 (efficient for frequent polling)
    current_state = await hyperliquid_client.get_user_state(trader_address)

    # Compare with previous state to detect position changes
    positions = current_state.get("assetPositions", [])
```

### **Performance Analysis**

```python
async def analyze_trader_performance(trader_address: str):
    # Get trading history - Weight: 20
    fills = await hyperliquid_client.get_user_fills(trader_address)

    # Get funding payments - Weight: 20
    funding = await hyperliquid_client.get_user_funding_history(trader_address)

    # Calculate performance metrics
```

## ⚠️ Important Notes

### **API URL Configuration**

- Base URL: `https://api.hyperliquid.xyz`
- Info endpoint: `https://api.hyperliquid.xyz/info`
- Exchange endpoint: `https://api.hyperliquid.xyz/exchange`

### **Rate Limiting Best Practices**

1. **Use Low-Weight Methods**: Prefer `clearinghouseState` (weight 2) over `userFills` (weight 20) for frequent polling
2. **Batch Operations**: Group related requests together
3. **Monitor Limits**: The client logs when rate limiting occurs
4. **Error Handling**: Handle rate limit responses gracefully

### **Data Processing**

- All price fields are strings in the API response (convert to float)
- Timestamps are in milliseconds
- Position sizes (`szi`) can be negative (short positions)
- Funding rates are per 8-hour period

### **Security Considerations**

- Info endpoints don't require authentication
- Exchange endpoints (trading) require proper signing (not implemented)
- Never log or expose private keys or wallet addresses unnecessarily

## 🚀 Future Enhancements

1. **WebSocket Support**: Real-time data streaming
2. **Order Signing**: Implement proper cryptographic signing for trading
3. **Advanced Rate Limiting**: Dynamic backoff based on server responses
4. **Caching Layer**: Redis caching for frequently accessed data
5. **Retry Logic**: Exponential backoff for failed requests

---

This client provides a robust foundation for building copy trading systems on Hyperliquid while respecting their API limits and following best practices.
