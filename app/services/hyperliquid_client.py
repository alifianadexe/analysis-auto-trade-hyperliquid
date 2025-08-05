import httpx
import json
import asyncio
from typing import Dict, List, Optional, Any
from app.core.config import settings
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class RateLimiter:
    """Rate limiter to respect Hyperliquid API limits"""
    def __init__(self):
        self.requests_per_minute = 0
        self.weight_per_minute = 0
        self.last_reset = datetime.now()
        self.max_weight_per_minute = 1200  # Per IP limit
        
    async def wait_if_needed(self, weight: int = 20):
        """Wait if we're approaching rate limits"""
        now = datetime.now()
        
        # Reset counters every minute
        if now - self.last_reset >= timedelta(minutes=1):
            self.requests_per_minute = 0
            self.weight_per_minute = 0
            self.last_reset = now
        
        # Check if we need to wait
        if self.weight_per_minute + weight > self.max_weight_per_minute:
            wait_time = 60 - (now - self.last_reset).seconds
            if wait_time > 0:
                logger.info(f"Rate limit approaching, waiting {wait_time} seconds")
                await asyncio.sleep(wait_time)
                # Reset after waiting
                self.requests_per_minute = 0
                self.weight_per_minute = 0
                self.last_reset = datetime.now()
        
        # Add to counters
        self.requests_per_minute += 1
        self.weight_per_minute += weight

class HyperliquidClient:
    def __init__(self):
        self.base_url = settings.HYPERLIQUID_API_URL.rstrip('/info')  # Remove /info if present
        self.info_url = f"{self.base_url}/info"
        self.exchange_url = f"{self.base_url}/exchange"
        self.session = httpx.AsyncClient(timeout=30.0)
        self.rate_limiter = RateLimiter()
    
    async def close(self):
        """Close the HTTP session"""
        await self.session.aclose()
    
    async def _make_request(self, url: str, payload: Dict[str, Any], weight: int = 20) -> Optional[Dict[str, Any]]:
        """Make a request with rate limiting"""
        try:
            await self.rate_limiter.wait_if_needed(weight)
            
            response = await self.session.post(url, json=payload)
            response.raise_for_status()
            
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Request error: {e}")
            return None

    # PERPETUALS API METHODS
    
    async def get_perp_meta(self) -> Optional[Dict[str, Any]]:
        """Get perpetuals metadata (universe and margin tables) - Weight: 20"""
        payload = {"type": "meta"}
        return await self._make_request(self.info_url, payload, weight=20)
    
    async def get_perp_asset_contexts(self) -> Optional[List[Dict[str, Any]]]:
        """Get perpetuals asset contexts (mark price, funding, open interest) - Weight: 20"""
        payload = {"type": "metaAndAssetCtxs"}
        return await self._make_request(self.info_url, payload, weight=20)
    
    async def get_user_state(self, wallet_address: str) -> Optional[Dict[str, Any]]:
        """Get user's perpetuals account summary - Weight: 2"""
        payload = {
            "type": "clearinghouseState",
            "user": wallet_address
        }
        return await self._make_request(self.info_url, payload, weight=2)
    
    async def get_user_fills(self, wallet_address: str) -> Optional[List[Dict[str, Any]]]:
        """Get user's recent fills/trades - Weight: 20"""
        payload = {
            "type": "userFills",
            "user": wallet_address
        }
        return await self._make_request(self.info_url, payload, weight=20)
    
    async def get_user_funding_history(self, wallet_address: str, start_time: Optional[int] = None, end_time: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
        """Get user's funding history - Weight: 20"""
        payload = {
            "type": "userFunding",
            "user": wallet_address
        }
        if start_time:
            payload["startTime"] = start_time
        if end_time:
            payload["endTime"] = end_time
            
        return await self._make_request(self.info_url, payload, weight=20)
    
    async def get_funding_history(self, coin: str, start_time: Optional[int] = None, end_time: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
        """Get historical funding rates for a coin - Weight: 20"""
        payload = {
            "type": "fundingHistory",
            "coin": coin
        }
        if start_time:
            payload["startTime"] = start_time
        if end_time:
            payload["endTime"] = end_time
            
        return await self._make_request(self.info_url, payload, weight=20)
    
    async def get_predicted_funding(self) -> Optional[List[Dict[str, Any]]]:
        """Get predicted funding rates for different venues - Weight: 20"""
        payload = {"type": "predictedFundings"}
        return await self._make_request(self.info_url, payload, weight=20)
    
    async def get_open_interest_caps(self) -> Optional[List[str]]:
        """Get perps at open interest caps - Weight: 20"""
        payload = {"type": "openInterestCaps"}
        return await self._make_request(self.info_url, payload, weight=20)
    
    async def get_user_active_asset_data(self, wallet_address: str, coin: str) -> Optional[Dict[str, Any]]:
        """Get user's active asset data - Weight: 20"""
        payload = {
            "type": "userActiveAssetData",
            "user": wallet_address,
            "coin": coin
        }
        return await self._make_request(self.info_url, payload, weight=20)
    
    # SPOT API METHODS
    
    async def get_spot_meta(self) -> Optional[Dict[str, Any]]:
        """Get spot metadata - Weight: 20"""
        payload = {"type": "spotMeta"}
        return await self._make_request(self.info_url, payload, weight=20)
    
    async def get_spot_asset_contexts(self) -> Optional[List[Dict[str, Any]]]:
        """Get spot asset contexts - Weight: 20"""
        payload = {"type": "spotMetaAndAssetCtxs"}
        return await self._make_request(self.info_url, payload, weight=20)
    
    async def get_spot_clearinghouse_state(self, wallet_address: str) -> Optional[Dict[str, Any]]:
        """Get user's spot token balances - Weight: 2"""
        payload = {
            "type": "spotClearinghouseState",
            "user": wallet_address
        }
        return await self._make_request(self.info_url, payload, weight=2)
    
    async def get_token_details(self, token_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific token - Weight: 20"""
        payload = {
            "type": "tokenDetails",
            "tokenId": token_id
        }
        return await self._make_request(self.info_url, payload, weight=20)
    
    # TRADING DATA METHODS (for copy trading)
    
    async def get_recent_trades(self, coin: str) -> Optional[List[Dict[str, Any]]]:
        """Get recent trades for a coin - Weight: 20"""
        payload = {
            "type": "recentTrades",
            "coin": coin
        }
        return await self._make_request(self.info_url, payload, weight=20)
    
    async def get_l2_book(self, coin: str) -> Optional[Dict[str, Any]]:
        """Get L2 order book - Weight: 2"""
        payload = {
            "type": "l2Book",
            "coin": coin
        }
        return await self._make_request(self.info_url, payload, weight=2)
    
    async def get_all_mids(self) -> Optional[Dict[str, str]]:
        """Get all mid prices - Weight: 2"""
        payload = {"type": "allMids"}
        return await self._make_request(self.info_url, payload, weight=2)
    
    # LEGACY COMPATIBILITY METHODS (deprecated, use specific methods above)
    
    async def get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get market data for a specific symbol (legacy method)"""
        logger.warning("get_market_data is deprecated, use get_perp_asset_contexts or get_spot_asset_contexts")
        
        # Try perpetuals first
        perp_data = await self.get_perp_asset_contexts()
        if perp_data and len(perp_data) >= 2:
            universe = perp_data[0].get("universe", [])
            contexts = perp_data[1]
            
            for i, asset in enumerate(universe):
                if asset.get("name") == symbol and i < len(contexts):
                    return self._process_market_data_legacy(contexts[i], symbol)
        
        # Try spot if not found in perpetuals
        spot_data = await self.get_spot_asset_contexts()
        if spot_data and len(spot_data) >= 2:
            universe = spot_data[0].get("universe", [])
            contexts = spot_data[1]
            
            for i, asset in enumerate(universe):
                if asset.get("name") == symbol and i < len(contexts):
                    return self._process_spot_market_data_legacy(contexts[i], symbol)
        
        return None
    
    async def get_all_market_data(self) -> Optional[List[Dict[str, Any]]]:
        """Get market data for all symbols (legacy method)"""
        logger.warning("get_all_market_data is deprecated, use get_perp_asset_contexts or get_spot_asset_contexts")
        
        all_data = []
        
        # Get perpetuals data
        perp_data = await self.get_perp_asset_contexts()
        if perp_data and len(perp_data) >= 2:
            universe = perp_data[0].get("universe", [])
            contexts = perp_data[1]
            
            for i, asset in enumerate(universe):
                if i < len(contexts):
                    processed = self._process_market_data_legacy(contexts[i], asset.get("name", ""))
                    if processed:
                        all_data.append(processed)
        
        # Get spot data
        spot_data = await self.get_spot_asset_contexts()
        if spot_data and len(spot_data) >= 2:
            universe = spot_data[0].get("universe", [])
            contexts = spot_data[1]
            
            for i, asset in enumerate(universe):
                if i < len(contexts):
                    processed = self._process_spot_market_data_legacy(contexts[i], asset.get("name", ""))
                    if processed:
                        all_data.append(processed)
        
        return all_data
    
    def _process_market_data_legacy(self, context: Dict[str, Any], symbol: str) -> Optional[Dict[str, Any]]:
        """Process perpetuals market data for legacy compatibility"""
        try:
            return {
                "symbol": symbol,
                "type": "perpetual",
                "price": float(context.get("markPx", 0)),
                "mid_price": float(context.get("midPx", 0)),
                "funding_rate": float(context.get("funding", 0)),
                "open_interest": float(context.get("openInterest", 0)),
                "volume_24h": float(context.get("dayNtlVlm", 0)),
                "prev_day_price": float(context.get("prevDayPx", 0)),
                "premium": float(context.get("premium", 0)),
                "oracle_price": float(context.get("oraclePx", 0))
            }
        except Exception as e:
            logger.error(f"Error processing market data for {symbol}: {e}")
            return None
    
    def _process_spot_market_data_legacy(self, context: Dict[str, Any], symbol: str) -> Optional[Dict[str, Any]]:
        """Process spot market data for legacy compatibility"""
        try:
            return {
                "symbol": symbol,
                "type": "spot",
                "price": float(context.get("markPx", 0)),
                "mid_price": float(context.get("midPx", 0)),
                "volume_24h": float(context.get("dayNtlVlm", 0)),
                "prev_day_price": float(context.get("prevDayPx", 0))
            }
        except Exception as e:
            logger.error(f"Error processing spot data for {symbol}: {e}")
            return None
    
    # TRADING METHODS (for future copy trading functionality)
    
    async def place_order(self, order_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Place a new order - Weight: 1"""
        # Note: This requires proper signing which is not implemented in this version
        logger.warning("Order placement requires proper signing implementation")
        return await self._make_request(self.exchange_url, order_data, weight=1)
    
    async def cancel_order(self, cancel_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Cancel an existing order - Weight: 1"""
        # Note: This requires proper signing which is not implemented in this version  
        logger.warning("Order cancellation requires proper signing implementation")
        return await self._make_request(self.exchange_url, cancel_data, weight=1)

# Global client instance
hyperliquid_client = HyperliquidClient()
