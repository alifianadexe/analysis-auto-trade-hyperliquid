"""
Task 3: Leaderboard Calculation and Trader Scoring

This task calculates individual performance metrics for traders and computes
a composite trader score using normalization and weighted scoring.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

from app.services.celery_app import celery_app
from app.database.models import Trader, TradeEvent, LeaderboardMetric
from .utils import get_db

logger = logging.getLogger(__name__)


@celery_app.task
def task_calculate_leaderboard():
    """REVISED Task 3: Calculate Leaderboard and Trader Score (Service 3)"""
    try:
        db = get_db()
        try:
            # Get all active traders
            traders = db.query(Trader).filter(Trader.is_active == True).all()
            
            if not traders:
                logger.info("No active traders found for leaderboard calculation")
                return
            
            logger.info(f"Calculating leaderboard metrics for {len(traders)} traders")
            
            # PART A: Calculate Individual Metrics for ALL traders
            trader_metrics_list = []
            
            for trader in traders:
                try:
                    metrics = _calculate_individual_metrics(db, trader)
                    trader_metrics_list.append({
                        'trader_id': trader.id,
                        'trader': trader,
                        'metrics': metrics
                    })
                except Exception as e:
                    logger.error(f"Error calculating individual metrics for trader {trader.id}: {e}")
                    # Add default metrics for this trader to avoid skipping
                    trader_metrics_list.append({
                        'trader_id': trader.id,
                        'trader': trader,
                        'metrics': _get_default_metrics()
                    })
            
            # PART B: Calculate Composite Trader Score
            trader_metrics_list = _calculate_trader_scores(trader_metrics_list)
            
            # Save all metrics to database
            for trader_data in trader_metrics_list:
                try:
                    _save_trader_metrics(db, trader_data)
                except Exception as e:
                    logger.error(f"Error saving metrics for trader {trader_data['trader_id']}: {e}")
            
            db.commit()
            logger.info(f"Successfully updated leaderboard metrics and scores for {len(trader_metrics_list)} traders")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error in leaderboard calculation: {e}")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in task_calculate_leaderboard: {e}")


def _calculate_individual_metrics(db, trader):
    """Calculate individual performance metrics for a trader"""
    metrics = {}
    
    # Calculate account_age_days
    if trader.first_seen_at:
        # Use timezone-aware datetime to match trader.first_seen_at
        now = datetime.now(trader.first_seen_at.tzinfo)
        age_delta = now - trader.first_seen_at
        metrics['account_age_days'] = age_delta.days
    else:
        metrics['account_age_days'] = 0
    
    # Get all trade events for this trader
    trade_events = db.query(TradeEvent).filter(
        TradeEvent.trader_id == trader.id
    ).order_by(TradeEvent.timestamp.asc()).all()
    
    # Calculate total_volume_usd
    total_volume = 0.0
    open_positions = []
    closed_positions = []
    
    for event in trade_events:
        try:
            details = event.details
            if not details:
                continue
                
            if event.event_type == 'OPEN_POSITION':
                if 'size' in details and 'entry_price' in details:
                    size = float(details['size'])
                    entry_price = float(details['entry_price'])
                    notional_value = abs(size) * entry_price
                    total_volume += notional_value
                    
                    open_positions.append({
                        'coin': details.get('coin', ''),
                        'size': size,
                        'entry_price': entry_price,
                        'timestamp': event.timestamp,
                        'notional': notional_value
                    })
                    
            elif event.event_type == 'CLOSE_POSITION':
                closed_positions.append({
                    'coin': details.get('coin', ''),
                    'size': float(details.get('size', 0)),
                    'timestamp': event.timestamp
                })
                
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Error processing trade event {event.id}: {e}")
    
    metrics['total_volume_usd'] = total_volume
    
    # Calculate win_rate (simplified - based on profitable vs unprofitable positions)
    # Note: This is a basic implementation - real win rate would need exit prices
    if closed_positions:
        # For now, use a placeholder calculation
        metrics['win_rate'] = 0.6  # Placeholder - would need actual P&L calculation
    else:
        metrics['win_rate'] = 0.0
    
    # Calculate other metrics with improved logic
    metrics.update({
        'avg_risk_ratio': 2.0 if total_volume > 0 else 0.0,  # Placeholder
        'max_drawdown': 0.1 if total_volume > 0 else 0.0,    # Placeholder - would need equity curve
        'max_profit_usd': total_volume * 0.05 if total_volume > 0 else 0.0,  # Placeholder
        'max_loss_usd': total_volume * 0.02 if total_volume > 0 else 0.0      # Placeholder
    })
    
    return metrics


def _get_default_metrics():
    """Return default metrics for traders with errors"""
    return {
        'account_age_days': 0,
        'total_volume_usd': 0.0,
        'win_rate': 0.0,
        'avg_risk_ratio': 0.0,
        'max_drawdown': 0.0,
        'max_profit_usd': 0.0,
        'max_loss_usd': 0.0
    }


def _calculate_trader_scores(trader_metrics_list):
    """Calculate normalized and weighted trader scores"""
    if not trader_metrics_list:
        return trader_metrics_list
    
    # Extract all metric values for normalization
    all_metrics = {
        'win_rate': [],
        'total_volume_usd': [],
        'max_drawdown': [],
        'avg_risk_ratio': [],
        'max_profit_usd': []
    }
    
    for trader_data in trader_metrics_list:
        metrics = trader_data['metrics']
        for key in all_metrics.keys():
            all_metrics[key].append(metrics.get(key, 0.0))
    
    # Calculate min/max for normalization (avoid division by zero)
    normalization_params = {}
    for key, values in all_metrics.items():
        min_val = min(values) if values else 0.0
        max_val = max(values) if values else 1.0
        range_val = max_val - min_val if max_val != min_val else 1.0
        normalization_params[key] = {'min': min_val, 'max': max_val, 'range': range_val}
    
    # Define scoring weights
    weights = {
        'win_rate': 0.3,
        'total_volume_usd': 0.2,
        'max_drawdown': 0.25,  # Inverted (lower is better)
        'avg_risk_ratio': 0.15,
        'max_profit_usd': 0.1
    }
    
    # Calculate normalized scores and final trader_score
    for trader_data in trader_metrics_list:
        metrics = trader_data['metrics']
        normalized_scores = {}
        
        # Normalize each metric
        for key in weights.keys():
            value = metrics.get(key, 0.0)
            params = normalization_params[key]
            
            # Min-max normalization
            if params['range'] > 0:
                normalized = (value - params['min']) / params['range']
            else:
                normalized = 0.0
            
            # Invert "bad" metrics (lower is better)
            if key == 'max_drawdown':
                normalized = 1.0 - normalized
            
            normalized_scores[key] = max(0.0, min(1.0, normalized))  # Clamp to [0,1]
        
        # Calculate weighted composite score
        trader_score = sum(
            normalized_scores.get(key, 0.0) * weight
            for key, weight in weights.items()
        )
        
        # Store the final score
        trader_data['metrics']['trader_score'] = round(trader_score, 4)
        
        logger.debug(f"Trader {trader_data['trader_id']}: score={trader_score:.4f}, "
                    f"normalized={normalized_scores}")
    
    return trader_metrics_list


def _save_trader_metrics(db, trader_data):
    """Save calculated metrics to database"""
    trader_id = trader_data['trader_id']
    metrics = trader_data['metrics']
    
    # Update or create leaderboard metric
    leaderboard_metric = db.query(LeaderboardMetric).filter(
        LeaderboardMetric.trader_id == trader_id
    ).first()
    
    if leaderboard_metric:
        # Update existing metrics
        for key, value in metrics.items():
            setattr(leaderboard_metric, key, value)
        leaderboard_metric.updated_at = datetime.utcnow()
    else:
        # Create new metrics entry
        leaderboard_metric = LeaderboardMetric(
            trader_id=trader_id,
            **metrics
        )
        db.add(leaderboard_metric)
