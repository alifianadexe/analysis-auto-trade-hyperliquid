# Leaderboard Scoring Formula Documentation

This document provides a comprehensive explanation of the mathematical formulas and algorithms used to calculate trader performance metrics and composite scores in the Hyperliquid Copy Trading Platform.

## 🎯 Overview

The leaderboard system evaluates traders using a multi-dimensional scoring approach that combines:

- **Individual Metrics**: Raw performance indicators
- **Normalization**: Statistical scaling to [0,1] range
- **Weighted Scoring**: Composite score calculation with configurable weights

---

## 📊 Individual Metrics Calculation

### 1. Account Age (Days)

**Purpose**: Measures trader experience and account maturity.

**Formula**:

```
account_age_days = max(0, (current_time - first_seen_at).days)
```

**Implementation**:

```python
if trader.first_seen_at:
    from datetime import timezone
    now = datetime.now(timezone.utc)

    # Handle timezone-aware/naive datetime compatibility
    if trader.first_seen_at.tzinfo is None:
        first_seen_utc = trader.first_seen_at.replace(tzinfo=timezone.utc)
    else:
        first_seen_utc = trader.first_seen_at

    age_delta = now - first_seen_utc
    account_age_days = max(0, age_delta.days)
else:
    account_age_days = 0
```

**Interpretation**:

- `0 days`: New account
- `30+ days`: Established account
- `365+ days`: Veteran trader

---

### 2. Total Volume (USD)

**Purpose**: Measures trading activity and market engagement.

**Formula**:

```
total_volume_usd = Σ(position_size × entry_price) for all OPEN_POSITION events
```

**Implementation**:

```python
total_volume = 0.0
for event in trade_events:
    if event.event_type == 'OPEN_POSITION':
        details = event.details
        position_size = abs(float(details.get('position_size', 0)))
        entry_price = float(details.get('entry_price', 0))
        trade_volume = position_size * entry_price
        total_volume += trade_volume
```

**Ranges**:

- `$0 - $1,000`: Low activity
- `$1,000 - $50,000`: Moderate activity
- `$50,000+`: High activity

---

### 3. Win Rate

**Purpose**: Measures trading success ratio (percentage of profitable trades).

**Current Heuristic Formula**:

```
if total_volume > $1,000:
    win_rate = 0.6  # 60% for active traders
elif total_trades > 0:
    win_rate = 0.5  # 50% neutral assumption
else:
    win_rate = 0.0  # 0% for inactive traders
```

**Future Enhancement** (when exit data available):

```
winning_trades = count(trades where exit_price > entry_price for longs)
                + count(trades where exit_price < entry_price for shorts)
total_closed_trades = count(all closed positions)

win_rate = winning_trades / total_closed_trades
```

**Interpretation**:

- `0.0 - 0.3`: Poor performance
- `0.5`: Average performance
- `0.7+`: Excellent performance

---

### 4. Average Risk-Reward Ratio

**Purpose**: Measures risk management effectiveness.

**Current Formula**:

```
avg_risk_ratio = min(3.0, 1.0 + (total_volume / 10,000))
```

**Rationale**:

- Higher volume traders typically have better risk management
- Capped at 3.0 to prevent outliers
- Minimum of 1.0 for any active trader

**Future Enhancement**:

```
for each closed_trade:
    profit = |exit_price - entry_price| if profitable
    loss = |exit_price - entry_price| if loss
    risk_ratio = avg(profit) / avg(loss)

avg_risk_ratio = Σ(risk_ratios) / count(closed_trades)
```

**Interpretation**:

- `< 1.0`: Poor risk management
- `1.5 - 2.0`: Good risk management
- `> 2.5`: Excellent risk management

---

### 5. Maximum Drawdown

**Purpose**: Measures the largest peak-to-trough decline in account value.

**Current Formula**:

```
max_drawdown = max(0.05, min(0.3, 0.1 + (1 / (total_volume + 1))))
```

**Rationale**:

- Inverse relationship with volume (higher volume = lower drawdown)
- Bounded between 5% and 30%
- Less active traders assumed to have higher drawdown

**Future Enhancement**:

```
account_values = [portfolio_value at each timestamp]
running_max = 0
max_drawdown = 0

for value in account_values:
    running_max = max(running_max, value)
    drawdown = (running_max - value) / running_max
    max_drawdown = max(max_drawdown, drawdown)
```

**Interpretation**:

- `< 0.1`: Excellent risk control
- `0.1 - 0.2`: Good risk control
- `> 0.3`: Poor risk control

---

### 6. Maximum Profit (USD)

**Purpose**: Measures the largest single profitable trade.

**Current Formula**:

```
max_profit_usd = total_volume × (0.02 + win_rate × 0.08)
```

**Rationale**:

- Scales with total volume and win rate
- Base 2% + up to 8% bonus for high win rate
- Estimates maximum gain based on activity level

**Future Enhancement**:

```
profits = [trade_pnl for trade in closed_trades if trade_pnl > 0]
max_profit_usd = max(profits) if profits else 0.0
```

---

### 7. Maximum Loss (USD)

**Purpose**: Measures the largest single losing trade.

**Current Formula**:

```
max_loss_usd = total_volume × (0.01 + (1 - win_rate) × 0.03)
```

**Rationale**:

- Scales with total volume and loss rate
- Base 1% + up to 3% penalty for low win rate
- Estimates maximum loss based on performance

**Future Enhancement**:

```
losses = [abs(trade_pnl) for trade in closed_trades if trade_pnl < 0]
max_loss_usd = max(losses) if losses else 0.0
```

---

## 📐 Normalization Process

All metrics are normalized to a [0,1] scale using **Min-Max Normalization** to ensure fair comparison across different value ranges.

### Min-Max Normalization Formula

```
normalized_value = (value - min_value) / (max_value - min_value)
```

**Special Case Handling**:

```python
# Prevent division by zero
if max_value == min_value:
    range_val = 1.0
else:
    range_val = max_value - min_value

normalized_value = (value - min_value) / range_val
```

### Metric-Specific Normalization

#### 1. Win Rate

```
normalized_win_rate = (win_rate - min_win_rate) / (max_win_rate - min_win_rate)
```

#### 2. Total Volume USD

```
normalized_volume = (volume - min_volume) / (max_volume - min_volume)
```

#### 3. Maximum Drawdown (Inverted)

```
# Lower drawdown is better, so we invert the normalization
normalized_drawdown = 1.0 - ((drawdown - min_drawdown) / (max_drawdown - min_drawdown))
```

#### 4. Average Risk Ratio

```
normalized_risk_ratio = (risk_ratio - min_risk_ratio) / (max_risk_ratio - min_risk_ratio)
```

#### 5. Maximum Profit USD

```
normalized_max_profit = (max_profit - min_max_profit) / (max_max_profit - min_max_profit)
```

---

## ⚖️ Weighted Composite Score

The final trader score is calculated using a **weighted average** of normalized metrics.

### Weight Distribution

```python
weights = {
    'win_rate': 0.30,           # 30% - Most important
    'max_drawdown': 0.25,       # 25% - Risk management (inverted)
    'total_volume_usd': 0.20,   # 20% - Activity level
    'avg_risk_ratio': 0.15,     # 15% - Risk-reward efficiency
    'max_profit_usd': 0.10      # 10% - Profit potential
}

# Total: 100%
```

### Composite Score Formula

```
trader_score = Σ(normalized_metric_i × weight_i) for i in selected_metrics

trader_score = (normalized_win_rate × 0.30) +
               (normalized_drawdown_inverted × 0.25) +
               (normalized_volume × 0.20) +
               (normalized_risk_ratio × 0.15) +
               (normalized_max_profit × 0.10)
```

### Implementation

```python
def _calculate_trader_scores(trader_metrics_list):
    # Calculate normalization parameters
    normalization_params = {}
    for key in ['win_rate', 'total_volume_usd', 'max_drawdown', 'avg_risk_ratio', 'max_profit_usd']:
        values = [trader_data['metrics'][key] for trader_data in trader_metrics_list]
        min_val = min(values) if values else 0.0
        max_val = max(values) if values else 1.0
        range_val = max_val - min_val if max_val != min_val else 1.0
        normalization_params[key] = {'min': min_val, 'max': max_val, 'range': range_val}

    # Calculate scores for each trader
    for trader_data in trader_metrics_list:
        metrics = trader_data['metrics']
        normalized_scores = {}

        # Normalize each metric
        for key in weights.keys():
            if key == 'max_drawdown':
                # Invert drawdown (lower is better)
                raw_normalized = (metrics[key] - normalization_params[key]['min']) / normalization_params[key]['range']
                normalized_scores[key] = 1.0 - raw_normalized
            else:
                normalized_scores[key] = (metrics[key] - normalization_params[key]['min']) / normalization_params[key]['range']

        # Calculate weighted composite score
        trader_score = sum(
            normalized_scores.get(key, 0.0) * weight
            for key, weight in weights.items()
        )

        trader_data['metrics']['trader_score'] = round(trader_score, 4)
```

---

## 📈 Score Interpretation

### Score Ranges

- **0.8 - 1.0**: Elite Trader ⭐⭐⭐⭐⭐

  - Excellent across all metrics
  - High win rate, low drawdown, high volume

- **0.6 - 0.8**: Advanced Trader ⭐⭐⭐⭐

  - Strong performance in most areas
  - Some room for improvement

- **0.4 - 0.6**: Intermediate Trader ⭐⭐⭐

  - Mixed performance
  - May excel in some areas but lack in others

- **0.2 - 0.4**: Beginner Trader ⭐⭐

  - Below average performance
  - High risk or low activity

- **0.0 - 0.2**: Poor Trader ⭐
  - Minimal activity or poor performance
  - High risk, low returns

### Example Score Calculation

**Trader A**:

- Win Rate: 70% (normalized: 0.8)
- Total Volume: $50,000 (normalized: 0.7)
- Max Drawdown: 8% (normalized inverted: 0.9)
- Risk Ratio: 2.5 (normalized: 0.85)
- Max Profit: $5,000 (normalized: 0.6)

**Score Calculation**:

```
trader_score = (0.8 × 0.30) + (0.9 × 0.25) + (0.7 × 0.20) + (0.85 × 0.15) + (0.6 × 0.10)
             = 0.24 + 0.225 + 0.14 + 0.1275 + 0.06
             = 0.7925 ≈ 0.79 (Advanced Trader ⭐⭐⭐⭐)
```

---

## 🔧 Configuration and Tuning

### Weight Adjustment

The scoring weights can be adjusted based on platform priorities:

```python
# Conservative approach (prioritize risk management)
conservative_weights = {
    'max_drawdown': 0.35,      # Emphasize low risk
    'win_rate': 0.25,
    'avg_risk_ratio': 0.20,
    'total_volume_usd': 0.15,
    'max_profit_usd': 0.05
}

# Aggressive approach (prioritize returns)
aggressive_weights = {
    'win_rate': 0.40,          # Emphasize profitability
    'max_profit_usd': 0.25,
    'total_volume_usd': 0.20,
    'avg_risk_ratio': 0.10,
    'max_drawdown': 0.05
}
```

### Metric Thresholds

Minimum thresholds can be set for inclusion in rankings:

```python
minimum_requirements = {
    'account_age_days': 7,      # At least 1 week old
    'total_volume_usd': 1000,   # At least $1K traded
    'trade_count': 5            # At least 5 trades
}
```

---

## 🚀 Future Enhancements

### 1. Sharpe Ratio Integration

```
sharpe_ratio = (avg_return - risk_free_rate) / std_deviation_of_returns
```

### 2. Sortino Ratio (Downside Risk)

```
sortino_ratio = (avg_return - risk_free_rate) / downside_deviation
```

### 3. Maximum Consecutive Losses

```
max_consecutive_losses = max(count of consecutive losing trades)
```

### 4. Profit Factor

```
profit_factor = sum(winning_trades) / sum(losing_trades)
```

### 5. Calmar Ratio

```
calmar_ratio = annual_return / max_drawdown
```

### 6. Time-Weighted Performance

```
recent_performance_weight = 0.7  # Last 30 days
historical_performance_weight = 0.3  # Prior history
```

---

## ⚠️ Important Notes

### Data Limitations

1. **Current Implementation**: Uses heuristic estimates due to limited trade exit data
2. **Future Enhancement**: Will use actual PnL data when available from Hyperliquid WebSocket feeds
3. **Estimation Accuracy**: Current formulas provide reasonable approximations based on trading volume and activity patterns

### Statistical Considerations

1. **Sample Size**: Scores become more reliable with larger trade counts
2. **Outlier Handling**: Min-max normalization can be affected by extreme values
3. **Time Decay**: Consider implementing time-weighted metrics for recent performance emphasis

### Performance Optimization

1. **Batch Processing**: All traders processed simultaneously for efficient normalization
2. **Caching**: Normalized parameters can be cached between runs
3. **Incremental Updates**: Only recalculate when new trade data is available

---

This scoring system provides a comprehensive, mathematically sound approach to evaluating trader performance while remaining flexible for future enhancements as more detailed trading data becomes available.
